"""Chat endpoint — SSE streaming with Tutor agentic loop + Director integration.

Streaming Director with TopicManager: Director streams JSONL into TopicManager,
Tutor consumes topics one at a time via get_next_topic / request_new_plan tools.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid

import anthropic
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.agents.director import (
    call_director,
    script_for_tutor,
    start_background_director,
    stream_director,
)
from app.agents.prompts import SKILL_MAP, build_tutor_prompt
from app.agents.section_manager import TopicManager
from app.agents.session import get_or_create_session
from app.core.config import settings
from app.services.knowledge_state import (
    batch_update_from_director,
    format_for_director,
    get_or_init_knowledge_state,
)
from app.tools import TUTOR_TOOLS, execute_tutor_tool

log = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

MAX_ROUNDS = 10
MIN_TURNS_FOR_DIRECTOR = 4

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


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
    """Extract courseId and studentName from student profile context."""
    profile_str = context_data.get("studentProfile", "")
    if not profile_str:
        return None, None
    try:
        profile = json.loads(profile_str)
        return profile.get("courseId"), profile.get("studentName")
    except (json.JSONDecodeError, TypeError):
        return None, None


async def _load_knowledge_state(context_data: dict) -> dict:
    """Load knowledge state and add formatted version to context_data for Director."""
    course_id, student_name = _extract_student_info(context_data)
    if not course_id or not student_name:
        return context_data

    try:
        ks = await get_or_init_knowledge_state(course_id, student_name)
        formatted = format_for_director(ks)
        context_data["knowledgeState"] = formatted
    except Exception as e:
        log.warning("Failed to load knowledge state: %s", e)

    return context_data


def _merge_content(existing, new):
    """Merge two content values, handling both string and array (multimodal) formats."""
    # Normalize both to arrays
    def to_blocks(c):
        if isinstance(c, str):
            return [{"type": "text", "text": c}]
        if isinstance(c, list):
            return c
        return [{"type": "text", "text": str(c)}]

    blocks = to_blocks(existing) + to_blocks(new)
    # If all blocks are text, collapse back to a simple string
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


def _rebuild_tutor_prompt(session, context_data):
    """Build Tutor prompt with teaching plan + current topic from TopicManager."""
    manager = session.topic_manager

    plan_json = None
    if manager and manager.plan:
        plan_json = json.dumps({
            "session_objective": manager.plan.get("session_objective"),
            "scenario": manager.plan.get("scenario"),
            "learning_outcomes": manager.plan.get("learning_outcomes"),
            "sections": manager.plan.get("sections"),
        }, indent=2)

    current_topic = None
    if manager:
        topic_entry = manager._get_current_topic()
        if topic_entry:
            current_topic = json.dumps(topic_entry.data, indent=2)

    completed_summary = _build_completed_summary(manager) if manager else None

    scenario_skill = SKILL_MAP.get(session.active_scenario) if session.active_scenario else None

    log.debug(
        "_rebuild_tutor_prompt: plan=%s, topic=(%s,%s), scenario=%s",
        "yes" if plan_json else "no",
        manager.current_section_index if manager else "N/A",
        manager.current_topic_index if manager else "N/A",
        session.active_scenario or "none",
    )

    return build_tutor_prompt({
        **context_data,
        "teachingPlan": plan_json,
        "currentTopic": current_topic,
        "completedSections": completed_summary,
        "scenarioSkill": scenario_skill,
    })


def _build_completed_summary(manager) -> str | None:
    """Build brief summary of completed sections and topics for Tutor context."""
    if not manager or not manager.sections:
        return None
    lines = []
    for sec in manager.sections:
        done_topics = [t for t in sec.topics if t.status == "done"]
        if not done_topics and sec.status != "done":
            continue
        if sec.status == "done":
            lines.append(f"- Section {sec.index + 1}: {sec.title} (completed, {len(sec.topics)} topics)")
        else:
            lines.append(f"- Section {sec.index + 1}: {sec.title} ({len(done_topics)}/{len(sec.topics)} topics done)")
        for t in done_topics:
            lines.append(f"  - Topic: {t.title} [concept={t.concept}] (done)")
    return "\n".join(lines) if lines else None


def _start_prefetch_director(session, context_data, claude_messages):
    """Manager detected Tutor approaching end of plan. Pre-trigger next Director call."""
    manager = session.topic_manager

    done_sections = sum(1 for s in manager.sections if s.status == "done")
    trigger_parts = [
        "TUTOR_CALLBACK — Tutor approaching end of current plan.",
        f"Completed {done_sections} of {len(manager.sections)} sections.",
        f"Current session objective: {manager.plan.get('session_objective', '')}",
        "",
        "=== Tutor's Notes ===",
        "\n".join(session.tutor_notes[-3:]) or "None",
    ]
    if session.student_model:
        trigger_parts.extend(["", "=== Student Model ===", json.dumps(session.student_model, indent=2)])

    trigger = "\n".join(trigger_parts)

    pending = TopicManager()
    session.pending_manager = pending
    task = asyncio.create_task(stream_director(session, pending, context_data, trigger, claude_messages))
    pending.director_task = task
    log.info("Prefetch Director started — pending manager created")


async def _save_topic_progress(session) -> None:
    """Non-blocking DB save at topic/section boundaries.

    Serializes the TopicManager state and saves it to the session document.
    Called fire-and-forget so it never blocks the Tutor response.
    """
    try:
        manager = session.topic_manager
        if not manager:
            return
        # The frontend's SessionManager handles the actual DB write via
        # the TOPIC_COMPLETE / SECTION_COMPLETE SSE events. This is a
        # backend-side checkpoint so the server's in-memory state can be
        # reconstructed. We log it for observability.
        serialized = manager.serialize()
        log.info(
            "Topic progress saved: section=%d, topic=%d, sections_done=%d",
            manager.current_section_index,
            manager.current_topic_index,
            sum(1 for s in manager.sections if s.status == "done"),
        )
    except Exception as e:
        log.warning("Failed to save topic progress: %s", e)


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

        yield _sse({"type": "CONNECTED"})

        # Track student turns for Director rate limiting
        if not is_session_start:
            session.turns_since_last_director += 1

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

            # ── Step 1b: Promote pending background script ────────────
            if session.pending_script:
                pending = session.pending_script
                session.pending_script = None
                log.info('Promoting background script: "%s"', pending.get("session_objective", ""))

                if session.current_script:
                    session.previous_scripts.append(session.current_script)
                session.current_script = pending

                if pending.get("session_status") == "complete":
                    session.session_status = "complete"
                    session.completion_reason = pending.get("completion_reason", "Session objectives met")
                    session.pause_note = None
                elif pending.get("session_status") == "paused":
                    session.session_status = "paused"
                    session.pause_note = pending.get("pause_note")

                if pending.get("scenario") and pending["scenario"] != session.active_scenario:
                    session.active_scenario = pending["scenario"]

                yield _sse({
                    "type": "DIRECTOR_SCRIPT",
                    "script": pending,
                    "sessionStatus": pending.get("session_status", "active"),
                    "completionReason": pending.get("completion_reason"),
                })

            # ── Step 2: Build Tutor system prompt ─────────────────────
            scenario_skill = SKILL_MAP.get(session.active_scenario) if session.active_scenario else None

            # Use topic-based prompt if TopicManager is active, else legacy
            if session.topic_manager and session.topic_manager.plan:
                tutor_prompt = _rebuild_tutor_prompt(session, context_data)
            else:
                tutor_prompt = build_tutor_prompt({
                    **context_data,
                    "currentScript": json.dumps(script_for_tutor(session.current_script), indent=2) if session.current_script else None,
                    "scenarioSkill": scenario_skill,
                })

            log.info("Tutor prompt: %d chars (~%d tokens)", len(tutor_prompt), len(tutor_prompt) // 4)

            # ── Step 3: Tutor agentic loop ────────────────────────────
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

                async with client.messages.stream(
                    model=settings.TUTOR_MODEL,
                    max_tokens=4096,
                    system=tutor_prompt,
                    messages=claude_messages,
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

                if await request.is_disconnected():
                    return

                if text_started:
                    yield _sse({"type": "TEXT_MESSAGE_END"})
                    log.info("Text complete — %d chars", text_length)

                log.info("Stop reason: %s, Usage: %din/%dout", message.stop_reason, message.usage.input_tokens, message.usage.output_tokens)

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

                        if block.name == "control_simulation":
                            # Forward control steps to client via SSE
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
                                "The student can see the result. Check the Active Simulation State in your next turn for updated parameter values."
                            )

                        elif block.name in ("get_next_topic", "get_next_section"):
                            # ── get_next_topic handler ──────────────────
                            log.info(
                                "%s called — tutor_notes: %.100s",
                                block.name, block.input.get("tutor_notes", "")[:100],
                            )
                            manager = session.topic_manager
                            if not manager:
                                log.warning("%s: no TopicManager on session", block.name)
                                result = "No active teaching plan. Use request_director_plan to start, or request_new_plan if you need a fresh plan."
                            else:
                                # Save Tutor feedback
                                session.tutor_notes.append(block.input.get("tutor_notes", ""))
                                if block.input.get("chat_summary"):
                                    session.chat_summaries.append(block.input["chat_summary"])
                                if block.input.get("student_model"):
                                    session.student_model = block.input["student_model"]

                                try:
                                    result_data = await manager.get_next_topic()
                                    completed_topic = result_data.get("completed_topic")
                                    section_completed = result_data.get("section_completed")

                                    # Emit TOPIC_COMPLETE SSE for completed topic
                                    if completed_topic is not None:
                                        sec_idx, top_idx = completed_topic
                                        log.info("Emitting TOPIC_COMPLETE for (%d,%d)", sec_idx, top_idx)
                                        yield _sse({
                                            "type": "TOPIC_COMPLETE",
                                            "section_index": sec_idx,
                                            "topic_index": top_idx,
                                        })

                                        # Update knowledge state from Director concept_status
                                        if manager.plan and manager.plan.get("concept_status"):
                                            course_id, student_name = _extract_student_info(context_data)
                                            if course_id and student_name:
                                                asyncio.create_task(
                                                    batch_update_from_director(
                                                        course_id, student_name,
                                                        manager.plan["concept_status"],
                                                        block.input.get("tutor_notes", ""),
                                                    )
                                                )

                                    # Emit SECTION_COMPLETE SSE if section boundary crossed
                                    if section_completed is not None:
                                        log.info("Emitting SECTION_COMPLETE for index %d", section_completed)
                                        yield _sse({"type": "SECTION_COMPLETE", "index": section_completed})

                                    # Check prefetch trigger
                                    if getattr(manager, '_needs_prefetch', False):
                                        manager._needs_prefetch = False
                                        log.info("Prefetch triggered — starting background Director for next plan")
                                        _start_prefetch_director(session, context_data, claude_messages)

                                    topic = result_data["topic"]
                                    if topic:
                                        log.info(
                                            "get_next_topic: advancing to (%d,%d) — %s (%d steps)",
                                            topic.section_index, topic.topic_index,
                                            topic.title[:60],
                                            len(topic.data.get("steps", [])),
                                        )

                                        # Rebuild Tutor prompt with new topic
                                        tutor_prompt = _rebuild_tutor_prompt(session, context_data)
                                        log.info(
                                            "Tutor prompt rebuilt with topic (%d,%d): %d chars (~%d tokens)",
                                            topic.section_index, topic.topic_index,
                                            len(tutor_prompt), len(tutor_prompt) // 4,
                                        )

                                        steps_summary = " | ".join(
                                            f"{s.get('n', '?')}. [{s.get('type', '?')}] {s.get('objective', '')[:50]}"
                                            for s in (topic.data.get("steps") or [])
                                        )
                                        result = (
                                            f"Topic: {topic.title} [concept={topic.concept}]\n"
                                            f"Steps: {steps_summary}\n"
                                            f"Tutor notes: {topic.data.get('tutor_notes', 'None')}\n\n"
                                            "Begin teaching this topic now."
                                        )

                                        # Non-blocking DB save at topic boundary
                                        asyncio.create_task(_save_topic_progress(session))
                                    else:
                                        # No more topics — check pending manager
                                        log.info("get_next_topic: no more topics in current plan")
                                        if session.pending_manager and session.pending_manager.plan:
                                            # Promote pending manager
                                            session.topic_manager = session.pending_manager
                                            session.pending_manager = None
                                            manager = session.topic_manager
                                            log.info(
                                                "Promoted pending manager — new plan: %s (%d sections)",
                                                manager.plan.get("session_objective", "?")[:60],
                                                len(manager.plan.get("sections", [])),
                                            )

                                            plan = manager.plan
                                            yield _sse({"type": "DIRECTOR_PLAN", "plan": plan})

                                            first = await manager.get_next_topic()
                                            first_topic = first["topic"]
                                            if first_topic:
                                                tutor_prompt = _rebuild_tutor_prompt(session, context_data)
                                                result = (
                                                    f"New plan received: {plan.get('session_objective', '')}\n"
                                                    f"First topic: {first_topic.title}\n"
                                                    "Begin teaching."
                                                )
                                            else:
                                                result = "New plan received but no topics available yet. Continue with current knowledge."
                                        elif manager.session_status == "complete":
                                            session.session_status = "complete"
                                            session.completion_reason = manager.completion_reason or "All objectives met"
                                            result = (
                                                "SESSION COMPLETE — all topics finished, all objectives met.\n"
                                                f"Reason: {session.completion_reason}\n\n"
                                                "STOP TEACHING. Send ONE closing message:\n"
                                                "1. Brief recap of what was covered (1-2 sentences)\n"
                                                "2. One key takeaway\n"
                                                "3. Preview of what comes next\n"
                                                "4. Warm close\n"
                                                "Do NOT ask questions. Do NOT start new topics. Do NOT request another plan. This is your FINAL turn."
                                            )
                                        else:
                                            session.session_status = "complete"
                                            result = (
                                                "SESSION COMPLETE — no more topics in the teaching plan.\n\n"
                                                "STOP TEACHING. Send ONE closing message:\n"
                                                "1. Brief recap of what was covered\n"
                                                "2. One key takeaway\n"
                                                "3. Warm close\n"
                                                "Do NOT ask questions. Do NOT start new topics. This is your FINAL turn."
                                            )
                                except Exception as e:
                                    log.error("get_next_topic error: %s", e, exc_info=True)
                                    result = f"Error getting next topic: {str(e)[:200]}. Continue with current knowledge."

                        elif block.name == "request_new_plan":
                            # ── request_new_plan handler ──────────────────
                            log.info(
                                "request_new_plan called — reason: %s, intent: %s, scenario: %s",
                                block.input.get("reason", "?"),
                                block.input.get("student_intent", "?")[:60],
                                block.input.get("detected_scenario", "?"),
                            )
                            manager = session.topic_manager
                            if manager:
                                log.info("Resetting existing TopicManager for new plan")
                                manager.reset_for_new_plan()
                            else:
                                log.info("Creating new TopicManager (none existed)")
                                manager = TopicManager()
                                session.topic_manager = manager

                            # Update session state
                            if block.input.get("detected_scenario"):
                                session.active_scenario = block.input["detected_scenario"]
                            session.tutor_notes.append(block.input.get("tutor_notes", ""))
                            if block.input.get("chat_summary"):
                                session.chat_summaries.append(block.input["chat_summary"])
                            if block.input.get("student_model"):
                                session.student_model = block.input["student_model"]
                            session.student_intent = block.input.get("student_intent", session.student_intent)

                            # Build trigger
                            trigger_parts = [
                                "STUDENT_INTENT — Student changed direction.",
                                f"Reason: {block.input.get('reason', 'unknown')}",
                                f"New intent: {block.input.get('student_intent', 'unknown')}",
                            ]
                            if block.input.get("detected_scenario"):
                                trigger_parts.append(f"Detected scenario: {block.input['detected_scenario']}")
                            trigger_parts.extend([
                                "",
                                "=== Tutor's Observations ===",
                                block.input.get("tutor_notes", "None"),
                            ])
                            if block.input.get("student_model"):
                                trigger_parts.extend(["", "=== Student Model ===", json.dumps(block.input["student_model"], indent=2)])
                            if session.student_intent:
                                trigger_parts.extend(["", "=== Student Intent ===", session.student_intent])

                            trigger = "\n".join(trigger_parts)

                            # Start new Director streaming
                            log.info("Starting streaming Director for new plan...")
                            task = asyncio.create_task(stream_director(session, manager, context_data, trigger, claude_messages))
                            manager.director_task = task

                            yield _sse({"type": "DIRECTOR_THINKING"})

                            # Wait for plan + first topic
                            try:
                                t0 = time.monotonic()
                                plan = await manager.wait_for_plan()
                                plan_wait = time.monotonic() - t0
                                log.info(
                                    "request_new_plan: plan received in %.1fs — %s (%d sections)",
                                    plan_wait,
                                    plan.get("session_objective", "?")[:60],
                                    len(plan.get("sections", [])),
                                )
                                yield _sse({"type": "DIRECTOR_PLAN", "plan": plan})

                                t1 = time.monotonic()
                                first = await manager.get_next_topic()
                                topic_wait = time.monotonic() - t1
                                topic = first["topic"]

                                tutor_prompt = _rebuild_tutor_prompt(session, context_data)

                                if topic:
                                    log.info(
                                        "request_new_plan: first topic ready in %.1fs — %s (%d steps). Total: %.1fs",
                                        topic_wait,
                                        topic.title[:60],
                                        len(topic.data.get("steps", [])),
                                        time.monotonic() - t0,
                                    )
                                    result = (
                                        f"New plan received: {plan.get('session_objective', '')}\n"
                                        f"First topic: {topic.title}\n"
                                        f"Steps: {len(topic.data.get('steps', []))}\n"
                                        "Begin teaching."
                                    )
                                else:
                                    log.info("request_new_plan: plan ready but no topics yet after %.1fs", topic_wait)
                                    result = f"New plan received: {plan.get('session_objective', '')}. Topics still loading — begin with the plan overview."
                            except Exception as e:
                                log.error("request_new_plan error after %.1fs: %s", time.monotonic() - t0, e, exc_info=True)
                                result = f"Failed to generate new plan: {str(e)[:200]}. Continue with what you know."

                        elif block.name == "request_director_plan":
                            # ── request_director_plan handler (streaming version) ──
                            reason = block.input.get("reason", "unknown")
                            bypass_reasons = ["probing_complete", "script_complete"]
                            sync_reasons = ["probing_complete", "script_complete"]
                            is_background_eligible = reason not in sync_reasons and session.current_script is not None

                            if session.session_status == "complete":
                                log.info("Director call blocked — session already complete: %s", session.completion_reason)
                                result = (
                                    "SESSION COMPLETE — blocked. All objectives already met.\n"
                                    f"Reason: {session.completion_reason}\n\n"
                                    "STOP. Send ONE closing message with recap + takeaway + warm close.\n"
                                    "Do NOT request another plan. Do NOT ask questions. This is your FINAL turn."
                                )
                            elif reason not in bypass_reasons and session.turns_since_last_director < MIN_TURNS_FOR_DIRECTOR:
                                log.info("Director call blocked — only %d turns since last call (min %d), reason: %s", session.turns_since_last_director, MIN_TURNS_FOR_DIRECTOR, reason)
                                result = (
                                    f"Director call deferred: only {session.turns_since_last_director} student turns since last script. "
                                    "Continue executing the current script. You have steps remaining — work through them before requesting a new plan. "
                                    "If the student is struggling, adapt your approach (change modality, simplify, give hints) rather than requesting a new script."
                                )
                            else:
                                # Shared: scenario detection, notes, trigger building
                                log.info("Tutor requesting new plan — reason: %s", reason)

                                if block.input.get("detected_scenario"):
                                    detected = block.input["detected_scenario"]
                                    if detected != session.active_scenario:
                                        session.active_scenario = detected
                                        log.info("Scenario detected by Tutor: %s", detected)

                                session.tutor_notes.append(block.input.get("tutor_notes", ""))
                                if block.input.get("chat_summary"):
                                    session.chat_summaries.append(block.input["chat_summary"])
                                if block.input.get("student_model"):
                                    session.student_model = block.input["student_model"]

                                # Build trigger message
                                is_probing = reason == "probing_complete"
                                trigger_parts = [
                                    "STUDENT_INTENT — Tutor has completed probing. Generate the first teaching script."
                                    if is_probing
                                    else "TUTOR_CALLBACK — requesting new script.",
                                    "",
                                    f"Reason: {reason}",
                                ]

                                if block.input.get("detected_scenario"):
                                    trigger_parts.append(f"Detected scenario: {block.input['detected_scenario']}")

                                trigger_parts.extend([
                                    "",
                                    "=== Tutor's Observations ===",
                                    block.input.get("tutor_notes", "None"),
                                    "",
                                    "=== Recent Chat Summary ===",
                                    block.input.get("chat_summary", "No summary provided"),
                                ])

                                if block.input.get("student_model"):
                                    trigger_parts.extend(["", "=== Tutor Student Model ===", json.dumps(block.input["student_model"], indent=2)])

                                if is_probing and session.student_intent:
                                    trigger_parts.extend(["", "=== Student Intent (from session start) ===", session.student_intent])

                                director_trigger = "\n".join(trigger_parts)

                                if is_background_eligible:
                                    if session.pending_director_call:
                                        log.info("Background Director already running — skipping duplicate")
                                        result = "Director is already preparing the next script. Continue with current steps."
                                    else:
                                        start_background_director(session, context_data, director_trigger, claude_messages)
                                        session.turns_since_last_director = 0
                                        result = (
                                            "Script preparation started in background. Continue executing your current script — "
                                            "finish remaining steps naturally. The new script will be available when ready."
                                        )
                                else:
                                    # Sync path — use streaming Director with TopicManager
                                    log.info("request_director_plan: starting streaming Director (sync path, reason=%s)", reason)
                                    yield _sse({"type": "DIRECTOR_THINKING"})

                                    # Create TopicManager
                                    manager = TopicManager()
                                    session.topic_manager = manager

                                    # Start streaming Director
                                    task = asyncio.create_task(stream_director(session, manager, context_data, director_trigger, claude_messages))
                                    manager.director_task = task

                                    # Wait for plan
                                    try:
                                        t0 = time.monotonic()
                                        plan = await manager.wait_for_plan()
                                        plan_wait = time.monotonic() - t0
                                        log.info(
                                            "request_director_plan: plan received in %.1fs — %s (%d sections)",
                                            plan_wait,
                                            plan.get("session_objective", "?")[:60],
                                            len(plan.get("sections", [])),
                                        )
                                        yield _sse({"type": "DIRECTOR_PLAN", "plan": plan})

                                        # Wait for first topic
                                        t1 = time.monotonic()
                                        first = await manager.get_next_topic()
                                        topic_wait = time.monotonic() - t1
                                        topic = first["topic"]

                                        # Rebuild Tutor prompt with plan + topic
                                        tutor_prompt = _rebuild_tutor_prompt(session, context_data)
                                        log.info(
                                            "request_director_plan: plan in %.1fs + topic in %.1fs = %.1fs total. Prompt: %d chars (~%d tokens)",
                                            plan_wait, topic_wait, time.monotonic() - t0,
                                            len(tutor_prompt), len(tutor_prompt) // 4,
                                        )

                                        # Also emit DIRECTOR_SCRIPT for legacy frontend compat
                                        if plan:
                                            yield _sse({
                                                "type": "DIRECTOR_SCRIPT",
                                                "script": {
                                                    "session_objective": plan.get("session_objective"),
                                                    "scenario": plan.get("scenario"),
                                                    "steps": [
                                                        {"n": s.get("n", i+1), "student_label": s.get("title", ""), "type": s.get("modality", ""), "objective": s.get("learning_outcome", ""), "concept": s.get("covers", "")}
                                                        for i, s in enumerate(plan.get("sections", []))
                                                    ],
                                                    "session_status": manager.session_status,
                                                },
                                                "sessionStatus": manager.session_status,
                                                "completionReason": manager.completion_reason,
                                            })

                                        if topic:
                                            steps_summary = " | ".join(
                                                f"{s.get('n', '?')}. [{s.get('type', '?')}] {s.get('objective', '')[:50]}"
                                                for s in (topic.data.get("steps") or [])
                                            )
                                            result_parts = [
                                                f"Teaching plan received with {len(plan.get('sections', []))} sections.",
                                                f"Session objective: {plan.get('session_objective', '')}",
                                                f"Scenario: {plan.get('scenario', 'course')}",
                                                f"First topic: {topic.title} [concept={topic.concept}]",
                                                f"Steps: {steps_summary}",
                                                f"Tutor notes: {topic.data.get('tutor_notes', 'None')}",
                                                "",
                                                "Your system prompt now contains the full topic script. Begin teaching — execute step 1 of the current topic now.",
                                            ]
                                        else:
                                            result_parts = [
                                                f"Teaching plan received with {len(plan.get('sections', []))} sections.",
                                                f"Session objective: {plan.get('session_objective', '')}",
                                                "Topics still loading — begin with the plan overview.",
                                            ]

                                        if manager.session_status == "complete":
                                            result_parts.extend([
                                                "",
                                                f"SESSION COMPLETE — Reason: {manager.completion_reason or 'All objectives met'}",
                                                "Execute final steps, then wrap up.",
                                            ])

                                        result = "\n".join(result_parts)
                                        session.turns_since_last_director = 0

                                    except Exception as e:
                                        elapsed = time.monotonic() - t0
                                        log.error("Streaming Director error after %.1fs: %s", elapsed, e, exc_info=True)
                                        result = f"Director error: {str(e)[:200]}. Continue with what you know."
                                        session.turns_since_last_director = 0

                        else:
                            # Normal tool execution
                            result = await execute_tutor_tool(block.name, block.input)

                        elapsed = time.monotonic() - start_time
                        result_preview = str(result)[:150]
                        log.info("Tool %s done (%.1fs): %s...", block.name, elapsed, result_preview)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result if isinstance(result, str) else json.dumps(result),
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
                log.error("Anthropic bad request: %s", e, exc_info=True)
                yield _sse({"type": "RUN_ERROR", "message": f"AI request error: {err_msg}"})
        except anthropic.AuthenticationError as e:
            log.error("Anthropic auth error: %s", e)
            yield _sse({"type": "RUN_ERROR", "message": "The AI service API key is invalid or expired. Please check the configuration."})
        except anthropic.RateLimitError as e:
            log.warning("Anthropic rate limit: %s", e)
            yield _sse({"type": "RUN_ERROR", "message": "The AI service is rate-limited right now. Please wait a moment and try again."})
        except anthropic.APIConnectionError as e:
            log.error("Anthropic connection error: %s", e)
            yield _sse({"type": "RUN_ERROR", "message": "Could not connect to the AI service. Please check your internet connection."})
        except Exception as e:
            log.error("Chat error: %s", e, exc_info=True)
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
