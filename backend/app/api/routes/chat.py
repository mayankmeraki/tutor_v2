"""Chat endpoint — SSE streaming with Tutor agentic loop + sub-agent architecture.

The Tutor starts teaching immediately. Background agents handle planning,
asset preparation, and research. Teaching delegation hands off bounded
tasks to focused sub-agents.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import traceback
import uuid

import anthropic
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.agents.agent_runtime import AgentRuntime, DelegationState
from app.agents.prompts import SKILL_MAP, build_tutor_prompt
from app.agents.prompts.teaching_delegate import build_delegation_prompt
from app.agents.session import get_or_create_session
from app.services.knowledge_state import (
    get_or_init_knowledge_state,
    format_knowledge_state,
)
from app.tools import (
    TUTOR_TOOLS,
    DELEGATION_TOOLS,
    RETURN_TO_TUTOR_TOOL,
    execute_tutor_tool,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

MAX_ROUNDS = 10
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds, doubles each retry

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        from app.core.config import settings
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


# ── Retry helpers ─────────────────────────────────────────────────────────────

def _is_retryable(error: Exception) -> bool:
    """Check if an error is transient and worth retrying."""
    if isinstance(error, anthropic.RateLimitError):
        return True
    if isinstance(error, anthropic.APIStatusError) and error.status_code in (429, 529):
        return True
    if isinstance(error, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    if isinstance(error, anthropic.InternalServerError):
        return True
    return False


def _extract_retry_after(error: Exception) -> float | None:
    """Extract Retry-After header value from an API error."""
    headers = getattr(error, "response", None)
    if headers is not None:
        headers = getattr(headers, "headers", None)
    if headers:
        val = headers.get("retry-after")
        if val:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
    return None


# ── Message validation ────────────────────────────────────────────────────────

def _validate_messages(messages: list[dict]) -> list[dict]:
    """Ensure all messages have non-empty content before sending to API.

    Fixes the 'user messages must have non-empty content' 400 error.
    """
    validated = []
    for msg in messages:
        content = msg.get("content")

        # Skip messages with no content at all
        if content is None:
            continue

        # String content: must be non-empty
        if isinstance(content, str):
            if not content.strip():
                log.warning("Dropping %s message with empty string content", msg.get("role"))
                continue
            validated.append(msg)

        # List content (tool results, multi-part): must be non-empty list
        elif isinstance(content, list):
            if not content:
                log.warning("Dropping %s message with empty list content", msg.get("role"))
                continue
            # Ensure each tool_result block has non-empty content
            fixed_blocks = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    block_content = block.get("content", "")
                    if not block_content:
                        block = {**block, "content": "(no output)"}
                    fixed_blocks.append(block)
                else:
                    fixed_blocks.append(block)
            validated.append({**msg, "content": fixed_blocks})

        else:
            # ContentBlock objects from SDK — pass through
            validated.append(msg)

    return validated


# ── Helpers ──────────────────────────────────────────────────────────────────

def extract_context(context_items: list[dict] | None) -> dict:
    data: dict[str, str] = {}
    key_map = {
        "student profile": "studentProfile",
        "course map": "courseMap",
        "simulations": "simulations",
        "interactive tools": "simulations",
        "concepts": "concepts",
        "session metrics": "sessionMetrics",
        "active simulation state": "activeSimulation",
    }
    for item in context_items or []:
        desc = (item.get("description") or "").lower()
        for keyword, field_name in key_map.items():
            if keyword in desc and field_name not in data:
                data[field_name] = item.get("value", "")
    return data


def _extract_student_info(context_data: dict) -> tuple[int | None, str | None]:
    profile_str = context_data.get("studentProfile", "")
    if not profile_str:
        return None, None
    try:
        profile = json.loads(profile_str)
        return profile.get("courseId"), profile.get("studentName")
    except (json.JSONDecodeError, TypeError):
        return None, None


async def _load_knowledge_state(context_data: dict) -> dict:
    course_id, student_name = _extract_student_info(context_data)
    if not course_id or not student_name:
        return context_data
    try:
        ks = await get_or_init_knowledge_state(course_id, student_name)
        formatted = format_knowledge_state(ks)
        context_data["knowledgeState"] = formatted
    except Exception as e:
        log.warning("Failed to load knowledge state: %s", e)
    return context_data


def _merge_content(existing, new):
    def to_blocks(c):
        if isinstance(c, str):
            return [{"type": "text", "text": c}]
        if isinstance(c, list):
            return c
        return [{"type": "text", "text": str(c)}]
    blocks = to_blocks(existing) + to_blocks(new)
    if all(b.get("type") == "text" for b in blocks):
        return "\n".join(b["text"] for b in blocks)
    return blocks


def convert_messages(messages: list[dict] | None) -> list[dict]:
    result: list[dict] = []
    for m in messages or []:
        if m.get("role") not in ("user", "assistant"):
            continue
        if result and result[-1]["role"] == m["role"]:
            result[-1]["content"] = _merge_content(result[-1]["content"], m["content"])
        else:
            result.append({"role": m["role"], "content": m["content"]})
    if result and result[0]["role"] != "user":
        result.insert(0, {"role": "user", "content": "[Session started]"})
    return result


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ── Plan promotion helpers ──────────────────────────────────────────────────

def _promote_plan(session, plan_data: dict) -> None:
    """Promote a completed planning agent result into session state."""
    session.current_plan = plan_data

    # Extract topics from the plan
    topics = plan_data.get("_topics", [])
    if topics:
        session.current_topics = topics
        session.current_topic_index = 0
        log.info(
            "Plan promoted: %s (%d topics)",
            plan_data.get("session_objective", "?")[:60],
            len(topics),
        )
    else:
        # If topics are inline in sections, extract them
        for sec in plan_data.get("sections", []):
            for topic_outline in sec.get("topics", []):
                session.current_topics.append(topic_outline)
        if session.current_topics and session.current_topic_index < 0:
            session.current_topic_index = 0
        log.info(
            "Plan promoted (inline topics): %s (%d topic outlines)",
            plan_data.get("session_objective", "?")[:60],
            len(session.current_topics),
        )

    # Set scenario if present
    if plan_data.get("scenario"):
        session.active_scenario = plan_data["scenario"]


def _advance_topic(session) -> dict | None:
    """Move to the next topic. Returns the next topic dict or None."""
    if session.current_topic_index < 0 or not session.current_topics:
        return None

    # Mark current topic as completed
    if 0 <= session.current_topic_index < len(session.current_topics):
        current = session.current_topics[session.current_topic_index]
        session.completed_topics.append({
            "title": current.get("title", ""),
            "concept": current.get("concept", ""),
        })

    # Advance
    session.current_topic_index += 1

    if session.current_topic_index < len(session.current_topics):
        return session.current_topics[session.current_topic_index]
    return None


def _format_completed(completed: list[dict]) -> str | None:
    if not completed:
        return None
    lines = [f"- {t.get('title', '?')} [concept={t.get('concept', '?')}]" for t in completed]
    return "\n".join(lines)


def _format_agent_results(completed: list[dict]) -> str | None:
    if not completed:
        return None
    parts = []
    for agent in completed:
        if agent["status"] == "error":
            parts.append(
                f"Agent {agent['agent_id']} ({agent['type']}): ERROR — {agent.get('error', 'unknown')}"
            )
        else:
            result_str = json.dumps(agent["result"], indent=2) if isinstance(agent["result"], dict) else str(agent.get("result", ""))
            parts.append(
                f"Agent {agent['agent_id']} ({agent['type']}): COMPLETE\n{result_str}"
            )
    return "\n\n".join(parts)


def _format_assets(assets: list[dict]) -> str | None:
    if not assets:
        return None
    return json.dumps(assets, indent=2)


def _build_tutor_prompt(session, context_data) -> str:
    """Build the Tutor prompt with all current state."""
    scenario_skill = SKILL_MAP.get(session.active_scenario) if session.active_scenario else None

    current_topic = None
    if (
        session.current_topics
        and 0 <= session.current_topic_index < len(session.current_topics)
    ):
        current_topic = json.dumps(
            session.current_topics[session.current_topic_index], indent=2
        )

    return build_tutor_prompt({
        **context_data,
        "teachingPlan": json.dumps(session.current_plan, indent=2) if session.current_plan else None,
        "currentTopic": current_topic,
        "completedTopics": _format_completed(session.completed_topics),
        "scenarioSkill": scenario_skill,
        "preparedAssets": _format_assets(session.available_assets),
    })


# ── Delegation handler ──────────────────────────────────────────────────────

async def _handle_delegated_teaching(session, claude_messages, context_data, request):
    """Handle a turn during active teaching delegation."""
    from app.core.config import settings

    delegation = session.delegation
    delegation.turns_used += 1

    # Hard turn limit
    if delegation.turns_used > delegation.max_turns:
        log.info("Delegation turn limit reached (%d/%d)", delegation.turns_used, delegation.max_turns)
        session.delegation_result = {
            "reason": "max_turns",
            "summary": f"Sub-agent reached {delegation.max_turns}-turn limit.",
            "turns_used": delegation.turns_used,
        }
        session.delegation = None
        yield _sse({"type": "TEACHING_DELEGATION_END", "reason": "max_turns"})
        yield _sse({"type": "RUN_FINISHED"})
        return

    client = _get_client()

    # Build sub-agent tools: content tools + return_to_tutor
    sub_tools = DELEGATION_TOOLS + [RETURN_TO_TUTOR_TOOL]

    rounds = 0
    while rounds < MAX_ROUNDS:
        rounds += 1
        log.info("Delegation round %d/%d", rounds, MAX_ROUNDS)

        if await request.is_disconnected():
            return

        text_started = False
        message_id = None

        # Validate messages before API call
        valid_messages = _validate_messages(claude_messages)

        # Retry loop for transient errors
        message = None
        for attempt in range(MAX_RETRIES):
            try:
                async with client.messages.stream(
                    model=settings.TUTOR_MODEL,
                    max_tokens=4096,
                    system=delegation.system_prompt,
                    messages=valid_messages,
                    tools=sub_tools,
                ) as stream:
                    async for text in stream.text_stream:
                        if await request.is_disconnected():
                            return
                        if not text_started:
                            message_id = str(uuid.uuid4())
                            yield _sse({"type": "TEXT_MESSAGE_START", "messageId": message_id})
                            text_started = True
                        yield _sse({"type": "TEXT_MESSAGE_CONTENT", "delta": text})

                    message = await stream.get_final_message()
                break  # Success
            except Exception as e:
                if _is_retryable(e) and attempt < MAX_RETRIES - 1:
                    delay = _extract_retry_after(e) or RETRY_BASE_DELAY * (2 ** attempt)
                    log.warning("Delegation API retry %d/%d after %.1fs: %s", attempt + 1, MAX_RETRIES, delay, e)
                    if text_started:
                        yield _sse({"type": "TEXT_MESSAGE_END"})
                        text_started = False
                    await asyncio.sleep(delay)
                    continue
                raise

        if message is None:
            yield _sse({"type": "RUN_ERROR", "message": "Failed to get response after retries"})
            return

        if await request.is_disconnected():
            return

        if text_started:
            yield _sse({"type": "TEXT_MESSAGE_END"})

        if message.stop_reason == "tool_use":
            tool_blocks = [b for b in message.content if b.type == "tool_use"]
            tool_results: list[dict] = []

            for block in tool_blocks:
                log.info("Delegation tool: %s", block.name)
                yield _sse({"type": "TOOL_CALL_START", "toolCallId": block.id, "toolCallName": block.name})

                if block.name == "return_to_tutor":
                    # End delegation
                    session.delegation_result = {
                        "reason": block.input.get("reason", "task_complete"),
                        "summary": block.input.get("summary", ""),
                        "student_performance": block.input.get("student_performance"),
                        "turns_used": delegation.turns_used,
                        "topic": delegation.topic,
                    }
                    session.delegation = None
                    log.info(
                        "Delegation ended: reason=%s, turns=%d",
                        session.delegation_result["reason"],
                        session.delegation_result["turns_used"],
                    )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Control returned to Tutor.",
                    })
                    yield _sse({"type": "TOOL_CALL_END", "toolCallId": block.id})
                    yield _sse({"type": "TEACHING_DELEGATION_END", "reason": session.delegation_result["reason"]})
                    yield _sse({"type": "RUN_FINISHED"})
                    return

                elif block.name == "control_simulation":
                    steps = block.input.get("steps", [])
                    yield _sse({"type": "SIM_CONTROL", "steps": steps})
                    step_descs = "; ".join(
                        f"Set {s.get('name')} = {s.get('value')}" if s.get("action") == "set_parameter"
                        else f'Click "{s.get("label")}"'
                        for s in steps
                    )
                    result = f"Simulation control sent: {step_descs}."
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
                else:
                    try:
                        result = await execute_tutor_tool(block.name, block.input)
                    except Exception as e:
                        log.error("Delegation tool %s failed: %s", block.name, e, exc_info=True)
                        result = f"Tool error ({block.name}): {str(e)[:200]}"
                    result_str = result if isinstance(result, str) else json.dumps(result)
                    if not result_str.strip():
                        result_str = "(no output)"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

                yield _sse({"type": "TOOL_CALL_END", "toolCallId": block.id})

            claude_messages.append({"role": "assistant", "content": message.content})
            claude_messages.append({"role": "user", "content": tool_results})
            continue

        # No more tool calls — done
        yield _sse({"type": "RUN_FINISHED"})
        return

    yield _sse({"type": "RUN_ERROR", "message": "Too many delegation rounds"})


# ── Chat Route ───────────────────────────────────────────────────────────────

@router.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    messages = body.get("messages")
    context = body.get("context")
    req_session_id = body.get("sessionId")
    is_session_start = body.get("isSessionStart", False)

    context_data = extract_context(context)
    session, session_id = get_or_create_session(req_session_id)
    claude_messages = convert_messages(messages)

    msg_count = len(claude_messages)
    last_msg = claude_messages[-1] if claude_messages else {}
    preview = (last_msg.get("content", "")[:80] if isinstance(last_msg.get("content"), str) else "[complex]")
    log.info("POST /api/chat — session: %s, %d msgs, last: %.80s", session_id[:8], msg_count, preview)

    if not claude_messages:
        async def _err():
            yield _sse({"type": "RUN_ERROR", "message": "No messages provided"})
        return StreamingResponse(_err(), media_type="text/event-stream")

    async def generate():
        nonlocal claude_messages

        from app.core.config import settings

        yield _sse({"type": "CONNECTED"})

        try:
            # ── Step 1: Extract student intent ────────────────────────
            if is_session_start:
                first_content = claude_messages[0].get("content", "") if claude_messages else ""
                if isinstance(first_content, str):
                    import re
                    intent_match = re.search(r'The student said: "([^"]+)"', first_content)
                    if intent_match:
                        session.student_intent = intent_match.group(1)

                if not session.student_intent and context_data.get("studentProfile"):
                    try:
                        profile = json.loads(context_data["studentProfile"])
                        if profile.get("studentIntent"):
                            session.student_intent = profile["studentIntent"]
                    except (json.JSONDecodeError, TypeError):
                        pass

            # ── Step 1a: Load knowledge state ──────────────────────────
            if is_session_start:
                await _load_knowledge_state(context_data)

            # ── Step 2: Initialize agent runtime ──────────────────────
            if not session.agent_runtime:
                session.agent_runtime = AgentRuntime()
            runtime = session.agent_runtime

            # ── Step 3: Check delegation → route to sub-agent ─────────
            if session.delegation:
                log.info(
                    "Routing to delegated sub-agent (turn %d/%d, topic: %s)",
                    session.delegation.turns_used + 1,
                    session.delegation.max_turns,
                    session.delegation.topic[:40],
                )
                async for chunk in _handle_delegated_teaching(
                    session, claude_messages, context_data, request
                ):
                    yield chunk
                return

            # ── Step 4: Promote completed agent results ───────────────
            completed = runtime.pop_completed()
            for agent in completed:
                if agent["type"] == "planning" and agent["status"] == "complete" and agent.get("result"):
                    log.info("Promoting planning agent result into session")
                    _promote_plan(session, agent["result"])

                    # Emit plan update SSE for frontend
                    plan = agent["result"]
                    yield _sse({
                        "type": "PLAN_UPDATE",
                        "plan": plan,
                        "sessionObjective": plan.get("session_objective", ""),
                    })

            # Check delegation result from just-ended delegation
            delegation_result_ctx = None
            if session.delegation_result:
                delegation_result_ctx = json.dumps(session.delegation_result, indent=2)
                session.delegation_result = None

            # ── Step 5: Build Tutor prompt ────────────────────────────
            # Inject agent results and delegation result into prompt
            agent_results_str = _format_agent_results(completed) if completed else None

            tutor_prompt = build_tutor_prompt({
                **context_data,
                "teachingPlan": json.dumps(session.current_plan, indent=2) if session.current_plan else None,
                "currentTopic": (
                    json.dumps(session.current_topics[session.current_topic_index], indent=2)
                    if session.current_topics and 0 <= session.current_topic_index < len(session.current_topics)
                    else None
                ),
                "completedTopics": _format_completed(session.completed_topics),
                "agentResults": agent_results_str,
                "delegationResult": delegation_result_ctx,
                "preparedAssets": _format_assets(session.available_assets),
                "scenarioSkill": SKILL_MAP.get(session.active_scenario) if session.active_scenario else None,
            })

            log.info("Tutor prompt: %d chars (~%d tokens)", len(tutor_prompt), len(tutor_prompt) // 4)

            # ── Step 6: Tutor agentic loop ────────────────────────────
            client = _get_client()
            rounds = 0

            while rounds < MAX_ROUNDS:
                rounds += 1
                log.info("Tutor API call — round %d/%d, model: %s", rounds, MAX_ROUNDS, settings.TUTOR_MODEL)

                if await request.is_disconnected():
                    log.info("Client disconnected")
                    return

                text_started = False
                message_id = None
                text_length = 0

                # Validate messages before API call
                valid_messages = _validate_messages(claude_messages)

                # Retry loop for transient errors
                message = None
                for attempt in range(MAX_RETRIES):
                    try:
                        async with client.messages.stream(
                            model=settings.TUTOR_MODEL,
                            max_tokens=4096,
                            system=tutor_prompt,
                            messages=valid_messages,
                            tools=TUTOR_TOOLS,
                        ) as stream:
                            async for text in stream.text_stream:
                                if await request.is_disconnected():
                                    return
                                if not text_started:
                                    message_id = str(uuid.uuid4())
                                    yield _sse({"type": "TEXT_MESSAGE_START", "messageId": message_id})
                                    text_started = True
                                text_length += len(text)
                                yield _sse({"type": "TEXT_MESSAGE_CONTENT", "delta": text})

                            message = await stream.get_final_message()
                        break  # Success
                    except Exception as e:
                        if _is_retryable(e) and attempt < MAX_RETRIES - 1:
                            delay = _extract_retry_after(e) or RETRY_BASE_DELAY * (2 ** attempt)
                            log.warning(
                                "Tutor API retry %d/%d after %.1fs: %s",
                                attempt + 1, MAX_RETRIES, delay, e,
                            )
                            if text_started:
                                yield _sse({"type": "TEXT_MESSAGE_END"})
                                text_started = False
                            await asyncio.sleep(delay)
                            continue
                        raise

                if message is None:
                    yield _sse({"type": "RUN_ERROR", "message": "Failed to get response after retries"})
                    return

                if await request.is_disconnected():
                    return

                if text_started:
                    yield _sse({"type": "TEXT_MESSAGE_END"})
                    log.info("Text complete — %d chars", text_length)

                log.info(
                    "Stop reason: %s, Usage: %din/%dout",
                    message.stop_reason,
                    message.usage.input_tokens,
                    message.usage.output_tokens,
                )

                # ── Tool calls ────────────────────────────────────────
                if message.stop_reason == "tool_use":
                    tool_blocks = [b for b in message.content if b.type == "tool_use"]

                    for block in tool_blocks:
                        log.info("Tool call: %s(%.100s)", block.name, json.dumps(block.input))
                        yield _sse({
                            "type": "TOOL_CALL_START",
                            "toolCallId": block.id,
                            "toolCallName": block.name,
                        })

                    tool_results: list[dict] = []
                    for block in tool_blocks:
                        if await request.is_disconnected():
                            return

                        start_time = time.monotonic()
                        result: str

                        # ── spawn_agent ───────────────────────────────
                        if block.name == "spawn_agent":
                            agent_type = block.input.get("type", "research")
                            task_desc = block.input.get("task", "")
                            instructions = block.input.get("instructions", task_desc)

                            agent_id = runtime.spawn(
                                agent_type, task_desc, instructions, context_data
                            )
                            result = (
                                f"Agent {agent_id} spawned ({agent_type}). "
                                "Results will be available in [AGENT RESULTS] on your next turn."
                            )

                        # ── check_agents ──────────────────────────────
                        elif block.name == "check_agents":
                            check_completed = runtime.pop_completed()
                            # Promote any planning results
                            for agent in check_completed:
                                if agent["type"] == "planning" and agent["status"] == "complete" and agent.get("result"):
                                    _promote_plan(session, agent["result"])
                                    yield _sse({
                                        "type": "PLAN_UPDATE",
                                        "plan": agent["result"],
                                        "sessionObjective": agent["result"].get("session_objective", ""),
                                    })
                                    # Rebuild prompt with new plan
                                    tutor_prompt = build_tutor_prompt({
                                        **context_data,
                                        "teachingPlan": json.dumps(session.current_plan, indent=2) if session.current_plan else None,
                                        "currentTopic": (
                                            json.dumps(session.current_topics[session.current_topic_index], indent=2)
                                            if session.current_topics and 0 <= session.current_topic_index < len(session.current_topics)
                                            else None
                                        ),
                                        "completedTopics": _format_completed(session.completed_topics),
                                        "scenarioSkill": SKILL_MAP.get(session.active_scenario) if session.active_scenario else None,
                                    })

                            result = json.dumps({
                                "agents": runtime.get_all_status(),
                                "completed": check_completed,
                            }, indent=2)

                        # ── delegate_teaching ─────────────────────────
                        elif block.name == "delegate_teaching":
                            topic = block.input.get("topic", "")
                            instructions = block.input.get("instructions", "")
                            agent_type = block.input.get("agent_type", "practice_drill")
                            max_turns = min(block.input.get("max_turns", 6), 10)

                            custom_prompt = build_delegation_prompt(
                                topic, instructions, context_data, agent_type
                            )
                            session.delegation = DelegationState(
                                agent_type=agent_type,
                                system_prompt=custom_prompt,
                                tools=DELEGATION_TOOLS,
                                max_turns=max_turns,
                                topic=topic,
                                instructions=instructions,
                            )
                            log.info(
                                "Teaching delegated: type=%s, topic=%s, max_turns=%d",
                                agent_type, topic[:40], max_turns,
                            )
                            yield _sse({
                                "type": "TEACHING_DELEGATION_START",
                                "topic": topic,
                                "agentType": agent_type,
                                "maxTurns": max_turns,
                            })
                            result = (
                                f"Teaching delegated to {agent_type} sub-agent for up to {max_turns} turns. "
                                f"Topic: {topic}. The sub-agent will handle the next interactions."
                            )

                        # ── advance_topic ─────────────────────────────
                        elif block.name == "advance_topic":
                            session.tutor_notes.append(block.input.get("tutor_notes", ""))
                            if block.input.get("student_model"):
                                session.student_model = block.input["student_model"]

                            # Emit TOPIC_COMPLETE for the just-finished topic
                            if (
                                session.current_topics
                                and 0 <= session.current_topic_index < len(session.current_topics)
                            ):
                                current = session.current_topics[session.current_topic_index]
                                yield _sse({
                                    "type": "TOPIC_COMPLETE",
                                    "topic_index": session.current_topic_index,
                                    "title": current.get("title", ""),
                                    "concept": current.get("concept", ""),
                                })

                            next_topic = _advance_topic(session)
                            if next_topic:
                                log.info(
                                    "advance_topic: moving to topic %d — %s",
                                    session.current_topic_index,
                                    next_topic.get("title", "?")[:60],
                                )

                                # Rebuild Tutor prompt with new topic
                                tutor_prompt = build_tutor_prompt({
                                    **context_data,
                                    "teachingPlan": json.dumps(session.current_plan, indent=2) if session.current_plan else None,
                                    "currentTopic": json.dumps(next_topic, indent=2),
                                    "completedTopics": _format_completed(session.completed_topics),
                                    "scenarioSkill": SKILL_MAP.get(session.active_scenario) if session.active_scenario else None,
                                })

                                steps_summary = " | ".join(
                                    f"{s.get('n', '?')}. [{s.get('type', '?')}] {s.get('objective', '')[:50]}"
                                    for s in (next_topic.get("steps") or [])
                                )
                                result = (
                                    f"Topic: {next_topic.get('title', '')} [concept={next_topic.get('concept', '')}]\n"
                                    f"Steps: {steps_summary}\n"
                                    f"Tutor notes: {next_topic.get('tutor_notes', 'None')}\n\n"
                                    "Begin teaching this topic now."
                                )
                            else:
                                # No more topics
                                if session.session_status == "complete":
                                    result = (
                                        "SESSION COMPLETE — all topics finished.\n\n"
                                        "STOP TEACHING. Send ONE closing message:\n"
                                        "1. Brief recap of what was covered (1-2 sentences)\n"
                                        "2. One key takeaway\n"
                                        "3. Preview of what comes next\n"
                                        "4. Warm close\n"
                                        "Do NOT ask questions. Do NOT start new topics. This is your FINAL turn."
                                    )
                                else:
                                    result = (
                                        "No more planned topics. Options:\n"
                                        "1. Spawn a planning agent for the next section: "
                                        "spawn_agent('planning', task='Plan next section', instructions='...')\n"
                                        "2. If session objectives are met, wrap up.\n\n"
                                        "Remember: give the student an assessment while the planning agent runs."
                                    )

                        # ── control_simulation ────────────────────────
                        elif block.name == "control_simulation":
                            steps = block.input.get("steps", [])
                            log.info("ControlSimulation: %d step(s)", len(steps))
                            yield _sse({"type": "SIM_CONTROL", "steps": steps})
                            step_descs = "; ".join(
                                f"Set {s.get('name')} = {s.get('value')}" if s.get("action") == "set_parameter"
                                else f'Click "{s.get("label")}"'
                                for s in steps
                            )
                            result = (
                                f"Simulation control sent: {step_descs}. Changes applied in real-time. "
                                "The student can see the result."
                            )

                        # ── Normal tool execution ─────────────────────
                        else:
                            try:
                                result = await execute_tutor_tool(block.name, block.input)
                            except Exception as e:
                                log.error("Tool %s failed: %s", block.name, e, exc_info=True)
                                result = f"Tool error ({block.name}): {str(e)[:200]}"

                        elapsed = time.monotonic() - start_time

                        # Ensure result is never empty
                        if result is None:
                            result = "(no output)"
                        result_str = result if isinstance(result, str) else json.dumps(result)
                        if not result_str.strip():
                            result_str = "(no output)"

                        log.info("Tool %s done (%.1fs): %s...", block.name, elapsed, result_str[:150])

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        })
                        yield _sse({"type": "TOOL_CALL_END", "toolCallId": block.id})

                    # Continue conversation with tool results
                    claude_messages.append({"role": "assistant", "content": message.content})
                    claude_messages.append({"role": "user", "content": tool_results})
                    continue

                # No more tool calls — done
                log.info("Request complete — %d round(s)", rounds)
                yield _sse({"type": "RUN_FINISHED"})
                return

            # Too many rounds
            log.warning("Too many tool call rounds (%d)", MAX_ROUNDS)
            yield _sse({"type": "RUN_ERROR", "message": "Too many tool call rounds"})

        except anthropic.BadRequestError as e:
            err_body = getattr(e, "body", {}) or {}
            err_msg = (err_body.get("error", {}).get("message", "") if isinstance(err_body, dict) else str(e))
            if "credit balance" in err_msg.lower() or "billing" in err_msg.lower():
                log.warning("Anthropic billing error: %s", err_msg)
                yield _sse({"type": "RUN_ERROR", "message": "The AI service is temporarily unavailable — the API credit balance needs to be topped up. Please try again later."})
            else:
                log.error("Anthropic bad request: %s\nMessages: %d total, last role: %s",
                          e, len(claude_messages),
                          claude_messages[-1].get("role", "?") if claude_messages else "none",
                          exc_info=True)
                yield _sse({"type": "RUN_ERROR", "message": f"AI request error: {err_msg}"})
        except anthropic.AuthenticationError as e:
            log.error("Anthropic auth error: %s", e)
            yield _sse({"type": "RUN_ERROR", "message": "The AI service API key is invalid or expired. Please check the configuration."})
        except anthropic.RateLimitError as e:
            # If retry loop exhausted, this propagates here
            retry_after = _extract_retry_after(e)
            wait_msg = f" Try again in {int(retry_after)}s." if retry_after else ""
            log.warning("Anthropic rate limit (retries exhausted): %s", e)
            yield _sse({"type": "RUN_ERROR", "message": f"The AI service is busy right now.{wait_msg} Please wait a moment and try again."})
        except anthropic.APIConnectionError as e:
            log.error("Anthropic connection error: %s", e)
            yield _sse({"type": "RUN_ERROR", "message": "Could not connect to the AI service. Please check your internet connection."})
        except Exception as e:
            log.error("Chat error: %s\n%s", e, traceback.format_exc())
            yield _sse({"type": "RUN_ERROR", "message": "Something went wrong. Please try again."})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
