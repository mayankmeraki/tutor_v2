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
    system_prompt: str              # Assessment agent's full system prompt
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
                log.info("Cancelling duplicate %s agent %s (superseded)", agent_type, aid)
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
            coro = self._run_planning_agent(task, context)
        elif agent_type == "asset":
            coro = self._run_asset_agent(task, context)
        elif agent_type == "visual_gen":
            coro = self._run_visual_gen_agent(task, context)
        else:
            # "research", "content", "problem_gen", or any custom type
            # All go through the generic LLM agent
            coro = self._run_llm_agent(task, context)

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
        except asyncio.CancelledError:
            task.status = "error"
            task.error = "Cancelled"
            task.error_type = "permanent"
            task.completed_at = time.time()
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
        """Run a planning agent with Sonnet using a two-phase approach.

        Phase 1 (Tool Gathering): Up to MAX_PLANNING_TOOL_ROUNDS rounds with tools.
            Strips narrative text from assistant messages (keeps only tool_use blocks).
            Exits when: total tool calls >= 4, model stops using tools, or valid JSONL.
        Phase 2 (Output): Up to MAX_PLANNING_OUTPUT_ROUNDS rounds without tools.
            Round 1: Nudge message asking for JSONL output.
            Round 2: Assistant prefill + harder nudge if Round 1 failed.
        """
        from app.agents.prompts import build_planning_prompt

        planning_prompt = build_planning_prompt(context)
        planning_tools = _get_planning_tools()

        # Wrap instructions with phase guidance
        wrapped_instructions = (
            f"<task>\n{task.instructions}\n</task>\n\n"
            "Phase 1: Call get_section_content (max 3) and search_images (max 1).\n"
            "Phase 2: Output the complete JSONL plan.\n"
            "Do NOT output narrative text — only tool calls and JSONL."
        )
        messages: list[dict] = [{"role": "user", "content": wrapped_instructions}]

        total_tool_calls = 0

        # ── Phase 1: Tool gathering ──────────────────────────────────────
        for round_num in range(1, MAX_PLANNING_TOOL_ROUNDS + 1):
            request_params: dict[str, Any] = {
                "model": settings.PLANNING_MODEL,
                "max_tokens": 4096,
                "system": planning_prompt,
                "messages": messages,
                "tools": planning_tools,
                "metadata": self._meta("planning", task.agent_id),
            }

            async def _call(params=request_params):
                return await llm_call(**params)

            response = await _retry_api_call(
                _call, label=f"Planning[{task.agent_id}] P1R{round_num}"
            )
            task.retries_used = 0
            task.track_usage(response)

            log.info(
                "Planning P1 round %d — stop: %s, %din/%dout",
                round_num, response.stop_reason,
                response.usage.input_tokens, response.usage.output_tokens,
            )

            # Check for valid JSONL in any text blocks
            plan_data = None
            for block in response.content:
                if block.type == "text" and block.text and block.text.strip():
                    try:
                        plan_data = _parse_planning_jsonl(block.text)
                    except (ValueError, json.JSONDecodeError) as e:
                        log.warning(
                            "Planning JSONL parse failed (P1R%d): %s — raw: %s",
                            round_num, e, block.text[:200],
                        )

            if plan_data:
                return plan_data

            # Handle tool calls
            if response.stop_reason == "tool_use":
                tool_blocks = [b for b in response.content if b.type == "tool_use"]
                total_tool_calls += len(tool_blocks)

                tool_results = []
                for block in tool_blocks:
                    log.info("Planning tool: %s(%s)", block.name, json.dumps(block.input)[:80])
                    try:
                        result = await execute_tutor_tool(block.name, block.input)
                    except Exception as e:
                        log.warning("Planning tool %s failed: %s", block.name, e)
                        result = f"Tool error: {type(e).__name__}: {str(e)[:200]}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result if isinstance(result, str) else json.dumps(result),
                    })

                # Strip narrative text — keep only tool_use blocks in assistant message
                tool_only_content = [b for b in response.content if b.type == "tool_use"]
                messages.append({"role": "assistant", "content": tool_only_content})
                messages.append({"role": "user", "content": tool_results})

                # Break to Phase 2 if enough tools called
                if total_tool_calls >= 4:
                    log.info("Planning: %d tool calls reached, moving to Phase 2", total_tool_calls)
                    break
                continue

            # Model stopped using tools without producing JSONL — move to Phase 2
            log.info("Planning: model stopped using tools at P1R%d, moving to Phase 2", round_num)
            # Add the response to messages so Phase 2 has context
            messages.append({"role": "assistant", "content": response.content})
            break

        # ── Nudge between phases ─────────────────────────────────────────
        messages.append({
            "role": "user",
            "content": (
                "You have gathered enough content. Now output the complete JSONL plan. "
                'Output ONLY valid JSONL — no prose. Start with the {"type":"plan",...} line.'
            ),
        })

        # ── Phase 2: Output (no tools) ───────────────────────────────────
        prefill = ""
        for round_num in range(1, MAX_PLANNING_OUTPUT_ROUNDS + 1):
            request_params = {
                "model": settings.PLANNING_MODEL,
                "max_tokens": 4096,
                "system": planning_prompt,
                "messages": messages,
                "metadata": self._meta("planning", task.agent_id),
            }

            async def _call2(params=request_params):
                return await llm_call(**params)

            response = await _retry_api_call(
                _call2, label=f"Planning[{task.agent_id}] P2R{round_num}"
            )
            task.retries_used = 0
            task.track_usage(response)

            log.info(
                "Planning P2 round %d — stop: %s, %din/%dout",
                round_num, response.stop_reason,
                response.usage.input_tokens, response.usage.output_tokens,
            )

            # Try parsing with any prefill prepended
            for block in response.content:
                if block.type == "text" and block.text and block.text.strip():
                    text_to_parse = prefill + block.text if prefill else block.text
                    try:
                        return _parse_planning_jsonl(text_to_parse)
                    except (ValueError, json.JSONDecodeError) as e:
                        log.warning(
                            "Planning JSONL parse failed (P2R%d): %s — raw: %s",
                            round_num, e, block.text[:200],
                        )

            # Round 1 failed — set up prefill + harder nudge for Round 2
            if round_num == 1:
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": (
                        "That was not valid JSONL. Output ONLY JSON lines. "
                        "No markdown, no explanation, no prose. "
                        "Line 1: {\"type\":\"plan\",...}. "
                        "Line 2+: {\"type\":\"topic\",...}. "
                        "Last line: {\"type\":\"done\",\"status\":\"active\"}."
                    ),
                })
                # Use assistant prefill to force JSON start
                prefill = '{"type":"plan"'
                messages.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": prefill}],
                })

        raise RuntimeError(
            f"Planning agent failed to produce valid plan after "
            f"{MAX_PLANNING_TOOL_ROUNDS} tool rounds + {MAX_PLANNING_OUTPUT_ROUNDS} output rounds"
        )

    # ── Asset agent ───────────────────────────────────────────────────────

    async def _run_asset_agent(self, task: AgentTask, context: dict) -> list[dict]:
        """Run parallel asset fetches (images, section content). No LLM needed."""
        instructions = task.instructions
        try:
            specs = json.loads(instructions)
        except (json.JSONDecodeError, TypeError):
            specs = [{"type": "search_images", "query": instructions}]

        if not isinstance(specs, list):
            specs = [specs]

        async def _fetch_one(spec: dict) -> dict:
            spec_type = spec.get("type", "search_images")
            for attempt in range(MAX_RETRIES + 1):
                try:
                    if spec_type == "search_images":
                        result = await execute_tutor_tool("search_images", {
                            "query": spec.get("query", "physics"),
                            "limit": spec.get("limit", 3),
                        })
                        return {"type": "images", "query": spec.get("query"), "result": result}
                    elif spec_type == "get_section_content":
                        result = await execute_tutor_tool("get_section_content", {
                            "lesson_id": spec["lesson_id"],
                            "section_index": spec["section_index"],
                        })
                        return {"type": "section_content", "result": result}
                    elif spec_type == "get_simulation_details":
                        result = await execute_tutor_tool("get_simulation_details", {
                            "simulation_id": spec["simulation_id"],
                        })
                        return {"type": "simulation_details", "result": result}
                    elif spec_type == "web_search":
                        result = await execute_tutor_tool("web_search", {
                            "query": spec.get("query", "physics"),
                            "limit": spec.get("limit", 5),
                        })
                        return {"type": "web_search", "query": spec.get("query"), "result": result}
                    else:
                        return {"type": spec_type, "error": f"Unknown asset type: {spec_type}"}
                except Exception as e:
                    if is_retryable(e) and attempt < MAX_RETRIES:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        log.warning("Asset fetch retry %d: %s", attempt + 1, str(e)[:100])
                        await asyncio.sleep(delay)
                        task.retries_used += 1
                        continue
                    return {"type": spec_type, "error": f"{type(e).__name__}: {str(e)[:200]}"}
            return {"type": spec_type, "error": "Max retries exceeded"}

        results = await asyncio.gather(*(_fetch_one(s) for s in specs))
        return list(results)

    # ── Generic LLM agent ─────────────────────────────────────────────────

    async def _run_llm_agent(self, task: AgentTask, context: dict) -> str:
        """Run a generic LLM agent. Works for research, content gen, problem gen, etc.

        Uses Haiku for lightweight tasks, Sonnet if the Tutor specifies.
        The Tutor's instructions define what this agent does — it's fully dynamic.
        """
        # Build a context-aware system prompt
        system_parts = [
            f"You are a background assistant for a physics tutoring system.",
            f"Task type: {task.type}",
            f"Your output will be delivered to the Tutor in [AGENT RESULTS].",
            f"Be concise and structured. Output what the Tutor needs, nothing more.",
        ]

        # Include relevant course context
        for key in ("courseMap", "concepts", "simulations"):
            val = context.get(key)
            if val:
                system_parts.append(f"\n[{key}]\n{val}")

        system_prompt = "\n".join(system_parts)

        # Choose model based on type — heavier tasks can use Sonnet
        model = settings.RESEARCH_MODEL  # Haiku default
        if task.type in ("content", "problem_gen", "analysis"):
            model = settings.PLANNING_MODEL  # Sonnet for heavier work

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
                model=settings.PLANNING_MODEL,  # Sonnet — good at code generation
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


def _get_planning_tools() -> list[dict]:
    """Tools available to the planning agent."""
    return [
        {
            "name": "get_section_content",
            "description": (
                "Fetch detailed content for a specific course section — transcript, "
                "key points, formulas. Use to ground topic plans in actual lecture content."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "lesson_id": {"type": "number", "description": "Lesson ID from Course Map"},
                    "section_index": {"type": "number", "description": "Section index within lesson"},
                },
                "required": ["lesson_id", "section_index"],
            },
        },
        {
            "name": "search_images",
            "description": "Search Wikimedia Commons for educational images.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "number", "description": "Max results (1-5, default 3)"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "web_search",
            "description": (
                "Search the web for supplementary information — formulas, derivations, "
                "real-world examples, diagrams, or context not in course materials."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query — be specific"},
                    "limit": {"type": "number", "description": "Max results (1-8, default 5)"},
                },
                "required": ["query"],
            },
        },
    ]


def _parse_planning_jsonl(text: str, prefill: str = "") -> dict:
    """Parse JSONL output from planning agent. Returns plan dict.

    If `prefill` is provided, it is prepended to the first line of text
    (used when assistant prefill was used to force JSON start).
    """
    import re

    plan = None
    topics = []

    lines = text.strip().splitlines()

    # Prepend prefill to first non-empty line
    if prefill and lines:
        for i, line in enumerate(lines):
            if line.strip():
                lines[i] = prefill + line
                break

    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', line)
            if m:
                try:
                    obj = json.loads(m.group(0))
                except json.JSONDecodeError:
                    continue
            else:
                continue

        obj_type = obj.get("type")
        if obj_type == "plan":
            plan = obj
        elif obj_type == "topic":
            topics.append(obj)
        elif obj_type == "done":
            pass

    if not plan:
        # Try parsing the whole text as a single JSON object
        try:
            plan = json.loads(text.strip())
        except json.JSONDecodeError:
            raise ValueError(f"Planning agent did not produce valid plan. Raw output: {text[:300]}")

    plan["_topics"] = topics
    return plan
