"""Agent runtime — background agents and teaching delegation.

The Tutor spawns background agents that run as asyncio tasks. Results land
in completed_queue and are injected into the Tutor's system prompt on
the next POST /api/chat request.

Retry logic: transient errors (rate limits, overloaded, connection) are
retried with exponential backoff. Permanent errors fail immediately.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.llm import llm_call, is_retryable, extract_retry_after, LLMCallMetadata
from app.tools import execute_tutor_tool

log = logging.getLogger(__name__)

MAX_PLANNING_TOOL_ROUNDS = 3
MAX_PLANNING_OUTPUT_ROUNDS = 2
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds — doubles each retry (2, 4, 8)
AGENT_TIMEOUT = 90  # seconds — hard timeout for background agent coroutines

# ── Data classes ────────────────────────────────────────────────────────────


@dataclass
class AgentTask:
    agent_id: str
    type: str              # "planning", "asset", "research", or any custom type
    status: str = "spawned"  # spawned | running | complete | error
    description: str = ""
    instructions: str = ""
    result: Any = None
    error: str | None = None
    error_type: str | None = None   # "transient" | "permanent" | "parse"
    retries_used: int = 0
    created_at: float = 0
    completed_at: float | None = None
    _task: asyncio.Task | None = field(default=None, repr=False)
    # LLM usage tracking for cost computation
    usage_input_tokens: int = 0
    usage_output_tokens: int = 0
    usage_model: str = ""

    def track_usage(self, response) -> None:
        """Accumulate token usage from an LLM response."""
        self.usage_input_tokens += response.usage.input_tokens
        self.usage_output_tokens += response.usage.output_tokens
        self.usage_model = response.model or self.usage_model


@dataclass
class DelegationState:
    agent_type: str           # free-form: "practice_drill", "sim_explore", etc.
    system_prompt: str        # The sub-agent's system prompt
    tools: list[dict] = field(default_factory=list)
    max_turns: int = 6
    turns_used: int = 0
    topic: str = ""
    instructions: str = ""


@dataclass
class AssessmentState:
    """Active assessment checkpoint — the assessment agent is in control."""
    system_prompt: str = ""         # Assessment agent's full system prompt (built lazily if empty)
    tools: list[dict] = field(default_factory=list)
    brief: dict = field(default_factory=dict)   # Tutor's handoff brief
    section_title: str = ""
    concepts_tested: list[str] = field(default_factory=list)
    questions_asked: int = 0
    max_questions: int = 5
    min_questions: int = 3
    turns_used: int = 0
    max_turns: int = 15             # Hard limit (min 3 questions × ~2 turns each + overhead)
    messages: list = field(default_factory=list)  # Assessment's own message history (separate from tutor)


# ── Retry helpers ──────────────────────────────────────────────────────────


async def _retry_api_call(fn, *, max_retries: int = MAX_RETRIES, label: str = "API"):
    """Call an async function with exponential backoff on transient errors.

    Returns the result on success. Raises on permanent error or max retries.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            last_exc = e
            if not is_retryable(e) or attempt >= max_retries:
                raise
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            retry_after = extract_retry_after(e)
            if retry_after and retry_after > delay:
                delay = min(retry_after, 30.0)
            log.warning(
                "%s transient error (attempt %d/%d, retry in %.1fs): %s: %s",
                label, attempt + 1, max_retries + 1, delay,
                type(e).__name__, str(e)[:200],
            )
            await asyncio.sleep(delay)
    raise last_exc  # unreachable, but satisfies type checker


# ── Agent Runtime ───────────────────────────────────────────────────────────


class AgentRuntime:
    """Manages background agents and collects their results."""

    def __init__(self, session_id: str | None = None):
        self.agents: dict[str, AgentTask] = {}
        self.completed_queue: list[AgentTask] = []
        self.event_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.session_id: str | None = session_id

    def _meta(self, caller: str, agent_id: str = "") -> LLMCallMetadata:
        return LLMCallMetadata(session_id=self.session_id, caller=caller, agent_id=agent_id)

    def spawn(
        self,
        agent_type: str,
        description: str,
        instructions: str,
        context: dict,
    ) -> str:
        """Create and start a background agent. Returns agent_id."""
        # Cancel existing agents of the same type to avoid duplicates
        for aid, existing in list(self.agents.items()):
            if existing.type == agent_type and existing.status in ("spawned", "running"):
                log.debug("Cancelling duplicate %s agent %s (superseded)", agent_type, aid)
                if existing._task and not existing._task.done():
                    existing._task.cancel()
                else:
                    existing.status = "cancelled"
                    del self.agents[aid]

        agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        task = AgentTask(
            agent_id=agent_id,
            type=agent_type,
            status="spawned",
            description=description,
            instructions=instructions,
            created_at=time.time(),
        )
        self.agents[agent_id] = task

        # Pick the right runner — open-ended, not restricted
        if agent_type == "planning":
            coro = self._run_planning_agent(task, context)  # Sonnet + tools, JSON output
        elif agent_type == "enrichment":
            coro = self._run_enrichment_agent(task, context)
        elif agent_type == "visual_gen":
            coro = self._run_visual_gen_agent(task, context)
        else:
            # "research", "content", "problem_gen", or any custom type
            # All go through the generic LLM agent
            coro = self._run_llm_agent(task, context)

        # Wrap in timeout to prevent hung agents
        coro = asyncio.wait_for(coro, timeout=AGENT_TIMEOUT)
        task._task = asyncio.create_task(self._safe_run(task, coro))
        log.info(
            "Spawned %s (%s) — %s",
            agent_id, agent_type, description[:80],
        )
        self._push_event({
            "type": "AGENT_SPAWNED",
            "agent_id": agent_id,
            "agent_type": agent_type,
            "description": description[:120],
        })
        return agent_id

    def pop_completed(self) -> list[dict]:
        """Return and clear completed agent results for Tutor context injection."""
        results = []
        for agent in self.completed_queue:
            entry: dict[str, Any] = {
                "agent_id": agent.agent_id,
                "type": agent.type,
                "status": agent.status,
                "description": agent.description,
                "elapsed": (
                    round(agent.completed_at - agent.created_at, 1)
                    if agent.completed_at else None
                ),
            }
            if agent.status == "complete":
                entry["result"] = agent.result
            else:
                entry["error"] = agent.error
                entry["error_type"] = agent.error_type
                entry["retries_used"] = agent.retries_used
            # Include LLM usage for cost tracking
            if agent.usage_input_tokens or agent.usage_output_tokens:
                entry["usage"] = {
                    "input_tokens": agent.usage_input_tokens,
                    "output_tokens": agent.usage_output_tokens,
                    "model": agent.usage_model,
                }
            results.append(entry)
        self.completed_queue.clear()
        return results

    def get_all_status(self) -> list[dict]:
        """Return status of all agents (for check_agents tool)."""
        return [
            {
                "agent_id": a.agent_id,
                "type": a.type,
                "status": a.status,
                "description": a.description,
                "elapsed": round(time.time() - a.created_at, 1),
                "retries_used": a.retries_used,
            }
            for a in self.agents.values()
        ]

    def _push_event(self, event: dict) -> None:
        """Push an event to the SSE queue. Discards if full (no consumer)."""
        try:
            self.event_queue.put_nowait(event)
        except asyncio.QueueFull:
            log.debug("Event queue full, discarding: %s", event.get("type"))

    # ── Safe wrapper with retry ───────────────────────────────────────────

    async def _safe_run(self, task: AgentTask, coro) -> None:
        """Wrap agent execution. Transient errors are retried by the runners.

        This outer wrapper catches anything that escapes the runners and
        ensures the task always lands in completed_queue (success or error).
        """
        try:
            task.status = "running"
            result = await coro
            task.status = "complete"
            task.result = result
            task.completed_at = time.time()
            self.completed_queue.append(task)
            log.info(
                "%s complete (%.1fs, %d retries) — %s",
                task.agent_id,
                task.completed_at - task.created_at,
                task.retries_used,
                str(result)[:120],
            )
            event = {
                "type": "AGENT_COMPLETE",
                "agent_id": task.agent_id,
                "agent_type": task.type,
                "elapsed": round(task.completed_at - task.created_at, 1),
            }
            if task.type == "visual_gen" and isinstance(result, dict):
                event["visual_id"] = result.get("visual_id")
                event["title"] = result.get("title")
                event["html"] = result.get("html")
            self._push_event(event)
        except asyncio.TimeoutError:
            task.status = "error"
            task.error = f"Agent timed out after {AGENT_TIMEOUT}s"
            task.error_type = "timeout"
            task.completed_at = time.time()
            self.completed_queue.append(task)
            log.error("%s timed out after %.1fs", task.agent_id, task.completed_at - task.created_at)
            self._push_event({
                "type": "AGENT_ERROR",
                "agent_id": task.agent_id,
                "agent_type": task.type,
                "error": f"Timed out after {AGENT_TIMEOUT}s",
            })
        except asyncio.CancelledError:
            task.status = "error"
            task.error = "Cancelled"
            task.error_type = "permanent"
            task.completed_at = time.time()
            self.completed_queue.append(task)  # Must add so plan endpoint sees the error
            log.info("%s cancelled", task.agent_id)
            self._push_event({
                "type": "AGENT_ERROR",
                "agent_id": task.agent_id,
                "agent_type": task.type,
                "error": "Cancelled",
            })
        except Exception as e:
            task.status = "error"
            task.error_type = "transient" if is_retryable(e) else "permanent"
            task.error = (
                f"{type(e).__name__}: {str(e)[:300]}\n"
                f"Retries used: {task.retries_used}/{MAX_RETRIES}"
            )
            task.completed_at = time.time()
            self.completed_queue.append(task)
            log.error(
                "%s error (%.1fs, %d retries) — %s: %s",
                task.agent_id,
                task.completed_at - task.created_at,
                task.retries_used,
                type(e).__name__,
                str(e)[:200],
            )
            log.debug("Full traceback for %s:\n%s", task.agent_id, traceback.format_exc())
            self._push_event({
                "type": "AGENT_ERROR",
                "agent_id": task.agent_id,
                "agent_type": task.type,
                "error": f"{type(e).__name__}: {str(e)[:200]}",
            })

    # ── Planning agent ────────────────────────────────────────────────────

    async def _run_planning_agent(self, task: AgentTask, context: dict) -> dict:
        """Run planning agent — Sonnet with tools, JSON output.

        Spawned at turn ~4 when tutor has enough context (student model,
        conversation history). Uses content/search tools to ground the plan
        in real material. Outputs a single JSON plan object.
        """
        from app.agents.prompts import build_planning_prompt

        planning_prompt = build_planning_prompt(context)
        has_course = "courseMap" in context and context.get("courseMap")

        # Build tool list — planner can use content + search tools
        from app.tools import TUTOR_TOOLS
        planner_tool_names = {"content_read", "content_peek", "web_search",
                              "query_knowledge", "get_section_content"}
        if not has_course:
            planner_tool_names -= {"content_read", "content_peek", "get_section_content"}
        # Add BYO tools if BYO context present
        session_ctx = context.get("sessionContext", "")
        if session_ctx and "collection_id" in str(session_ctx):
            planner_tool_names |= {"byo_read", "byo_list"}
        planner_tools = [t for t in TUTOR_TOOLS if t["name"] in planner_tool_names]

        messages: list[dict] = [{"role": "user", "content": f"<task>\n{task.instructions}\n</task>"}]

        # Agentic loop — planner can make tool calls to ground the plan
        max_rounds = 4  # max tool-call rounds
        for round_num in range(max_rounds):
            request_params: dict[str, Any] = {
                "model": settings.medium_model,  # Sonnet — better quality
                "max_tokens": 4096,
                "system": planning_prompt,
                "messages": messages,
                "tools": planner_tools if round_num < max_rounds - 1 else [],  # no tools on last round
                "metadata": self._meta("planning", task.agent_id),
            }

            response = await _retry_api_call(
                lambda p=request_params: llm_call(**p),
                label=f"Planning[{task.agent_id}] round {round_num + 1}",
            )
            task.track_usage(response)

            # Check for tool calls
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text" and b.text and b.text.strip()]

            if not tool_blocks:
                # No tool calls — extract JSON plan from text
                for block in text_blocks:
                    plan = _parse_plan_json(block.text)
                    if plan:
                        log.debug("Planning done (round %d) — %din/%dout",
                                 round_num + 1, response.usage.input_tokens, response.usage.output_tokens)
                        return plan
                # If no valid JSON found, ask for retry
                if round_num < max_rounds - 1:
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": "Output ONLY a valid JSON plan object. No markdown fences, no prose."})
                    continue
                break

            # Execute tool calls
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for tb in tool_blocks:
                result = await self._execute_planning_tool(tb.name, tb.input, context)
                tool_results.append({
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": tb.id, "content": result[:3000]}],
                })
            for tr in tool_results:
                messages.append(tr)

        raise RuntimeError("Planning agent failed to produce valid JSON plan")

    @staticmethod
    def _extract_course_id_from_context(context: dict) -> int | None:
        """Try to extract course_id from context data."""
        # Try direct field
        cid = context.get("courseId") or context.get("course_id")
        if cid:
            try:
                return int(cid)
            except (ValueError, TypeError):
                pass
        # Try from sessionContext
        sc = context.get("sessionContext", "")
        if sc and isinstance(sc, str):
            try:
                sc_data = json.loads(sc)
                cid = sc_data.get("courseId") or sc_data.get("course_id")
                if cid:
                    return int(cid)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        return None

    async def _execute_planning_tool(self, tool_name: str, tool_input: dict, context: dict) -> str:
        """Execute a tool call from the planning agent.

        Uses execute_tutor_tool for most tools. For content adapter tools
        that need course context, falls back to get_section_content which
        works standalone.
        """
        try:
            from app.tools import execute_tutor_tool
            result = await execute_tutor_tool(tool_name, tool_input)
            if result and "must be routed through the adapter" not in result:
                return result
            # Content adapter tools that failed — try via get_section_content
            # which works without the adapter
            if tool_name in ("content_read", "content_peek", "get_section_content"):
                from app.tools.handlers import get_section_content
                lesson_id = tool_input.get("lesson_id")
                section_index = tool_input.get("section_index", 0)
                ref = tool_input.get("ref", "")
                # Parse ref format "lesson:X:section:Y" if provided
                if ref and not lesson_id:
                    import re
                    m = re.match(r'lesson:(\d+)(?::section:(\d+))?', ref)
                    if m:
                        lesson_id = int(m.group(1))
                        section_index = int(m.group(2) or 0)
                if lesson_id is not None:
                    return await get_section_content(int(lesson_id), int(section_index))
                return f"Cannot resolve content ref: {ref or tool_input}"
            return result or f"No result from {tool_name}"
        except Exception as e:
            return f"Tool error ({tool_name}): {e}"

    # ── Generic LLM agent ─────────────────────────────────────────────────

    async def _run_llm_agent(self, task: AgentTask, context: dict) -> str:
        """Run a generic LLM agent. Works for research, content gen, problem gen, etc.

        Uses Haiku for lightweight tasks, Sonnet if the Tutor specifies.
        The Tutor's instructions define what this agent does — it's fully dynamic.
        """
        # Build a context-aware system prompt
        system_parts = [
            f"You are a background assistant for an AI tutoring system.",
            f"Task type: {task.type}",
            f"Your output will be delivered to the Tutor in [AGENT RESULTS].",
            f"Be concise and structured. Output what the Tutor needs, nothing more.",
        ]

        # Include relevant course/content context
        for key in ("courseMap", "concepts", "simulations"):
            val = context.get(key)
            if val:
                system_parts.append(f"\n[{key}]\n{val}")

        # Include session context (enriched intent, BYO info)
        session_ctx_str = context.get("sessionContext", "")
        if session_ctx_str:
            try:
                import json as _j
                ctx = _j.loads(session_ctx_str) if isinstance(session_ctx_str, str) else session_ctx_str
                enriched = ctx.get("enriched_intent", "")
                if enriched:
                    system_parts.append(f"\n[Session Intent]\n{enriched[:500]}")
            except (ValueError, TypeError, AttributeError):
                pass

        system_prompt = "\n".join(system_parts)

        # Choose model based on type — heavier tasks can use Sonnet
        model = settings.research_model  # Haiku default
        if task.type in ("content", "problem_gen", "analysis"):
            model = settings.planning_model  # Sonnet for heavier work

        async def _call():
            return await llm_call(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": task.instructions}],
                metadata=self._meta(task.type, task.agent_id),
            )

        response = await _retry_api_call(
            _call, label=f"LLM[{task.agent_id}/{task.type}]"
        )
        task.track_usage(response)

        log.info(
            "LLM agent %s (%s) — %din/%dout",
            task.agent_id, task.type,
            response.usage.input_tokens, response.usage.output_tokens,
        )

        text = ""
        for block in response.content:
            if block.text:
                text += block.text
        return text

    # ── Shadow enrichment agent ───────────────────────────────────────────

    async def _run_enrichment_agent(self, task: AgentTask, context: dict) -> str:
        """Background enrichment agent — runs every ~5 turns to pre-fetch resources.

        Uses Haiku with tools (web_search, content_search, get_section_content,
        query_knowledge). Encourages parallel tool calls for speed.
        Output is injected into tutor's context as [ENRICHMENT CONTEXT].
        """
        system_prompt = (
            "You are a fast background enrichment agent for an AI physics tutor.\n"
            "Your job: pre-fetch supplementary resources the tutor might need.\n\n"
            "INSTRUCTIONS:\n"
            "1. Read the recent conversation and current teaching topic\n"
            "2. Identify what supplementary content would help the tutor\n"
            "3. Call tools IN PARALLEL to fetch resources efficiently\n"
            "4. Compile a concise enrichment pack\n\n"
            "OUTPUT FORMAT:\n"
            "[Web References]\n- URL: description (if web_search found useful results)\n\n"
            "[Course Content]\n- Section: key points (if content_search/get_section_content found relevant material)\n\n"
            "[Student Knowledge Gaps]\n- Concept: gap description (if query_knowledge revealed gaps)\n\n"
            "BE FAST. Call multiple tools at once. Keep output under 500 words.\n"
            "If no enrichment is needed, output: (no enrichment needed)"
        )

        # Add course context
        for key in ("courseMap", "concepts"):
            val = context.get(key)
            if val:
                system_prompt += f"\n\n[{key}]\n{val[:2000]}"

        # Enrichment tools — subset tutor can't call directly anymore
        enrichment_tools = []
        from app.tools import TUTOR_TOOLS
        for t in TUTOR_TOOLS:
            if t["name"] in ("web_search", "content_search", "get_section_content", "query_knowledge"):
                enrichment_tools.append(t)

        # Build the enrichment request from task instructions (contains recent conversation + topic)
        messages = [{"role": "user", "content": task.instructions}]

        # Agentic loop — max 2 rounds (initial + tool results)
        model = settings.research_model  # Haiku — fast and cheap
        rounds = 0
        max_rounds = 3
        result_text = ""

        while rounds < max_rounds:
            rounds += 1

            async def _call():
                kwargs = {
                    "model": model,
                    "max_tokens": 2048,
                    "system": system_prompt,
                    "messages": messages,
                    "metadata": self._meta("enrichment", task.agent_id),
                }
                if enrichment_tools and rounds <= 2:
                    kwargs["tools"] = enrichment_tools
                return await llm_call(**kwargs)

            response = await _retry_api_call(
                _call, label=f"Enrichment[{task.agent_id}]"
            )
            task.track_usage(response)

            # Collect text output
            for block in response.content:
                if hasattr(block, 'text') and block.text:
                    result_text += block.text

            # Check for tool calls
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            if not tool_blocks:
                break  # No tools called — done

            # Execute tools in parallel
            import asyncio as _aio
            from app.tools import execute_tutor_tool

            async def _exec_tool(block):
                try:
                    return block.id, await execute_tutor_tool(block.name, block.input)
                except Exception as e:
                    log.warning("Enrichment tool %s failed: %s", block.name, e)
                    return block.id, f"Error: {e}"

            tool_tasks = [_exec_tool(b) for b in tool_blocks]
            tool_outputs = await _aio.gather(*tool_tasks)

            # Build tool results for next round
            tool_results = []
            for tool_id, output in tool_outputs:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": str(output)[:3000] if output else "(no result)",
                })

            # Append assistant + tool results for next round
            messages.append({"role": "assistant", "content": [b.to_dict() if hasattr(b, 'to_dict') else b for b in response.content]})
            messages.append({"role": "user", "content": tool_results})

        log.info(
            "Enrichment agent %s done — %d rounds, %d chars",
            task.agent_id, rounds, len(result_text),
        )
        return result_text.strip() or "(no enrichment needed)"

    # ── Visual generation agent ──────────────────────────────────────────

    async def _run_visual_gen_agent(self, task: AgentTask, context: dict) -> dict:
        """Generate an interactive HTML/JS simulation using Sonnet.

        Returns {"visual_id": "vis-XXXXXXXX", "html": "<html>...", "title": "..."}.
        """
        import re

        visual_id = f"vis-{uuid.uuid4().hex[:8]}"

        # Build context-aware system prompt
        system_parts = [
            "You are a physics visualization generator. Your job is to create a SINGLE, COMPLETE, "
            "self-contained HTML document that implements an interactive physics simulation or visualization.",
            "",
            "═══ OUTPUT FORMAT ═══",
            "Output ONLY a complete HTML document. No explanation, no markdown fences, just the HTML.",
            "The document must be fully self-contained: inline CSS and JS, no external dependencies.",
            "",
            "═══ DESIGN REQUIREMENTS ═══",
            "- Dark background: use #1a1a2e as the base background color",
            "- Accent colors: #e94560 (red/pink), #0f3460 (dark blue), #16213e (navy), #53d8fb (cyan)",
            "- Text color: #e0e0e0 (light gray)",
            "- Responsive: fill the available width and height (use 100vw/100vh or percentage-based sizing)",
            "- Clean, minimal controls: sliders, buttons, and labels styled to match the dark theme",
            "- Smooth animations: use requestAnimationFrame for canvas animations",
            "- Clear labels: show parameter values, axis labels, and units",
            "",
            "═══ BRIDGE PROTOCOL ═══",
            "Include this bridge code in your script so the parent frame can track interactions:",
            "",
            "// Notify parent that the visual is ready",
            "window.addEventListener('load', () => {",
            "  window.parent.postMessage({ type: 'capacity-sim-ready' }, '*');",
            "});",
            "",
            "// Report state whenever parameters change",
            "function reportState(parameters, description) {",
            "  window.parent.postMessage({",
            "    type: 'capacity-sim-state',",
            "    payload: { parameters, description }",
            "  }, '*');",
            "}",
            "",
            "// Report individual interactions (slider moves, button clicks)",
            "function reportInteraction(action, detail) {",
            "  window.parent.postMessage({",
            "    type: 'capacity-sim-interaction',",
            "    payload: { action, detail }",
            "  }, '*');",
            "}",
            "",
            "// Listen for control commands from the tutor",
            "window.addEventListener('message', (event) => {",
            "  const data = event.data;",
            "  if (data?.type === 'capacity-sim-command') {",
            "    const { action, name, value, label } = data.payload || {};",
            "    if (action === 'set_parameter' && name) {",
            "      // Find the control and update it",
            "      const input = document.querySelector(`[data-param='${name}']`);",
            "      if (input) { input.value = value; input.dispatchEvent(new Event('input')); }",
            "    }",
            "    if (action === 'click_button' && label) {",
            "      const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === label);",
            "      if (btn) btn.click();",
            "    }",
            "    window.parent.postMessage({ type: 'capacity-sim-ack', payload: { success: true } }, '*');",
            "  }",
            "});",
            "",
            "═══ INTERACTIVE ELEMENT GUIDELINES ═══",
            "- Add data-param='paramName' attribute to slider/input controls so the bridge can find them",
            "- Call reportState({...params}, 'description') whenever a parameter changes",
            "- Call reportInteraction('slider_change', 'Set mass to 5 kg') on user interactions",
            "- Use <canvas> for animations and dynamic graphics",
            "- Include a 'Reset' button that restores default values",
            "- Show real-time numerical readouts next to sliders",
            "",
            "═══ EXAMPLES OF WHAT TO GENERATE ═══",
            "- Projectile motion with adjustable angle, velocity, and gravity sliders",
            "- Wave interference with adjustable frequency, amplitude, and phase",
            "- Electric field lines around point charges with draggable charges",
            "- Spring-mass oscillation with adjustable spring constant and mass",
            "- Pendulum with adjustable length and gravity",
            "",
            "Make it engaging, educational, and physically accurate.",
        ]

        # Include relevant course context
        for key in ("courseMap", "concepts"):
            val = context.get(key)
            if val:
                system_parts.append(f"\n[{key}]\n{val}")

        system_prompt = "\n".join(system_parts)

        user_prompt = task.instructions
        if task.description and task.description != task.instructions:
            user_prompt = f"Task: {task.description}\n\nDetails: {task.instructions}"

        async def _call():
            return await llm_call(
                model=settings.planning_model,  # Sonnet — good at code generation
                max_tokens=8192,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                metadata=self._meta("visual_gen", task.agent_id),
            )

        response = await _retry_api_call(
            _call, label=f"VisualGen[{task.agent_id}]"
        )
        task.track_usage(response)

        log.info(
            "VisualGen %s — %din/%dout",
            task.agent_id,
            response.usage.input_tokens, response.usage.output_tokens,
        )

        # Extract HTML from response
        text = ""
        for block in response.content:
            if block.text:
                text += block.text

        # Handle ```html fenced code blocks or raw HTML
        html_match = re.search(r"```html\s*\n(.*?)```", text, re.DOTALL)
        if html_match:
            html = html_match.group(1).strip()
        elif text.strip().startswith("<!") or text.strip().startswith("<html"):
            html = text.strip()
        else:
            # Try to find any HTML block
            html_match = re.search(r"(<(!DOCTYPE|html)[^>]*>.*</html>)", text, re.DOTALL | re.IGNORECASE)
            if html_match:
                html = html_match.group(1).strip()
            else:
                html = text.strip()

        # Extract a title from the HTML <title> tag if present
        title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
        title = title_match.group(1) if title_match else "Interactive Visual"

        return {"visual_id": visual_id, "html": html, "title": title}


# ── Helpers ─────────────────────────────────────────────────────────────────


def _parse_plan_json(text: str) -> dict | None:
    """Parse a JSON plan from the planning agent's text output.

    Handles: raw JSON, JSON in markdown fences, JSON embedded in prose.
    Returns the plan dict with _topics extracted, or None if parsing fails.
    """
    import re

    # Strip markdown fences if present
    text = re.sub(r'```(?:json)?\s*', '', text).strip()
    text = re.sub(r'```\s*$', '', text).strip()

    plan = None

    # Try parsing as a single JSON object
    try:
        plan = json.loads(text)
    except json.JSONDecodeError:
        # Extract the outermost JSON object from the text
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                plan = json.loads(m.group(0))
            except json.JSONDecodeError:
                return None

    if not plan or not isinstance(plan, dict):
        return None

    # Extract topics from sections if not already in _topics
    topics = plan.get("_topics", [])
    if not topics and plan.get("sections"):
        for sec in plan["sections"]:
            for t in sec.get("topics", []):
                if isinstance(t, dict):
                    t.setdefault("type", "topic")
                    topics.append(t)

    plan["_topics"] = topics
    return plan
