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

import anthropic

from app.core.config import settings
from app.tools import execute_tutor_tool

log = logging.getLogger(__name__)

MAX_PLANNING_ROUNDS = 6
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds — doubles each retry (2, 4, 8)

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


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


@dataclass
class DelegationState:
    agent_type: str           # free-form: "practice_drill", "sim_explore", etc.
    system_prompt: str        # The sub-agent's system prompt
    tools: list[dict] = field(default_factory=list)
    max_turns: int = 6
    turns_used: int = 0
    topic: str = ""
    instructions: str = ""


# ── Retry helpers ──────────────────────────────────────────────────────────


def _is_transient(exc: Exception) -> bool:
    """Check if an exception is transient and should be retried."""
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APIStatusError) and exc.status_code in (429, 529):
        return True
    if isinstance(exc, anthropic.APIConnectionError):
        return True
    if isinstance(exc, anthropic.InternalServerError):
        return True
    if isinstance(exc, (asyncio.TimeoutError, ConnectionError, TimeoutError)):
        return True
    return False


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
            if not _is_transient(e) or attempt >= max_retries:
                raise
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            retry_after = _extract_retry_after(e)
            if retry_after and retry_after > delay:
                delay = min(retry_after, 30.0)
            log.warning(
                "%s transient error (attempt %d/%d, retry in %.1fs): %s: %s",
                label, attempt + 1, max_retries + 1, delay,
                type(e).__name__, str(e)[:200],
            )
            await asyncio.sleep(delay)
    raise last_exc  # unreachable, but satisfies type checker


def _extract_retry_after(exc: Exception) -> float | None:
    """Try to extract Retry-After header from Anthropic errors."""
    if hasattr(exc, "response") and hasattr(exc.response, "headers"):
        ra = exc.response.headers.get("retry-after")
        if ra:
            try:
                return float(ra)
            except (ValueError, TypeError):
                pass
    return None


# ── Agent Runtime ───────────────────────────────────────────────────────────


class AgentRuntime:
    """Manages background agents and collects their results."""

    def __init__(self):
        self.agents: dict[str, AgentTask] = {}
        self.completed_queue: list[AgentTask] = []

    def spawn(
        self,
        agent_type: str,
        description: str,
        instructions: str,
        context: dict,
    ) -> str:
        """Create and start a background agent. Returns agent_id."""
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
        else:
            # "research", "content", "problem_gen", or any custom type
            # All go through the generic LLM agent
            coro = self._run_llm_agent(task, context)

        task._task = asyncio.create_task(self._safe_run(task, coro))
        log.info(
            "Spawned %s (%s) — %s",
            agent_id, agent_type, description[:80],
        )
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
        except asyncio.CancelledError:
            task.status = "error"
            task.error = "Cancelled"
            task.error_type = "permanent"
            task.completed_at = time.time()
            log.info("%s cancelled", task.agent_id)
        except Exception as e:
            task.status = "error"
            task.error_type = "transient" if _is_transient(e) else "permanent"
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

    # ── Planning agent ────────────────────────────────────────────────────

    async def _run_planning_agent(self, task: AgentTask, context: dict) -> dict:
        """Run a planning agent with Sonnet. Returns parsed plan dict."""
        from app.agents.prompts import build_planning_prompt

        planning_prompt = build_planning_prompt(context)
        client = _get_client()
        planning_tools = _get_planning_tools()

        messages: list[dict] = [{"role": "user", "content": task.instructions}]

        for round_num in range(1, MAX_PLANNING_ROUNDS + 1):
            is_last = round_num == MAX_PLANNING_ROUNDS

            request_params: dict[str, Any] = {
                "model": settings.PLANNING_MODEL,
                "max_tokens": 4096,
                "system": planning_prompt,
                "messages": messages,
            }
            if not is_last:
                request_params["tools"] = planning_tools

            # API call with retry
            async def _call(params=request_params):
                return await client.messages.create(**params)

            response = await _retry_api_call(
                _call, label=f"Planning[{task.agent_id}] round {round_num}"
            )
            task.retries_used = 0  # reset per-round (total tracked at task level)

            log.info(
                "Planning round %d — stop: %s, %din/%dout",
                round_num, response.stop_reason,
                response.usage.input_tokens, response.usage.output_tokens,
            )

            # Parse text from every round
            plan_data = None
            for block in response.content:
                if hasattr(block, "text") and block.text.strip():
                    try:
                        plan_data = _parse_planning_jsonl(block.text)
                    except (ValueError, json.JSONDecodeError) as e:
                        log.warning(
                            "Planning JSONL parse failed (round %d): %s — raw: %s",
                            round_num, e, block.text[:200],
                        )
                        # Don't fail yet — might get valid output in a later round

            # Handle tool calls
            if response.stop_reason == "tool_use":
                tool_blocks = [b for b in response.content if b.type == "tool_use"]
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
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                continue

            # End turn — return parsed plan
            if plan_data:
                return plan_data

        raise RuntimeError(
            f"Planning agent failed to produce valid plan after {MAX_PLANNING_ROUNDS} rounds"
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
                    else:
                        return {"type": spec_type, "error": f"Unknown asset type: {spec_type}"}
                except Exception as e:
                    if _is_transient(e) and attempt < MAX_RETRIES:
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
        client = _get_client()

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
            return await client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": task.instructions}],
            )

        response = await _retry_api_call(
            _call, label=f"LLM[{task.agent_id}/{task.type}]"
        )

        log.info(
            "LLM agent %s (%s) — %din/%dout",
            task.agent_id, task.type,
            response.usage.input_tokens, response.usage.output_tokens,
        )

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
        return text


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
    ]


def _parse_planning_jsonl(text: str) -> dict:
    """Parse JSONL output from planning agent. Returns plan dict."""
    import re

    plan = None
    topics = []

    for line in text.strip().splitlines():
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
