"""Tutor agentic loop + sub-agent architecture.

The Tutor starts teaching immediately. Background agents handle planning,
asset preparation, and research. Teaching delegation hands off bounded
tasks to focused sub-agents.

This module exposes `_generate_for_turn`, the per-turn pipeline called
by the WebSocket SessionRouter. There are no HTTP routes here — the
WebSocket path is the only entry point for teaching.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re as _re
import uuid

# Pymongo's sync client raises _OperationCancelled when motor's thread-dispatched
# op is cancelled. Semantically a cancellation, but not a subclass of
# asyncio.CancelledError — catch both together everywhere cancel is expected.
try:
    from pymongo.errors import _OperationCancelled as _PyMongoCancelled
    _CANCEL_EXCEPTIONS: tuple = (asyncio.CancelledError, _PyMongoCancelled)
except ImportError:
    _CANCEL_EXCEPTIONS = (asyncio.CancelledError,)

from app.agents.agent_runtime import AgentRuntime, AssessmentState, DelegationState
from app.agents.session import SessionPhase
from app.core.llm import (
    llm_stream,
    is_retryable,
    extract_retry_after,
    LLMBadRequestError,
    LLMRateLimitError,
    LLMConnectionError,
    LLMCallMetadata,
)
from app.core.logging_config import SessionLogger
from app.agents.prompts import build_tutor_prompt, build_assessment_prompt
from app.agents.session import get_or_create_session
from app.services.knowledge.knowledge_state import (
    get_or_init_knowledge_state,
    format_knowledge_state,
    hybrid_search_notes,
    get_knowledge_summary,
)
from app.services.session.session_service import sync_backend_state
from app.tools import (
    TUTOR_TOOLS,
    DELEGATION_TOOLS,
    ASSESSMENT_TOOLS,
    RETURN_TO_TUTOR_TOOL,
    VIDEO_FOLLOW_TOOLS,
    execute_tutor_tool,
)

from app.api.routes import sse as _sse

log = logging.getLogger(__name__)

MAX_ROUNDS = 8  # cap tutor tool rounds
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds, doubles each retry


def _cost_update_event(session) -> dict:
    """Build the canonical COST_UPDATE payload.

    Includes session totals + the current in-flight turn's breakdown so the
    client can show per-turn spend alongside the running total.
    """
    current = session.current_turn_cost()
    return {
        "type": "COST_UPDATE",
        "costCents": round(session.llm_cost_cents + session.tts_cost_cents, 2),
        "llmCostCents": round(session.llm_cost_cents, 2),
        "ttsCostCents": round(session.tts_cost_cents, 2),
        "callCount": session.llm_call_count,
        "ttsCharCount": session.tts_char_count,
        "inputTokens": session.llm_total_input_tokens,
        "outputTokens": session.llm_total_output_tokens,
        "currentTurn": current,  # {turn, llmCents, ttsCents, inputTokens, outputTokens, calls, models}
    }


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
                elif isinstance(block, dict) and block.get("type") == "image" and block.get("source"):
                    # Convert Anthropic image format → OpenRouter/OpenAI image_url format
                    src = block["source"]
                    if src.get("type") == "base64" and src.get("data"):
                        mime = src.get("media_type", "image/png")
                        fixed_blocks.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{src['data']}"},
                        })
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

                    # Collect existing tool_use IDs in the assistant message.
                    # Handles both dict blocks AND SDK ContentBlock objects (which
                    # have .type/.id attributes instead of dict keys).
                    existing_ids = set()
                    if isinstance(prev_content, list):
                        for b in prev_content:
                            btype = b.get("type") if isinstance(b, dict) else getattr(b, "type", None)
                            bid = b.get("id") if isinstance(b, dict) else getattr(b, "id", None)
                            if btype == "tool_use" and bid:
                                existing_ids.add(bid)

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

    # Pass 1: Fix duplicate tool_use IDs (reassign, update matching results).
    # Handles both dict blocks AND SDK ContentBlock objects.
    seen_tool_ids = set()
    for i, msg in enumerate(cleaned):
        content = msg.get("content")
        if msg.get("role") == "assistant" and isinstance(content, list):
            for block in content:
                btype = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                if btype != "tool_use":
                    continue
                tid = block.get("id") if isinstance(block, dict) else getattr(block, "id", None)
                if tid and tid in seen_tool_ids:
                    new_id = f"toolu_{_uuid.uuid4().hex[:24]}"
                    old_id = tid
                    log.warning("Reassigning duplicate tool_use id %s → %s", old_id, new_id)
                    if isinstance(block, dict):
                        block["id"] = new_id
                    else:
                        try:
                            block.id = new_id
                        except (AttributeError, TypeError):
                            # SDK object is frozen — fall back to dict serialization
                            # of the entire message (caller should serialize first,
                            # this is the safety net)
                            log.error("Cannot mutate SDK ContentBlock id; "
                                      "message should have been serialized via "
                                      "_serialize_content() before validation")
                    # Update matching tool_result in the next user message
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

        # Collect tool_use IDs in this assistant message (handles dicts + SDK)
        tool_use_ids = []
        for b in content:
            btype = b.get("type") if isinstance(b, dict) else getattr(b, "type", None)
            bid = b.get("id") if isinstance(b, dict) else getattr(b, "id", None)
            if btype == "tool_use" and bid:
                tool_use_ids.append(bid)
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
_PREFETCH_RE = _re.compile(
    r'<prefetch_context\s+([\s\S]*?)\s*/?>',
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
                    from app.services.knowledge.knowledge_state import upsert_concept_note

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

        elif action == "replan":
            # Tutor signaled the plan is fundamentally wrong — clear it so
            # the planner re-spawns on the next turn with updated context.
            session.current_plan = None
            session.current_topics = []
            session.current_topic_index = -1
            session._planner_spawned = False  # allow re-spawn
            slog.info("Plan: replan triggered", extra={"reason": reason})

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
                context={},
            )
            slog.info("Agent spawned via tag", extra={"type": agent_type, "task": task_desc[:80]})

    # Parse <ui-panel> tags — tutor controls workspace panels + media viewer
    _UI_PANEL_RE = _re.compile(r'<ui-panel\s+([\s\S]*?)/>')
    for _upm in _UI_PANEL_RE.finditer(hk_content):
        _attrs_str = _upm.group(1)
        _attr = lambda name: (_re.search(rf'{name}="([^"]*)"', _attrs_str) or [None, None])[1]
        panel_id = _attr('id')
        action = _attr('action')
        if not panel_id or not action:
            continue
        _pending = context_data.setdefault("_pending_ws_events", [])
        _data = {"id": panel_id, "action": action}
        # Optional attributes for media-viewer and other panels
        for _k in ('language', 'src', 'type', 'title', 'timestamp', 'speed'):
            _v = _attr(_k)
            if _v:
                _data[_k] = _v
        _pending.append({"type": "UI_PANEL", "data": _data})
        slog.info("UI panel: %s %s", action, panel_id)

    # Parse <prefetch_context> tags — tutor requests tool calls to be
    # executed in the BACKGROUND. Results are injected into the next
    # turn's prompt as [PREFETCHED CONTENT]. This avoids tool call
    # latency: the tutor teaches while the system fetches content.
    #
    # Format: <prefetch_context tool="search" query="integration" scope="collection" k="3" />
    #         <prefetch_context tool="fetch" ref="chunk:abc123" />
    #         <prefetch_context tool="peek" ref="resource:xyz" />
    #         <prefetch_context tool="web_search" query="Bernoulli equation derivation" />
    #
    # Max 5 per turn. Total output capped at ~4000 tokens.
    prefetch_requests = list(_PREFETCH_RE.finditer(hk_content))[:5]
    if prefetch_requests:
        import asyncio as _pf_aio

        async def _run_prefetch():
            try:
                parts = []
                total_tokens = 0
                MAX_TOKENS = 4000

                _uid = ""
                _cid = ""
                try:
                    _prof = json.loads(context_data.get("studentProfile", "{}"))
                    _uid = _prof.get("userEmail", "")
                    _sc = json.loads(context_data.get("sessionContext", "{}"))
                    _cid = _sc.get("collection_id", "")
                except (json.JSONDecodeError, TypeError):
                    pass

                for m in prefetch_requests:
                    if total_tokens >= MAX_TOKENS:
                        break
                    attrs_str = m.group(1) or ""
                    # Parse key="value" pairs
                    import re as _pre
                    attrs = dict(_pre.findall(r'(\w+)=["\']([^"\']*)["\']', attrs_str))
                    tool = attrs.get("tool", "search")
                    query = attrs.get("query", "")
                    ref = attrs.get("ref", "")
                    scope = attrs.get("scope", "collection")
                    k = min(int(attrs.get("k", "3")), 5)

                    result_text = ""

                    if tool == "search" and query and _uid:
                        from app.services.content.embedding_service import generate_embedding
                        from byo.shared.store import get_content_store
                        emb = await generate_embedding(query)
                        if emb:
                            hits = await get_content_store().search(
                                emb, user_id=_uid,
                                collection_id=_cid if scope == "collection" else None,
                                k=k, min_score=0.3,
                            )
                            for h in hits:
                                result_text += (
                                    f"\n--- ref: chunk:{h.chunk_id} | {h.resource_name} p.{h.anchor_page} ---\n"
                                    f"{h.content[:600]}\n"
                                )

                    elif tool == "fetch" and ref and _uid:
                        from byo.retrieval.service import fetch as _svc_fetch
                        hit = await _svc_fetch(ref, user_id=_uid)
                        if hit:
                            result_text = (
                                f"--- ref: {ref} | {hit.resource_name} p.{hit.anchor.page if hit.anchor else '?'} ---\n"
                                f"{hit.content[:800]}\n"
                            )

                    elif tool == "peek" and ref and _uid:
                        from byo.retrieval.service import peek as _svc_peek
                        info = await _svc_peek(ref, user_id=_uid)
                        if info:
                            result_text = f"peek({ref}): {json.dumps(info, default=str)[:400]}\n"

                    elif tool == "nearby" and ref and _uid:
                        from byo.retrieval.service import nearby as _svc_nearby
                        direction = attrs.get("direction", "next")
                        neighbors = await _svc_nearby(ref, user_id=_uid, window=k)
                        if neighbors:
                            # Filter to forward-only if direction="next"
                            target_idx = next((n.index for n in neighbors if n.chunk_id == ref), -1)
                            if direction == "next" and target_idx >= 0:
                                neighbors = [n for n in neighbors if n.index > target_idx][:k]
                            for n in neighbors:
                                result_text += (
                                    f"\n--- ref: chunk:{n.chunk_id} | {n.resource_name} p.{n.anchor_page} ---\n"
                                    f"{n.content[:600]}\n"
                                )

                    elif tool == "web_search" and query:
                        try:
                            from app.tools.web_search import web_search
                            result_text = await web_search({"query": query, "limit": 3})
                            result_text = f"web_search(\"{query}\"):\n{(result_text or '')[:600]}\n"
                        except Exception:
                            pass

                    if result_text:
                        parts.append(f"[prefetch: {tool}({query or ref})]\n{result_text}")
                        total_tokens += len(result_text) // 4

                if parts:
                    session.prefetched_content = "\n".join(parts)
                    slog.info("prefetch_context completed: %d calls, ~%d tokens",
                              len(parts), total_tokens)
            except Exception as e:
                slog.warning("prefetch_context failed: %s", e)

        _pf_aio.get_event_loop().create_task(_run_prefetch())



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


CONTENT_TOOL_NAMES = {"search", "fetch", "peek", "nearby", "list_contents"}


# ── Session Phase Controller ──────────────────────────────────────────────────

def _init_session_phase(session, context_data: dict, slog):
    """Set the initial session phase. Always TEACHING — triage is now
    embedded in the per-topic READ-CHECK-TEACH-VERIFY cycle."""
    session.phase = SessionPhase.TEACHING
    slog.info("Phase: TEACHING (diagnostic embedded in teaching cycle)")


def _check_phase_transition(session, agent_output: dict) -> SessionPhase | None:
    """Check if the session should transition to a new phase based on agent signals."""
    phase = session.phase

    if phase == SessionPhase.TRIAGE:
        # Triage runs as a tutor prompt overlay — phase transitions out via the
        # complete_triage tool, which routes through the housekeeping path.
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


# NOTE: `_run_content_tool` was removed in task #11 — content dispatch is now
# unified in `app.tools.retrieval` (search/fetch/peek/nearby/list_contents).
# The adapter is still used internally by those handlers.


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

    # Preserve ALL messages with attachments (images/PDFs) — never drop uploads
    pinned_multimodal = [m for m in old if _has_multimodal(m)]
    old = [m for m in old if not _has_multimodal(m)]
    recent_tokens = _count_messages_tokens(recent)
    pinned_tokens = _count_messages_tokens(pinned_multimodal) if pinned_multimodal else 0

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

    # 4. Pin all messages with attachments at the front (always visible to LLM)
    if pinned_multimodal:
        for i, pm in enumerate(pinned_multimodal):
            result.insert(i, pm)

    final_tokens = _count_messages_tokens(result)
    log.info(
        "Context window applied",
        extra={
            "msg_count": len(result),
            "token_count": final_tokens,
            "pinned_attachments": len(pinned_multimodal),
        },
    )

    return result


# ── Fast start: auto-spawn planner ─────────────────────────────────────────

def _auto_spawn_planner_if_ready(session, runtime, context_data: dict, slog) -> None:
    """Auto-spawn planning agent on turn 1 (BEFORE the tutor responds).

    The planner takes 10-30 seconds. To make it feel responsive, we spawn it
    BEFORE the LLM call so it runs in parallel with the tutor's first response.
    This way the plan is often ready by the time turn 2 starts.

    The planner gets: intent + student model + course map + grounding tools
    (search, fetch, peek, list_contents, web_search). Uses Sonnet for high-quality plans.
    """
    slog.info("[PLANNER_SPAWN] called — current_plan=%s _planner_spawned=%s",
              bool(session.current_plan),
              getattr(session, '_planner_spawned', False))
    # Guard: don't spawn if plan already exists or planner already running
    if session.current_plan:
        slog.info("[PLANNER_SPAWN] skipped — plan already exists")
        return
    if getattr(session, '_planner_spawned', False):
        slog.info("[PLANNER_SPAWN] skipped — already spawned")
        return
    # Check if a pre-built teaching plan exists for the topic in MongoDB.
    # Uses content_search module: exact slug → alias table → text search → regex.
    _slug = None
    if session.problem_data:
        _topics = session.problem_data.get("topics", [])
        _slug = _topics[0] if _topics else None
    if not _slug:
        _slug = (context_data.get("problemSlug") or context_data.get("topicSlug") or "").replace("-", "_")

    try:
        from pymongo import MongoClient as _MC
        import certifi as _cert
        from app.core.config import settings as _s
        import os as _os
        _db = _MC(_s.MONGODB_URI, tlsCAFile=_cert.where(),
                  serverSelectionTimeoutMS=2000)[_os.environ.get("MONGODB_DB", "myprofessor")]

        from app.services.teaching.content_search import find_teaching_plan
        _intent = session.student_intent or context_data.get("studentIntent", "")
        _plan = find_teaching_plan(_db, _slug, _intent, slog)

        if _plan:
            session.current_plan = _plan
            slog.info("[PLANNER_SPAWN] skipped — loaded pre-built teaching plan: %s", _plan.get("slug", "?"))
            return
    except Exception as e:
        slog.warning("[PLANNER_SPAWN] pre-built plan check failed: %s", e)

    # Spawn on first turn — planner runs in background while tutor starts teaching.
    # No need to wait for observations — the planner has intent + student model + course content.
    turn_count = session.assistant_turn_count
    note_count = len((session.student_model or {}).get("notes", {}))

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
                    byo_text = (
                        f"Student uploaded content (collection: {ctx['collection_id']}). "
                        f"Use search(scope='collection', collection_id='{ctx['collection_id']}') or "
                        f"list_contents(scope='collection') to access."
                    )
                if ctx.get("enriched_intent"):
                    byo_text += f"\nEnriched intent: {ctx['enriched_intent'][:300]}"
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        has_course = bool(context_data.get("courseMap"))
        course_instruction = (
            "Use search(scope='course') and fetch/peek on returned refs to inspect relevant course sections and ground your plan in the professor's material."
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

        agent_id = runtime.spawn(
            agent_type="planning",
            description=f"Plan session: {intent[:60]}",
            instructions=plan_instructions,
            context={**context_data},
        )
        session._planner_spawned = True
        slog.info("[PLANNER_SPAWN] spawned agent_id=%s intent=%s", agent_id, intent[:80])
    except Exception as e:
        import traceback
        slog.error("[PLANNER_SPAWN] FAILED: %s\n%s", e, traceback.format_exc())


def _auto_spawn_enrichment(session, runtime, context_data: dict, slog):
    """Auto-spawn shadow enrichment agent on turn 1.

    Runs in background with Haiku + tools (web_search, search, fetch,
    query_knowledge). Results injected on turn 2+.
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
            f"1. Fetch course content for '{topic_title}' (use search(scope='course') then fetch on the best ref)\n"
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


def _auto_spawn_concept_research_if_needed(session, runtime, context_data: dict, slog) -> None:
    """Spawn the concept_research agent for the CURRENT topic if it's a
    concept-type topic and doesn't already have research attached.

    Result lands in topic["_research"] via _promote_concept_research() when the
    next turn pops completed agents. Persisted on the session, so re-research
    is never triggered for the same topic.
    """
    if not runtime:
        return
    if not session.current_topics:
        return
    if not (0 <= session.current_topic_index < len(session.current_topics)):
        return

    topic = session.current_topics[session.current_topic_index]
    topic_type = (topic.get("type") or "concept").lower()
    if topic_type not in ("concept", "concept_topic"):
        return  # Skill / review / drill topics don't need research

    if topic.get("_research"):
        return  # Already researched

    # Idempotency: avoid spawning twice for the same topic in flight
    spawned_key = f"_research_spawned_topic_{session.current_topic_index}"
    if getattr(session, spawned_key, False):
        return

    concept = topic.get("title") or topic.get("name") or "(unknown concept)"
    teaching_notes = topic.get("teaching_notes") or topic.get("notes") or ""

    instructions = (
        f"Generate teaching research for the concept: {concept}\n\n"
        f"Topic context: {teaching_notes[:1200]}\n\n"
        f"Student intent: {(session.student_intent or '')[:300]}\n\n"
        "Output the JSON object as instructed in your system prompt. Use "
        "tools to find a NON-OBVIOUS surprising application — don't settle "
        "for the textbook example."
    )

    try:
        runtime.spawn(
            "concept_research",
            f"ConceptResearch: {concept[:50]}",
            instructions,
            context_data,
        )
        setattr(session, spawned_key, True)
        slog.info("Spawned concept_research agent", extra={"concept": concept[:60]})
    except Exception as e:
        slog.warning("Failed to spawn concept_research agent: %s", e)


def _promote_concept_research(session, research: dict) -> None:
    """Attach a completed concept_research result to the matching topic.

    Matches by concept name (case-insensitive). If no match, drops it.
    """
    if not isinstance(research, dict):
        return
    concept = (research.get("concept") or "").strip().lower()
    if not concept:
        return
    if not session.current_topics:
        return
    for i, topic in enumerate(session.current_topics):
        title = (topic.get("title") or topic.get("name") or "").strip().lower()
        if not title:
            continue
        if title == concept or concept in title or title in concept:
            topic["_research"] = research
            # Clear the in-flight flag now that research is here
            try:
                delattr(session, f"_research_spawned_topic_{i}")
            except AttributeError:
                pass
            return


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


def _format_completed(completed: list[dict]) -> str | None:
    if not completed:
        return None
    lines = []
    for t in completed:
        if isinstance(t, dict):
            lines.append(f"- {t.get('title', '?')} [concept={t.get('concept', '?')}]")
        elif isinstance(t, str):
            lines.append(f"- {t}")
    return "\n".join(lines) if lines else None


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
                yield _sse(_cost_update_event(session))
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
                else:
                    try:
                        result = await execute_tutor_tool(
                            block.name, block.input, context_data=context_data,
                        )
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
                yield _sse(_cost_update_event(session))
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
                        from app.services.session.session_service import sync_backend_state
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
                        from app.services.session.session_service import sync_backend_state
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
                        from app.services.knowledge.knowledge_state import upsert_concept_note
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

                # ── All other tools (including unified retrieval) ──
                else:
                    try:
                        result = await execute_tutor_tool(
                            block.name, block.input, context_data=context_data,
                        )
                    except Exception as e:
                        slog.error("Assessment tool failed: %s", e, exc_info=True, extra={"agent": "assessment", "tool": block.name})
                        result = f"Tool error ({block.name}): {str(e)[:200]}"
                    result_str = result if isinstance(result, str) else json.dumps(result)
                    if not result_str.strip():
                        result_str = "(no output)"
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result_str})

                yield _sse({"type": "TOOL_CALL_END", "toolCallId": block.id})

            assessment.messages.append({"role": "assistant", "content": _serialize_content(message.content)})
            assessment.messages.append({"role": "user", "content": _serialize_content(tool_results)})
            continue

        # No more tool calls — text response to student
        # Append the assistant response to assessment's own history
        assessment.messages.append({"role": "assistant", "content": _serialize_content(message.content)})
        yield _sse({"type": "RUN_FINISHED"})
        return

    yield _sse({"type": "RUN_ERROR", "message": "Too many assessment rounds"})



# ── Tool execution helper ──


async def _execute_tool_block(*, block, session, session_id, context_data, runtime, request, slog):
    """Execute a single tool call block and return the result string.

    Handles the small set of tools the main tutor still calls directly.
    Plan management, agent orchestration, signals, notes, handoffs, and
    delegations are all handled via housekeeping tags now — not tool calls.
    """
    name = block.name
    inp = block.input or {}

    try:
        # ── Unified retrieval tools (task #11) ───────────────────────
        if name in ("search", "fetch", "peek", "nearby", "list_contents"):
            try:
                result = await execute_tutor_tool(name, inp, context_data=context_data)
                return result or f"No results for {name}"
            except Exception as e:
                slog.warning("Retrieval tool %s failed: %s", name, e)
                return f"Retrieval tool error: {e}"

        elif name == "search_images":
            from app.tools.search_images import search_images as _search_images
            query = inp.get("query", "")
            limit = int(inp.get("limit", 3))
            results = await _search_images(query, limit=limit)
            return json.dumps(results) if results else "No images found"

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

        elif name == "control_simulation":
            return json.dumps({"status": "ok", "action": inp.get("action", "unknown")})

        elif name == "web_search":
            from app.tools.web_search import web_search as _web_search
            query = inp.get("query", "")
            results = await _web_search(query) if query else None
            return json.dumps(results) if results else "No results found"

        # ── DSA / System Design / Mock Interview tools ──
        elif name == "run_code":
            from app.tools.code_execution import handle_run_code
            result = await handle_run_code(inp, context_data or {})
            if isinstance(result, dict):
                if "__ws_event" in result:
                    _pending = context_data.setdefault("_pending_ws_events", [])
                    _pending.append(result["__ws_event"])
                return result.get("text", "Code executed.")
            return result if isinstance(result, str) else str(result)

        elif name == "push_code":
            _pending = context_data.setdefault("_pending_ws_events", [])
            _action = inp.get("action", "replace")
            _evt_data = {
                "action": _action,
                "code": inp.get("code", ""),
                "language": inp.get("language", "python"),
                "highlight_lines": inp.get("highlight_lines", []),
            }
            if _action == "insert":
                _evt_data["at_line"] = inp.get("at_line", 1)
            elif _action == "delete_lines":
                _evt_data["lines"] = inp.get("lines", [])
            elif _action == "replace_lines":
                _evt_data["from_line"] = inp.get("from_line", 1)
                _evt_data["to_line"] = inp.get("to_line", 1)
            _pending.append({"type": "CODE_PUSH", "data": _evt_data})
            # Push test cases if provided
            _test_cases = inp.get("test_cases")
            if _test_cases and isinstance(_test_cases, list):
                _pending.append({"type": "TEST_CASES_PUSH", "data": {"test_cases": _test_cases}})
            _labels = {"replace": "Code replaced in editor.", "insert": f"Code inserted at line {inp.get('at_line', 1)}.",
                       "append": "Code appended to editor.", "delete_lines": f"Lines {inp.get('lines', [])} deleted.",
                       "replace_lines": f"Lines {inp.get('from_line')}-{inp.get('to_line')} replaced."}
            _result = _labels.get(_action, "Code pushed to editor.")
            if _test_cases:
                _result += f" {len(_test_cases)} test cases loaded."

            # Persist the new code to the session doc so resume can recover it
            # even if the WS CODE_PUSH event was dropped (navigation, reconnect,
            # turn killed before flush). Only on 'replace' — append/insert/etc.
            # send deltas, not the full code, and the periodic frontend save
            # will catch those up via state.dsaMode → dsaState.code.
            if _action == "replace" and session_id:
                try:
                    from app.services.session.session_service import update_session as _upd
                    _set_doc = {
                        "dsaState.code": inp.get("code", ""),
                        "dsaState.language": inp.get("language", "python"),
                    }
                    if _test_cases and isinstance(_test_cases, list):
                        _set_doc["dsaState.testCases"] = _test_cases
                    await _upd(session_id, _set_doc)
                except Exception as _persist_err:
                    slog.warning("push_code persistence failed: %s", _persist_err)
            return _result

        elif name == "draw_on_canvas":
            _pending = context_data.setdefault("_pending_ws_events", [])
            _pending.append({
                "type": "CANVAS_DRAW",
                "data": {
                    "add_nodes": inp.get("add_nodes", []),
                    "add_edges": inp.get("add_edges", []),
                    "remove": inp.get("remove", []),
                    "update": inp.get("update", []),
                    "annotate": inp.get("annotate", []),
                    "highlight": inp.get("highlight", []),
                    "clear": inp.get("clear", False),
                },
            })
            parts = []
            if inp.get("add_nodes"): parts.append(f"{len(inp['add_nodes'])} nodes added")
            if inp.get("add_edges"): parts.append(f"{len(inp['add_edges'])} connections added")
            if inp.get("remove"): parts.append(f"{len(inp['remove'])} items removed")
            if inp.get("update"): parts.append(f"{len(inp['update'])} items updated")
            if inp.get("highlight"): parts.append(f"{len(inp['highlight'])} items highlighted")
            if inp.get("clear"): parts.append("canvas cleared")
            return "Canvas updated: " + ", ".join(parts) if parts else "Canvas operation complete."

        elif name == "query_knowledge":
            # Removed from active tools but model sometimes still calls it.
            # Route through hybrid_search_notes if we have student info,
            # otherwise return a graceful message.
            course_id, _ = _extract_student_info(context_data)
            user_email = _extract_user_email(context_data)
            if course_id and user_email:
                try:
                    from app.services.student_model.service import hybrid_search_notes
                    return await hybrid_search_notes(course_id, user_email, inp.get("query", ""))
                except Exception as e:
                    slog.debug("query_knowledge failed: %s", e)
            return "No student knowledge records available. Teach from your current context."

        elif name == "update_student_model":
            # Terminal tool — model calls it but we handle notes via housekeeping tags.
            return "Student model updated."

        else:
            slog.warning("Unknown tool: %s", name)
            return f"Tool '{name}' executed (no specific handler)"

    except Exception as e:
        slog.warning("Tool %s failed: %s", name, e)
        return f"Tool error: {e}"


# ── Per-turn entry point (called by SessionRouter over WebSocket) ──


class _FakeRequest:
    """Minimal stand-in for starlette.requests.Request.

    Provides .is_disconnected() and .state.db — the only things
    the agentic-loop pipeline needs from the request object now that
    teaching runs over WebSocket.
    """
    def __init__(self, is_disconnected_fn):
        self._is_disconnected = is_disconnected_fn
        self.state = type("State", (), {"db": None})()

    async def is_disconnected(self) -> bool:
        result = self._is_disconnected()
        if asyncio.iscoroutine(result):
            return await result
        return bool(result)


async def _generate_for_turn(
    *,
    session_id: str,
    messages: list | None = None,
    context: dict | None = None,
    is_session_start: bool = False,
    is_disconnected=None,
    attachments: list | None = None,
):
    """Run a single tutor turn and yield SSE event strings.

    Called by the WebSocket SessionRouter (the only entry point for teaching).
    Sets up session state, applies the context window, then runs the agentic
    loop (LLM stream → tool calls → repeat) inside the generate() closure.
    """
    # Build a fake request that generate() can use
    request = _FakeRequest(is_disconnected or (lambda: False))

    context_data = extract_context(context) if context else {}
    session, sid = await get_or_create_session(session_id)

    # Message setup
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
                    # OpenRouter format: image_url with data URI
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{data}"},
                    })
                elif mime == "application/pdf" or fname.lower().endswith(".pdf"):
                    # OpenRouter PDF format
                    content_parts.append({
                        "type": "file",
                        "file": {"filename": fname, "file_data": f"data:application/pdf;base64,{data}"},
                    })
                else:
                    # Other files: use file content type
                    content_parts.append({
                        "type": "file",
                        "file": {"filename": fname, "file_data": f"data:{mime};base64,{data}"},
                    })
            last_user["content"] = content_parts

            # Fire-and-forget: upload to GCS + persist metadata (non-blocking)
            async def _bg_upload(session_id, attachments, session_obj):
                try:
                    from app.services.session.attachment_storage import upload_attachments
                    meta = await upload_attachments(session_id, attachments)
                    if meta:
                        session_obj.attachment_meta = meta
                        from app.services.session.session_service import update_session
                        await update_session(session_id, {"attachments": meta})
                except Exception as e:
                    log.warning("Background attachment upload failed: %s", e)

            import asyncio as _aio
            _aio.create_task(_bg_upload(sid, attachments, session))

    # Re-inject stored attachments for restored sessions (images from previous turns)
    if session.attachment_meta and claude_messages:
        _stored_images = [a for a in session.attachment_meta if a.get("data_b64") and a.get("mime_type", "").startswith("image/")]
        if _stored_images and not any(_has_multimodal(m) for m in claude_messages):
            # No images in current messages — inject stored ones into first user message
            for m in claude_messages:
                if m.get("role") == "user":
                    _existing = m.get("content", "")
                    _parts = [{"type": "text", "text": _existing}] if isinstance(_existing, str) else (list(_existing) if isinstance(_existing, list) else [])
                    for _sa in _stored_images[:3]:  # max 3 images to avoid token explosion
                        _parts.insert(0, {
                            "type": "image_url",
                            "image_url": {"url": f"data:{_sa['mime_type']};base64,{_sa['data_b64']}"},
                        })
                    _parts.insert(0, {"type": "text", "text": "[Previously uploaded files — still available for reference]"})
                    m["content"] = _parts
                    break

    user_email = _extract_user_email(context_data)
    slog = SessionLogger(log, session_id=sid, user=user_email or "")

    if not claude_messages:
        yield _sse({"type": "RUN_ERROR", "message": "No messages provided"})
        return

    # ── The generate() closure ──
    # FULL pipeline: assessment routing, delegation routing, triage,
    # tool execution, agentic loop, housekeeping. Defined as a closure
    # so it can yield SSE events while capturing session state.

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
                        from app.services.content.content_resolver import resolve_content, format_content_brief
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

            # Plan setup — emit PLAN_UPDATE if we already have one cached.
            # Otherwise the background planner spawned below will deliver one.
            if is_session_start and not is_video_mode and session.current_plan:
                yield _sse({"type": "PLAN_UPDATE", "plan": session.current_plan, "sessionObjective": session.session_objective or "", "currentTopicIndex": session.current_topic_index})

            # ── Spawn planner BEFORE LLM call so it runs in parallel with the tutor ──
            # The planner takes 10-30s. By spawning before the tutor responds,
            # we give it the entire turn duration to complete.
            if not is_video_mode and not session.current_plan:
                _auto_spawn_planner_if_ready(session, runtime, context_data, slog)

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
                elif agent["type"] == "concept_research" and agent["status"] == "complete" and agent.get("result"):
                    _promote_concept_research(session, agent["result"])

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

            # ── Auto-inject BYO collection context ──
            # If synthesis exists: use it (replaces Level 1+2, strictly better)
            # Otherwise: fall back to 3-level preload (Level 1+2+3)
            # Level 3 (intent-matched chunks) always runs as supplement
            _sc_str = context_data.get("sessionContext", "")
            if _sc_str and not context_data.get("_byoPreloaded"):
                try:
                    _sc = json.loads(_sc_str) if isinstance(_sc_str, str) else _sc_str
                    _byo_cid = _sc.get("collection_id") if isinstance(_sc, dict) else None
                    _byo_rids = _sc.get("resource_ids") if isinstance(_sc, dict) else None

                    if _byo_cid:
                        _byo_uid = None
                        try:
                            _prof = json.loads(context_data.get("studentProfile", "{}"))
                            _byo_uid = _prof.get("userEmail", "")
                        except (json.JSONDecodeError, TypeError):
                            pass

                        if _byo_uid:
                            from app.core.mongodb import get_mongo_db
                            _byo_db = get_mongo_db()
                            _byo_parts = []
                            _used_synthesis = False

                            # ── Check for synthesis (replaces Level 1+2) ──
                            try:
                                _col_doc = await _byo_db.collections.find_one(
                                    {"collection_id": _byo_cid},
                                    {"synthesis": 1, "title": 1},
                                )
                                _synthesis = (_col_doc or {}).get("synthesis")
                                if _synthesis and _synthesis.get("overview"):
                                    from byo.processing.synthesis import format_synthesis_for_prompt
                                    _col_title = (_col_doc or {}).get("title", "")
                                    # Pass resource docs for direct URL mapping
                                    _synth_text = format_synthesis_for_prompt(
                                        _synthesis, _col_title,
                                        resource_docs=_resources,
                                    )
                                    if _synth_text:
                                        _byo_parts.append(_synth_text)
                                        _used_synthesis = True
                                        slog.info("BYO using synthesis for collection %s", _byo_cid[:8])
                            except Exception as _synth_err:
                                slog.debug("BYO synthesis lookup failed: %s", _synth_err)

                            # ── Fallback: Level 1+2 if no synthesis ──
                            _resources = []
                            if not _used_synthesis:
                                # Level 1: Catalog — resource names + topics (~300 tokens)
                                # Level 2: TOC — ordered chunk titles per resource (~500 tokens)
                                async for _r in _byo_db.byo_resources.find(
                                    {"collection_id": _byo_cid, "user_id": _byo_uid, "status": "ready"},
                                    {"resource_id": 1, "original_name": 1, "chunk_count": 1,
                                     "topics": 1, "toc": 1, "meta": 1, "_id": 0},
                                ):
                                    _resources.append(_r)

                                if _resources:
                                    _cat_lines = [f"[COLLECTION CONTENT — {len(_resources)} resource(s)]"]
                                    for _ri, _r in enumerate(_resources, 1):
                                        _name = _r.get("original_name", "untitled")
                                        _pages = (_r.get("meta") or {}).get("pages", "?")
                                        _topics = ", ".join((_r.get("topics") or [])[:8])
                                        _chunks = _r.get("chunk_count", "?")
                                        _cat_lines.append(
                                            f"  {_ri}. {_name} — {_pages} pages, {_chunks} chunks"
                                            + (f", topics: [{_topics}]" if _topics else "")
                                        )
                                    _byo_parts.append("\n".join(_cat_lines))

                                    # Level 2: TOC from resource docs
                                    _toc_resources = _resources
                                    if _byo_rids:
                                        _toc_resources = [r for r in _resources if r.get("resource_id") in _byo_rids]
                                    if not _toc_resources:
                                        _toc_resources = _resources[:3]  # cap at 3 for large collections

                                    for _r in _toc_resources:
                                        _toc = _r.get("toc") or []
                                        if _toc:
                                            _toc_lines = [f"\n[TABLE OF CONTENTS — {_r.get('original_name', 'resource')}]"]
                                            for _entry in _toc[:20]:  # cap at 20 entries
                                                _pg = f"p.{_entry.get('page')}" if _entry.get("page") else ""
                                                _sec = _entry.get("section") or ""
                                                _title = _entry.get("title") or _sec or f"Section {_entry.get('index', 0) + 1}"
                                                _cid = _entry.get("chunk_id", "")[:12]
                                                _toc_lines.append(f"  [{_entry.get('index', 0)}] {_title} {_pg} (ref: chunk:{_cid})")
                                            _byo_parts.append("\n".join(_toc_lines))
                            else:
                                # Still need resource list for Level 3 search
                                async for _r in _byo_db.byo_resources.find(
                                    {"collection_id": _byo_cid, "user_id": _byo_uid, "status": "ready"},
                                    {"resource_id": 1, "_id": 0},
                                ):
                                    _resources.append(_r)

                            # ── Level 3: Intent-matched content from Qdrant ──
                            # Always runs as supplement (even with synthesis)
                            _intent = session.student_intent or ""
                            if _intent and _resources:
                                try:
                                    from byo.shared.store import get_content_store
                                    from app.services.content.embedding_service import generate_embedding
                                    _emb = await generate_embedding(_intent)
                                    if _emb:
                                        _store = get_content_store()
                                        _search_kwargs = dict(
                                            user_id=_byo_uid,
                                            collection_id=_byo_cid,
                                            k=5, min_score=0.3,
                                        )
                                        if _byo_rids:
                                            _search_kwargs["resource_id"] = _byo_rids[0]
                                        _hits = await _store.search(_emb, **_search_kwargs)
                                        if _hits:
                                            _content_lines = [f"\n[CONTENT — most relevant for \"{_intent[:60]}\"]"]
                                            _token_budget = 2500
                                            _used = 0
                                            for _h in _hits:
                                                _text = _h.content or _h.segment_content or ""
                                                _toks = len(_text) // 4
                                                if _used + _toks > _token_budget:
                                                    _text = _text[:(_token_budget - _used) * 4]
                                                _pg = _h.anchor_page or "?"
                                                _title = _h.title or ""
                                                _header = f"--- ref: chunk:{_h.chunk_id[:12]} | {_h.resource_name} p.{_pg}"
                                                if _title:
                                                    _header += f" | {_title[:80]}"
                                                _header += " ---"
                                                _content_lines.append(f"\n{_header}\n{_text}")
                                                _used += len(_text) // 4
                                                if _used >= _token_budget:
                                                    break
                                            _byo_parts.append("\n".join(_content_lines))
                                except Exception as _search_err:
                                    slog.debug("BYO content search failed: %s", _search_err)

                            if _byo_parts:
                                _preloaded = "\n\n".join(_byo_parts)
                                context_data["_byoPreloaded"] = _preloaded
                                slog.info(
                                    "BYO preloaded: %d resources, %d chars, synthesis=%s",
                                    len(_resources), len(_preloaded), _used_synthesis,
                                )
                except Exception as _byo_err:
                    log.debug("BYO context pre-load failed: %s", _byo_err)

            # ── Inject prefetched content from previous turn's <prefetch> tag ──
            if hasattr(session, 'prefetched_content') and session.prefetched_content:
                context_data["_prefetchedContent"] = session.prefetched_content
                session.prefetched_content = None  # one-shot: clear after use

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

            # ── DSA / SD / Mock mode detection ──────────────────────
            _sc_raw = context_data.get("sessionContext", "")
            try:
                _sc_obj = json.loads(_sc_raw) if isinstance(_sc_raw, str) and _sc_raw else (_sc_raw if isinstance(_sc_raw, dict) else {})
            except (json.JSONDecodeError, TypeError):
                _sc_obj = {}

            _session_mode = _sc_obj.get("mode", session.session_mode or "general")
            if _session_mode != session.session_mode and _session_mode in ("dsa", "sd", "mock_interview"):
                session.session_mode = _session_mode
                slog.info("Session mode set: %s", _session_mode, extra={"event": "SESSION_MODE"})

                # Create blueprint if not already frozen
                if not session.blueprint:
                    from app.agents.blueprint import classify_intent
                    _bp = await classify_intent(
                        text=session.student_intent or "",
                        explicit_mode=_session_mode,
                        explicit_interaction=_sc_obj.get("interaction"),
                        explicit_slug=_sc_obj.get("problem_slug"),
                        explicit_company=_sc_obj.get("company"),
                        explicit_timer=_sc_obj.get("timer_minutes"),
                    )
                    session.blueprint = _bp.to_dict()
                    slog.info("Blueprint frozen: mode=%s interaction=%s ui=%s sections=%s",
                              _bp.mode, _bp.interaction, _bp.ui_layout,
                              _bp.prompt_sections, extra={"event": "BLUEPRINT_FROZEN"})

                # Load problem data on first turn (non-blocking — skip if MongoDB unavailable)
                _problem_slug = _sc_obj.get("problem_slug")
                if _problem_slug and not session.problem_data:
                    try:
                        from pymongo import MongoClient as _MC
                        import certifi as _cert
                        from app.core.config import settings as _settings
                        _mdb = _MC(
                            _settings.MONGODB_URI,
                            tlsCAFile=_cert.where(),
                            serverSelectionTimeoutMS=3000,
                            connectTimeoutMS=3000,
                        )["tutor_v2"]
                        # For mock interviews, mockType determines whether it's a DSA or SD problem
                        _mock_type = _sc_obj.get("mockType", "dsa")
                        _is_sd = _session_mode == "sd" or (_session_mode == "mock_interview" and _mock_type == "sd")
                        _coll = "sd_problems" if _is_sd else "dsa_problems"
                        session.problem_data = _mdb[_coll].find_one({"slug": _problem_slug}, {"_id": 0})
                        if session.problem_data:
                            slog.info("Loaded problem: %s", _problem_slug)
                    except Exception as _pe:
                        slog.warning("Problem load skipped (MongoDB unavailable): %s", _pe)

                # Load teaching plan for the topic
                if not session.current_plan:
                    try:
                        _topic_slug = None
                        if session.problem_data:
                            _topics = session.problem_data.get("topics", [])
                            _topic_slug = _topics[0] if _topics else None
                        if not _topic_slug:
                            _topic_slug = _problem_slug or (_sc_obj.get("problem_slug", "") or "").replace("-", "_")
                        if _topic_slug:
                            from pymongo import MongoClient as _MC2
                            import certifi as _cert2
                            from app.core.config import settings as _s2
                            _tdb = _MC2(_s2.MONGODB_URI, tlsCAFile=_cert2.where(), serverSelectionTimeoutMS=2000)["tutor_v2"]
                            _plan_doc = _tdb["teaching_plans"].find_one({"slug": _topic_slug}, {"_id": 0})
                            if not _plan_doc:
                                _plan_doc = _tdb["teaching_plans"].find_one({"slug": _topic_slug.replace("_", "-")}, {"_id": 0})
                            if _plan_doc:
                                session.current_plan = _plan_doc
                                slog.info("Loaded teaching plan: %s", _topic_slug)
                    except Exception as _tpe:
                        slog.warning("Teaching plan load skipped: %s", _tpe)

                # Mock interview: initialize timer
                if _session_mode == "mock_interview":
                    import time as _t
                    session.mock_start_time = _t.time()
                    session.mock_timer_minutes = _sc_obj.get("timer_minutes", 45)
                    session.mock_company = _sc_obj.get("company", "generic")
                    session.mock_phase = "intro"

            # Inject code/canvas/interview/test state into context + persist on session
            _test_results = _sc_obj.get("testResults")
            if _test_results:
                context_data["testResults"] = _test_results

            _active_panels = _sc_obj.get("activePanels")
            if _active_panels:
                context_data["activePanels"] = _active_panels

            if session.session_mode in ("dsa", "mock_interview"):
                _code_state = _sc_obj.get("codeState")
                if _code_state:
                    context_data["codeState"] = _code_state
                    session.code_state = _code_state
            if session.session_mode == "sd":
                _canvas_state = _sc_obj.get("canvasState")
                if _canvas_state:
                    context_data["canvasState"] = _canvas_state
                    session.canvas_state = _canvas_state
                _canvas_snap = _sc_obj.get("canvasSnapshot")
                if _canvas_snap:
                    context_data["_canvasSnapshot"] = _canvas_snap
            if session.session_mode == "mock_interview":
                # Use client-side MockEngine state (real-time silence, hints, phase)
                _client_state = _sc_obj.get("interviewState")
                if _client_state:
                    context_data["interviewState"] = _client_state
                elif session.mock_start_time:
                    # Fallback: compute from session fields (less accurate)
                    import time as _t
                    _elapsed = _t.time() - session.mock_start_time
                    context_data["interviewState"] = {
                        "phase": session.mock_phase,
                        "elapsed": f"{int(_elapsed//60)}:{int(_elapsed%60):02d}",
                        "hints_used": session.mock_hints_used,
                        "silence": "0s",
                        "timer_minutes": session.mock_timer_minutes,
                        "company": session.mock_company,
                    }

            # Problem metadata for prompt injection
            if session.problem_data:
                _pd = session.problem_data
                _problem_json = {
                    "name": _pd.get("name"),
                    "difficulty": _pd.get("difficulty"),
                    "topics": _pd.get("topics", []),
                    "description": _pd.get("description", ""),
                    "examples": _pd.get("examples", []),
                    "constraints": _pd.get("constraints", []),
                    "hints": _pd.get("hints", []),
                    "optimal_complexity": _pd.get("optimal_complexity", {}),
                    "test_cases": _pd.get("test_cases", [])[:5],
                    "starter_code": _pd.get("starter_code", {}),
                }
                # SD enriched fields — pass ALL to tutor for teaching/practice/mock
                for _ef in ("level_expectations", "edge_cases", "follow_ups",
                            "deep_dives", "common_mistakes", "solution_outline",
                            "teaching_notes", "requirements", "key_decisions",
                            "evaluation_rubric"):
                    if _pd.get(_ef):
                        _problem_json[_ef] = _pd[_ef]
                context_data["problemData"] = json.dumps(_problem_json, indent=2)

            tutor_prompt = build_tutor_prompt({
                **context_data,
                "session_mode": session.session_mode,
                "prompt_sections": session.blueprint.get("prompt_sections") if session.blueprint else None,
                "interaction": session.blueprint.get("interaction", "study") if session.blueprint else "study",
                "studentModel": json.dumps(session.student_model, indent=2) if session.student_model else None,
                "teachingPlan": json.dumps(session.current_plan, indent=2, default=str) if session.current_plan else None,
                "currentTopic": (
                    json.dumps(session.current_topics[session.current_topic_index], indent=2)
                    if session.current_topics and 0 <= session.current_topic_index < len(session.current_topics)
                    else None
                ),
                "conceptResearch": (
                    json.dumps(
                        session.current_topics[session.current_topic_index].get("_research"),
                        indent=2,
                    )
                    if session.current_topics
                    and 0 <= session.current_topic_index < len(session.current_topics)
                    and session.current_topics[session.current_topic_index].get("_research")
                    else None
                ),
                "completedTopics": _format_completed(session.completed_topics),
                "sessionScope": _format_session_scope(session),
                "agentResults": agent_results_str,
                "planAccountability": _build_plan_accountability(session),
                "checkpointAndPace": _build_checkpoint_and_pace(session),
                "_housekeepingDue": _housekeeping_due,
            })

            # Spawn concept_research for the current topic if needed (runs
            # in parallel with the tutor's response — result lands next turn).
            _auto_spawn_concept_research_if_needed(session, runtime, context_data, slog)

            # Track topic dwell time for pace nudges
            _track_topic_dwell(session)

            # ── Tool filtering ──────────────────────────────────
            # The schema includes tools used by sub-agents (assessment,
            # delegation, planner, enrichment) — strip those out for the
            # main tutor. Plan/agent/notes/handoff control all happens via
            # housekeeping tags now, not tool calls — those tools are gone
            # from the schema entirely.
            _removed_tools = {
                "web_search", "search_images",  # disabled — not working reliably
                "query_knowledge",              # student model already in context
                "update_student_model",         # tutor uses <notes> housekeeping tag
            }
            is_first_turn = (session.assistant_turn_count == 0)

            # complete_triage only available during triage phase
            if session.phase != SessionPhase.TRIAGE:
                _removed_tools.add("complete_triage")

            # First 3 turns: remove retrieval lookup tools — tutor should
            # teach from plan + course map context, not fetch content. Teaches
            # immediately. Re-enabled from turn 4 onwards. (Unified retrieval
            # surface: search/fetch/peek/nearby/list_contents.)
            #
            # EXCEPTION: when a BYO collection is in scope, the tutor MUST
            # be able to discover what the student uploaded — there is no
            # static map for BYO content the way there is for course content.
            # Stripping retrieval here makes the tutor ask clueless
            # clarifying questions instead of just listing the materials.
            byo_in_scope = False
            _sc_str = context_data.get("sessionContext", "")
            if _sc_str:
                try:
                    _sc = json.loads(_sc_str) if isinstance(_sc_str, str) else _sc_str
                    byo_in_scope = bool(_sc.get("collection_id"))
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
            if (
                session.assistant_turn_count < 3
                and session.phase != SessionPhase.TRIAGE
                and not byo_in_scope
            ):
                _removed_tools |= {"search", "fetch", "peek", "nearby", "list_contents"}

            # ── DSA/SD/Mock tool filtering (blueprint-driven when available) ──
            _bp = session.blueprint
            if _bp and _bp.get("tools_enable") is not None:
                _removed_tools |= {"run_code", "push_code", "draw_on_canvas", "complete_triage"}
                _removed_tools -= set(_bp.get("tools_enable", []))
                _removed_tools |= set(_bp.get("tools_disable", []))
            elif session.session_mode == "dsa":
                _removed_tools -= {"run_code", "push_code"}
                _removed_tools |= {"draw_on_canvas", "complete_triage"}
            elif session.session_mode == "sd":
                _removed_tools -= {"draw_on_canvas"}
                _removed_tools |= {"run_code", "push_code", "complete_triage"}
            elif session.session_mode == "mock_interview":
                # Mock: tutor has NO code/canvas tools — student does everything
                _removed_tools |= {"run_code", "push_code", "draw_on_canvas", "complete_triage"}
            else:
                _removed_tools |= {"run_code", "push_code", "draw_on_canvas"}

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
            _euler_ui_sent = set()  # track which inline <euler-ui> tags we've already sent

            session.assistant_turn_count += 1
            slog.set_turn(session.assistant_turn_count)
            slog.info("Turn started", extra={"event": "TURN_START"})

            valid_messages = _validate_messages(claude_messages)

            # Inject canvas snapshot as image in last user message (SD mode only)
            _snap = context_data.get("_canvasSnapshot")
            if _snap and session.session_mode == "sd":
                # Only send if canvas changed (compare hash with last turn)
                import hashlib as _hl
                _snap_hash = _hl.md5(_snap[:200].encode() if isinstance(_snap, str) else _snap[:200]).hexdigest()
                _last_hash = getattr(session, '_last_canvas_hash', None)
                if _snap_hash != _last_hash:
                    session._last_canvas_hash = _snap_hash
                    _snap_b64 = _snap.split(",")[1] if "," in _snap else _snap
                    # Validate base64 — skip if empty or too short (blank canvas)
                    if not _snap_b64 or len(_snap_b64) < 100:
                        slog.info("Canvas snapshot skipped (empty/too small)")
                    elif valid_messages:
                        _last_user = None
                        for _m in reversed(valid_messages):
                            if _m.get("role") == "user":
                                _last_user = _m
                                break
                        if _last_user:
                            _existing = _last_user.get("content", "")
                            _parts = []
                            if isinstance(_existing, str):
                                _parts.append({"type": "text", "text": _existing})
                            elif isinstance(_existing, list):
                                _parts.extend(_existing)
                            _parts.append({"type": "text", "text": "[Canvas snapshot — current state of the student's architecture diagram]"})
                            _parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_snap_b64}"}})
                            _last_user["content"] = _parts
                            slog.info("Canvas snapshot injected (%d bytes)", len(_snap_b64))

            api_kwargs = {
                "system": tutor_prompt,
                "messages": valid_messages,
                "model": settings.tutor_model,
                "max_tokens": 32768,
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

                                # ── Inline <euler-ui> tag detection ──
                                # Scan accumulated text for complete <euler-ui .../> tags.
                                # Track sent positions to avoid duplicate sends.
                                _accumulated = "".join(_partial_text_parts)
                                for _ui_m in _re.finditer(r'<euler-ui\s+([\s\S]*?)/>', _accumulated):
                                    _tag_pos = _ui_m.start()
                                    if _tag_pos in _euler_ui_sent:
                                        continue
                                    _euler_ui_sent.add(_tag_pos)
                                    _ui_attrs = _ui_m.group(1)
                                    _ui_data = {}
                                    for _k in ('panel', 'action', 'src', 'type', 'title', 'timestamp', 'speed', 'language', 'code'):
                                        _am = _re.search(rf'{_k}="([^"]*)"', _ui_attrs)
                                        if _am:
                                            _ui_data[_k] = _am.group(1)
                                    if _ui_data.get('panel') and _ui_data.get('action'):
                                        _ui_data['id'] = _ui_data.pop('panel')
                                        yield _sse({"type": "UI_PANEL", "data": _ui_data})
                                        slog.info("Inline euler-ui: %s %s", _ui_data.get('action'), _ui_data.get('id'))

                                yield _sse({"type": "TEXT_MESSAGE_CONTENT", "delta": text})

                            message = await stream.get_final_message()
                        break
                    except _CANCEL_EXCEPTIONS:
                        # Turn cancelled (asyncio.CancelledError or pymongo._OperationCancelled)
                        # Save partial message cleanly
                        partial = "".join(_partial_text_parts)
                        if partial:
                            cleaned = _clean_partial_content(partial)
                            session.messages.append({
                                "role": "assistant",
                                "content": cleaned + "\n[interrupted]",
                            })
                            # Parse housekeeping from whatever the LLM produced
                            # before cancellation. The regex requires closing tags
                            # so an incomplete block is a safe no-op. If the model
                            # had already emitted </teaching-housekeeping> we still
                            # want to honor the handoff/notes/signal/plan-modify.
                            try:
                                _process_housekeeping_tags(session, partial, context_data, sid, slog)
                            except Exception as _hk_err:
                                slog.warning("Housekeeping parse on cancel failed: %s", _hk_err)
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
                        # Parse housekeeping from the partial — if the LLM had
                        # already emitted </teaching-housekeeping> before the
                        # disconnect, we still want to honor the handoff /
                        # notes / signal / plan-modify.
                        try:
                            _process_housekeeping_tags(session, partial, context_data, sid, slog)
                        except Exception as _hk_err:
                            slog.warning("Housekeeping parse on disconnect failed: %s", _hk_err)
                        await sync_backend_state(sid, session)
                    return

                tool_blocks = [b for b in message.content if b.type == "tool_use"]
                has_tool_calls = len(tool_blocks) > 0

                if text_started and not has_tool_calls:
                    yield _sse({"type": "TEXT_MESSAGE_END"})

                yield _sse(_cost_update_event(session))

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
                    # Skip SSE events for terminal/silent tools (no visible delay to student)
                    if not is_terminal:
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
                    if not is_terminal:
                        yield _sse({"type": "TOOL_CALL_END", "toolCallId": block.id})

                    # Drain pending WS events (from push_code, draw_on_canvas, run_code)
                    _pending_evts = context_data.pop("_pending_ws_events", [])
                    for _evt in _pending_evts:
                        yield _sse(_evt)

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

            # Drain any WS events from housekeeping (UI_PANEL, etc.)
            _hk_events = context_data.pop("_pending_ws_events", [])
            for _hk_evt in _hk_events:
                yield _sse(_hk_evt)

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

    # WebSocket path uses TurnQueue for turn isolation; session lock not needed.
    async for chunk in generate():
        yield chunk
