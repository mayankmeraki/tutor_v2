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

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.agents.agent_runtime import AgentRuntime, AssessmentState, DelegationState
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
from app.agents.prompts import SKILL_MAP, build_tutor_prompt, build_byo_tutor_prompt, build_assessment_prompt
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
    MQL_TOOLS,
    MQL_TOOL_NAMES,
    DELEGATION_TOOLS,
    ASSESSMENT_TOOLS,
    COMPLETE_ASSESSMENT_TOOL,
    HANDBACK_TO_TUTOR_TOOL,
    RETURN_TO_TUTOR_TOOL,
    VIDEO_FOLLOW_TOOLS,
    VIDEO_CONTROL_TOOLS,
    execute_tutor_tool,
    execute_mql_tool,
)

from app.core.rate_limit import check_rate_limit_chat as _check_rate_limit
from app.api.routes import sse as _sse
from app.api.routes.auth import get_optional_user

log = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

def _sse_raw(data: dict) -> str:
    """Format a single SSE event as a string (for non-generator error responses)."""
    return f"data: {json.dumps(data)}\n\n"

MAX_ROUNDS = 6  # cap tutor tool rounds — prevents content-gathering loops
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds, doubles each retry


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
        "active board": "activeBoard",
        "previous boards": "previousBoards",
        "video state": "videoState",
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


def _extract_collection_id(context_data: dict) -> str | None:
    """Extract collectionId from student profile (BYO mode indicator)."""
    profile_str = context_data.get("studentProfile", "")
    if not profile_str:
        return None
    try:
        profile = json.loads(profile_str)
        return profile.get("collectionId")
    except (json.JSONDecodeError, TypeError):
        return None


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
        # If all blocks are text, join into a single string
        if all(b.get("type") == "text" for b in result):
            return "\n".join(b.get("text", "") for b in result)
        return result
    return str(content)


# ── Context management — conversation windowing + Haiku summarization ───────

import re as _re

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
            model=settings.SUMMARIZATION_MODEL,
            system="You are a concise tutoring session summarizer.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        new_summary = response.content[0].text.strip()

        # Track internal LLM cost on the session
        if response.usage:
            session.track_llm_usage(
                settings.SUMMARIZATION_MODEL,
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


def apply_context_window(session, messages: list[dict]) -> list[dict]:
    """Apply conversation windowing to fit within token budget.

    Strategy:
    1. Keep last RECENT_MESSAGE_COUNT messages in full (board-draw content intact)
    2. Prepend conversation summary (replaces oldest messages)
    3. Between summary and recent: compressed messages (JSONL stripped) that fit budget
    4. Hard enforce MESSAGES_TOKEN_BUDGET
    """
    if len(messages) <= RECENT_MESSAGE_COUNT:
        return messages

    recent = messages[-RECENT_MESSAGE_COUNT:]
    old = messages[:-RECENT_MESSAGE_COUNT]
    recent_tokens = _count_messages_tokens(recent)

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
        available = MESSAGES_TOKEN_BUDGET - recent_tokens - summary_tokens

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

    final_tokens = _count_messages_tokens(result)
    log.info(
        "Context window applied",
        extra={
            "msg_count": len(result),
            "token_count": final_tokens,
        },
    )

    return result


# ── Fast start: auto-spawn planner ─────────────────────────────────────────

def _auto_spawn_planner(session, runtime, context_data: dict, slog) -> None:
    """Pre-spawn planning agent at session start so plan builds in background.

    The tutor starts teaching / calibrating immediately without waiting.
    Plan lands in completed_queue by turn 2 or 3.
    """
    try:
        intent = session.student_intent or "general study session"
        spawn_context = {
            **context_data,
            "sessionScope": None,
            "completedTopics": None,
            "studentModel": None,
            "lastAssessmentSummary": None,
            "tutorNotes": None,
        }
        runtime.spawn(
            agent_type="planning",
            description=f"Plan session: {intent[:60]}",
            instructions=(
                f"The student wants to study: {intent}\n"
                "Create a teaching plan based on the course content and student knowledge state.\n"
                "Use get_section_content to inspect relevant sections, then output JSONL."
            ),
            context=spawn_context,
        )
        # Flag so the tutor doesn't spawn a duplicate planner
        session._planner_auto_spawned = True
        slog.info("Auto-spawned planning agent at session start",
                   extra={"intent": intent[:80]})
    except Exception as e:
        slog.warning("Failed to auto-spawn planner: %s", e)


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

    # Build sub-agent tools: content tools + return_to_tutor
    sub_tools = DELEGATION_TOOLS + [RETURN_TO_TUTOR_TOOL]

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
                    model=settings.TUTOR_MODEL,
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
                    model=settings.TUTOR_MODEL,
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
    slog.info("POST /api/chat", extra={"msg_count": msg_count, "preview": preview})

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

            # ── Step 2b: Auto-spawn planning agent on session start ───
            # Pre-spawn so plan builds while tutor greets / calibrates.
            # Skip in video mode — the video IS the plan.
            if is_session_start and not session.current_plan and context_data.get("courseMap") and not is_video_mode:
                collection_id_check = _extract_collection_id(context_data)
                if not collection_id_check:  # skip BYO — only course mode
                    _auto_spawn_planner(session, runtime, context_data, slog)

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

            # ── Step 3b: Check delegation → route to sub-agent ────────
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

            # ── Step 5: Detect BYO/voice mode and build appropriate prompt ───
            agent_results_str = _format_agent_results(completed) if completed else None
            collection_id = _extract_collection_id(context_data)
            user_email = _extract_user_email(context_data)
            teaching_mode = _extract_teaching_mode(context_data)
            session.teaching_mode = teaching_mode  # Persist for session restore
            is_byo = bool(collection_id)

            if is_byo:
                # BYO mode — build lean context and use MQL tools
                try:
                    from app.services.lean_context import build_lean_context
                    lean_ctx = await build_lean_context(
                        collection_id, user_email or "anonymous", session_id
                    )
                    context_data["leanContext"] = lean_ctx
                except Exception as e:
                    slog.warning("Failed to build lean context: %s", e)
                    context_data["leanContext"] = f"[Error loading context for collection {collection_id}]"

                tutor_prompt = build_byo_tutor_prompt({
                    **context_data,
                    "studentModel": json.dumps(session.student_model, indent=2) if session.student_model else None,
                    "agentResults": agent_results_str,
                    "assessmentResult": assessment_result_ctx,
                })
                active_tools = MQL_TOOLS + [t for t in TUTOR_TOOLS if t["name"] in (
                    "search_images", "web_search", "control_simulation",
                    "spawn_agent", "check_agents", "update_student_model",
                    "handoff_to_assessment", "delegate_teaching",
                    "log_knowledge", "query_knowledge",
                )]
                slog.info("BYO mode active, MQL tools enabled")
            else:
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
                    "teachingMode": teaching_mode,
                })
                if is_video_mode:
                    active_tools = VIDEO_FOLLOW_TOOLS
                    slog.info("Video follow-along mode: using VIDEO_FOLLOW_TOOLS")
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

            # Periodic student model update (every 5 turns)
            session.assistant_turn_count += 1
            force_student_update = (
                session.assistant_turn_count >= 5
                and session.assistant_turn_count % 5 == 0
            )

            while rounds < MAX_ROUNDS:
                rounds += 1
                slog.info("Tutor LLM call", extra={"round": rounds, "model": settings.TUTOR_MODEL})

                if await request.is_disconnected():
                    slog.info("Client disconnected")
                    return

                text_started = False
                message_id = None
                text_length = 0

                # Validate messages before API call
                valid_messages = _validate_messages(claude_messages)

                # Build API kwargs — force student model update on schedule
                api_kwargs: dict = {
                    "model": settings.TUTOR_MODEL,
                    "max_tokens": 4096,
                    "system": tutor_prompt,
                    "messages": valid_messages,
                    "tools": active_tools,
                }
                suppress_text = False
                if force_student_update and rounds == 1:
                    api_kwargs["tool_choice"] = {"type": "tool", "name": "update_student_model"}
                    force_student_update = False
                    suppress_text = True
                    slog.info("Forcing update_student_model — suppressing preamble text")

                # Retry loop for transient errors
                message = None
                for attempt in range(MAX_RETRIES):
                    try:
                        async with await llm_stream(**api_kwargs, metadata=LLMCallMetadata(session_id=session_id, caller="tutor")) as stream:
                            async for text in stream.text_stream:
                                if await request.is_disconnected():
                                    return
                                if suppress_text:
                                    continue
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
                        "model": settings.TUTOR_MODEL,
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
                            if agent_type == "planning" and getattr(session, '_planner_auto_spawned', False):
                                session._planner_auto_spawned = False  # allow future spawns
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

                        # ── MQL tool execution (BYO mode) ────────────
                        elif is_byo and block.name in MQL_TOOL_NAMES:
                            try:
                                result = await execute_mql_tool(
                                    block.name, block.input,
                                    collection_id=collection_id,
                                    user_email=user_email or "anonymous",
                                    session_id=session_id,
                                )
                            except Exception as e:
                                slog.error("MQL tool failed: %s", e, exc_info=True, extra={"tool": block.name})
                                result = f"Tool error ({block.name}): {str(e)[:200]}"

                        # ── Video control tools (resume/seek) ────────
                        elif block.name in VIDEO_CONTROL_TOOLS:
                            if block.name == "resume_video":
                                yield _sse({"type": "VIDEO_RESUME", "message": block.input.get("message", "")})
                                result = "Video playback resumed."
                            elif block.name == "seek_video":
                                ts = float(block.input.get("timestamp", 0))
                                yield _sse({"type": "VIDEO_SEEK", "timestamp": ts})
                                result = f"Video seeked to {ts:.0f}s."

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
                    # claude_messages IS session.messages (same reference), so only append once
                    # and always serialize ContentBlocks for MongoDB compatibility
                    claude_messages.append({"role": "assistant", "content": _serialize_content(message.content)})
                    claude_messages.append({"role": "user", "content": _serialize_content(tool_results)})
                    continue

                # No more tool calls — done. Persist final assistant message.
                session.messages.append({"role": "assistant", "content": _serialize_content(message.content)})
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

            # Too many rounds
            slog.warning("Too many tool call rounds", extra={"round": MAX_ROUNDS})
            yield _sse({"type": "RUN_ERROR", "message": "Too many tool call rounds"})

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
