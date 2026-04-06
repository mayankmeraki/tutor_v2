"""Chat endpoint — SSE streaming with Tutor agentic loop + sub-agent architecture.

The Tutor starts teaching immediately. Background agents handle planning,
asset preparation, and research. Teaching delegation hands off bounded
tasks to focused sub-agents.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re as _re
import time
import traceback
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.agents.agent_runtime import AgentRuntime, AssessmentState, DelegationState
from app.agents.session import SessionPhase
from app.core.llm import (
    llm_stream,
    is_retryable,
    extract_retry_after,
    LLMBadRequestError,
    LLMAuthError,
    LLMRateLimitError,
    LLMConnectionError,
    LLMCallMetadata,
)
from app.core.logging_config import SessionLogger
from app.agents.prompts import SKILL_MAP, build_tutor_prompt, build_assessment_prompt
from app.agents.prompts.teaching_delegate import build_delegation_prompt
from app.agents.session import get_or_create_session, get_session_lock
from app.services.knowledge_state import (
    get_or_init_knowledge_state,
    format_knowledge_state,
    search_notes,
    hybrid_search_notes,
    get_knowledge_summary,
)
from app.services.session_service import sync_backend_state
from app.tools import (
    TUTOR_TOOLS,
    DELEGATION_TOOLS,
    ASSESSMENT_TOOLS,
    COMPLETE_ASSESSMENT_TOOL,
    HANDBACK_TO_TUTOR_TOOL,
    RETURN_TO_TUTOR_TOOL,
    VIDEO_FOLLOW_TOOLS,
    VIDEO_CONTROL_TOOLS,
    execute_tutor_tool,
)

from app.core.rate_limit import check_rate_limit_chat as _check_rate_limit
from app.api.routes import sse as _sse
from app.api.routes.auth import get_optional_user

log = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

def _sse_raw(data: dict) -> str:
    """Format a single SSE event as a string (for non-generator error responses)."""
    return f"data: {json.dumps(data)}\n\n"

MAX_ROUNDS = 8  # cap tutor tool rounds
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds, doubles each retry


# ── Message validation ────────────────────────────────────────────────────────

def _validate_messages(messages: list[dict]) -> list[dict]:
    """Ensure all messages have valid content before sending to API.

    Fixes:
    - 'user messages must have non-empty content' 400 error
    - Partial/interrupted assistant messages with broken XML
    - Tool result blocks with empty content
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

            # Clean interrupted assistant messages — close broken XML tags
            if msg.get("role") == "assistant":
                content = _clean_partial_content(content)

            validated.append({**msg, "content": content})

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
                elif isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    if text:
                        fixed_blocks.append({**block, "text": _clean_partial_content(text)})
                    else:
                        fixed_blocks.append(block)
                else:
                    fixed_blocks.append(block)
            validated.append({**msg, "content": fixed_blocks})

        else:
            # ContentBlock objects from SDK — pass through
            validated.append(msg)

    # Safety net: ensure every tool_result has a matching tool_use in the
    # preceding assistant message. If not, inject dummy tool_use blocks.
    cleaned = []
    for i, msg in enumerate(validated):
        content = msg.get("content")
        if msg.get("role") == "user" and isinstance(content, list):
            tool_result_ids = set(
                b.get("tool_use_id") for b in content
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id")
            )
            if tool_result_ids and i > 0 and cleaned:
                prev = cleaned[-1]
                if prev.get("role") == "assistant":
                    prev_content = prev.get("content")

                    # Collect existing tool_use IDs in the assistant message
                    existing_ids = set()
                    if isinstance(prev_content, list):
                        for b in prev_content:
                            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id"):
                                existing_ids.add(b["id"])

                    # Find orphaned IDs (in results but not in assistant tool_use)
                    orphaned = tool_result_ids - existing_ids

                    if orphaned:
                        # Reconstruct: inject dummy tool_use blocks
                        if isinstance(prev_content, str):
                            reconstructed = [{"type": "text", "text": prev_content}]
                        elif isinstance(prev_content, list):
                            reconstructed = list(prev_content)
                        else:
                            reconstructed = [{"type": "text", "text": str(prev_content)}]

                        for tid in orphaned:
                            reconstructed.append({
                                "type": "tool_use",
                                "id": tid,
                                "name": "_reconstructed",
                                "input": {},
                            })
                        cleaned[-1] = {**prev, "content": reconstructed}
                        log.info("Reconstructed %d orphaned tool_use blocks", len(orphaned))

        cleaned.append(msg)

    # ── Tool pairing validation ──
    # Anthropic requires:
    # - Every tool_use ID is unique across all messages
    # - Every tool_use has a matching tool_result in the next user message
    # - Every tool_result has a matching tool_use in the preceding assistant message
    #
    # Violations happen when:
    # - Turn interrupted after tool_use appended but before tool_results (orphan tool_use)
    # - Messages duplicated during serialization/restore (duplicate IDs)
    # - tool_result message lost during context windowing (orphan tool_use)

    import uuid as _uuid

    # Pass 1: Fix duplicate tool_use IDs (reassign, update matching results)
    seen_tool_ids = set()
    for i, msg in enumerate(cleaned):
        content = msg.get("content")
        if msg.get("role") == "assistant" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tid = block.get("id")
                    if tid and tid in seen_tool_ids:
                        new_id = f"toolu_{_uuid.uuid4().hex[:24]}"
                        old_id = tid
                        log.warning("Reassigning duplicate tool_use id %s → %s", old_id, new_id)
                        block["id"] = new_id
                        # Update matching tool_result
                        for k in range(i + 1, len(cleaned)):
                            sub = cleaned[k].get("content")
                            if cleaned[k].get("role") == "user" and isinstance(sub, list):
                                for rb in sub:
                                    if isinstance(rb, dict) and rb.get("type") == "tool_result" and rb.get("tool_use_id") == old_id:
                                        rb["tool_use_id"] = new_id
                                        break
                                break
                        tid = new_id
                    if tid:
                        seen_tool_ids.add(tid)

    # Pass 2: Ensure every tool_use has a matching tool_result
    # If an assistant message has tool_use blocks but the next message
    # doesn't have matching tool_results (interrupted turn), inject them.
    final = []
    for i, msg in enumerate(cleaned):
        final.append(msg)
        content = msg.get("content")
        if msg.get("role") != "assistant" or not isinstance(content, list):
            continue

        # Collect tool_use IDs in this assistant message
        tool_use_ids = [
            b["id"] for b in content
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id")
        ]
        if not tool_use_ids:
            continue

        # Check if next message has matching tool_results
        next_msg = cleaned[i + 1] if i + 1 < len(cleaned) else None
        next_result_ids = set()
        if next_msg and next_msg.get("role") == "user" and isinstance(next_msg.get("content"), list):
            next_result_ids = {
                b.get("tool_use_id") for b in next_msg["content"]
                if isinstance(b, dict) and b.get("type") == "tool_result"
            }

        # Find tool_use IDs without matching results
        missing = [tid for tid in tool_use_ids if tid not in next_result_ids]
        if missing:
            log.warning("Injecting %d missing tool_results for interrupted tool calls", len(missing))
            missing_results = [
                {"type": "tool_result", "tool_use_id": tid, "content": "[interrupted — tool execution was cancelled]"}
                for tid in missing
            ]
            if next_msg and next_msg.get("role") == "user" and isinstance(next_msg.get("content"), list):
                # Append to existing user message
                next_msg["content"] = list(next_msg["content"]) + missing_results
            else:
                # Insert a new user message with the missing results
                final.append({"role": "user", "content": missing_results})

    return final


def _clean_partial_content(text: str) -> str:
    """Clean partial/interrupted content to prevent broken XML from corrupting the API call.

    When a student interrupts mid-response, the assistant message may contain:
    - Unclosed <teaching-voice-scene> tags
    - Partial <vb say="incomplete...
    - Unclosed <teaching-board-draw> tags
    - Half-written tool call blocks

    This function closes or strips broken tags to make the content valid.
    """
    import re as _re_clean

    # Strip the "[Student interrupted — tutor stopped here]" marker
    text = text.replace('\n\n[Student interrupted — tutor stopped here]', '')
    text = text.replace('[Student interrupted — tutor stopped here]', '')

    # Close any unclosed teaching-voice-scene tags
    open_vs = text.count('<teaching-voice-scene')
    close_vs = text.count('</teaching-voice-scene>')
    if open_vs > close_vs:
        # Remove the partial/unclosed voice scene — the model doesn't need to see it
        # Find the last unclosed opening tag and truncate
        last_open = text.rfind('<teaching-voice-scene')
        last_close = text.rfind('</teaching-voice-scene>')
        if last_open > last_close:
            # Truncate at the unclosed tag, add a note
            text = text[:last_open].rstrip() + '\n[interrupted mid-voice-scene]'

    # Close any unclosed teaching-board-draw tags
    open_bd = text.count('<teaching-board-draw')
    close_bd = text.count('</teaching-board-draw>')
    if open_bd > close_bd:
        last_open = text.rfind('<teaching-board-draw')
        last_close = text.rfind('</teaching-board-draw>')
        if last_open > last_close:
            text = text[:last_open].rstrip() + '\n[interrupted mid-board-draw]'

    # Strip any incomplete <vb tags (partial self-closing tags without />)
    # e.g. <vb say="Hello wor  → remove it
    text = _re_clean.sub(r'<vb\s+[^/]*$', '', text)

    return text.strip() or "(interrupted)"


# Regex for housekeeping tag
_HOUSEKEEPING_RE = _re.compile(
    r'<teaching-housekeeping>([\s\S]*?)</teaching-housekeeping>',
    _re.DOTALL,
)
_SIGNAL_RE = _re.compile(
    r'<signal\s+progress=["\']([^"\']*)["\'](?:\s+student=["\']([^"\']*)["\'])?(?:\s+[^/]*)?\s*/?>',
)
_NOTES_RE = _re.compile(
    r'<notes>([\s\S]*?)</notes>',
)
_PLAN_MODIFY_RE = _re.compile(
    r'<plan-modify\s+action=["\'](\w+)["\']'
    r'(?:\s+title=["\']([^"\']*)["\'])?'
    r'(?:\s+concept=["\']([^"\']*)["\'])?'
    r'(?:\s+reason=["\']([^"\']*)["\'])?'
    r'\s*/?>',
)
_HANDOFF_RE = _re.compile(
    r'<handoff\s+type=["\'](\w+)["\']'
    r'(?:\s+section=["\']([^"\']*)["\'])?'
    r'(?:\s+concepts=["\']([^"\']*)["\'])?'
    r'(?:\s+topic=["\']([^"\']*)["\'])?'
    r'(?:\s+instructions=["\']([^"\']*)["\'])?'
    r'\s*/?>',
)
_SPAWN_RE = _re.compile(
    r'<spawn\s+type=["\'](\w+)["\']'
    r'(?:\s+task=["\']([^"\']*)["\'])?'
    r'(?:\s+instructions=["\']([^"\']*)["\'])?'
    r'\s*/?>',
)


def _strip_housekeeping_tag(text: str) -> str:
    """Strip <teaching-housekeeping> from message text before saving to history."""
    return _HOUSEKEEPING_RE.sub('', text).rstrip()


def _process_housekeeping_tags(session, full_text: str, context_data: dict, session_id: str, slog):
    """Parse housekeeping tags from response, update session state, strip from history.

    Called after the LLM response is complete. Extracts:
    - <signal progress="..." student="..." /> → session.last_signals + auto-advance + auto-assessment
    - <notes>[...]</notes> → session.student_model (fire-and-forget DB upsert)
    - <plan-modify .../> → session.current_topics modification
    - <handoff .../> → session.assessment or session.delegation

    Robust: all parsing is wrapped in try/except. Malformed tags are logged and skipped.
    """
    try:
        _process_housekeeping_inner(session, full_text, context_data, session_id, slog)
    except Exception as e:
        slog.error("Housekeeping processing failed (non-fatal): %s", e, exc_info=True)

    # Always strip the tag from history, even if parsing failed
    if session.messages:
        last_msg = session.messages[-1]
        if last_msg.get("role") == "assistant":
            content = last_msg.get("content", "")
            if isinstance(content, str):
                last_msg["content"] = _strip_housekeeping_tag(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        block["text"] = _strip_housekeeping_tag(block.get("text", ""))


def _process_housekeeping_inner(session, full_text: str, context_data: dict, session_id: str, slog):
    """Inner housekeeping parser — called within try/except wrapper."""
    match = _HOUSEKEEPING_RE.search(full_text)
    if not match:
        return

    hk_content = match.group(1)

    # Parse signal
    sig_match = _SIGNAL_RE.search(hk_content)
    if sig_match:
        progress = sig_match.group(1) or "in_progress"
        student_state = sig_match.group(2) or "engaged"
        session.last_signals = {
            "section_progress": progress,
            "student_state": student_state,
        }
        slog.debug("Housekeeping signal", extra={"progress": progress, "student": student_state})

        # Auto-advance topic when section is complete
        if progress == "complete":
            completed_topic_title = ""
            completed_concepts = []
            if session.current_topics and 0 <= session.current_topic_index < len(session.current_topics):
                completed_topic = session.current_topics[session.current_topic_index]
                completed_topic_title = completed_topic.get("title", "Unknown")
                completed_concepts = [completed_topic.get("concept", "")] if completed_topic.get("concept") else []
                session.completed_topics.append(completed_topic_title)
                session.current_topic_index += 1
                slog.debug("Auto-advanced topic via housekeeping signal",
                          extra={"completed": completed_topic_title, "next_index": session.current_topic_index})
            session.pre_assessment_note = None

            # Auto-create assessment state so next turn routes to assessment agent
            if completed_topic_title and not session.assessment:
                from app.agents.agent_runtime import AssessmentState
                # Build assessment prompt and state
                assessment_brief = {
                    "section": {"title": completed_topic_title},
                    "conceptsTested": completed_concepts,
                    "plan": {"questionCount": {"min": 3, "max": 5}},
                }
                assessment_prompt = build_assessment_prompt({
                    **context_data,
                    "assessmentBrief": assessment_brief,
                    "studentModel": json.dumps(session.student_model, indent=2) if session.student_model else None,
                })
                session.assessment = AssessmentState(
                    system_prompt=assessment_prompt,
                    tools=ASSESSMENT_TOOLS,
                    brief=assessment_brief,
                    section_title=completed_topic_title,
                    concepts_tested=completed_concepts,
                )
                session.pre_assessment_note = {
                    "section": completed_topic_title,
                    "concepts": completed_concepts,
                }
                slog.info("Auto-created assessment for completed topic",
                          extra={"section": completed_topic_title, "concepts": completed_concepts})

        # Check phase transition
        new_phase = _check_phase_transition(session, {})
        if new_phase and new_phase != session.phase:
            session.phase = new_phase
            slog.info("Phase transition from housekeeping", extra={"to": new_phase})

    # Parse notes (only present when housekeeping was due)
    notes_match = _NOTES_RE.search(hk_content)
    if notes_match:
        notes_raw = notes_match.group(1).strip()
        try:
            notes = json.loads(notes_raw)
            if isinstance(notes, list):
                # Update in-memory student model
                if not session.student_model:
                    session.student_model = {"notes": {}}
                model_notes = session.student_model.setdefault("notes", {})
                for entry in notes:
                    concepts = entry.get("concepts", [])
                    primary = concepts[0] if concepts else "_uncategorized"
                    # Support both old format (note) and new format (blooms/observation/implication)
                    blooms = entry.get("blooms")
                    observation = entry.get("observation", entry.get("note", ""))
                    implication = entry.get("implication", "")
                    model_notes[primary] = {
                        "concepts": concepts,
                        "blooms": blooms,
                        "observation": observation,
                        "implication": implication,
                        "note": observation,  # backwards compat
                    }
                slog.debug("Housekeeping notes updated", extra={"count": len(notes)})

                # Build rich note text for DB persistence
                _sm_course_id, _ = _extract_student_info(context_data)
                _sm_email = _extract_user_email(context_data)
                if _sm_course_id and _sm_email:
                    import asyncio as _aio
                    from app.services.knowledge_state import upsert_concept_note

                    async def _upsert_notes():
                        for entry in notes:
                            # Build full note text from structured fields
                            parts = []
                            if entry.get("blooms"):
                                parts.append(f"[Bloom's: {entry['blooms'].upper()}]")
                            obs = entry.get("observation", entry.get("note", ""))
                            if obs:
                                parts.append(obs)
                            imp = entry.get("implication")
                            if imp:
                                parts.append(f"→ {imp}")
                            note_text = " ".join(parts) if parts else ""
                            try:
                                await upsert_concept_note(
                                    _sm_course_id, _sm_email, session_id,
                                    concepts=entry.get("concepts", ["_uncategorized"]),
                                    note_text=note_text,
                                    lesson=entry.get("lesson"),
                                )
                            except Exception as e:
                                slog.warning("Failed to upsert note: %s", e)

                    _aio.ensure_future(_upsert_notes())
        except (json.JSONDecodeError, TypeError) as e:
            slog.warning("Failed to parse housekeeping notes: %s", e)

    # Parse plan modifications
    for pm in _PLAN_MODIFY_RE.finditer(hk_content):
        action = pm.group(1)
        title = pm.group(2) or ""
        concept = pm.group(3) or ""
        reason = pm.group(4) or ""

        if action == "append" and title:
            # Add topic to end of plan
            new_topic = {"title": title, "concept": concept, "steps": [], "status": "pending", "_source": "tutor"}
            session.current_topics.append(new_topic)
            slog.debug("Plan: appended topic", extra={"title": title, "reason": reason})

        elif action == "skip":
            # Skip current topic
            if session.current_topics and 0 <= session.current_topic_index < len(session.current_topics):
                skipped = session.current_topics[session.current_topic_index]
                session.current_topic_index += 1
                slog.debug("Plan: skipped topic", extra={"title": skipped.get("title"), "reason": reason})

        elif action == "insert" and title:
            # Insert topic right after current
            new_topic = {"title": title, "concept": concept, "steps": [], "status": "pending", "_source": "tutor"}
            idx = session.current_topic_index + 1
            session.current_topics.insert(idx, new_topic)
            slog.debug("Plan: inserted topic", extra={"title": title, "at": idx, "reason": reason})

    # Parse handoff tags (assessment or delegation)
    handoff_match = _HANDOFF_RE.search(hk_content)
    if handoff_match:
        handoff_type = handoff_match.group(1)
        if handoff_type == "assessment":
            from app.agents.agent_runtime import AssessmentState
            section_title = handoff_match.group(2) or ""
            concepts = [c.strip() for c in (handoff_match.group(3) or "").split(",") if c.strip()]
            session.assessment = AssessmentState(
                section_title=section_title,
                concepts_tested=concepts,
            )
            session.pre_assessment_note = {
                "section": section_title,
                "concepts": concepts,
            }
            slog.info("Assessment handoff", extra={"event": "ASSESSMENT_START", "preview": section_title})

        elif handoff_type == "delegate":
            from app.agents.agent_runtime import DelegationState
            topic = handoff_match.group(4) or ""
            instructions = handoff_match.group(5) or ""
            session.delegation = DelegationState(
                topic=topic,
                instructions=instructions,
            )
            slog.debug("Handoff: delegation", extra={"topic": topic})

    # Parse spawn tags (background agent requests from tutor)
    for spawn_match in _SPAWN_RE.finditer(hk_content):
        agent_type = spawn_match.group(1) or ""
        task_desc = spawn_match.group(2) or ""
        instructions = spawn_match.group(3) or ""
        if agent_type and task_desc and hasattr(session, 'agent_runtime') and session.agent_runtime:
            session.agent_runtime.spawn(
                agent_type=agent_type,
                description=task_desc[:120],
                instructions=instructions or task_desc,
                context={},  # will be enriched by the runtime
            )
            slog.info("Agent spawned via tag", extra={"type": agent_type, "task": task_desc[:80]})



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
        "active board": "activeBoard",
        "previous boards": "previousBoards",
        "video state": "videoState",
        "teaching plan": "teachingPlan",
        "session context": "sessionContext",
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


def _extract_user_email(context_data: dict) -> str | None:
    profile_str = context_data.get("studentProfile", "")
    if not profile_str:
        return None
    try:
        profile = json.loads(profile_str)
        return profile.get("userEmail")
    except (json.JSONDecodeError, TypeError):
        return None


def _extract_teaching_mode(context_data: dict) -> str:
    """Extract teaching mode from student profile ('text' or 'voice')."""
    profile_str = context_data.get("studentProfile", "")
    if not profile_str:
        return "text"
    try:
        profile = json.loads(profile_str)
        return profile.get("teachingMode", "text")
    except (json.JSONDecodeError, TypeError):
        return "text"


CONTENT_TOOL_NAMES = {"content_map", "content_read", "content_peek", "content_search"}


# ── Session Phase Controller ──────────────────────────────────────────────────

def _should_skip_triage(session, context_data: dict) -> bool:
    """Determine if triage can be skipped.

    Almost never skip. The triage agent itself decides how much probing is needed.
    Only skip on between-chunk transitions where assessment just ran.
    """
    # Skip if triage already completed this session (don't re-triage)
    if session.triage_result:
        return True

    # Skip if session already has a plan (restored from DB or orchestrator-provided)
    if session.current_plan:
        return True

    # Skip if continuing from a recent assessment with decent score
    if session.last_assessment_summary:
        score_pct = session.last_assessment_summary.get("score", {}).get("pct", 0)
        if score_pct >= 60:
            return True

    return False


def _init_session_phase(session, context_data: dict, slog):
    """Set the initial session phase based on intent + student model."""
    if _should_skip_triage(session, context_data):
        session.phase = SessionPhase.TEACHING
        slog.info("Phase: skip triage → TEACHING", extra={"reason": "clear_intent_or_rich_model"})
    else:
        session.phase = SessionPhase.TRIAGE
        slog.info("Phase: starting with TRIAGE", extra={"intent": (session.student_intent or "")[:50]})


def _check_phase_transition(session, agent_output: dict) -> SessionPhase | None:
    """Check if the session should transition to a new phase based on agent signals."""
    phase = session.phase

    if phase == SessionPhase.TRIAGE:
        # Triage runs as tutor prompt overlay — transition happens via complete_triage tool.
        # This branch handles legacy delegation-based triage (if any).
        reason = agent_output.get("reason")
        if reason == "task_complete":
            session.triage_result = agent_output.get("student_performance") or {}
            return SessionPhase.PLANNING

    elif phase == SessionPhase.TEACHING:
        signals = session.last_signals
        # Section complete → assess
        if signals.get("section_progress") == "complete":
            return SessionPhase.ASSESSMENT
        # Tutor flagged student is fundamentally lost
        if signals.get("needs_diagnostic"):
            session.struggle_streak = 0
            return SessionPhase.TRIAGE
        # Student confused multiple turns in a row
        if signals.get("student_state") == "struggling":
            session.struggle_streak += 1
            if session.struggle_streak >= 3:
                session.struggle_streak = 0
                return SessionPhase.TRIAGE
        else:
            session.struggle_streak = 0

    elif phase == SessionPhase.ASSESSMENT:
        score = agent_output.get("score", {}).get("pct", 100)
        if score < 40:
            # Failed badly — triage to find what's missing
            return SessionPhase.TRIAGE
        if score < 70:
            # Partial — reteach, no triage needed (assessment IS the triage)
            return SessionPhase.TEACHING
        # Passed — triage for next chunk (light, may be 0 questions)
        return SessionPhase.TRIAGE

    return None  # Stay in current phase


async def _run_content_tool(tool_name: str, tool_input: dict, context_data: dict, request) -> str:
    """Dispatch a content tool through the ContentProvider adapter."""
    course_id, _ = _extract_student_info(context_data)
    if not course_id:
        return "No course context available."

    from app.services.content_providers import create_adapter
    from app.core.database import get_db

    db_session = request.state.db if hasattr(request.state, "db") else None
    if not db_session:
        db_gen = get_db()
        db_session = await db_gen.__anext__()
    adapter = create_adapter(course_id, db_session)

    if tool_name == "content_map":
        return await adapter.content_map()
    elif tool_name == "content_read":
        return await adapter.content_read(tool_input.get("ref", ""))
    elif tool_name == "content_peek":
        return await adapter.content_peek(tool_input.get("ref", ""))
    elif tool_name == "content_search":
        return await adapter.content_search(
            tool_input.get("query", ""), limit=int(tool_input.get("limit", 5))
        )
    return f"Unknown content tool: {tool_name}"


async def _load_knowledge_context(context_data: dict) -> dict:
    """Load knowledge state + summary in parallel at session start."""
    course_id, student_name = _extract_student_info(context_data)
    if not course_id or not student_name:
        return context_data
    user_email = _extract_user_email(context_data)
    try:
        ks, summary = await asyncio.gather(
            get_or_init_knowledge_state(course_id, student_name),
            get_knowledge_summary(course_id, user_email or student_name),
        )
        context_data["knowledgeState"] = format_knowledge_state(ks)
        if summary:
            context_data["knowledgeSummary"] = summary
    except Exception as e:
        log.warning("Failed to load knowledge context: %s", e)
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


def _serialize_content(content) -> str | list[dict]:
    """Convert LLM ContentBlock objects to JSON-serializable format for MongoDB."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        result = []
        for block in content:
            if hasattr(block, 'to_dict'):
                result.append(block.to_dict())
            elif isinstance(block, dict):
                result.append(block)
            else:
                result.append({"type": "text", "text": str(block)})
        # If all blocks are text, join into a single string (skip empty)
        if all(b.get("type") == "text" for b in result):
            joined = "\n".join(b.get("text", "") for b in result if b.get("text"))
            return joined or "(no text)"
        # Filter out empty text blocks from mixed content
        result = [b for b in result if not (b.get("type") == "text" and not b.get("text", "").strip())]
        return result or [{"type": "text", "text": "(no text)"}]
    return str(content)


# ── Context management — conversation windowing + Haiku summarization ───────

try:
    import tiktoken
    _enc = tiktoken.encoding_for_model("claude-3-haiku-20240307")  # Close enough for Claude tokenizer
except Exception:
    _enc = None

RECENT_MESSAGE_COUNT = 10      # Keep last 10 messages (5 turns) in full
SUMMARY_TRIGGER_INTERVAL = 6   # Run summarization every 6 assistant turns
MESSAGES_TOKEN_BUDGET = 10000  # Hard budget for messages (system prompt ~14k + dynamic ~4k = ~28k total)

_BOARD_DRAW_RE = _re.compile(
    r'<teaching-board-draw(?:-resume)?[^>]*?(?:title="([^"]*)")?[^>]*?>'
    r'([\s\S]*?)</teaching-board-draw(?:-resume)?>',
)
_WIDGET_RE = _re.compile(
    r'<teaching-widget[^>]*?(?:title="([^"]*)")?[^>]*?>'
    r'([\s\S]*?)</teaching-widget>',
)
_SIM_RE = _re.compile(
    r'<teaching-simulation[^>]*?(?:title="([^"]*)")?[^>]*/?>',
)
_VOICE_SCENE_RE = _re.compile(
    r'<teaching-voice-scene[^>]*?(?:title="([^"]*)")?[^>]*?>'
    r'([\s\S]*?)</teaching-voice-scene>',
)

SUMMARY_PROMPT = """\
Summarize this tutoring conversation for continuity. Be structured and concise:
- Topics taught + student's level per topic (L1-L5)
- Student struggles, misconceptions, breakthroughs
- Board-draws: title + what it showed (preserve asset_ids exactly)
- Widgets: title + what student explored
- Simulations used + student observations
- Teaching decisions made + promises to student
- Current trajectory + what comes next

{previous_summary_note}

Conversation:
{conversation}

CRITICAL: Preserve ALL asset_ids (like spot-ref-xxx) exactly. Under 350 words. Bullets only."""


def _count_tokens(text: str) -> int:
    """Count tokens using tiktoken if available, else estimate."""
    if _enc:
        try:
            return len(_enc.encode(text))
        except Exception:
            pass
    return len(text) // 4


def _count_messages_tokens(messages: list[dict]) -> int:
    """Count total tokens across a message array."""
    total = 0
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, str):
            total += _count_tokens(c)
        elif isinstance(c, list):
            for b in c:
                if isinstance(b, dict):
                    if b.get("type") == "text":
                        total += _count_tokens(b.get("text", ""))
                    elif b.get("type") == "image_url":
                        total += 1000  # Images cost ~1k tokens
        total += 4  # Message overhead
    return total


def _compress_voice_scene(match) -> str:
    """Compress a voice scene to a short summary — extract say texts only."""
    title = match.group(1) or "untitled"
    content = match.group(2)
    # Extract all say="..." values
    say_texts = _re.findall(r'say=["\']([^"\']*)["\']', content)
    # Check if it ended with a question
    has_question = 'question="true"' in content or "question='true'" in content
    summary_parts = [f'[voice-scene: "{title}"']
    if say_texts:
        # Keep just the spoken text, concatenated
        spoken = ' '.join(s for s in say_texts if s.strip())
        if len(spoken) > 300:
            spoken = spoken[:297] + '...'
        summary_parts.append(f' — said: "{spoken}"')
    if has_question:
        summary_parts.append(' (asked question)')
    summary_parts.append(']')
    return ''.join(summary_parts)


def _compress_old_messages(messages: list[dict]) -> list[dict]:
    """Strip board-draw JSONL, widget HTML, and sim tags from older messages."""
    compressed = []
    for msg in messages:
        content = msg.get("content", "")
        if not isinstance(content, str):
            compressed.append(msg)
            continue
        # Skip old summary messages entirely (they'll be replaced by current summary)
        if content.startswith("[CONVERSATION SUMMARY"):
            continue
        content = _BOARD_DRAW_RE.sub(lambda m: f'[board-draw: "{m.group(1) or "untitled"}"]', content)
        content = _WIDGET_RE.sub(lambda m: f'[widget: "{m.group(1) or "untitled"}"]', content)
        content = _SIM_RE.sub(lambda m: f'[simulation: "{m.group(1) or ""}"]', content)
        content = _VOICE_SCENE_RE.sub(lambda m: _compress_voice_scene(m), content)
        # Skip empty messages after stripping
        if not content.strip() or content.strip() == '.':
            continue
        compressed.append({"role": msg["role"], "content": content})
    return compressed


async def _maybe_generate_summary(session, messages: list[dict]) -> None:
    """Generate/update conversation summary using Haiku.

    Triggers:
    1. Every SUMMARY_TRIGGER_INTERVAL assistant turns
    2. When message count exceeds RECENT_MESSAGE_COUNT and no summary exists
    3. When total message tokens exceed budget (emergency compression)
    """
    msg_count = len(messages)
    has_enough = msg_count > RECENT_MESSAGE_COUNT
    turn_trigger = (
        session.assistant_turn_count >= SUMMARY_TRIGGER_INTERVAL
        and session.assistant_turn_count % SUMMARY_TRIGGER_INTERVAL == 0
    )
    # Emergency: if total tokens are way over budget, force summary
    total_tokens = _count_messages_tokens(messages)
    emergency = total_tokens > MESSAGES_TOKEN_BUDGET * 2 and not session.conversation_summary

    if not has_enough:
        return
    if not turn_trigger and not emergency:
        return

    old_count = msg_count - RECENT_MESSAGE_COUNT
    # Skip if summary already covers these messages
    if session.summary_covers_through >= old_count - 2 and not emergency:
        return

    old_messages = messages[:old_count]

    # Build conversation text for Haiku (compact, board-draw content stripped)
    conv_parts = []
    for msg in old_messages:
        role = "Tutor" if msg["role"] == "assistant" else "Student"
        content = msg.get("content", "")
        if isinstance(content, str):
            content = _BOARD_DRAW_RE.sub(lambda m: f'[board-draw: "{m.group(1) or "?"}"]', content)
            content = _WIDGET_RE.sub(lambda m: f'[widget: "{m.group(1) or "?"}"]', content)
            if content.startswith("[CONVERSATION SUMMARY"):
                continue
            conv_parts.append(f"{role}: {content[:250]}")
        elif isinstance(content, list):
            text = " ".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
            if text:
                conv_parts.append(f"{role}: {text[:250]}")

    # Cap to last 30 exchanges to keep Haiku input small
    conversation_text = "\n".join(conv_parts[-30:])

    prev_note = ""
    if session.conversation_summary:
        prev_note = (
            "A PREVIOUS SUMMARY exists — build on it, don't duplicate:\n"
            f"{session.conversation_summary}\n\n"
            "Summarize ONLY the NEW messages below:"
        )

    prompt = SUMMARY_PROMPT.format(
        previous_summary_note=prev_note,
        conversation=conversation_text,
    )

    try:
        from app.core.llm import llm_call
        response = await llm_call(
            model=settings.summarization_model,
            system="You are a concise tutoring session summarizer.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        new_summary = response.content[0].text.strip()

        # Track internal LLM cost on the session
        if response.usage:
            session.track_llm_usage(
                settings.summarization_model,
                response.usage.input_tokens,
                response.usage.output_tokens,
            )

        if session.conversation_summary:
            # Merge: keep old summary + append new
            combined = session.conversation_summary.rstrip() + "\n\n" + new_summary
            # Hard cap at 2500 chars (~600 tokens)
            if len(combined) > 2500:
                combined = combined[-2500:]
            session.conversation_summary = combined
        else:
            session.conversation_summary = new_summary

        session.summary_covers_through = old_count
        log.info("Summary generated", extra={"msg_count": old_count})
    except Exception as e:
        log.warning("Summary generation failed: %s", e)


def _has_multimodal(msg: dict) -> bool:
    """Check if a message contains multimodal content (images, files, audio, video)."""
    content = msg.get("content")
    if not isinstance(content, list):
        return False
    return any(
        isinstance(b, dict) and b.get("type") in ("image", "image_url", "file", "input_audio", "video_url")
        for b in content
    )


def apply_context_window(session, messages: list[dict]) -> list[dict]:
    """Apply conversation windowing to fit within token budget.

    Strategy:
    0. Always preserve the first message if it has multimodal content (attachments)
    1. Keep last RECENT_MESSAGE_COUNT messages in full (board-draw content intact)
    2. Prepend conversation summary (replaces oldest messages)
    3. Between summary and recent: compressed messages (JSONL stripped) that fit budget
    4. Hard enforce MESSAGES_TOKEN_BUDGET
    """
    if len(messages) <= RECENT_MESSAGE_COUNT:
        return messages

    # Find the split point — but never split a tool_use/tool_result pair.
    # If the first "recent" message is a user message with tool_results,
    # pull the preceding assistant message into recent too.
    split = len(messages) - RECENT_MESSAGE_COUNT
    if split > 0 and split < len(messages):
        first_recent = messages[split]
        if (first_recent.get("role") == "user"
            and isinstance(first_recent.get("content"), list)
            and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in first_recent["content"])):
            split = max(0, split - 1)  # pull preceding assistant msg into recent
    recent = messages[split:]
    old = messages[:split]

    # Preserve first message if it has attachments (images/PDFs/audio/video)
    pinned_first = None
    if old and _has_multimodal(old[0]):
        pinned_first = old[0]
        old = old[1:]
    recent_tokens = _count_messages_tokens(recent)
    pinned_tokens = _count_messages_tokens([pinned_first]) if pinned_first else 0

    result = []

    # 1. Summary message
    if session.conversation_summary:
        covered = session.summary_covers_through
        summary_msg = {
            "role": "user",
            "content": (
                f"[CONVERSATION SUMMARY — {covered} earlier messages condensed]\n"
                f"{session.conversation_summary}\n"
                f"[END SUMMARY — recent conversation follows]"
            ),
        }
        result.append(summary_msg)
        # Drop messages covered by summary
        uncovered_old = old[covered:] if covered < len(old) else []
    else:
        uncovered_old = old

    # 2. Compress uncovered old messages
    if uncovered_old:
        compressed = _compress_old_messages(uncovered_old)
        summary_tokens = _count_messages_tokens(result)
        available = MESSAGES_TOKEN_BUDGET - recent_tokens - summary_tokens - pinned_tokens

        if available > 500:
            # Fit as many compressed messages as budget allows (newest first)
            fitted = []
            used = 0
            for msg in reversed(compressed):
                t = _count_messages_tokens([msg])
                if used + t > available:
                    break
                fitted.insert(0, msg)
                used += t
            result.extend(fitted)

    # 3. Recent messages in full
    result.extend(recent)

    # 4. Pin first message with attachments at the front (always visible to LLM)
    if pinned_first:
        result.insert(0, pinned_first)

    final_tokens = _count_messages_tokens(result)
    log.info(
        "Context window applied",
        extra={
            "msg_count": len(result),
            "token_count": final_tokens,
            "pinned_attachments": bool(pinned_first),
        },
    )

    return result


# ── Fast start: auto-spawn planner ─────────────────────────────────────────

def _extract_orchestrator_plan(context_data: dict) -> dict | None:
    """Extract a pre-built plan from the orchestrator's session context.

    The orchestrator can pass a plan via start_tutor_session(plan=[...]).
    If present, we convert it to the planner's output format and use it
    directly — skipping the background planner entirely (0ms latency).
    """
    # Check sessionContext for plan from orchestrator
    session_ctx_str = context_data.get("sessionContext", "")
    if not session_ctx_str:
        return None

    try:
        ctx = json.loads(session_ctx_str) if isinstance(session_ctx_str, str) else session_ctx_str
        plan_steps = ctx.get("plan", [])
        if not plan_steps or not isinstance(plan_steps, list):
            return None

        # Convert orchestrator's plan format to planner's output format
        topics = []
        for i, step in enumerate(plan_steps):
            topics.append({
                "title": step.get("title", f"Topic {i + 1}"),
                "type": step.get("type", "concept"),
                "content_refs": step.get("content_refs", []),
                "teaching_notes": step.get("teaching_notes", ""),
                "status": "pending",
            })

        return {
            "session_objective": ctx.get("enriched_intent", ""),
            "_topics": topics,
            "_source": "orchestrator",
        }
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None


def _auto_spawn_planner_if_ready(session, runtime, context_data: dict, slog) -> None:
    """Auto-spawn planning agent when tutor has enough context (~turn 4+).

    Triggers when: turn_count >= 4 AND student_model has >= 2 concept observations.
    The planner gets FULL context: conversation history, student model, course map,
    and grounding tools (content_read, web_search, etc.) to build a rich plan.

    Uses Sonnet for high-quality, tool-grounded plans.
    """
    # Guard: don't spawn if plan already exists or planner already running
    if session.current_plan:
        return
    if getattr(session, '_planner_spawned', False):
        return

    # Check readiness: enough turns AND enough student observations
    turn_count = session.assistant_turn_count
    student_notes = (session.student_model or {}).get("notes", {})
    note_count = len(student_notes)

    if turn_count < 4 or note_count < 2:
        return

    try:
        intent = session.student_intent or "general study session"

        # Build rich conversation summary from recent messages
        recent_msgs = (session.messages or [])[-12:]  # last 12 messages
        conversation_summary = []
        for msg in recent_msgs:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
            if content and role in ("user", "assistant"):
                # Truncate long messages but keep enough for context
                content_short = content[:500] + ("..." if len(content) > 500 else "")
                conversation_summary.append(f"[{role}]: {content_short}")
        conversation_text = "\n".join(conversation_summary)

        # Build student model summary
        student_model_text = ""
        if session.student_model:
            student_model_text = json.dumps(session.student_model, indent=2, default=str)[:2000]

        # Completed topics
        completed_text = ""
        if session.completed_topics:
            completed_text = ", ".join(
                t if isinstance(t, str) else t.get("title", "")
                for t in session.completed_topics
            )

        # Triage results
        triage_text = ""
        if session.triage_result:
            triage_text = json.dumps(session.triage_result, indent=2, default=str)[:1000]

        # BYO context
        byo_text = ""
        session_ctx_str = context_data.get("sessionContext", "")
        if session_ctx_str:
            try:
                ctx = json.loads(session_ctx_str) if isinstance(session_ctx_str, str) else session_ctx_str
                if ctx.get("collection_id"):
                    byo_text = f"Student uploaded content (collection: {ctx['collection_id']}). Use byo_read/byo_list to access."
                if ctx.get("enriched_intent"):
                    byo_text += f"\nEnriched intent: {ctx['enriched_intent'][:300]}"
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        has_course = bool(context_data.get("courseMap"))
        course_instruction = (
            "Use content_read/content_peek to inspect relevant course sections and ground your plan in the professor's material."
            if has_course else
            "No structured course available. Use web_search to find authoritative resources and plan from your knowledge."
        )

        plan_instructions = f"""Plan a focused teaching session for this student.

[STUDENT INTENT]
{intent}

[CONVERSATION SO FAR — {turn_count} turns]
{conversation_text}

[STUDENT MODEL — tutor's observations]
{student_model_text or "No observations yet."}

[COMPLETED TOPICS]
{completed_text or "None yet."}

{f"[TRIAGE DIAGNOSTIC]{chr(10)}{triage_text}" if triage_text else ""}
{f"[BYO CONTENT]{chr(10)}{byo_text}" if byo_text else ""}

[INSTRUCTIONS]
{course_instruction}
Based on what the tutor has taught so far and how the student is doing, plan the NEXT section of teaching.
Include pre-fetched content summaries for each topic so the tutor can teach without fetching.
Output a single JSON object (not JSONL).
"""

        runtime.spawn(
            agent_type="planning",
            description=f"Plan session: {intent[:60]}",
            instructions=plan_instructions,
            context={**context_data},
        )
        session._planner_spawned = True
        slog.info("Auto-spawned planner at turn %d (%d student observations)",
                   turn_count, note_count, extra={"intent": intent[:80]})
    except Exception as e:
        slog.warning("Failed to auto-spawn planner: %s", e)


def _auto_spawn_enrichment(session, runtime, context_data: dict, slog):
    """Auto-spawn shadow enrichment agent on turn 1.

    Runs in background with Haiku + tools (web_search, content_search,
    get_section_content, query_knowledge). Results injected on turn 2+.
    """
    _spawn_enrichment_agent(session, runtime, context_data, slog, is_initial=True)


def _spawn_enrichment_agent(session, runtime, context_data: dict, slog, is_initial=False):
    """Spawn the shadow enrichment agent with recent conversation context.

    Called on turn 1 (initial) and every ~5 turns (periodic).
    The agent uses Haiku with tools to pre-fetch resources the tutor might need.
    """
    if not runtime:
        return

    intent = session.student_intent or ""
    current_topic = None
    if session.current_topics and 0 <= session.current_topic_index < len(session.current_topics):
        current_topic = session.current_topics[session.current_topic_index]

    topic_title = current_topic.get("title", "") if current_topic else intent

    # Build enrichment request with conversation context
    parts = []
    parts.append(f"[Student Intent] {intent}")

    if current_topic:
        parts.append(f"[Current Topic] {json.dumps(current_topic, indent=2)}")

    if session.current_plan:
        # Include plan summary (not full plan — keep it concise)
        plan_topics = [t.get("title", "?") for t in (session.current_topics or [])[:10]]
        parts.append(f"[Plan Topics] {', '.join(plan_topics)}")
        parts.append(f"[Progress] Topic {session.current_topic_index + 1} of {len(session.current_topics or [])}")

    # Recent conversation (last 3 turns)
    recent = session.messages[-6:] if session.messages else []
    if recent:
        conv_parts = []
        for m in recent:
            role = m.get("role", "?")
            content = m.get("content", "")
            if isinstance(content, str):
                conv_parts.append(f"{role}: {content[:300]}")
            elif isinstance(content, list):
                text_blocks = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                conv_parts.append(f"{role}: {' '.join(text_blocks)[:300]}")
        parts.append(f"[Recent Conversation]\n" + "\n".join(conv_parts))

    instructions = "\n\n".join(parts)

    if is_initial:
        instructions += (
            "\n\nThis is the START of the session. Focus on:\n"
            f"1. Fetch course content for '{topic_title}' (use content_search + get_section_content)\n"
            "2. Web search for supplementary examples/references\n"
            "3. Check student's knowledge gaps (use query_knowledge)\n"
            "Call tools IN PARALLEL for speed."
        )
    else:
        instructions += (
            "\n\nThis is a PERIODIC enrichment check. Focus on:\n"
            "1. Any topics the student asked about that need external references\n"
            "2. Upcoming topics from the plan that need content pre-fetch\n"
            "3. Gaps or misconceptions that need supplementary explanation\n"
            "Call tools IN PARALLEL. Be fast."
        )

    try:
        runtime.spawn(
            "enrichment",
            f"Enrichment: {topic_title[:50]}",
            instructions,
            context_data,
        )
        slog.info("Spawned enrichment agent", extra={"topic": topic_title[:60], "initial": is_initial})
    except Exception as e:
        slog.warning("Failed to spawn enrichment agent: %s", e)


# ── Plan promotion helpers ──────────────────────────────────────────────────

def _promote_plan(session, plan_data: dict) -> None:
    """Promote a completed planning agent result into session state."""
    session.current_plan = plan_data

    # Set session scope on first plan
    if not session.session_objective:
        session.session_objective = plan_data.get("session_objective", "")
        session.scope_concepts = plan_data.get("learning_outcomes", [])
        session.session_scope = plan_data.get("scope", "")

    # Extract topics from the plan
    topics = plan_data.get("_topics", [])
    if topics:
        session.current_topics = topics
        session.current_topic_index = 0
        log.info("Plan promoted", extra={"agent": "planning"})
    else:
        # If topics are inline in sections, extract them
        for sec in plan_data.get("sections", []):
            for topic_outline in sec.get("topics", []):
                session.current_topics.append(topic_outline)
        if session.current_topics and session.current_topic_index < 0:
            session.current_topic_index = 0
        log.info("Plan promoted (inline topics)", extra={"agent": "planning"})

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


def _build_plan_accountability(session) -> dict | None:
    """Build plan accountability context for tutor prompt injection."""
    if not session.current_topics or session.current_topic_index < 0:
        return None

    plan = session.current_plan or {}
    sections = plan.get("sections", [{}])
    # Find active section
    section_title = sections[0].get("title", "Current Section") if sections else "Current Section"
    section_n = 1
    section_total = len(sections) if sections else 1

    topic_total = len(session.current_topics)
    topic_n = session.current_topic_index + 1
    current = (
        session.current_topics[session.current_topic_index]
        if 0 <= session.current_topic_index < topic_total
        else {}
    )

    done_count = len(session.completed_topics)
    total_count = done_count + topic_total

    result = {
        "section_title": section_title,
        "section_n": section_n,
        "section_total": section_total,
        "topic_title": current.get("title", "?"),
        "topic_n": topic_n,
        "topic_total": topic_total,
        "done_count": done_count,
        "total_count": total_count,
        "detour_active": bool(session.detour_stack),
    }

    if session.detour_stack:
        saved = session.detour_stack[-1]
        result["detour_reason"] = saved.get("reason", "prerequisite gap")
        saved_topics = saved.get("saved_topics", [])
        saved_idx = saved.get("saved_topic_index", 0)
        if 0 <= saved_idx < len(saved_topics):
            result["return_topic"] = saved_topics[saved_idx].get("title", "previous topic")

    return result


def _build_checkpoint_and_pace(session) -> str | None:
    """Build checkpoint injection and pace nudges for the tutor context.

    - CHECKPOINT: when all topics in current section are done → forces assessment
    - PACE CHECK: when tutor has been on same topic for 5+ turns → soft nudge
    Returns a string to inject into the dynamic context, or None.
    """
    parts = []

    # ── Checkpoint: all section topics done → require assessment ──
    if session.current_topics and session.current_topic_index >= len(session.current_topics):
        # All topics exhausted — section is complete
        section_title = "Current Section"
        if session.current_plan and session.current_plan.get("sections"):
            section_title = session.current_plan["sections"][0].get("title", section_title)
        completed_concepts = [
            t.get("concept", t.get("title", ""))
            for t in session.current_topics if isinstance(t, dict)
        ]
        if not session.assessment:  # Don't double-inject if assessment already pending
            parts.append(
                f"[CHECKPOINT] Section \"{section_title}\" complete ({len(session.current_topics)}/{len(session.current_topics)} topics done).\n"
                f"You MUST include <handoff type=\"assessment\" section=\"{section_title}\" "
                f"concepts=\"{','.join(c for c in completed_concepts if c)}\" /> in your <teaching-housekeeping> tag.\n"
                "Do not teach new content until assessment runs."
            )

    # ── Pace check: same topic for too long ──
    if hasattr(session, '_topic_dwell_turns'):
        dwell = session._topic_dwell_turns
        if dwell >= 12:
            parts.append(
                f"[PACE CHECK] You've been on the current topic for {dwell} turns.\n"
                "This is significantly longer than planned. Consider:\n"
                "- If the student is progressing → wrap up and <signal progress=\"complete\" />\n"
                "- If stuck → <plan-modify action=\"insert\" title=\"prerequisite topic\" />\n"
                "- If the student is genuinely engaged and going deep → continue, but be mindful."
            )
        elif dwell >= 8:
            parts.append(
                f"[PACE CHECK] You've been on the current topic for {dwell} turns.\n"
                "Consider: is the student progressing, or stuck?\n"
                "If stuck → insert a prerequisite. If they understand → advance."
            )
        elif dwell >= 5:
            parts.append(
                f"[PACE CHECK] Topic dwell: {dwell} turns. This is informational.\n"
                "Continue if the student is making progress."
            )

    return "\n\n".join(parts) if parts else None


def _track_topic_dwell(session):
    """Track how many turns the tutor has spent on the current topic."""
    if not hasattr(session, '_topic_dwell_turns'):
        session._topic_dwell_turns = 0
        session._last_topic_index = getattr(session, 'current_topic_index', -1)

    current_idx = getattr(session, 'current_topic_index', -1)
    if current_idx != session._last_topic_index:
        # Topic changed — reset dwell counter
        session._topic_dwell_turns = 0
        session._last_topic_index = current_idx
    else:
        session._topic_dwell_turns += 1


def _build_assessment_summary(ar: dict) -> dict:
    """Build a persistent assessment summary that survives across turns.

    Unlike assessment_result (consumed on first post-assessment turn),
    this persists until the next assessment, so tutor and planning agent
    always know the most recent assessment outcome.
    """
    score = ar.get("score", {})
    weak_concepts = [
        pc.get("concept", "?")
        for pc in ar.get("perConcept", [])
        if pc.get("mastery") in ("weak", "not_demonstrated", "needs_work")
        or pc.get("correct", 1) == 0
    ]
    strong_concepts = [
        pc.get("concept", "?")
        for pc in ar.get("perConcept", [])
        if pc.get("mastery") in ("strong", "mastered")
        or (pc.get("correct", 0) == pc.get("total", 1) and pc.get("total", 0) > 0)
    ]
    return {
        "section": ar.get("section", ""),
        "type": ar.get("type", "complete"),
        "score": score,
        "overallMastery": ar.get("overallMastery", "unknown"),
        "weakConcepts": weak_concepts,
        "strongConcepts": strong_concepts,
        "recommendation": ar.get("recommendation", ""),
        "conceptsTested": ar.get("concepts", []),
    }


def _format_pre_assessment_note(note: dict | None) -> str | None:
    """Format pre-assessment marker for injection into tutor prompt.

    Includes assessment results when available so the tutor always knows
    what happened in the checkpoint, even on subsequent turns.
    """
    if not note:
        return None
    lines = []
    if note.get("sectionTitle"):
        lines.append(f"Section assessed: {note['sectionTitle']}")
    if note.get("currentTopicTitle"):
        lines.append(f"Topic at time of checkpoint: {note['currentTopicTitle']}")
    if note.get("conceptsTested"):
        lines.append(f"Concepts tested: {', '.join(note['conceptsTested'])}")
    # Enriched fields (added when assessment results arrive)
    score = note.get("assessmentScore")
    if score:
        pct = score.get("pct", 0)
        lines.append(f"Assessment score: {score.get('correct', 0)}/{score.get('total', 0)} ({pct}%)")
        lines.append(f"Overall mastery: {note.get('overallMastery', '?')}")
    weak = note.get("weakConcepts")
    if weak:
        lines.append(f"WEAK concepts (need re-teaching): {', '.join(weak)}")
    rec = note.get("recommendation")
    if rec:
        lines.append(f"Assessment recommendation: {rec}")
    return "\n".join(lines) if lines else None


def _format_session_scope(session) -> str | None:
    """Format session scope for injection into tutor/planning prompts."""
    if not session.session_objective:
        return None

    parts = [f"Session Objective: {session.session_objective}"]
    if session.session_scope:
        parts.append(f"Scope: {session.session_scope}")
    if session.scope_concepts:
        parts.append(f"Learning Outcomes: {', '.join(session.scope_concepts)}")

    total = len(session.current_topics) if session.current_topics else 0
    done = len(session.completed_topics) if session.completed_topics else 0
    parts.append(f"Progress: {done} of {total} topics complete")

    if session.completed_topics:
        completed_summary = "; ".join(
            t.get("title", "?") for t in session.completed_topics
        )
        parts.append(f"Completed: {completed_summary}")

    return "\n".join(parts)


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
        "studentModel": json.dumps(session.student_model, indent=2) if session.student_model else None,
        "teachingPlan": json.dumps(session.current_plan, indent=2) if session.current_plan else None,
        "currentTopic": current_topic,
        "completedTopics": _format_completed(session.completed_topics),
        "scenarioSkill": scenario_skill,
        "planAccountability": _build_plan_accountability(session),
        "checkpointAndPace": _build_checkpoint_and_pace(session),
        "teachingMode": session.teaching_mode,
    })


# ── Delegation handler ──────────────────────────────────────────────────────

async def _handle_delegated_teaching(session, session_id, claude_messages, context_data, request, slog=None):
    """Handle a turn during active teaching delegation."""
    from app.core.config import settings

    if slog is None:
        slog = SessionLogger(log, session_id=session_id)

    delegation = session.delegation
    delegation.turns_used += 1

    # Hard turn limit
    if delegation.turns_used > delegation.max_turns:
        slog.info("Delegation turn limit reached", extra={"agent": "delegation", "round": delegation.turns_used})
        session.delegation_result = {
            "reason": "max_turns",
            "summary": f"Sub-agent reached {delegation.max_turns}-turn limit.",
            "turns_used": delegation.turns_used,
        }
        session.delegation = None
        yield _sse({"type": "TEACHING_DELEGATION_END", "reason": "max_turns"})
        yield _sse({"type": "RUN_FINISHED"})
        return

    # Build sub-agent tools: use delegation-specific tools if set, else defaults
    sub_tools = (delegation.tools or DELEGATION_TOOLS) + [RETURN_TO_TUTOR_TOOL]

    rounds = 0
    while rounds < MAX_ROUNDS:
        rounds += 1
        slog.info("Delegation round", extra={"agent": "delegation", "round": rounds})

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
                async with await llm_stream(
                    model=settings.tutor_model,
                    max_tokens=4096,
                    system=delegation.system_prompt,
                    messages=valid_messages,
                    tools=sub_tools,
                    metadata=LLMCallMetadata(session_id=session_id, caller="delegation"),
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
                # Cost tracked by centralized callback — emit SSE update
                yield _sse({
                    "type": "COST_UPDATE",
                    "costCents": round(session.llm_cost_cents, 2),
                    "callCount": session.llm_call_count,
                })
                break  # Success
            except Exception as e:
                if is_retryable(e) and attempt < MAX_RETRIES - 1:
                    delay = extract_retry_after(e) or RETRY_BASE_DELAY * (2 ** attempt)
                    slog.warning("Delegation API retry %d/%d after %.1fs: %s", attempt + 1, MAX_RETRIES, delay, e, extra={"agent": "delegation"})
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
                slog.info("Delegation tool call", extra={"agent": "delegation", "tool": block.name})
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
                    slog.info("Delegation ended", extra={"agent": "delegation", "round": session.delegation_result["turns_used"]})

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Control returned to Tutor.",
                    })
                    yield _sse({"type": "TOOL_CALL_END", "toolCallId": block.id})
                    yield _sse({"type": "TEACHING_DELEGATION_END", "reason": session.delegation_result["reason"]})

                    # ── Phase transition after delegation ──
                    new_phase = _check_phase_transition(session, session.delegation_result)
                    if new_phase:
                        old_phase = session.phase
                        session.phase = new_phase
                        slog.info("Phase transition", extra={"from": old_phase, "to": new_phase})

                        # TRIAGE → PLANNING: spawn planner with triage diagnostic
                        if old_phase == SessionPhase.TRIAGE and new_phase == SessionPhase.PLANNING:
                            session.phase = SessionPhase.TEACHING  # Move to teaching immediately
                            # Planner will auto-spawn when tutor has enough context (turn ~4)
                            slog.info("Triage complete — planner will auto-spawn when ready")

                    # Sync session state after delegation ends
                    try:
                        await sync_backend_state(session_id, session)
                    except Exception as e:
                        slog.warning("Failed to sync session state after delegation: %s", e)

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
                elif block.name in CONTENT_TOOL_NAMES:
                    try:
                        result = await _run_content_tool(block.name, block.input, context_data, request)
                    except Exception as e:
                        slog.error("Content adapter failed (delegation): %s", e, exc_info=True, extra={"tool": block.name})
                        result = f"Content tool error: {str(e)[:200]}"
                    result_str = result if isinstance(result, str) else json.dumps(result)
                    if not result_str.strip():
                        result_str = "(no output)"
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_str})
                else:
                    try:
                        result = await execute_tutor_tool(block.name, block.input)
                    except Exception as e:
                        slog.error("Delegation tool failed: %s", e, exc_info=True, extra={"agent": "delegation", "tool": block.name})
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

            claude_messages.append({"role": "assistant", "content": _serialize_content(message.content)})
            claude_messages.append({"role": "user", "content": _serialize_content(tool_results)})
            continue

        # No more tool calls — done
        yield _sse({"type": "RUN_FINISHED"})
        return

    yield _sse({"type": "RUN_ERROR", "message": "Too many delegation rounds"})


# ── Assessment handler ────────────────────────────────────────────────────────

async def _handle_assessment(session, session_id, claude_messages, context_data, request, slog=None):
    """Handle a turn during active assessment checkpoint.

    The assessment agent has its own system prompt, tools, and persona.
    Uses its own message history (assessment.messages) separate from the tutor's.
    The student's latest message is copied in, but assessment Q&A stays isolated.
    """
    from app.core.config import settings

    if slog is None:
        slog = SessionLogger(log, session_id=session_id)

    assessment = session.assessment
    assessment.turns_used += 1

    # Copy the student's latest message into assessment's own history
    # (assessment keeps its own message list, separate from tutor)
    if claude_messages:
        latest = claude_messages[-1]
        if latest.get("role") == "user":
            assessment.messages.append(latest)

    # Hard turn limit
    if assessment.turns_used > assessment.max_turns:
        slog.info("Assessment turn limit reached", extra={"agent": "assessment", "round": assessment.turns_used})
        session.assessment_result = {
            "type": "handback",
            "reason": "max_turns",
            "questionsCompleted": assessment.questions_asked,
            "score": {"correct": 0, "total": assessment.questions_asked},
            "stuckOn": "Assessment reached maximum turn limit.",
            "recommendation": "Resume teaching — assessment was unable to complete in time.",
            "section": assessment.section_title,
            "concepts": assessment.concepts_tested,
        }
        session.assessment = None
        yield _sse({
            "type": "ASSESSMENT_END",
            "reason": "max_turns",
            "score": session.assessment_result.get("score"),
            "section": session.assessment_result.get("section", ""),
            "concepts": session.assessment_result.get("concepts", []),
            "recommendation": session.assessment_result.get("recommendation", ""),
        })
        yield _sse({"type": "RUN_FINISHED"})
        return

    rounds = 0
    while rounds < MAX_ROUNDS:
        rounds += 1
        slog.info("Assessment round", extra={"agent": "assessment", "round": rounds})

        if await request.is_disconnected():
            return

        text_started = False
        message_id = None

        valid_messages = _validate_messages(assessment.messages)

        # Retry loop
        message = None
        for attempt in range(MAX_RETRIES):
            try:
                async with await llm_stream(
                    model=settings.tutor_model,
                    max_tokens=4096,
                    system=assessment.system_prompt,
                    messages=valid_messages,
                    tools=assessment.tools,
                    metadata=LLMCallMetadata(session_id=session_id, caller="assessment"),
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
                # Cost tracked by centralized callback — emit SSE update
                yield _sse({
                    "type": "COST_UPDATE",
                    "costCents": round(session.llm_cost_cents, 2),
                    "callCount": session.llm_call_count,
                })
                break
            except Exception as e:
                if is_retryable(e) and attempt < MAX_RETRIES - 1:
                    delay = extract_retry_after(e) or RETRY_BASE_DELAY * (2 ** attempt)
                    slog.warning("Assessment API retry %d/%d after %.1fs: %s", attempt + 1, MAX_RETRIES, delay, e, extra={"agent": "assessment"})
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
                slog.info("Assessment tool call", extra={"agent": "assessment", "tool": block.name})
                yield _sse({"type": "TOOL_CALL_START", "toolCallId": block.id, "toolCallName": block.name})

                # ── complete_assessment ─────────────────────────
                if block.name == "complete_assessment":
                    result_data = {
                        "type": "complete",
                        "score": block.input.get("score", {}),
                        "perConcept": block.input.get("perConcept", []),
                        "updatedNotes": block.input.get("updatedNotes", {}),
                        "studentQuestions": block.input.get("studentQuestions", []),
                        "recommendation": block.input.get("recommendation", ""),
                        "overallMastery": block.input.get("overallMastery", "developing"),
                        "section": assessment.section_title,
                        "concepts": assessment.concepts_tested,
                    }
                    session.assessment_result = result_data
                    session.assessment = None

                    slog.info("Assessment complete", extra={"agent": "assessment"})

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Assessment recorded. Control returned to Tutor.",
                    })
                    yield _sse({"type": "TOOL_CALL_END", "toolCallId": block.id})

                    # Emit assessment end SSE for frontend UI
                    yield _sse({
                        "type": "ASSESSMENT_END",
                        "reason": "complete",
                        "score": result_data["score"],
                        "overallMastery": result_data["overallMastery"],
                        "perConcept": result_data.get("perConcept", []),
                        "section": result_data.get("section", ""),
                        "recommendation": result_data.get("recommendation", ""),
                    })

                    # Phase transition after assessment
                    new_phase = _check_phase_transition(session, result_data)
                    if new_phase:
                        old_phase = session.phase
                        session.phase = new_phase
                        slog.info("Phase transition after assessment", extra={
                            "from": old_phase, "to": new_phase,
                            "score_pct": result_data.get("score", {}).get("pct", 0),
                        })

                    # Sync session state
                    try:
                        from app.services.session_service import sync_backend_state
                        await sync_backend_state(session_id, session)
                    except Exception as e:
                        slog.warning("Failed to sync session after assessment: %s", e)

                    yield _sse({"type": "RUN_FINISHED"})
                    return

                # ── handback_to_tutor ──────────────────────────
                elif block.name == "handback_to_tutor":
                    result_data = {
                        "type": "handback",
                        "reason": block.input.get("reason", "student_struggling"),
                        "questionsCompleted": block.input.get("questionsCompleted", 0),
                        "score": block.input.get("score", {}),
                        "stuckOn": block.input.get("stuckOn", ""),
                        "studentQuestions": block.input.get("studentQuestions", []),
                        "studentState": block.input.get("studentState", ""),
                        "updatedNotes": block.input.get("updatedNotes", {}),
                        "recommendation": block.input.get("recommendation", ""),
                        "section": assessment.section_title,
                        "concepts": assessment.concepts_tested,
                    }
                    session.assessment_result = result_data
                    session.assessment = None

                    slog.info("Assessment handback", extra={"agent": "assessment"})

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Assessment ended. Control returned to Tutor.",
                    })
                    yield _sse({"type": "TOOL_CALL_END", "toolCallId": block.id})

                    yield _sse({
                        "type": "ASSESSMENT_END",
                        "reason": result_data["reason"],
                        "score": result_data.get("score"),
                        "stuckOn": result_data.get("stuckOn"),
                        "section": result_data.get("section", ""),
                        "concepts": result_data.get("concepts", []),
                        "recommendation": result_data.get("recommendation", ""),
                    })

                    # Handback = student struggling → go to triage
                    session.phase = SessionPhase.TRIAGE
                    slog.info("Phase → TRIAGE after assessment handback")

                    try:
                        from app.services.session_service import sync_backend_state
                        await sync_backend_state(session_id, session)
                    except Exception as e:
                        slog.warning("Failed to sync session after assessment handback: %s", e)

                    yield _sse({"type": "RUN_FINISHED"})
                    return

                # ── update_student_model (assessment can update notes) ──
                elif block.name == "update_student_model":
                    notes = block.input.get("notes", [])
                    if isinstance(notes, str):
                        try:
                            notes = json.loads(notes)
                        except (json.JSONDecodeError, TypeError):
                            notes = [{"concepts": ["_assessment"], "note": notes}]

                    if not session.student_model:
                        session.student_model = {"notes": {}}
                    model_notes = session.student_model.setdefault("notes", {})
                    for entry in notes:
                        concepts = entry.get("concepts", [])
                        primary = concepts[0] if concepts else "_uncategorized"
                        model_notes[primary] = {
                            "concepts": concepts,
                            "note": entry.get("note", ""),
                        }

                    slog.info("Assessment updated student model", extra={"agent": "assessment", "tool": "update_student_model"})

                    # Persist
                    _sm_course_id, _ = _extract_student_info(context_data)
                    _sm_email = _extract_user_email(context_data)
                    if _sm_course_id and _sm_email:
                        from app.services.knowledge_state import upsert_concept_note
                        for entry in notes:
                            try:
                                await upsert_concept_note(
                                    _sm_course_id, _sm_email, session_id,
                                    concepts=entry.get("concepts", ["_uncategorized"]),
                                    note_text=entry.get("note", ""),
                                    lesson=entry.get("lesson"),
                                )
                            except Exception as e:
                                slog.warning("Failed to upsert assessment note: %s", e)

                    result = "Student model updated with assessment observations."
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})

                # ── query_knowledge ─────────────────────────────
                elif block.name == "query_knowledge":
                    course_id, _ = _extract_student_info(context_data)
                    user_email = _extract_user_email(context_data)
                    if course_id and user_email:
                        try:
                            result = await hybrid_search_notes(course_id, user_email, block.input["query"])
                        except Exception as e:
                            result = f"Failed to query knowledge: {str(e)[:200]}"
                    else:
                        result = "Cannot query knowledge: missing student info"
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})

                # ── Content provider tools ─────────────────────
                elif block.name in CONTENT_TOOL_NAMES:
                    try:
                        result = await _run_content_tool(block.name, block.input, context_data, request)
                    except Exception as e:
                        slog.error("Content adapter failed (assessment): %s", e, exc_info=True, extra={"tool": block.name})
                        result = f"Content tool error: {str(e)[:200]}"
                    result_str = result if isinstance(result, str) else json.dumps(result)
                    if not result_str.strip():
                        result_str = "(no output)"
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_str})

                # ── Normal content tools ────────────────────────
                else:
                    try:
                        result = await execute_tutor_tool(block.name, block.input)
                    except Exception as e:
                        slog.error("Assessment tool failed: %s", e, exc_info=True, extra={"agent": "assessment", "tool": block.name})
                        result = f"Tool error ({block.name}): {str(e)[:200]}"
                    result_str = result if isinstance(result, str) else json.dumps(result)
                    if not result_str.strip():
                        result_str = "(no output)"
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_str})

                yield _sse({"type": "TOOL_CALL_END", "toolCallId": block.id})

            assessment.messages.append({"role": "assistant", "content": message.content})
            assessment.messages.append({"role": "user", "content": tool_results})
            continue

        # No more tool calls — text response to student
        # Append the assistant response to assessment's own history
        assessment.messages.append({"role": "assistant", "content": message.content})
        yield _sse({"type": "RUN_FINISHED"})
        return

    yield _sse({"type": "RUN_ERROR", "message": "Too many assessment rounds"})



# (Plan polling and repair endpoints removed — plan now auto-spawns at turn ~4
#  and is delivered via PLAN_UPDATE SSE. No frontend polling needed.)


# ── Chat Route ───────────────────────────────────────────────────────────────

@router.post("/api/chat", dependencies=[Depends(_check_rate_limit)])
async def chat(request: Request, user: dict = Depends(get_optional_user)):
    # ── Request validation ────────────────────────────────
    try:
        body = await request.json()
    except Exception:
        return StreamingResponse(
            iter([_sse_raw({"type": "RUN_ERROR", "message": "Invalid request body"})]),
            media_type="text/event-stream",
        )

    messages = body.get("messages")
    context = body.get("context")
    req_session_id = body.get("sessionId")
    is_session_start = body.get("isSessionStart", False)

    if not req_session_id or not isinstance(req_session_id, str) or len(req_session_id) > 100:
        return StreamingResponse(
            iter([_sse_raw({"type": "RUN_ERROR", "message": "Invalid session ID"})]),
            media_type="text/event-stream",
        )

    context_data = extract_context(context)
    session, session_id = await get_or_create_session(req_session_id)

    # ── Session lock — prevent concurrent requests for same session ──
    lock = get_session_lock(session_id)
    if lock.locked():
        # Another request is already processing this session
        return StreamingResponse(
            iter([_sse_raw({"type": "RUN_ERROR", "message": "Session busy — please wait for the current response"})]),
            media_type="text/event-stream",
        )

    # Server-side message history is the source of truth.
    # Frontend sends the latest user message; we append it to server history.
    frontend_messages = convert_messages(messages)
    if session.messages:
        # Existing session: append only the NEW user message from frontend
        if frontend_messages:
            last_msg = frontend_messages[-1]
            # Only append if it's a new user message (not a duplicate)
            if last_msg.get("role") == "user":
                if not session.messages or session.messages[-1].get("content") != last_msg.get("content"):
                    session.messages.append(last_msg)
        claude_messages = session.messages
    else:
        # First request OR no server history: seed from frontend
        session.messages = frontend_messages
        claude_messages = session.messages

    # Context management: summarize old messages + apply window
    await _maybe_generate_summary(session, claude_messages)
    windowed_messages = apply_context_window(session, claude_messages)
    # Use windowed copy for LLM call; keep full history on session
    claude_messages = windowed_messages

    user_email = _extract_user_email(context_data)
    slog = SessionLogger(log, session_id=session_id, user=user_email or "")

    msg_count = len(claude_messages)
    last_msg = claude_messages[-1] if claude_messages else {}
    last_content = last_msg.get("content", "")
    if isinstance(last_content, str):
        preview = last_content[:80]
    elif isinstance(last_content, list):
        types = [b.get("type", "?") for b in last_content if isinstance(b, dict)]
        preview = f"[multipart: {', '.join(types)}]"
    else:
        preview = "[complex]"
    slog.info("Chat request", extra={"event": "CHAT_REQUEST", "msg_count": msg_count, "preview": preview})

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

            # ── Step 1a: Load knowledge state + summary in parallel ────
            if is_session_start:
                await _load_knowledge_context(context_data)

            # ── Step 2: Initialize agent runtime ──────────────────────
            if not session.agent_runtime:
                session.agent_runtime = AgentRuntime(session_id=session_id)
            runtime = session.agent_runtime

            # ── Step 2a: Detect video follow-along mode ───────────────
            is_video_mode = bool(context_data.get("videoState"))
            if is_video_mode:
                session.active_scenario = "video_follow"
                # Sync video state for persistence/restoration
                try:
                    _vs_raw = context_data.get("videoState", "")
                    _vs = json.loads(_vs_raw) if isinstance(_vs_raw, str) else _vs_raw
                    if isinstance(_vs, dict):
                        session.video_state = _vs
                except (json.JSONDecodeError, TypeError):
                    pass

            # ── Step 2b: Session phase — triage or teach ──────────────
            if is_session_start and not is_video_mode:
                _init_session_phase(session, context_data, slog)
                slog.info("Session started", extra={
                    "event": "SESSION_START",
                    "course_id": session.course_id if hasattr(session, 'course_id') else None,
                    "intent": (session.student_intent or "")[:80],
                })

            # Plan setup — re-emit existing plan for frontend sidebar (if restored session)
            # New sessions: planner auto-spawns at turn ~4 when tutor has enough context.
            if is_session_start and not is_video_mode:
                if session.current_plan:
                    slog.debug("Re-emitting existing plan for frontend")
                    yield _sse({
                        "type": "PLAN_UPDATE",
                        "plan": session.current_plan,
                        "sessionObjective": session.session_objective or "",
                        "currentTopicIndex": session.current_topic_index,
                    })
                else:
                    orchestrator_plan = _extract_orchestrator_plan(context_data)
                    if orchestrator_plan:
                        slog.info("Using orchestrator-provided plan (skipping planner agent)")
                        _promote_plan(session, orchestrator_plan)
                        yield _sse({
                            "type": "PLAN_UPDATE",
                            "plan": orchestrator_plan,
                            "sessionObjective": orchestrator_plan.get("session_objective", ""),
                        })

            # ── Step 3a: Check assessment → route to assessment agent ──
            if session.assessment:
                slog.info(
                    "Routing to assessment agent",
                    extra={
                        "agent": "assessment",
                        "round": session.assessment.turns_used + 1,
                    },
                )
                async for chunk in _handle_assessment(
                    session, session_id, claude_messages, context_data, request, slog=slog
                ):
                    yield chunk
                return

            # ── Step 3b: Build triage context for tutor prompt overlay ──
            # (Triage runs through the tutor loop — same voice, board, everything)
            if session.phase == SessionPhase.TRIAGE:
                # Safety: auto-complete triage after 5 assistant turns
                triage_turns = sum(1 for m in session.messages if m.get("role") == "assistant") if session.messages else 0
                if triage_turns >= 5:
                    slog.info("Triage auto-completed after %d turns", triage_turns)
                    session.phase = SessionPhase.TEACHING
                    # Planner will auto-spawn when tutor has enough context (turn ~4)
                    # Fall through to normal tutor prompt (no triage overlay)
                else:
                    pass  # continue with triage overlay below

            if session.phase == SessionPhase.TRIAGE:
                triage_ctx = {}
                # Resolve content brief on first triage
                if not session.triage_result and session.student_intent:
                    try:
                        from app.services.content_resolver import resolve_content, format_content_brief
                        db_session = request.state.db if hasattr(request.state, 'db') else None
                        if not db_session:
                            from app.core.database import get_db
                            db_gen = get_db()
                            db_session = await db_gen.__anext__()
                        brief = await resolve_content(session.student_intent, db_session=db_session)
                        triage_ctx["contentBrief"] = format_content_brief(brief)
                        # Store brief on session for planner to use later
                        if not hasattr(session, '_content_brief'):
                            session._content_brief = brief
                    except Exception as e:
                        slog.warning("Content resolve failed: %s", e)
                # Upcoming topics from plan
                if session.current_topics and session.current_topic_index >= 0:
                    upcoming = session.current_topics[session.current_topic_index:][:5]
                    if upcoming:
                        triage_ctx["upcomingTopics"] = "\n".join(
                            f"  - {t.get('title', '?')}" for t in upcoming
                        )
                # Last assessment
                if session.last_assessment_summary:
                    la = session.last_assessment_summary
                    score = la.get("score", {})
                    triage_ctx["lastAssessment"] = (
                        f"Score: {score.get('correct',0)}/{score.get('total',0)} ({score.get('pct',0)}%)"
                    )
                context_data["triageContext"] = triage_ctx
                context_data["sessionPhase"] = "triage"
                slog.info("Phase TRIAGE: injecting triage overlay into tutor prompt")

            # ── Step 3c: Check delegation → route to sub-agent ────────
            if session.delegation:
                slog.info(
                    "Routing to delegated sub-agent",
                    extra={
                        "agent": "delegation",
                        "round": session.delegation.turns_used + 1,
                    },
                )
                async for chunk in _handle_delegated_teaching(
                    session, session_id, claude_messages, context_data, request, slog=slog
                ):
                    yield chunk
                return

            # ── Step 4: Promote completed agent results ───────────────
            completed = runtime.pop_completed()
            for agent in completed:
                # Background agent costs already tracked by centralized callback
                if agent["type"] == "planning" and agent["status"] == "complete" and agent.get("result"):
                    slog.info("Promoting planning agent result into session", extra={"agent": "planning"})
                    _promote_plan(session, agent["result"])

                    # Emit plan update SSE for frontend
                    plan = agent["result"]
                    yield _sse({
                        "type": "PLAN_UPDATE",
                        "plan": plan,
                        "sessionObjective": plan.get("session_objective", ""),
                    })

                elif agent["type"] == "visual_gen" and agent["status"] == "complete" and agent.get("result"):
                    result = agent["result"]
                    visual_id = result.get("visual_id", "")
                    title = result.get("title", "Interactive Visual")
                    html = result.get("html", "")

                    # Store in session
                    session.generated_visuals[visual_id] = {"html": html, "title": title}
                    slog.info("Visual gen complete", extra={"agent": "visual_gen", "tool": visual_id})

                    # Emit SSE event for frontend
                    yield _sse({
                        "type": "VISUAL_READY",
                        "id": visual_id,
                        "title": title,
                        "html": html,
                    })

                    # Replace the raw result with a summary for the tutor prompt
                    agent["result"] = (
                        f"Interactive visual ready — ID: {visual_id}, Title: \"{title}\"\n"
                        f'Display it with: <teaching-interactive id="{visual_id}" title="{title}" />\n'
                        "The student will see an interactive simulation in the spotlight panel.\n"
                        "You can observe their interactions via [Active Simulation State] on the next turn."
                    )

            # Check delegation result from just-ended delegation
            delegation_result_ctx = None
            if session.delegation_result:
                delegation_result_ctx = json.dumps(session.delegation_result, indent=2)
                session.delegation_result = None

            # Check assessment result from just-ended assessment
            assessment_result_ctx = None
            if session.assessment_result:
                ar = session.assessment_result
                assessment_result_ctx = (
                    f"Assessment checkpoint for \"{ar.get('section', '?')}\" just completed.\n"
                    f"Type: {ar.get('type', 'complete')}\n"
                )
                if ar.get("type") == "complete":
                    score = ar.get("score", {})
                    assessment_result_ctx += (
                        f"Score: {score.get('correct', 0)}/{score.get('total', 0)} ({score.get('pct', 0)}%)\n"
                        f"Overall Mastery: {ar.get('overallMastery', '?')}\n"
                    )
                    per_concept = ar.get("perConcept", [])
                    if per_concept:
                        assessment_result_ctx += "Per-Concept Results:\n"
                        for pc in per_concept:
                            assessment_result_ctx += f"  - {pc.get('concept', '?')}: {pc.get('correct', 0)}/{pc.get('total', 0)} ({pc.get('mastery', '?')})\n"
                else:
                    assessment_result_ctx += (
                        f"Reason: {ar.get('reason', '?')}\n"
                        f"Questions Completed: {ar.get('questionsCompleted', 0)}\n"
                        f"Stuck On: {ar.get('stuckOn', 'N/A')}\n"
                    )
                if ar.get("updatedNotes"):
                    assessment_result_ctx += "Updated Concept Notes:\n"
                    for cname, note in ar["updatedNotes"].items():
                        assessment_result_ctx += f"  {cname}: {note}\n"
                if ar.get("studentQuestions"):
                    assessment_result_ctx += "Student Questions During Checkpoint (follow up on these):\n"
                    for sq in ar["studentQuestions"]:
                        assessment_result_ctx += f"  - {sq}\n"
                if ar.get("studentState"):
                    assessment_result_ctx += f"Student State: {ar['studentState']}\n"
                if ar.get("recommendation"):
                    assessment_result_ctx += f"Assessment Recommendation: {ar['recommendation']}\n"

                # Save persistent summary before clearing one-shot result
                session.last_assessment_summary = _build_assessment_summary(ar)
                # Also enrich pre_assessment_note with results
                if session.pre_assessment_note:
                    session.pre_assessment_note["assessmentScore"] = ar.get("score", {})
                    session.pre_assessment_note["overallMastery"] = ar.get("overallMastery", "unknown")
                    session.pre_assessment_note["weakConcepts"] = [
                        pc.get("concept", "?")
                        for pc in ar.get("perConcept", [])
                        if pc.get("mastery") in ("weak", "not_demonstrated", "needs_work")
                        or pc.get("correct", 1) == 0
                    ]
                    session.pre_assessment_note["recommendation"] = ar.get("recommendation", "")

                session.assessment_result = None
                # pre_assessment_note stays alive — cleared when tutor calls advance_topic
                slog.info("Injecting assessment results into tutor context")

            # ── Step 4b: Knowledge summary already loaded in step 1a ──
            # (loaded in parallel by _load_knowledge_context on session start)
            if not context_data.get("knowledgeSummary"):
                try:
                    course_id, _ = _extract_student_info(context_data)
                    user_email = _extract_user_email(context_data)
                    if course_id and user_email:
                        ks_summary = await get_knowledge_summary(course_id, user_email)
                        if ks_summary:
                            context_data["knowledgeSummary"] = ks_summary
                except Exception as e:
                    slog.warning("Failed to load knowledge summary: %s", e)

            # ── Step 5: Build prompt and select tools ───
            agent_results_str = _format_agent_results(completed) if completed else None
            user_email = _extract_user_email(context_data)
            teaching_mode = _extract_teaching_mode(context_data)
            session.teaching_mode = teaching_mode  # Persist for session restore

            # ── Auto-inject context for video follow-along ──
            # Pre-fetch transcript + section content so tutor doesn't need tool calls
            video_state_raw = context_data.get("videoState")
            if video_state_raw:
                try:
                    import json as _vjson
                    vs = _vjson.loads(video_state_raw) if isinstance(video_state_raw, str) else video_state_raw
                    _vid_lesson = vs.get("lessonId")
                    _vid_ts = vs.get("currentTimestamp", 0)
                    _vid_section = vs.get("currentSectionIndex", 0)

                    if _vid_lesson:
                        # Fetch transcript + section content in parallel
                        import asyncio as _aio
                        _fetch_tasks = []
                        if _vid_ts > 0 and not context_data.get("_autoTranscript"):
                            from app.tools.handlers import get_transcript_context as _gtc
                            _fetch_tasks.append(_gtc(int(_vid_lesson), float(_vid_ts)))
                        else:
                            _fetch_tasks.append(_aio.sleep(0))  # placeholder

                        if not context_data.get("_autoSectionContent"):
                            from app.tools.handlers import get_section_content as _gsc
                            _fetch_tasks.append(_gsc(int(_vid_lesson), int(_vid_section)))
                        else:
                            _fetch_tasks.append(_aio.sleep(0))

                        results = await _aio.gather(*_fetch_tasks, return_exceptions=True)

                        if not isinstance(results[0], (Exception, type(None))) and results[0]:
                            context_data["_autoTranscript"] = results[0]
                        if not isinstance(results[1], (Exception, type(None))) and results[1]:
                            context_data["_autoSectionContent"] = results[1]
                except Exception as _te:
                    log.debug("Auto video context injection failed: %s", _te)

            tutor_prompt = build_tutor_prompt({
                **context_data,
                "studentModel": json.dumps(session.student_model, indent=2) if session.student_model else None,
                "teachingPlan": json.dumps(session.current_plan, indent=2) if session.current_plan else None,
                "currentTopic": (
                    json.dumps(session.current_topics[session.current_topic_index], indent=2)
                    if session.current_topics and 0 <= session.current_topic_index < len(session.current_topics)
                    else None
                ),
                "completedTopics": _format_completed(session.completed_topics),
                "sessionScope": _format_session_scope(session),
                "agentResults": agent_results_str,
                "delegationResult": delegation_result_ctx,
                "assessmentResult": assessment_result_ctx,
                "preAssessmentNote": _format_pre_assessment_note(session.pre_assessment_note),
                "lastAssessmentSummary": session.last_assessment_summary,
                "scenarioSkill": SKILL_MAP.get(session.active_scenario) if session.active_scenario else None,
                "planAccountability": _build_plan_accountability(session),
                "checkpointAndPace": _build_checkpoint_and_pace(session),
                "teachingMode": teaching_mode,
            })
            _track_topic_dwell(session)
            if is_video_mode:
                active_tools = VIDEO_FOLLOW_TOOLS
                slog.debug("Video follow-along mode")
            else:
                active_tools = TUTOR_TOOLS

            prompt_size = sum(len(p) for p in tutor_prompt) if isinstance(tutor_prompt, tuple) else len(tutor_prompt)
            slog.info("Tutor prompt built", extra={"token_count": prompt_size // 4})

            # ── Step 6: Tutor agentic loop ────────────────────────────
            import time as _time
            _turn_start = _time.monotonic()
            _first_text_at = None
            rounds = 0
            _section_content_calls = 0
            MAX_SECTION_CONTENT_CALLS = 3

            # Periodic student model update (every 5 turns) — injected as prompt nudge
            # instead of tool_choice to avoid burning a full Opus round on bookkeeping
            session.assistant_turn_count += 1
            _nudge_student_update = (
                session.assistant_turn_count >= 5
                and session.assistant_turn_count % 5 == 0
            )

            while rounds < MAX_ROUNDS:
                rounds += 1
                slog.info("Tutor LLM call", extra={"round": rounds, "model": settings.tutor_model})

                if await request.is_disconnected():
                    slog.info("Client disconnected")
                    return

                text_started = False
                message_id = None
                text_length = 0

                # Validate messages before API call
                valid_messages = _validate_messages(claude_messages)

                # Build API kwargs
                api_kwargs: dict = {
                    "model": settings.tutor_model,
                    "max_tokens": 4096,
                    "system": tutor_prompt,
                    "messages": valid_messages,
                    "tools": active_tools,
                }

                # Nudge student model update — append to dynamic part of system prompt
                # instead of tool_choice, so the model does it IN the same round as
                # teaching (avoids burning a full Opus round on bookkeeping)
                if _nudge_student_update and rounds == 1:
                    _nudge_student_update = False
                    nudge = (
                        "\n\n[SYSTEM — Student model update due. Include an update_student_model "
                        "call alongside your teaching response this turn. Do NOT call it alone — "
                        "teach AND update in the same response.]"
                    )
                    sys = api_kwargs["system"]
                    if isinstance(sys, tuple):
                        # (static, dynamic) — append to dynamic to preserve cache
                        api_kwargs["system"] = (sys[0], sys[1] + nudge)
                    elif isinstance(sys, str):
                        api_kwargs["system"] = sys + nudge
                    slog.info("Nudging update_student_model via prompt (no extra round)")

                # Retry loop for transient errors
                message = None
                for attempt in range(MAX_RETRIES):
                    try:
                        async with await llm_stream(**api_kwargs, metadata=LLMCallMetadata(session_id=session_id, caller="tutor")) as stream:
                            async for text in stream.text_stream:
                                if await request.is_disconnected():
                                    return
                                # (suppress_text removed — student model update
                                # is now nudged via prompt, not tool_choice)
                                if not text_started:
                                    message_id = str(uuid.uuid4())
                                    yield _sse({"type": "TEXT_MESSAGE_START", "messageId": message_id})
                                    text_started = True
                                    if _first_text_at is None:
                                        _first_text_at = _time.monotonic()
                                        slog.info("TTFT", extra={"ttft_ms": round((_first_text_at - _turn_start) * 1000), "round": rounds})
                                text_length += len(text)
                                yield _sse({"type": "TEXT_MESSAGE_CONTENT", "delta": text})

                            message = await stream.get_final_message()
                        break  # Success
                    except Exception as e:
                        if is_retryable(e) and attempt < MAX_RETRIES - 1:
                            delay = extract_retry_after(e) or RETRY_BASE_DELAY * (2 ** attempt)
                            slog.warning(
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

                # ── Mid-stream: check for completed background agents (planning, visuals) ──
                # This ensures the plan appears DURING the first response, not on the next turn.
                if not session.current_plan:
                    mid_completed = runtime.pop_completed()
                    for agent in mid_completed:
                        if agent["type"] == "planning" and agent["status"] == "complete" and agent.get("result"):
                            slog.info("Plan ready mid-stream — emitting immediately")
                            _promote_plan(session, agent["result"])
                            yield _sse({
                                "type": "PLAN_UPDATE",
                                "plan": agent["result"],
                                "sessionObjective": agent["result"].get("session_objective", ""),
                            })

                # Determine if this round has tool calls (will continue to next round)
                tool_blocks = [b for b in message.content if b.type == "tool_use"]
                has_tool_calls = len(tool_blocks) > 0

                # Only close the text message if there are NO tool calls (final round).
                # If there ARE tool calls, the next round may produce more text —
                # we keep the message open so the frontend sees one continuous response.
                if text_started and not has_tool_calls:
                    yield _sse({"type": "TEXT_MESSAGE_END"})

                slog.info(
                    "Tutor LLM response",
                    extra={
                        "model": settings.tutor_model,
                        "tokens_in": message.usage.input_tokens,
                        "tokens_out": message.usage.output_tokens,
                        "stop_reason": message.stop_reason,
                        "round": rounds,
                        "turn_elapsed_ms": round((_time.monotonic() - _turn_start) * 1000),
                    },
                )

                # Cost tracked by centralized callback — emit SSE update
                yield _sse({
                    "type": "COST_UPDATE",
                    "costCents": round(session.llm_cost_cents, 2),
                    "callCount": session.llm_call_count,
                })

                # ── Tool calls ────────────────────────────────────────
                if has_tool_calls:
                    for block in tool_blocks:
                        slog.info("Tool call: %s", block.name, extra={"tool": block.name})
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

                            # Skip duplicate planning spawn if auto-spawned
                            if agent_type == "planning" and getattr(session, '_planner_spawned', False):
                                session._planner_spawned = False  # allow future spawns
                                result = (
                                    "Planning agent is already running in the background (auto-spawned at session start). "
                                    "Results will be available in [AGENT RESULTS] on your next turn. "
                                    "Do NOT call get_section_content yourself — the planner handles that. "
                                    "Start teaching NOW with what you know from the course map."
                                )
                            else:
                                spawn_context = context_data
                                if agent_type == "planning":
                                    spawn_context = {
                                        **context_data,
                                        "sessionScope": _format_session_scope(session),
                                        "completedTopics": _format_completed(session.completed_topics),
                                        "studentModel": json.dumps(session.student_model, indent=2) if session.student_model else None,
                                        "lastAssessmentSummary": session.last_assessment_summary,
                                        "tutorNotes": "\n".join(session.tutor_notes[-5:]) if session.tutor_notes else None,
                                    }

                                agent_id = runtime.spawn(
                                    agent_type, task_desc, instructions, spawn_context
                                )
                                result = (
                                    f"Agent {agent_id} spawned ({agent_type}). "
                                    "Results will be available in [AGENT RESULTS] on your next turn."
                                )

                        # ── check_agents ──────────────────────────────
                        elif block.name == "check_agents":
                            check_completed = runtime.pop_completed()
                            # Promote any planning or visual_gen results
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
                                        "studentModel": json.dumps(session.student_model, indent=2) if session.student_model else None,
                                        "teachingPlan": json.dumps(session.current_plan, indent=2) if session.current_plan else None,
                                        "currentTopic": (
                                            json.dumps(session.current_topics[session.current_topic_index], indent=2)
                                            if session.current_topics and 0 <= session.current_topic_index < len(session.current_topics)
                                            else None
                                        ),
                                        "completedTopics": _format_completed(session.completed_topics),
                                        "sessionScope": _format_session_scope(session),
                                        "scenarioSkill": SKILL_MAP.get(session.active_scenario) if session.active_scenario else None,
                                    })

                                elif agent["type"] == "visual_gen" and agent["status"] == "complete" and agent.get("result"):
                                    vr = agent["result"]
                                    vid = vr.get("visual_id", "")
                                    vtitle = vr.get("title", "Interactive Visual")
                                    vhtml = vr.get("html", "")
                                    session.generated_visuals[vid] = {"html": vhtml, "title": vtitle}
                                    yield _sse({"type": "VISUAL_READY", "id": vid, "title": vtitle, "html": vhtml})
                                    agent["result"] = (
                                        f"Interactive visual ready — ID: {vid}, Title: \"{vtitle}\"\n"
                                        f'Display it with: <teaching-interactive id="{vid}" title="{vtitle}" />\n'
                                        "The student will see an interactive simulation in the spotlight panel.\n"
                                        "You can observe their interactions via [Active Simulation State] on the next turn."
                                    )

                            result = json.dumps({
                                "agents": runtime.get_all_status(),
                                "completed": check_completed,
                            }, indent=2)

                        # ── handoff_to_assessment ───────────────────────
                        elif block.name == "handoff_to_assessment":
                            brief = block.input
                            section = brief.get("section", {})
                            concepts = brief.get("conceptsTested", [])
                            plan = brief.get("plan", {})
                            qc = plan.get("questionCount", {})

                            # Save lightweight pre-assessment marker (auto-populated from session state)
                            current_topic = None
                            if session.current_topics and 0 <= session.current_topic_index < len(session.current_topics):
                                current_topic = session.current_topics[session.current_topic_index]
                            session.pre_assessment_note = {
                                "sectionTitle": section.get("title", ""),
                                "sectionIndex": section.get("index"),
                                "currentTopicTitle": current_topic.get("title", "") if current_topic else "",
                                "currentTopicIndex": session.current_topic_index,
                                "conceptsTested": concepts,
                            }

                            # Build assessment prompt with full brief
                            assessment_prompt = build_assessment_prompt({
                                **context_data,
                                "assessmentBrief": brief,
                                "studentModel": json.dumps(session.student_model, indent=2) if session.student_model else None,
                            })

                            session.assessment = AssessmentState(
                                system_prompt=assessment_prompt,
                                tools=ASSESSMENT_TOOLS,
                                brief=brief,
                                section_title=section.get("title", "Unknown"),
                                concepts_tested=concepts,
                                max_questions=qc.get("max", 5),
                                min_questions=qc.get("min", 3),
                            )

                            slog.info("Assessment handoff", extra={"tool": "handoff_to_assessment", "agent": "assessment"})

                            yield _sse({
                                "type": "ASSESSMENT_START",
                                "section": section,
                                "concepts": concepts,
                                "maxQuestions": qc.get("max", 5),
                            })

                            result = (
                                f"Assessment checkpoint started for section \"{section.get('title', '?')}\". "
                                f"Testing concepts: {', '.join(concepts)}. "
                                "The assessment agent will handle the next interactions and return results when complete."
                            )

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
                            slog.info("Teaching delegated", extra={"tool": "delegate_teaching", "agent": agent_type})
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

                        # ── reset_plan ──────────────────────────────
                        elif block.name == "reset_plan":
                            reason = block.input.get("reason", "direction change")
                            keep_scope = block.input.get("keep_scope", False)

                            slog.info("reset_plan", extra={"tool": "reset_plan"})

                            # Clear plan state
                            session.current_plan = None
                            session.current_topics = []
                            session.current_topic_index = -1
                            session.pre_assessment_note = None  # Old checkpoint is obsolete

                            # Optionally reset scope
                            if not keep_scope:
                                session.session_objective = None
                                session.session_scope = None
                                session.scope_concepts = []

                            # Emit PLAN_RESET SSE for frontend
                            yield _sse({
                                "type": "PLAN_RESET",
                                "reason": reason,
                                "keep_scope": keep_scope,
                            })

                            # Rebuild tutor prompt without plan
                            tutor_prompt = build_tutor_prompt({
                                **context_data,
                                "studentModel": json.dumps(session.student_model, indent=2) if session.student_model else None,
                                "teachingPlan": None,
                                "currentTopic": None,
                                "completedTopics": _format_completed(session.completed_topics),
                                "sessionScope": _format_session_scope(session),
                                "scenarioSkill": SKILL_MAP.get(session.active_scenario) if session.active_scenario else None,
                            })

                            result = (
                                f"Plan scrapped (reason: {reason}). "
                                "The student's plan sidebar has been cleared.\n\n"
                                "NOW: spawn a planning agent with the new direction. "
                                "Include the updated entry point, student model, and any completed topics "
                                "that are still relevant. Pair with an assessment to mask the wait."
                            )

                        # ── request_board_image ────────────────────────
                        elif block.name == "request_board_image":
                            reason = block.input.get("reason", "")
                            slog.info("Tutor requested board image", extra={"tool": "request_board_image"})
                            yield _sse({"type": "BOARD_CAPTURE_REQUEST", "reason": reason})
                            result = (
                                "Board capture requested. The frontend will capture the current board "
                                "and send it as the next user message (image). Continue your response — "
                                "when the image arrives you'll be able to see the combined tutor+student work."
                            )

                        # ── fetch_asset ───────────────────────────────
                        elif block.name == "fetch_asset":
                            asset_id = block.input.get("asset_id", "")
                            slog.info("Tutor fetching asset", extra={"tool": "fetch_asset"})
                            # Look up in session's asset_registry first, then send SSE to frontend
                            yield _sse({"type": "FETCH_ASSET_REQUEST", "assetId": asset_id})
                            result = (
                                f"Asset '{asset_id}' retrieval requested. The content will be provided "
                                f"by the frontend from spotlight history. If the asset is a board-draw, "
                                f"you'll receive the full JSONL commands. If it's a widget, the full HTML code. "
                                f"Use this content with <teaching-board-draw-resume> or <teaching-widget-update>."
                            )

                        # ── update_student_model ────────────────────────
                        elif block.name == "update_student_model":
                            notes = block.input.get("notes", [])

                            # Model sometimes sends notes as a JSON string — parse it
                            if isinstance(notes, str):
                                try:
                                    notes = json.loads(notes)
                                except (json.JSONDecodeError, TypeError):
                                    slog.warning("update_student_model: notes was a string, could not parse — wrapping", extra={"tool": "update_student_model"})
                                    notes = [{"concepts": ["_general"], "note": notes}]

                            # Backward compat: if old schema (observations field), convert
                            if not notes and block.input.get("observations"):
                                notes = [{"concepts": ["_profile"], "note": block.input["observations"]}]

                            # Update in-memory session model with latest notes
                            if not session.student_model:
                                session.student_model = {"notes": {}}
                            model_notes = session.student_model.setdefault("notes", {})
                            for entry in notes:
                                concepts = entry.get("concepts", [])
                                primary = concepts[0] if concepts else "_uncategorized"
                                model_notes[primary] = {
                                    "concepts": concepts,
                                    "note": entry.get("note", ""),
                                }

                            slog.info("Student model updated", extra={"tool": "update_student_model"})

                            # Persist each note via upsert (fire-and-forget)
                            _sm_course_id, _ = _extract_student_info(context_data)
                            _sm_email = _extract_user_email(context_data)
                            if _sm_course_id and _sm_email:
                                from app.services.knowledge_state import upsert_concept_note
                                for entry in notes:
                                    try:
                                        await upsert_concept_note(
                                            _sm_course_id, _sm_email, session_id,
                                            concepts=entry.get("concepts", ["_uncategorized"]),
                                            note_text=entry.get("note", ""),
                                            lesson=entry.get("lesson"),
                                        )
                                    except Exception as e:
                                        slog.warning("Failed to upsert student note: %s", e)

                            result = "Student model updated. Continue teaching — do not mention this update to the student."

                        # ── modify_plan ───────────────────────────────
                        elif block.name == "modify_plan":
                            action = block.input.get("action")
                            reason = block.input.get("reason", "")
                            slog.info("modify_plan", extra={"action": action, "reason": reason[:100]})

                            if action == "insert_prereq":
                                prereq_topics = block.input.get("prereq_topics", [])
                                if not prereq_topics:
                                    result = "Error: prereq_topics is required for insert_prereq."
                                else:
                                    # Push current position onto detour stack
                                    session.detour_stack.append({
                                        "saved_topic_index": session.current_topic_index,
                                        "saved_topics": [t.copy() for t in session.current_topics],
                                        "reason": reason,
                                    })
                                    # Replace current topics with prereqs
                                    session.current_topics = prereq_topics
                                    session.current_topic_index = 0
                                    # Emit SSE
                                    yield _sse({
                                        "type": "PLAN_DETOUR_START",
                                        "prereq_topics": prereq_topics,
                                        "reason": reason,
                                        "return_topic": session.detour_stack[-1]["saved_topics"][
                                            session.detour_stack[-1]["saved_topic_index"]
                                        ].get("title", "previous topic") if session.detour_stack[-1]["saved_topics"] else "previous topic",
                                    })
                                    current_topic = prereq_topics[0] if prereq_topics else None
                                    result = (
                                        f"Detour started. Now teaching prerequisite: {prereq_topics[0].get('title', '?')}. "
                                        f"When done, call modify_plan(action='end_detour') to resume."
                                    )

                            elif action == "end_detour":
                                if not session.detour_stack:
                                    result = "Error: No active detour to end. The detour stack is empty."
                                else:
                                    saved = session.detour_stack.pop()
                                    session.current_topics = saved["saved_topics"]
                                    session.current_topic_index = saved["saved_topic_index"]
                                    current_topic = (
                                        session.current_topics[session.current_topic_index]
                                        if 0 <= session.current_topic_index < len(session.current_topics)
                                        else None
                                    )
                                    yield _sse({"type": "PLAN_DETOUR_END"})
                                    result = (
                                        f"Detour complete. Resumed at: {current_topic.get('title', '?') if current_topic else 'end of section'}. "
                                        f"Continue teaching from where you left off."
                                    )

                            elif action == "skip":
                                next_topic = _advance_topic(session)
                                if session.current_topics and session.current_topic_index > 0:
                                    skipped = session.current_topics[session.current_topic_index - 1]
                                    yield _sse({
                                        "type": "TOPIC_COMPLETE",
                                        "topic": skipped.get("title", "?"),
                                        "skipped": True,
                                        "reason": reason,
                                    })
                                if next_topic:
                                    current_topic = next_topic
                                    result = f"Skipped. Now on: {next_topic.get('title', '?')}."
                                else:
                                    result = "Skipped. No more topics in current section."
                            else:
                                result = f"Unknown modify_plan action: {action}"

                        # ── advance_topic ─────────────────────────────
                        elif block.name == "advance_topic":
                            session.tutor_notes.append(block.input.get("tutor_notes", ""))
                            if block.input.get("student_model"):
                                session.student_model = block.input["student_model"]
                            # Clear pre-assessment note — tutor is past the review phase
                            session.pre_assessment_note = None

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

                                # Upsert knowledge note for the completed topic
                                _course_id, _ = _extract_student_info(context_data)
                                _user_email = _extract_user_email(context_data)
                                if _course_id and _user_email:
                                    try:
                                        from app.services.knowledge_state import upsert_concept_note
                                        concept_tag = current.get("concept", "") or "_uncategorized"
                                        await upsert_concept_note(
                                            _course_id, _user_email, session_id,
                                            concepts=[concept_tag, "topic_completed"],
                                            note_text=f"Topic completed: {current.get('title', '')}. {block.input.get('tutor_notes', '')}",
                                        )
                                    except Exception as e:
                                        slog.warning("Failed to upsert knowledge on advance_topic: %s", e)

                            next_topic = _advance_topic(session)
                            if next_topic:
                                slog.info(
                                    "advance_topic: moving to next topic",
                                    extra={"tool": "advance_topic"},
                                )

                                # Rebuild Tutor prompt with new topic
                                tutor_prompt = build_tutor_prompt({
                                    **context_data,
                                    "studentModel": json.dumps(session.student_model, indent=2) if session.student_model else None,
                                    "teachingPlan": json.dumps(session.current_plan, indent=2) if session.current_plan else None,
                                    "currentTopic": json.dumps(next_topic, indent=2),
                                    "completedTopics": _format_completed(session.completed_topics),
                                    "sessionScope": _format_session_scope(session),
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
                            slog.info("ControlSimulation", extra={"tool": "control_simulation"})
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

                        # ── log_knowledge (deprecated — redirect to upsert) ──
                        elif block.name == "log_knowledge":
                            course_id, _ = _extract_student_info(context_data)
                            user_email = _extract_user_email(context_data)
                            if course_id and user_email:
                                try:
                                    from app.services.knowledge_state import upsert_concept_note
                                    tags = block.input.get("tags", [])
                                    if isinstance(tags, str):
                                        tags = [t.strip() for t in tags.split(",") if t.strip()]
                                    if not tags:
                                        tags = ["_uncategorized"]
                                    await upsert_concept_note(
                                        course_id, user_email, session_id,
                                        concepts=tags,
                                        note_text=block.input.get("note", ""),
                                    )
                                    result = '{"logged": true}'
                                except Exception as e:
                                    slog.error("log_knowledge upsert failed: %s", e, exc_info=True, extra={"tool": "log_knowledge"})
                                    result = f"Failed to log knowledge: {str(e)[:200]}"
                            else:
                                result = "Cannot log knowledge: missing student info"

                        # ── query_knowledge ───────────────────────────
                        elif block.name == "query_knowledge":
                            course_id, _ = _extract_student_info(context_data)
                            user_email = _extract_user_email(context_data)
                            if course_id and user_email:
                                try:
                                    result = await hybrid_search_notes(
                                        course_id, user_email, block.input["query"]
                                    )
                                except Exception as e:
                                    slog.error("query_knowledge failed: %s", e, exc_info=True, extra={"tool": "query_knowledge"})
                                    result = f"Failed to query knowledge: {str(e)[:200]}"
                            else:
                                result = "Cannot query knowledge: missing student info (courseId or userEmail)"

                        # ── Video control tools (resume/seek) ────────
                        elif block.name in VIDEO_CONTROL_TOOLS:
                            if block.name == "resume_video":
                                yield _sse({"type": "VIDEO_RESUME", "message": block.input.get("message", "")})
                                result = "Video playback resumed."
                            elif block.name == "seek_video":
                                ts = float(block.input.get("timestamp", 0))
                                yield _sse({"type": "VIDEO_SEEK", "timestamp": ts})
                                result = f"Video seeked to {ts:.0f}s."
                            elif block.name == "capture_video_frame":
                                yield _sse({"type": "VIDEO_CAPTURE_FRAME"})
                                # The frontend will capture the frame and include it
                                # in the next context update. For now, return a note.
                                result = "Frame capture requested. The video frame will be included in the next context. Describe what you need to see and the student's current frame will be provided."

                        # ── Content provider tools (adapter-based) ──
                        elif block.name in CONTENT_TOOL_NAMES:
                            try:
                                result = await _run_content_tool(block.name, block.input, context_data, request)
                            except Exception as e:
                                slog.error("Content adapter failed: %s", e, exc_info=True, extra={"tool": block.name})
                                result = f"Content tool error: {str(e)[:200]}"

                        # ── Complete triage → transition to teaching ──
                        elif block.name == "complete_triage":
                            session.triage_result = {
                                "diagnosed_gaps": block.input.get("diagnosed_gaps", []),
                                "confirmed_strong": block.input.get("confirmed_strong", []),
                                "student_level": block.input.get("student_level", ""),
                                "recommended_start": block.input.get("recommended_start", ""),
                                "content_refs": block.input.get("content_refs", []),
                            }
                            session.phase = SessionPhase.TEACHING
                            slog.info("Triage complete → TEACHING", extra=session.triage_result)
                            # Spawn planner with triage diagnostic
                            # Planner will auto-spawn when tutor has enough context
                            result = (
                                "Triage complete. You now have a clear picture of the student. "
                                "Start teaching — use the board, draw, explain. "
                                "Do NOT repeat the diagnostic to the student."
                            )

                        # ── Session signal (phase controller) ────────
                        elif block.name == "session_signal":
                            session.last_signals = block.input or {}
                            slog.info("Session signal", extra=block.input or {})
                            # Check phase transition
                            new_phase = _check_phase_transition(session, {})
                            if new_phase and new_phase != session.phase:
                                old_phase = session.phase
                                session.phase = new_phase
                                slog.info("Phase transition from signal", extra={"from": old_phase, "to": new_phase})
                            result = "Signal received."

                        # ── Normal tool execution ─────────────────────
                        else:
                            # Cap get_section_content — planning agent handles bulk content loading
                            if block.name == "get_section_content":
                                _section_content_calls += 1
                                if _section_content_calls > MAX_SECTION_CONTENT_CALLS:
                                    result = (
                                        "You've already loaded enough section content this turn. "
                                        "The planning agent is gathering content in the background. "
                                        "Teach with what you have NOW — use the course map for structure."
                                    )
                                    slog.info("get_section_content capped at %d", MAX_SECTION_CONTENT_CALLS)
                                else:
                                    try:
                                        result = await execute_tutor_tool(block.name, block.input)
                                    except Exception as e:
                                        slog.error("Tool failed: %s", e, exc_info=True, extra={"tool": block.name})
                                        result = f"Tool error ({block.name}): {str(e)[:200]}"
                            else:
                                try:
                                    result = await execute_tutor_tool(block.name, block.input)
                                except Exception as e:
                                    slog.error("Tool failed: %s", e, exc_info=True, extra={"tool": block.name})
                                    result = f"Tool error ({block.name}): {str(e)[:200]}"

                        elapsed = time.monotonic() - start_time

                        # Ensure result is never empty
                        if result is None:
                            result = "(no output)"
                        result_str = result if isinstance(result, str) else json.dumps(result)
                        if not result_str.strip():
                            result_str = "(no output)"

                        slog.info("Tool done", extra={"tool": block.name, "duration_ms": round(elapsed * 1000)})

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        })
                        yield _sse({"type": "TOOL_CALL_END", "toolCallId": block.id})

                    # ── Check for agent handoff (assessment/delegation) ──
                    # If handoff occurred, break tutor loop and start the new agent
                    # immediately in the same response stream — no dead stop.
                    if session.assessment:
                        slog.info("Assessment handoff — breaking tutor loop", extra={"agent": "assessment"})
                        if text_started:
                            yield _sse({"type": "TEXT_MESSAGE_END"})
                            text_started = False
                        break
                    if session.delegation:
                        slog.info("Delegation handoff — breaking tutor loop", extra={"agent": "delegation"})
                        if text_started:
                            yield _sse({"type": "TEXT_MESSAGE_END"})
                            text_started = False
                        break

                    # Continue conversation with tool results
                    # IMPORTANT: append to session.messages (source of truth) AND rebuild
                    # claude_messages from it. This ensures tool_use/tool_result pairs survive
                    # across turns — they're in session.messages which gets re-windowed.
                    serialized_assistant = _serialize_content(message.content)
                    serialized_results = _serialize_content(tool_results)
                    session.messages.append({"role": "assistant", "content": serialized_assistant})
                    session.messages.append({"role": "user", "content": serialized_results})
                    claude_messages = apply_context_window(session, session.messages)
                    continue

                # No more tool calls — done. Persist final assistant message.
                session.messages.append({"role": "assistant", "content": _serialize_content(message.content)})

                # Final check for plan completion (planner may have finished during our response)
                if not session.current_plan and runtime:
                    final_completed = runtime.pop_completed()
                    for agent in final_completed:
                        if agent["type"] == "planning" and agent["status"] == "complete" and agent.get("result"):
                            slog.info("Plan ready at end of turn — emitting")
                            _promote_plan(session, agent["result"])
                            yield _sse({
                                "type": "PLAN_UPDATE",
                                "plan": agent["result"],
                                "sessionObjective": agent["result"].get("session_objective", ""),
                            })

                slog.info("Request complete", extra={"round": rounds, "msg_count": len(session.messages)})

                # Sync session state to MongoDB
                try:
                    await sync_backend_state(session_id, session)
                except Exception as e:
                    slog.warning("Failed to sync session state: %s", e)

                slog.info("TURN COMPLETE", extra={
                    "total_ms": round((_time.monotonic() - _turn_start) * 1000),
                    "ttft_ms": round((_first_text_at - _turn_start) * 1000) if _first_text_at else None,
                    "rounds": rounds,
                })

                yield _sse({"type": "RUN_FINISHED"})
                return

            # ── Post-loop: check for immediate agent handoffs ──────────
            if session.assessment:
                # Start assessment agent immediately in same stream
                assessment_trigger = (
                    f'[SYSTEM] Assessment checkpoint starting for section '
                    f'"{session.assessment.section_title}". '
                    f'Concepts to test: {", ".join(session.assessment.concepts_tested)}. '
                    f'Begin with a warm transition and ask your first question.'
                )
                claude_messages.append({"role": "user", "content": assessment_trigger})
                async for chunk in _handle_assessment(
                    session, session_id, claude_messages, context_data, request, slog=slog
                ):
                    yield chunk
                return

            if session.delegation:
                # Start delegate agent immediately in same stream
                delegation_trigger = (
                    f'[SYSTEM] Teaching delegation started. Topic: {session.delegation.topic}. '
                    f'Begin your first interaction with the student.'
                )
                claude_messages.append({"role": "user", "content": delegation_trigger})
                async for chunk in _handle_delegated_teaching(
                    session, session_id, claude_messages, context_data, request, slog=slog
                ):
                    yield chunk
                return

            # Too many rounds — force a text response by retrying without tools
            slog.warning("Too many tool call rounds — forcing text response", extra={"round": MAX_ROUNDS})
            try:
                forced_msg = [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_blocks[-1].id if tool_blocks else "forced", "content": "STOP using tools. You have gathered enough content. START TEACHING NOW. Write your board-draw response immediately."}]}]
                claude_messages.extend(forced_msg)
                api_kwargs_forced = {**api_kwargs, "tools": [], "tool_choice": None}
                api_kwargs_forced["messages"] = claude_messages
                async with await llm_stream(**api_kwargs_forced, metadata=LLMCallMetadata(session_id=session_id, caller="tutor_forced")) as forced_stream:
                    async for text in forced_stream.text_stream:
                        if not text_started:
                            message_id = str(uuid.uuid4())
                            yield _sse({"type": "TEXT_MESSAGE_START", "messageId": message_id})
                            text_started = True
                        yield _sse({"type": "TEXT_MESSAGE_CONTENT", "delta": text})
                    if text_started:
                        yield _sse({"type": "TEXT_MESSAGE_END"})
                    forced_final = await forced_stream.get_final_message()
                    session.messages.append({"role": "assistant", "content": _serialize_content(forced_final.content)})
            except Exception as fe:
                slog.error("Forced response also failed: %s", fe)
                yield _sse({"type": "RUN_ERROR", "message": "Taking too long to prepare. Please try again."})

        except LLMBadRequestError as e:
            err_body = getattr(e, "body", {}) or {}
            err_msg = (err_body.get("error", {}).get("message", "") if isinstance(err_body, dict) else str(e))
            if "credit balance" in err_msg.lower() or "billing" in err_msg.lower():
                slog.warning("LLM billing error: %s", err_msg)
                yield _sse({"type": "RUN_ERROR", "message": "The AI service is temporarily unavailable — the API credit balance needs to be topped up. Please try again later."})
            else:
                slog.error("LLM bad request: %s", e, exc_info=True, extra={"msg_count": len(claude_messages)})
                yield _sse({"type": "RUN_ERROR", "message": f"AI request error: {err_msg}"})
        except LLMAuthError as e:
            slog.error("LLM auth error: %s", e)
            yield _sse({"type": "RUN_ERROR", "message": "The AI service API key is invalid or expired. Please check the configuration."})
        except LLMRateLimitError as e:
            retry_after = extract_retry_after(e)
            wait_msg = f" Try again in {int(retry_after)}s." if retry_after else ""
            slog.warning("LLM rate limit (retries exhausted): %s", e)
            yield _sse({"type": "RUN_ERROR", "message": f"The AI service is busy right now.{wait_msg} Please wait a moment and try again."})
        except LLMConnectionError as e:
            slog.error("LLM connection error: %s", e)
            yield _sse({"type": "RUN_ERROR", "message": "Could not connect to the AI service. Please check your internet connection."})
        except Exception as e:
            slog.error("Chat error: %s", e, exc_info=True)
            yield _sse({"type": "RUN_ERROR", "message": "Something went wrong. Please try again."})

    async def locked_generate():
        await lock.acquire()
        try:
            async for chunk in generate():
                yield chunk
        finally:
            lock.release()

    return StreamingResponse(
        locked_generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Tool execution helper (shared by SSE and WebSocket paths) ──


async def _execute_tool_block(*, block, session, session_id, context_data, runtime, request, slog):
    """Execute a single tool call block and return the result string.

    Handles the most common tutor tools.  For tools that need SSE events
    (like spawn_agent, handoff_to_assessment), those are handled inline
    in generate() — this function handles the simpler content tools.
    """
    name = block.name
    inp = block.input or {}

    try:
        if name == "get_section_content":
            section_id = inp.get("section_id", "")
            result = await get_section_content(section_id, context_data=context_data)
            return result or f"No content found for section: {section_id}"

        elif name == "search_images":
            query = inp.get("query", "")
            limit = int(inp.get("limit", 3))
            results = await search_images(query, limit=limit)
            return json.dumps(results) if results else "No images found"

        elif name == "get_simulation_details":
            sim_id = inp.get("simulation_id", "")
            result = await get_simulation_details(sim_id)
            return result or f"No simulation found: {sim_id}"

        elif name == "update_student_model":
            notes = inp.get("notes", [])
            # Model sometimes sends notes as a JSON string — parse it
            if isinstance(notes, str):
                try:
                    notes = json.loads(notes)
                except (json.JSONDecodeError, TypeError):
                    notes = [{"concepts": ["_general"], "note": notes}]
            # Backward compat: observations field
            if not notes and inp.get("observations"):
                notes = [{"concepts": ["_profile"], "note": inp["observations"]}]
            # Update in-memory session model
            if not session.student_model:
                session.student_model = {"notes": {}}
            model_notes = session.student_model.setdefault("notes", {})
            for entry in notes:
                concepts = entry.get("concepts", [])
                primary = concepts[0] if concepts else "_uncategorized"
                model_notes[primary] = {
                    "concepts": concepts,
                    "note": entry.get("note", ""),
                }
            # Persist notes
            _sm_course_id, _ = _extract_student_info(context_data)
            _sm_email = _extract_user_email(context_data)
            if _sm_course_id and _sm_email:
                from app.services.knowledge_state import upsert_concept_note
                for entry in notes:
                    try:
                        await upsert_concept_note(
                            _sm_course_id, _sm_email, session_id,
                            concepts=entry.get("concepts", ["_uncategorized"]),
                            note_text=entry.get("note", ""),
                            lesson=entry.get("lesson"),
                        )
                    except Exception as e:
                        slog.warning("Failed to upsert student note: %s", e)
            return "Student model updated. Continue teaching — do not mention this update to the student."

        elif name == "advance_topic":
            # Mark current topic complete, move to next
            if session.current_topics and 0 <= session.current_topic_index < len(session.current_topics):
                current = session.current_topics[session.current_topic_index]
                session.completed_topics.append(current.get("title", "Unknown"))
                session.current_topic_index += 1
            session.pre_assessment_note = None
            return "Advanced to next topic"

        elif name == "handoff_to_assessment":
            from app.agents.agent_runtime import AssessmentState
            section_title = inp.get("section_title", "")
            concepts = inp.get("concepts", [])
            session.assessment = AssessmentState(
                section_title=section_title,
                concepts_tested=concepts,
            )
            session.pre_assessment_note = {
                "section": section_title,
                "concepts": concepts,
                "tutorNote": inp.get("tutor_note", ""),
            }
            return f"Assessment checkpoint started for: {section_title}"

        elif name == "delegate_teaching":
            from app.agents.agent_runtime import DelegationState
            topic = inp.get("topic", "")
            instructions = inp.get("instructions", "")
            session.delegation = DelegationState(
                topic=topic,
                instructions=instructions,
            )
            return f"Teaching delegated for topic: {topic}"

        elif name == "modify_plan":
            action = inp.get("action")
            if action == "insert_topic" and inp.get("topic"):
                idx = session.current_topic_index + 1
                session.current_topics.insert(idx, inp["topic"])
                return f"Inserted topic at position {idx}"
            elif action == "skip_topic":
                if session.current_topics and session.current_topic_index < len(session.current_topics):
                    skipped = session.current_topics[session.current_topic_index]
                    session.current_topic_index += 1
                    return f"Skipped topic: {skipped.get('title', '?')}"
            return "Plan modified"

        elif name == "reset_plan":
            session.current_plan = None
            session.current_topics = []
            session.current_topic_index = 0
            session._planner_spawned = False  # allow re-spawn on next eligible turn
            return "Plan reset — new planner will spawn when ready"

        elif name == "spawn_agent":
            agent_type = inp.get("type", "research")
            task_desc = inp.get("task", "")
            # Skip duplicate planning spawn
            if agent_type == "planning" and getattr(session, '_planner_spawned', False):
                session._planner_spawned = False
                return "Planning agent already running in background."
            agent_id = runtime.spawn(agent_type=agent_type, task=task_desc, context=context_data)
            return f"Agent spawned: {agent_id} (type={agent_type})"

        elif name == "check_agents":
            completed = runtime.pop_completed() if runtime else []
            return json.dumps([{"type": a.get("type"), "status": a.get("status")} for a in completed]) if completed else "No completed agents."

        elif name == "request_board_image":
            return "Board image requested — student's board state will be included on next turn."

        elif name == "complete_triage":
            session.triage_result = {
                "diagnosed_gaps": inp.get("diagnosed_gaps", []),
                "confirmed_strong": inp.get("confirmed_strong", []),
                "student_level": inp.get("student_level", ""),
                "recommended_start": inp.get("recommended_start", ""),
                "content_refs": inp.get("content_refs", []),
            }
            session.phase = SessionPhase.TEACHING
            slog.info("Triage complete → TEACHING", extra=session.triage_result)
            return (
                "Triage complete. You now have a clear picture of the student. "
                "Start teaching — use the board, draw, explain. "
                "Do NOT repeat the diagnostic to the student."
            )

        elif name == "session_signal":
            session.last_signals = inp or {}
            slog.info("Session signal", extra=inp or {})
            new_phase = _check_phase_transition(session, {})
            if new_phase and new_phase != session.phase:
                session.phase = new_phase
            return "Signal received. (terminal — no further rounds needed)"

        elif name == "control_simulation":
            return json.dumps({"status": "ok", "action": inp.get("action", "unknown")})

        elif name == "web_search":
            from app.tools.web_search import web_search as _web_search
            query = inp.get("query", "")
            results = await _web_search(query) if query else None
            return json.dumps(results) if results else "No results found"

        elif name in CONTENT_TOOL_NAMES:
            # Content tools — route through content adapter
            try:
                result = await _run_content_tool(name, inp, context_data, request)
                return result or f"No content found for {name}"
            except Exception as e:
                slog.warning("Content tool %s failed: %s", name, e)
                return f"Content tool error: {e}"

        else:
            slog.warning("Unknown tool: %s", name)
            return f"Tool '{name}' executed (no specific handler)"

    except Exception as e:
        slog.warning("Tool %s failed: %s", name, e)
        return f"Tool error: {e}"


# ── WebSocket-compatible entry point ─────────────────────────
# SessionRouter calls this to reuse the existing chat pipeline.
# Yields the same SSE-formatted strings as generate(), but without
# needing a real HTTP Request object.


class _FakeRequest:
    """Minimal stand-in for starlette.requests.Request.

    Provides .is_disconnected() and .state.db — the only things
    the generate() pipeline needs from the request object.
    """
    def __init__(self, is_disconnected_fn):
        self._is_disconnected = is_disconnected_fn
        self.state = type("State", (), {"db": None})()
        self.query_params = {}
        self.headers = {}

    async def is_disconnected(self) -> bool:
        result = self._is_disconnected()
        if asyncio.iscoroutine(result):
            return await result
        return bool(result)

    async def json(self):
        return self._body

    def _set_body(self, body: dict):
        self._body = body


async def _generate_for_turn(
    *,
    session_id: str,
    messages: list | None = None,
    context: dict | None = None,
    is_session_start: bool = False,
    is_disconnected=None,
    attachments: list | None = None,
):
    """Yields SSE event strings using the existing chat() pipeline.

    Called by the WebSocket SessionRouter.  Reuses the exact same
    session setup and generate() logic as the HTTP /api/chat endpoint —
    no duplication of the 1200-line agentic loop.

    The approach: construct the same environment that chat() creates,
    then call into the same generate() closure.
    """
    # Build a fake request that generate() can use
    request = _FakeRequest(is_disconnected or (lambda: False))

    context_data = extract_context(context) if context else {}
    session, sid = await get_or_create_session(session_id)

    # Session lock
    lock = get_session_lock(sid)
    if lock.locked():
        yield _sse({"type": "RUN_ERROR", "message": "Session busy — please wait"})
        return

    # Message setup (same as chat() handler)
    frontend_messages = convert_messages(messages) if messages else []
    if session.messages:
        if frontend_messages:
            last_msg = frontend_messages[-1]
            if last_msg.get("role") == "user":
                if not session.messages or session.messages[-1].get("content") != last_msg.get("content"):
                    session.messages.append(last_msg)
        claude_messages = session.messages
    else:
        session.messages = frontend_messages
        claude_messages = session.messages

    # Context window
    await _maybe_generate_summary(session, claude_messages)
    windowed_messages = apply_context_window(session, claude_messages)
    claude_messages = windowed_messages

    # ── Inject attachments on first turn, persist to GCS in background ──
    # Attachments are baked into session.messages on injection. The pinned
    # context window keeps the first multimodal message visible on all turns.
    # No re-injection needed — just upload to GCS for long-term persistence.
    if attachments and claude_messages:
        last_user = None
        for msg in reversed(claude_messages):
            if msg.get("role") == "user":
                last_user = msg
                break
        if last_user:
            existing = last_user.get("content", "")
            content_parts = []
            if isinstance(existing, str):
                content_parts.append({"type": "text", "text": existing})
            elif isinstance(existing, list):
                content_parts.extend(existing)
            for att in attachments:
                mime = att.get("mime_type", "")
                data = att.get("data", "")
                fname = att.get("filename", "file")
                if not data or not mime:
                    continue
                if mime.startswith("image/"):
                    content_parts.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime, "data": data},
                    })
                elif mime.startswith("audio/"):
                    fmt = mime.split("/")[-1]
                    if fmt == "mpeg": fmt = "mp3"
                    elif fmt == "x-wav": fmt = "wav"
                    content_parts.append({
                        "type": "input_audio",
                        "input_audio": {"data": data, "format": fmt},
                    })
                elif mime.startswith("video/"):
                    content_parts.append({
                        "type": "video_url",
                        "video_url": {"url": f"data:{mime};base64,{data}"},
                    })
                else:
                    content_parts.append({
                        "type": "file",
                        "file": {"filename": fname, "file_data": f"data:{mime};base64,{data}"},
                    })
            last_user["content"] = content_parts

            # Fire-and-forget: upload to GCS + persist metadata (non-blocking)
            async def _bg_upload(session_id, attachments, session_obj):
                try:
                    from app.services.attachment_storage import upload_attachments
                    meta = await upload_attachments(session_id, attachments)
                    if meta:
                        session_obj.attachment_meta = meta
                        from app.services.session_service import update_session
                        await update_session(session_id, {"attachments": meta})
                except Exception as e:
                    log.warning("Background attachment upload failed: %s", e)

            import asyncio as _aio
            _aio.create_task(_bg_upload(sid, attachments, session))

    user_email = _extract_user_email(context_data)
    slog = SessionLogger(log, session_id=sid, user=user_email or "")

    if not claude_messages:
        yield _sse({"type": "RUN_ERROR", "message": "No messages provided"})
        return

    # ── The generate() closure — same as in chat() ──
    # This is the FULL pipeline including assessment routing,
    # delegation routing, triage, tool execution, etc.
    # We define it here to capture the same closure variables.

    async def generate():
        nonlocal claude_messages

        from app.core.config import settings

        yield _sse({"type": "CONNECTED"})

        try:
            # Step 1: Student intent
            if is_session_start:
                first_content = claude_messages[0].get("content", "") if claude_messages else ""
                if isinstance(first_content, str):
                    intent_match = _re.search(r'The student said: "([^"]+)"', first_content)
                    if intent_match:
                        session.student_intent = intent_match.group(1)
                if not session.student_intent and context_data.get("studentProfile"):
                    try:
                        profile = json.loads(context_data["studentProfile"])
                        if profile.get("studentIntent"):
                            session.student_intent = profile["studentIntent"]
                    except (json.JSONDecodeError, TypeError):
                        pass

            if is_session_start:
                await _load_knowledge_context(context_data)

            # Step 2: Agent runtime
            if not session.agent_runtime:
                session.agent_runtime = AgentRuntime(session_id=sid)
            runtime = session.agent_runtime

            is_video_mode = bool(context_data.get("videoState"))
            if is_video_mode:
                session.active_scenario = "video_follow"

            if is_session_start and not is_video_mode:
                _init_session_phase(session, context_data, slog)

            # ── Triage phase: inject triage overlay into tutor prompt ──
            if session.phase == SessionPhase.TRIAGE:
                triage_ctx = {}
                # Resolve content brief so triage knows what's available
                if not session.triage_result and session.student_intent:
                    try:
                        from app.services.content_resolver import resolve_content, format_content_brief
                        from app.core.database import get_mongo_db
                        brief = await resolve_content(session.student_intent)
                        triage_ctx["contentBrief"] = format_content_brief(brief)
                        if not hasattr(session, '_content_brief'):
                            session._content_brief = brief
                    except Exception as e:
                        slog.warning("Content resolve for triage failed: %s", e)
                # Upcoming topics
                if session.current_topics and session.current_topic_index >= 0:
                    upcoming = session.current_topics[session.current_topic_index:][:5]
                    if upcoming:
                        triage_ctx["upcomingTopics"] = "\n".join(
                            f"  - {t.get('title', '?')}" for t in upcoming
                        )
                # Last assessment
                if session.last_assessment_summary:
                    la = session.last_assessment_summary
                    score = la.get("score", {})
                    triage_ctx["lastAssessment"] = (
                        f"Score: {score.get('correct',0)}/{score.get('total',0)} ({score.get('pct',0)}%)"
                    )
                context_data["triageContext"] = triage_ctx
                context_data["sessionPhase"] = "triage"
                slog.info("Phase TRIAGE: injecting triage overlay into tutor prompt (ws)")

            # Plan setup
            if is_session_start and not is_video_mode:
                if session.current_plan:
                    yield _sse({"type": "PLAN_UPDATE", "plan": session.current_plan, "sessionObjective": session.session_objective or "", "currentTopicIndex": session.current_topic_index})
                else:
                    orchestrator_plan = _extract_orchestrator_plan(context_data)
                    if orchestrator_plan:
                        _promote_plan(session, orchestrator_plan)
                        yield _sse({"type": "PLAN_UPDATE", "plan": orchestrator_plan, "sessionObjective": orchestrator_plan.get("session_objective", "")})

            # Step 3: Assessment / delegation routing
            if session.assessment:
                async for chunk in _handle_assessment(session, sid, claude_messages, context_data, request, slog=slog):
                    yield chunk
                return

            if session.delegation:
                async for chunk in _handle_delegated_teaching(session, sid, claude_messages, context_data, request, slog=slog):
                    yield chunk
                return

            # Step 4-5: Agent results, prompt building
            # (Reuse the same logic from the main generate() — this part
            #  is identical. For brevity, we call the shared helpers.)
            completed = runtime.pop_completed()
            for agent in completed:
                if agent["type"] == "planning" and agent["status"] == "complete" and agent.get("result"):
                    _promote_plan(session, agent["result"])
                    yield _sse({"type": "PLAN_UPDATE", "plan": agent["result"], "sessionObjective": agent["result"].get("session_objective", "")})
                elif agent["type"] == "visual_gen" and agent["status"] == "complete" and agent.get("result"):
                    result = agent["result"]
                    session.generated_visuals[result.get("visual_id", "")] = {"html": result.get("html", ""), "title": result.get("title", "")}
                    yield _sse({"type": "VISUAL_READY", "id": result.get("visual_id", ""), "title": result.get("title", ""), "html": result.get("html", "")})

            teaching_mode = _extract_teaching_mode(context_data)
            session.teaching_mode = teaching_mode
            agent_results_str = _format_agent_results(completed) if completed else None

            # Housekeeping: full notes due every 5th user turn, signal always
            _housekeeping_due = (
                session.assistant_turn_count >= 5
                and session.assistant_turn_count % 5 == 0
            )

            # Log plan state for debugging
            has_plan = bool(session.current_plan)
            has_topics = bool(session.current_topics)
            topic_idx = session.current_topic_index if has_topics else -1
            current_topic_title = (
                session.current_topics[topic_idx].get("title", "?")
                if has_topics and 0 <= topic_idx < len(session.current_topics)
                else "(none)"
            )
            slog.info("Prompt build", extra={
                "has_plan": has_plan,
                "topics": len(session.current_topics) if has_topics else 0,
                "topic_idx": topic_idx,
                "current_topic": current_topic_title,
                "completed": len(session.completed_topics),
                "student_model": bool(session.student_model),
            })

            # ── Auto-inject context for video follow-along ──
            # Pre-fetch transcript + section content so tutor doesn't need tool calls
            video_state_raw = context_data.get("videoState")
            if video_state_raw:
                try:
                    import json as _vjson
                    vs = _vjson.loads(video_state_raw) if isinstance(video_state_raw, str) else video_state_raw
                    _vid_lesson = vs.get("lessonId")
                    _vid_ts = vs.get("currentTimestamp", 0)
                    _vid_section = vs.get("currentSectionIndex", 0)

                    if _vid_lesson:
                        import asyncio as _aio
                        _fetch_tasks = []
                        if _vid_ts > 0 and not context_data.get("_autoTranscript"):
                            from app.tools.handlers import get_transcript_context as _gtc
                            _fetch_tasks.append(_gtc(int(_vid_lesson), float(_vid_ts)))
                        else:
                            _fetch_tasks.append(_aio.sleep(0))

                        if not context_data.get("_autoSectionContent"):
                            from app.tools.handlers import get_section_content as _gsc
                            _fetch_tasks.append(_gsc(int(_vid_lesson), int(_vid_section)))
                        else:
                            _fetch_tasks.append(_aio.sleep(0))

                        results = await _aio.gather(*_fetch_tasks, return_exceptions=True)

                        if not isinstance(results[0], (Exception, type(None))) and results[0]:
                            context_data["_autoTranscript"] = results[0]
                        if not isinstance(results[1], (Exception, type(None))) and results[1]:
                            context_data["_autoSectionContent"] = results[1]
                except Exception as _te:
                    log.debug("Auto video context injection failed (ws): %s", _te)

            tutor_prompt = build_tutor_prompt({
                **context_data,
                "studentModel": json.dumps(session.student_model, indent=2) if session.student_model else None,
                "teachingPlan": json.dumps(session.current_plan, indent=2) if session.current_plan else None,
                "currentTopic": (
                    json.dumps(session.current_topics[session.current_topic_index], indent=2)
                    if session.current_topics and 0 <= session.current_topic_index < len(session.current_topics)
                    else None
                ),
                "completedTopics": _format_completed(session.completed_topics),
                "sessionScope": _format_session_scope(session),
                "agentResults": agent_results_str,
                "teachingMode": teaching_mode,
                "planAccountability": _build_plan_accountability(session),
                "checkpointAndPace": _build_checkpoint_and_pace(session),
                "_housekeepingDue": _housekeeping_due,
            })

            # Track topic dwell time for pace nudges
            _track_topic_dwell(session)

            # ── Tool filtering ──────────────────────────────────
            # Remove tools that are tag-based, deterministic, or cause unnecessary LLM rounds.
            # spawn_agent/check_agents: enrichment handled by shadow agent in background
            # session_signal/update_student_model/advance_topic: tag-based (housekeeping)
            _removed_tools = {
                "update_student_model", "advance_topic", "session_signal",
                "spawn_agent", "check_agents",
                "modify_plan", "reset_plan",
                "handoff_to_assessment", "delegate_teaching",
                "web_search", "search_images",  # disabled — not working reliably
            }
            is_first_turn = (session.assistant_turn_count == 0)

            # content_map always removed — course map is already in context
            _removed_tools.add("content_map")

            # complete_triage only available during triage phase
            if session.phase != SessionPhase.TRIAGE:
                _removed_tools.add("complete_triage")

            # First 3 turns: remove ALL content tools — tutor should teach from
            # plan + course map context, not fetch content. Teaches immediately.
            if session.assistant_turn_count < 3 and session.phase != SessionPhase.TRIAGE:
                _removed_tools |= {"content_search", "get_section_content", "query_knowledge", "content_read", "content_peek"}

            if is_video_mode:
                # Determine if this is a NEW pause (fresh timestamp) or a follow-up at same spot
                _vid_ts = 0
                try:
                    _vs_raw = context_data.get("videoState", "")
                    _vs_parsed = json.loads(_vs_raw) if isinstance(_vs_raw, str) and _vs_raw else (_vs_raw if isinstance(_vs_raw, dict) else {})
                    _vid_ts = int(_vs_parsed.get("currentTimestamp", 0))
                    _is_youtube = "youtube" in str(_vs_parsed.get("videoUrl", "") or _vs_parsed.get("lessonTitle", "")).lower() or _vs_parsed.get("isYouTube", False)
                except (json.JSONDecodeError, TypeError, AttributeError):
                    _is_youtube = False

                session._last_video_timestamp = _vid_ts
                # Tools kept available for looking up OTHER sections/timestamps.
                # Current section context is pre-injected (see prompt).

                # capture_video_frame only works with custom player, not YouTube (cross-origin)
                if _is_youtube:
                    _removed_tools.add("capture_video_frame")

                active_tools = [t for t in VIDEO_FOLLOW_TOOLS if t["name"] not in _removed_tools]
            else:
                active_tools = [t for t in TUTOR_TOOLS if t["name"] not in _removed_tools]

            # Auto-spawn enrichment agents in background (turn 1 only)
            # These run in parallel with the tutor's first response.
            # Results are injected into context on turn 2+ via pop_completed().
            if is_first_turn and not is_video_mode:
                _auto_spawn_enrichment(session, runtime, context_data, slog)

            # Step 6: Agentic loop (LLM stream → tool calls → repeat)
            import time as _time
            _turn_start = _time.monotonic()
            _first_text_at = None
            rounds = 0
            text_started = False
            text_length = 0
            _partial_text_parts = []  # accumulate text for partial save on interrupt

            session.assistant_turn_count += 1
            slog.set_turn(session.assistant_turn_count)
            slog.info("Turn started", extra={"event": "TURN_START"})

            valid_messages = _validate_messages(claude_messages)
            api_kwargs = {
                "system": tutor_prompt,
                "messages": valid_messages,
                "model": settings.tutor_model,
                "max_tokens": 4096,
                "tools": active_tools,
            }

            while rounds < MAX_ROUNDS:
                rounds += 1

                if await request.is_disconnected():
                    return

                message = None
                for attempt in range(MAX_RETRIES):
                    try:
                        async with await llm_stream(**api_kwargs, metadata=LLMCallMetadata(session_id=sid, caller="tutor")) as stream:
                            async for text in stream.text_stream:
                                if await request.is_disconnected():
                                    return
                                if not text_started:
                                    message_id = str(uuid.uuid4())
                                    yield _sse({"type": "TEXT_MESSAGE_START", "messageId": message_id})
                                    text_started = True
                                    if _first_text_at is None:
                                        _first_text_at = _time.monotonic()
                                text_length += len(text)
                                _partial_text_parts.append(text)
                                yield _sse({"type": "TEXT_MESSAGE_CONTENT", "delta": text})

                            message = await stream.get_final_message()
                        break
                    except asyncio.CancelledError:
                        # Turn cancelled — save partial message cleanly
                        partial = "".join(_partial_text_parts)
                        if partial:
                            cleaned = _clean_partial_content(partial)
                            session.messages.append({
                                "role": "assistant",
                                "content": cleaned + "\n[interrupted]",
                            })
                            await sync_backend_state(sid, session)
                        return
                    except Exception as e:
                        if is_retryable(e) and attempt < MAX_RETRIES - 1:
                            delay = extract_retry_after(e) or RETRY_BASE_DELAY * (2 ** attempt)
                            if text_started:
                                yield _sse({"type": "TEXT_MESSAGE_END"})
                                text_started = False
                            await asyncio.sleep(delay)
                            continue
                        raise

                if message is None:
                    yield _sse({"type": "RUN_ERROR", "message": "Failed after retries"})
                    return

                # Save partial text on disconnect checks
                if await request.is_disconnected():
                    partial = "".join(_partial_text_parts)
                    if partial:
                        cleaned = _clean_partial_content(partial)
                        session.messages.append({
                            "role": "assistant",
                            "content": cleaned + "\n[interrupted]",
                        })
                        await sync_backend_state(sid, session)
                    return

                tool_blocks = [b for b in message.content if b.type == "tool_use"]
                has_tool_calls = len(tool_blocks) > 0

                if text_started and not has_tool_calls:
                    yield _sse({"type": "TEXT_MESSAGE_END"})

                yield _sse({"type": "COST_UPDATE", "costCents": round(session.llm_cost_cents, 2), "callCount": session.llm_call_count})

                if not has_tool_calls:
                    session.messages.append({"role": "assistant", "content": _serialize_content(message.content)})
                    break

                # Tool execution — every tool ALWAYS returns a result (even errors)
                # so there are never orphaned tool_result blocks.
                tool_names = {b.name for b in tool_blocks}
                is_terminal = tool_names <= {"session_signal", "update_student_model"}

                tool_results = []
                for block in tool_blocks:
                    if await request.is_disconnected():
                        return
                    yield _sse({"type": "TOOL_CALL_START", "toolCallId": block.id, "toolCallName": block.name})

                    # EVERY tool call MUST produce a result — never leave orphaned
                    try:
                        result = await _execute_tool_block(
                            block=block, session=session, session_id=sid,
                            context_data=context_data, runtime=runtime,
                            request=request, slog=slog,
                        )
                        if not result:
                            result = "(tool returned empty)"
                    except Exception as tool_err:
                        import traceback
                        tb = traceback.format_exc()[-500:]
                        slog.error("Tool %s crashed: %s", block.name, tool_err)
                        result = f"Tool error ({block.name}): {str(tool_err)[:200]}\n{tb}"

                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(result)})
                    yield _sse({"type": "TOOL_CALL_END", "toolCallId": block.id})

                # Save assistant message with tool_use blocks intact
                assistant_content = _serialize_content(message.content)
                session.messages.append({"role": "assistant", "content": assistant_content})

                if is_terminal:
                    slog.info("Terminal tool(s) %s — ending turn", tool_names)
                    break

                # Append tool results to BOTH session.messages AND claude_messages
                # This ensures the tool_use/tool_result pair stays together
                session.messages.append({"role": "user", "content": tool_results})
                # Re-window from session.messages — the pair is now in the source
                claude_messages = apply_context_window(session, session.messages)
                api_kwargs["messages"] = _validate_messages(claude_messages)
                slog.debug("Tool round %d done — %d results, next round messages: %d",
                          rounds, len(tool_results), len(api_kwargs["messages"]))

            # Parse and strip housekeeping tags from the final message
            full_text = "".join(_partial_text_parts)
            _process_housekeeping_tags(session, full_text, context_data, sid, slog)

            # ── Auto-spawn planner when tutor has enough context ──
            _auto_spawn_planner_if_ready(session, runtime, context_data, slog)

            # ── Check for plan completion: emit PLAN_UPDATE if planner finished ──
            if not session.current_plan and hasattr(session, 'agent_runtime') and session.agent_runtime:
                completed = session.agent_runtime.pop_completed()
                for agent in completed:
                    if agent["type"] == "planning" and agent["status"] == "complete" and agent.get("result"):
                        _promote_plan(session, agent["result"])
                        yield _sse({
                            "type": "PLAN_UPDATE",
                            "plan": agent["result"],
                            "sessionObjective": agent["result"].get("session_objective", ""),
                        })
                        plan_result = agent["result"]
                        slog.info("Plan arrived", extra={
                            "event": "PLAN_ARRIVED",
                            "topic_count": len(plan_result.get("_topics", [])),
                            "section_count": len(plan_result.get("sections", [])),
                        })

            # Periodic shadow enrichment — every 5th turn, fire-and-forget
            if session.assistant_turn_count >= 5 and session.assistant_turn_count % 5 == 0:
                _spawn_enrichment_agent(session, runtime, context_data, slog, is_initial=False)

            # ── TURN_END — log the complete turn ──
            _turn_dur = round((_time.monotonic() - _turn_start) * 1000)
            slog.info("Turn complete", extra={
                "event": "TURN_END",
                "duration_ms": _turn_dur,
                "rounds": rounds,
                "text_length": text_length,
                "cost": round(session.llm_cost_cents, 2),
            })

            # Save session
            await sync_backend_state(sid, session)

            yield _sse({"type": "RUN_FINISHED"})

        except LLMBadRequestError as e:
            err_body = getattr(e, "body", {}) or {}
            err_msg = (err_body.get("error", {}).get("message", "") if isinstance(err_body, dict) else str(e))
            if not err_msg:
                err_msg = str(e)  # Fallback to full exception string
            slog.error("LLM BadRequest: %s | body: %s", err_msg, err_body)
            yield _sse({"type": "RUN_ERROR", "message": f"AI request error: {err_msg}"})
        except LLMRateLimitError as e:
            retry_after = extract_retry_after(e)
            wait_msg = f" Try again in {int(retry_after)}s." if retry_after else ""
            yield _sse({"type": "RUN_ERROR", "message": f"AI service busy.{wait_msg}"})
        except LLMConnectionError as e:
            yield _sse({"type": "RUN_ERROR", "message": "Could not connect to AI service."})
        except Exception as e:
            slog.error("Chat error: %s", e, exc_info=True)
            yield _sse({"type": "RUN_ERROR", "message": "Something went wrong. Please try again."})

    # Session lock: only acquire for SSE path. The WebSocket path uses
    # TurnQueue for turn isolation and doesn't need the session lock.
    # Check if this is a WS call (is_disconnected is a lambda, not an HTTP check).
    _use_lock = is_disconnected is None  # SSE path has is_disconnected=None
    if _use_lock:
        await lock.acquire()
    try:
        async for chunk in generate():
            yield chunk
    finally:
        if _use_lock:
            lock.release()
