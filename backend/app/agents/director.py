"""Director agent — agentic loop with tool calls, JSON self-healing, background mode, JSONL streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import TYPE_CHECKING, Any

import anthropic

from app.agents.prompts import SKILL_MAP, build_director_prompt
from app.agents.session import Session, compact_previous_scripts, compact_session_history
from app.core.config import settings
from app.tools import DIRECTOR_TOOLS, execute_director_tool

if TYPE_CHECKING:
    from app.agents.section_manager import TopicManager

log = logging.getLogger(__name__)

MAX_DIRECTOR_ROUNDS = 12

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


# ── JSON Parsing ─────────────────────────────────────────────────────────────

def parse_script_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    m = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError("Failed to parse Director script JSON")


def script_for_tutor(script: dict | None) -> dict | None:
    if not script:
        return None
    return {
        "session_objective": script.get("session_objective"),
        "scenario": script.get("scenario"),
        "steps": script.get("steps"),
        "tutor_notes": script.get("tutor_notes"),
    }


def compact_tutor_notes(notes: list[str]) -> str | None:
    if not notes:
        return None
    combined = "\n---\n".join(notes)
    if len(combined) <= 2000:
        return combined
    kept = notes[-3:]
    dropped = len(notes) - 3
    return f"[{dropped} earlier note(s) summarized: Tutor provided observations over {dropped} interactions]\n---\n" + "\n---\n".join(kept)


def build_compact_chat_history(messages: list[dict], limit: int = 20) -> str | None:
    if not messages:
        return None
    recent = messages[-limit:]
    lines: list[str] = []
    for msg in recent:
        content = msg.get("content", "")
        if not isinstance(content, str) or not content.strip():
            continue
        role = "Student" if msg["role"] == "user" else "Tutor"
        text = content
        if msg["role"] == "assistant":
            text = re.sub(r"<teaching-[^>]*>[\s\S]*?</teaching-[^>]*>", "", text)
            text = re.sub(r"<teaching-[^/]*/?>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        if len(text) > 120:
            text = text[:117] + "..."
        lines.append(f"{role}: {text}")
    return "\n".join(lines) if lines else None


# ── Director Call ────────────────────────────────────────────────────────────

async def call_director(
    session: Session,
    context_data: dict,
    trigger_message: str,
    send_keepalive=None,
    messages: list[dict] | None = None,
) -> dict:
    """Call the Director (Opus) to produce a teaching script. Agentic loop."""

    # Build rich context
    all_scripts = [*session.previous_scripts]
    if session.current_script:
        all_scripts.append(session.current_script)
    compacted_scripts = compact_previous_scripts(all_scripts)

    previous_script_text = None
    if compacted_scripts:
        previous_script_text = "\n\n".join(
            s["text"] if s.get("_summary") else json.dumps(s, indent=2)
            for s in compacted_scripts
        )

    compact_session_history(session)
    session_history_parts: list[str] = []
    if session.session_history:
        session_history_parts.append(session.session_history)
    for i, summary in enumerate(session.chat_summaries):
        if summary:
            call_num = session.director_call_count - len(session.chat_summaries) + i + 1
            session_history_parts.append(f"[Director call {call_num}] {summary}")
    session_history_text = "\n".join(session_history_parts) if session_history_parts else None

    tutor_notes_text = compact_tutor_notes(session.tutor_notes)
    chat_history_text = build_compact_chat_history(messages) if messages else None

    director_prompt = build_director_prompt({
        **context_data,
        "previousScript": previous_script_text,
        "tutorNotes": tutor_notes_text,
        "studentModel": json.dumps(session.student_model, indent=2) if session.student_model else None,
        "sessionHistory": session_history_text,
        "studentIntent": session.student_intent,
        "chatHistory": chat_history_text,
        "pauseNote": session.pause_note,
    })

    log.info("Calling Director (%s) — trigger: %.100s...", settings.DIRECTOR_MODEL, trigger_message)
    log.info("Director prompt: %d chars (~%d tokens)", len(director_prompt), len(director_prompt) // 4)

    # Keepalive pings
    keepalive_task = None
    if send_keepalive:
        async def _keepalive():
            try:
                while True:
                    await asyncio.sleep(5)
                    await send_keepalive()
            except asyncio.CancelledError:
                pass
        keepalive_task = asyncio.create_task(_keepalive())

    client = _get_client()
    start_time = time.monotonic()

    try:
        director_messages: list[dict] = [{"role": "user", "content": trigger_message}]
        round_num = 0

        while round_num < MAX_DIRECTOR_ROUNDS:
            round_num += 1
            is_last_round = round_num == MAX_DIRECTOR_ROUNDS
            log.info("Director round %d/%d%s", round_num, MAX_DIRECTOR_ROUNDS, " (final — no tools)" if is_last_round else "")

            request_params: dict[str, Any] = {
                "model": settings.DIRECTOR_MODEL,
                "max_tokens": 4096,
                "system": director_prompt,
                "messages": director_messages,
            }
            if not is_last_round:
                request_params["tools"] = DIRECTOR_TOOLS

            response = await client.messages.create(**request_params)

            elapsed = time.monotonic() - start_time
            log.info(
                "Director round %d — stop: %s, %din/%dout (%.1fs total)",
                round_num, response.stop_reason,
                response.usage.input_tokens, response.usage.output_tokens,
                elapsed,
            )

            if response.stop_reason == "tool_use":
                tool_blocks = [b for b in response.content if b.type == "tool_use"]
                tool_names = ", ".join(b.name for b in tool_blocks)
                log.info("Director tool calls: %s", tool_names)

                tool_results = await asyncio.gather(*(
                    _run_director_tool(b) for b in tool_blocks
                ))

                director_messages.append({"role": "assistant", "content": response.content})
                director_messages.append({"role": "user", "content": tool_results})
                continue

            # end_turn — extract final text
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text = block.text
                    break

            log.info("Director finished in %.1fs, %d round(s) — %d chars", elapsed, round_num, len(text))

            try:
                script = parse_script_json(text)
            except ValueError:
                log.warning("Director JSON parse failed (%d chars). Sending fix-up round...", len(text))
                fixup_hint = (
                    "You did not output a script. You MUST output the full JSON script object now. No tool calls, no commentary — just the JSON."
                    if not text
                    else f"Your output was not valid JSON. Parse error on your text ({len(text)} chars). Output ONLY the corrected JSON script object — no markdown fences, no explanation."
                )
                director_messages.append({"role": "assistant", "content": response.content})
                director_messages.append({"role": "user", "content": fixup_hint})

                fixup_response = await client.messages.create(
                    model=settings.DIRECTOR_MODEL,
                    max_tokens=4096,
                    system=director_prompt,
                    messages=director_messages,
                )
                fixup_text = ""
                for block in fixup_response.content:
                    if hasattr(block, "text"):
                        fixup_text = block.text
                        break
                script = parse_script_json(fixup_text)

            log.info('Script: "%s" — %d steps', script.get("session_objective", ""), len(script.get("steps", [])))

            # Update session state
            if session.current_script:
                session.previous_scripts.append(session.current_script)
            session.current_script = script
            session.student_model = script.get("student_model") or session.student_model
            session.tutor_notes = []
            session.director_call_count += 1

            if script.get("session_status") == "complete":
                session.session_status = "complete"
                session.completion_reason = script.get("completion_reason", "Session objectives met")
                session.pause_note = None
                log.info("Director signaled session complete: %s", session.completion_reason)
            elif script.get("session_status") == "paused":
                session.session_status = "paused"
                session.pause_note = script.get("pause_note")

            return script

        log.warning("Director loop exited after %d rounds", MAX_DIRECTOR_ROUNDS)
        raise RuntimeError("Director failed to produce a script")

    finally:
        if keepalive_task:
            keepalive_task.cancel()
            try:
                await keepalive_task
            except asyncio.CancelledError:
                pass


async def _run_director_tool(block) -> dict:
    start = time.monotonic()
    log.info("Director → %s(%.120s)", block.name, json.dumps(block.input))
    result = await execute_director_tool(block.name, block.input)
    elapsed = time.monotonic() - start
    log.info("Director ← %s (%.1fs): %.120s...", block.name, elapsed, str(result))
    return {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": result if isinstance(result, str) else json.dumps(result),
    }


# ── Background Director ─────────────────────────────────────────────────────

def start_background_director(
    session: Session,
    context_data: dict,
    director_trigger: str,
    claude_messages: list[dict],
) -> None:
    session.pending_director_call = True

    async def _run():
        try:
            await call_director(session, context_data, director_trigger, messages=claude_messages)
            # Undo: move new script to pending, restore original
            session.pending_script = session.current_script
            session.current_script = session.previous_scripts.pop()
            session.pending_director_call = False
            log.info(
                'Background Director done: "%s" — %d steps',
                session.pending_script.get("session_objective", ""),
                len(session.pending_script.get("steps", [])),
            )
        except Exception as e:
            session.pending_director_call = False
            log.error("Background Director failed: %s", e)

    asyncio.create_task(_run())


# ── Streaming Director (JSONL) ────────────────────────────────────────────

async def stream_director(
    session: Session,
    manager: TopicManager,
    context_data: dict,
    trigger_message: str,
    messages: list[dict] | None = None,
) -> None:
    """Stream Director output into TopicManager. Runs as background task."""

    try:
        # Build rich context (same as call_director)
        all_scripts = [*session.previous_scripts]
        if session.current_script:
            all_scripts.append(session.current_script)
        compacted_scripts = compact_previous_scripts(all_scripts)

        previous_script_text = None
        if compacted_scripts:
            previous_script_text = "\n\n".join(
                s["text"] if s.get("_summary") else json.dumps(s, indent=2)
                for s in compacted_scripts
            )

        compact_session_history(session)
        session_history_parts: list[str] = []
        if session.session_history:
            session_history_parts.append(session.session_history)
        for i, summary in enumerate(session.chat_summaries):
            if summary:
                call_num = session.director_call_count - len(session.chat_summaries) + i + 1
                session_history_parts.append(f"[Director call {call_num}] {summary}")
        session_history_text = "\n".join(session_history_parts) if session_history_parts else None

        tutor_notes_text = compact_tutor_notes(session.tutor_notes)
        chat_history_text = build_compact_chat_history(messages) if messages else None

        director_prompt = build_director_prompt({
            **context_data,
            "previousScript": previous_script_text,
            "tutorNotes": tutor_notes_text,
            "studentModel": json.dumps(session.student_model, indent=2) if session.student_model else None,
            "sessionHistory": session_history_text,
            "studentIntent": session.student_intent,
            "chatHistory": chat_history_text,
            "pauseNote": session.pause_note,
        })

        log.info("Streaming Director (%s) — trigger: %.100s...", settings.DIRECTOR_MODEL, trigger_message)
        log.info("Director prompt: %d chars (~%d tokens)", len(director_prompt), len(director_prompt) // 4)

        client = _get_client()
        director_messages: list[dict] = [{"role": "user", "content": trigger_message}]
        start_time = time.monotonic()

        for round_num in range(1, MAX_DIRECTOR_ROUNDS + 1):
            is_last = round_num == MAX_DIRECTOR_ROUNDS
            log.info(
                "Director stream round %d/%d%s",
                round_num, MAX_DIRECTOR_ROUNDS,
                " (final — no tools)" if is_last else "",
            )

            request_params: dict[str, Any] = {
                "model": settings.DIRECTOR_MODEL,
                "max_tokens": 4096,
                "system": director_prompt,
                "messages": director_messages,
            }
            if not is_last:
                request_params["tools"] = DIRECTOR_TOOLS

            response = await client.messages.create(**request_params)

            elapsed = time.monotonic() - start_time
            log.info(
                "Director stream round %d — stop: %s, %din/%dout (%.1fs total)",
                round_num, response.stop_reason,
                response.usage.input_tokens, response.usage.output_tokens,
                elapsed,
            )

            # ★ Parse text from EVERY round, not just final
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            if text_blocks:
                total_chars = sum(len(t) for t in text_blocks)
                log.info("Director stream round %d — %d text block(s), %d chars total to parse", round_num, len(text_blocks), total_chars)
            for text in text_blocks:
                _parse_jsonl_into_manager(text, manager, session)

            # Handle tool calls
            if response.stop_reason == "tool_use":
                tool_blocks = [b for b in response.content if b.type == "tool_use"]
                tool_names = ", ".join(b.name for b in tool_blocks)
                log.info("Director tool calls: %s", tool_names)

                tool_results = await asyncio.gather(*(
                    _run_director_tool(b) for b in tool_blocks
                ))

                director_messages.append({"role": "assistant", "content": response.content})
                director_messages.append({"role": "user", "content": tool_results})

                # Lazy generation: pause if Tutor is far behind
                await manager.wait_if_paused()
                continue

            # end_turn — finalize
            log.info("Director stream finished in %.1fs, %d round(s)", elapsed, round_num)
            _finalize_director(session, manager)
            return

        # Fell through all rounds
        if not manager.director_done:
            manager.set_error("Director failed to complete after max rounds")

    except asyncio.CancelledError:
        log.info("Director streaming cancelled")
        if not manager.plan:
            manager.set_error("Director cancelled before producing a plan")
    except Exception as e:
        log.error("Director streaming error: %s", e, exc_info=True)
        manager.set_error(f"Director error: {str(e)[:200]}")


def _parse_jsonl_into_manager(text: str, manager: TopicManager, session: Session) -> None:
    """Parse JSONL lines from Director text output and dispatch to manager."""
    lines = text.strip().splitlines()
    parsed_count = 0
    skipped_count = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # Try extracting JSON from markdown fences or embedded in text
            m = re.search(r'\{.*\}', line)
            if m:
                try:
                    obj = json.loads(m.group(0))
                    log.debug("JSONL healed — extracted JSON from: %.80s", line)
                except json.JSONDecodeError:
                    log.warning("JSONL parse failed (even after healing): %.100s", line)
                    skipped_count += 1
                    continue
            else:
                log.debug("JSONL skipping non-JSON line: %.80s", line)
                skipped_count += 1
                continue

        obj_type = obj.get("type")
        if obj_type == "plan":
            log.info("JSONL → plan: scenario=%s, %d sections outlined", obj.get("scenario", "?"), len(obj.get("sections", [])))
            manager.set_plan(obj)
            if obj.get("scenario"):
                session.active_scenario = obj["scenario"]
            parsed_count += 1
        elif obj_type == "topic":
            sec_idx = obj.get("section_index", 0)
            top_idx = obj.get("topic_index", 0)
            log.info(
                "JSONL → topic (%d,%d): %s [concept=%s, %d steps]",
                sec_idx, top_idx, obj.get("title", "?")[:60],
                obj.get("concept", "?")[:30], len(obj.get("steps", [])),
            )
            manager.add_topic(obj)
            parsed_count += 1
        elif obj_type == "section":
            # Backward compat: treat old-style section as a single topic
            log.info("JSONL → section %d (legacy): %s (%d steps)", obj.get("index", -1), obj.get("title", "?")[:60], len(obj.get("steps", [])))
            sec_idx = obj.get("index", len(manager.sections))
            topic_data = {
                **obj,
                "type": "topic",
                "section_index": sec_idx,
                "topic_index": 0,
            }
            manager.add_topic(topic_data)
            manager.mark_section_done(sec_idx, 1)
            parsed_count += 1
        elif obj_type == "section_done":
            sec_idx = obj.get("section_index", 0)
            topic_count = obj.get("topic_count", 0)
            log.info("JSONL → section_done: section %d, %d topics", sec_idx, topic_count)
            manager.mark_section_done(sec_idx, topic_count)
            parsed_count += 1
        elif obj_type == "done":
            status = obj.get("session_status", "active")
            log.info("JSONL → done: status=%s, reason=%s", status, obj.get("completion_reason", "none"))
            manager.mark_done(status, obj.get("completion_reason"))
            if status == "complete":
                session.session_status = "complete"
                session.completion_reason = obj.get("completion_reason")
            elif status == "paused":
                session.session_status = "paused"
                session.pause_note = obj.get("pause_note")
            parsed_count += 1
        else:
            log.warning("JSONL unknown type=%s: %.100s", obj_type, line)
            skipped_count += 1

    if parsed_count > 0 or skipped_count > 0:
        log.info("JSONL parse summary: %d parsed, %d skipped, %d total lines", parsed_count, skipped_count, len(lines))


def _finalize_director(session: Session, manager: TopicManager) -> None:
    """Post-Director session bookkeeping."""
    session.director_call_count += 1
    session.tutor_notes = []
    session.turns_since_last_director = 0

    if manager.plan:
        session.student_model = manager.plan.get("student_model") or session.student_model

    if not manager.director_done:
        log.info("Director finalize: director didn't emit 'done' line — marking done with status=active")
        manager.mark_done("active")

    log.info(
        "Director finalize: call_count=%d, plan=%s, sections=%d, status=%s",
        session.director_call_count,
        "yes" if manager.plan else "no",
        len(manager.sections),
        manager.session_status,
    )
