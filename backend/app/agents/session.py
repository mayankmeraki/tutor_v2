"""In-memory session store — sub-agent architecture.

The Tutor spawns background agents via AgentRuntime
and can delegate teaching to focused sub-agents via DelegationState.

Sessions are restored from MongoDB on cache miss (server restart).

Session phases: TRIAGE → PLAN → TEACH → ASSESS (→ loop)
"""

from __future__ import annotations

import enum
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.agents.agent_runtime import AgentRuntime, DelegationState, AssessmentState

log = logging.getLogger(__name__)

MAX_SESSIONS = 500
SESSION_TTL_SECONDS = 1800  # 30 minutes


class SessionPhase(str, enum.Enum):
    """Session lifecycle phases."""
    TRIAGE = "triage"
    PLANNING = "planning"
    TEACHING = "teaching"
    ASSESSMENT = "assessment"


@dataclass
class Session:
    # ── Core state (kept) ──
    student_model: dict | None = None
    student_intent: str | None = None
    active_scenario: str | None = None
    video_state: dict | None = None  # {lessonId, lessonTitle, currentTimestamp, sectionIndex, ...}
    tutor_notes: list[str] = field(default_factory=list)
    assistant_turn_count: int = 0
    chat_summaries: list[str] = field(default_factory=list)
    session_history: str = ""
    session_status: str = "active"
    completion_reason: str | None = None
    pause_note: str | None = None
    teaching_mode: str = "voice"  # voice mode is default

    # ── Session phase (TRIAGE → PLAN → TEACH → ASSESS) ──
    phase: SessionPhase = SessionPhase.TEACHING  # Overridden by _init_session_phase on first turn
    triage_result: dict | None = None            # Diagnostic output from triage
    struggle_streak: int = 0                     # Consecutive confused signals from tutor
    last_signals: dict = field(default_factory=dict)  # Latest session_signal from tutor

    # ── Housekeeping ──
    last_accessed: float = field(default_factory=time.time)

    # ── Sub-agent architecture ──
    agent_runtime: AgentRuntime | None = None
    delegation: DelegationState | None = None
    delegation_result: dict | None = None

    # ── Assessment agent ──
    assessment: AssessmentState | None = None
    assessment_result: dict | None = None
    pre_assessment_note: dict | None = None  # Teaching checkpoint saved before assessment
    last_assessment_summary: dict | None = None  # Persists until next assessment — score, weak concepts, recommendation

    # ── Teaching plan (from planning agent) ──
    current_plan: dict | None = None           # Full plan JSON
    current_topics: list[dict] = field(default_factory=list)
    current_topic_index: int = -1              # Which topic is active (-1 = none)
    completed_topics: list[dict] = field(default_factory=list)
    detour_stack: list[dict] = field(default_factory=list)  # [{saved_topic_index, saved_topics, reason}]

    # ── Session scope ──
    session_objective: str | None = None
    session_scope: str | None = None
    scope_concepts: list[str] = field(default_factory=list)

    # ── Generated visuals (from visual_gen agents) ──
    generated_visuals: dict = field(default_factory=dict)  # {visual_id: {"html": ..., "title": ...}}

    # ── Conversation context management ──
    conversation_summary: str | None = None  # Haiku-generated digest of older messages
    summary_covers_through: int = 0          # How many messages the summary covers
    asset_registry: list[dict] = field(default_factory=list)  # [{id, type, title, turn}]
    messages: list[dict] = field(default_factory=list)  # Server-side source of truth for conversation

    # ── Session attachments (uploaded files persisted in GCS) ──
    attachment_meta: list[dict] = field(default_factory=list)  # [{filename, mime_type, gcs_path}]

    # ── LLM cost tracking ──
    llm_cost_cents: float = 0.0         # Accumulated cost in cents
    llm_total_input_tokens: int = 0     # Total input tokens across all calls
    llm_total_output_tokens: int = 0    # Total output tokens across all calls
    llm_call_count: int = 0             # Number of LLM calls made


    def track_llm_usage(
        self, model: str, input_tokens: int, output_tokens: int,
        provider_cost_usd: float | None = None,
    ) -> float:
        """Accumulate LLM cost from a single call. Returns cost in cents for this call."""
        from app.core.llm import compute_cost_cents
        cost = compute_cost_cents(model, input_tokens, output_tokens, provider_cost_usd)
        self.llm_cost_cents += cost
        self.llm_total_input_tokens += input_tokens
        self.llm_total_output_tokens += output_tokens
        self.llm_call_count += 1
        return cost


_sessions: dict[str, Session] = {}


async def get_or_create_session(session_id: str | None) -> tuple[Session, str]:
    if not session_id:
        session_id = str(uuid.uuid4())
    if session_id not in _sessions:
        # Try to restore from MongoDB
        restored = await _try_restore_session(session_id)
        if restored:
            _sessions[session_id] = restored
        else:
            _sessions[session_id] = Session()
            log.info("New session created: %s", session_id)

    session = _sessions[session_id]
    session.last_accessed = time.time()

    # Evict stale sessions to bound memory
    await _evict_stale_sessions()

    return session, session_id


async def _evict_stale_sessions() -> None:
    """Remove sessions older than TTL, sync to MongoDB first. Cap at MAX_SESSIONS."""
    now = time.time()
    stale_ids = [
        sid for sid, s in _sessions.items()
        if now - s.last_accessed > SESSION_TTL_SECONDS
    ]
    for sid in stale_ids:
        session = _sessions.get(sid)
        if not session:
            continue  # Already evicted by another coroutine
        try:
            from app.services.session.session_service import sync_backend_state
            await sync_backend_state(sid, session)
        except Exception as e:
            log.warning("Failed to sync stale session %s before eviction: %s", sid[:8], e)
        _sessions.pop(sid, None)
        _session_locks.pop(sid, None)
        log.info("Evicted stale session: %s", sid[:8])

    # Hard cap — evict least-recently-accessed sessions
    if len(_sessions) > MAX_SESSIONS:
        sorted_ids = sorted(_sessions, key=lambda sid: _sessions[sid].last_accessed)
        to_evict = sorted_ids[: len(_sessions) - MAX_SESSIONS]
        for sid in to_evict:
            session = _sessions.get(sid)
            if not session:
                continue
            try:
                from app.services.session.session_service import sync_backend_state
                await sync_backend_state(sid, session)
            except Exception as e:
                log.warning("Failed to sync capped session %s before eviction: %s", sid[:8], e)
            _sessions.pop(sid, None)
            _session_locks.pop(sid, None)
            log.info("Evicted session (cap): %s", sid[:8])


def _validate_restored_messages(messages: list[dict]) -> list[dict]:
    """Validate tool_use/tool_result integrity in restored messages.

    Ensures every tool_use has a matching tool_result and vice versa.
    Fixes: duplicate IDs, orphaned tool_use, orphaned tool_result.
    """
    if not messages:
        return messages

    import uuid as _uuid

    # Pass 1: Deduplicate tool_use IDs
    seen_ids = set()
    for msg in messages:
        content = msg.get("content")
        if msg.get("role") == "assistant" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tid = block.get("id")
                    if tid and tid in seen_ids:
                        new_id = f"toolu_{_uuid.uuid4().hex[:24]}"
                        # Update matching tool_result
                        for later in messages[messages.index(msg) + 1:]:
                            lc = later.get("content")
                            if later.get("role") == "user" and isinstance(lc, list):
                                for rb in lc:
                                    if isinstance(rb, dict) and rb.get("tool_use_id") == tid:
                                        rb["tool_use_id"] = new_id
                                break
                        block["id"] = new_id
                        tid = new_id
                    if tid:
                        seen_ids.add(tid)

    # Pass 2: Ensure every tool_use has a tool_result
    result = []
    for i, msg in enumerate(messages):
        result.append(msg)
        content = msg.get("content")
        if msg.get("role") != "assistant" or not isinstance(content, list):
            continue
        tool_ids = [b["id"] for b in content if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id")]
        if not tool_ids:
            continue
        # Check next message for matching results
        nxt = messages[i + 1] if i + 1 < len(messages) else None
        found_ids = set()
        if nxt and nxt.get("role") == "user" and isinstance(nxt.get("content"), list):
            found_ids = {b.get("tool_use_id") for b in nxt["content"] if isinstance(b, dict) and b.get("type") == "tool_result"}
        missing = [tid for tid in tool_ids if tid not in found_ids]
        if missing:
            filler = [{"type": "tool_result", "tool_use_id": tid, "content": "[interrupted]"} for tid in missing]
            if nxt and nxt.get("role") == "user" and isinstance(nxt.get("content"), list):
                nxt["content"] = list(nxt["content"]) + filler
            else:
                result.append({"role": "user", "content": filler})

    return result


async def _try_restore_session(session_id: str) -> Session | None:
    """Attempt to restore session state from MongoDB."""
    try:
        from app.services.session.session_service import load_backend_state
        from app.agents.agent_runtime import DelegationState, AssessmentState

        doc = await load_backend_state(session_id)
        if not doc or not doc.get("backendState"):
            return None

        bs = doc["backendState"]
        # Restore phase
        phase_str = bs.get("phase", "teaching")
        try:
            phase = SessionPhase(phase_str)
        except (ValueError, KeyError):
            phase = SessionPhase.TEACHING

        session = Session(
            student_model=bs.get("studentModel"),
            student_intent=bs.get("studentIntent"),
            tutor_notes=bs.get("tutorNotes", []),
            assistant_turn_count=bs.get("assistantTurnCount", 0),
            session_status=bs.get("sessionStatus", "active"),
            completion_reason=bs.get("completionReason"),
            teaching_mode=bs.get("teachingMode", "voice"),
            phase=phase,
            current_plan=bs.get("currentPlan"),
            current_topics=bs.get("currentTopics", []),
            current_topic_index=bs.get("currentTopicIndex", -1),
            completed_topics=bs.get("completedTopics", []),
            detour_stack=bs.get("detourStack", []),
            session_objective=bs.get("sessionObjective"),
            session_scope=bs.get("sessionScope"),
            scope_concepts=bs.get("scopeConcepts", []),
            active_scenario=bs.get("activeScenario"),
            video_state=bs.get("videoState") or doc.get("videoState"),
            generated_visuals=doc.get("generatedVisuals", {}),
            assessment_result=bs.get("assessmentResult"),
            pre_assessment_note=bs.get("preAssessmentNote"),
            last_assessment_summary=bs.get("lastAssessmentSummary"),
            delegation_result=bs.get("delegationResult"),
            llm_cost_cents=bs.get("llmCostCents", 0.0),
            llm_total_input_tokens=bs.get("llmTotalInputTokens", 0),
            llm_total_output_tokens=bs.get("llmTotalOutputTokens", 0),
            llm_call_count=bs.get("llmCallCount", 0),
            conversation_summary=bs.get("conversationSummary"),
            summary_covers_through=bs.get("summaryCoverCount", 0),
            asset_registry=bs.get("assetRegistry", []),
            messages=_validate_restored_messages(bs.get("messages", [])),
            attachment_meta=bs.get("attachmentMeta", []),
        )

        # Restore in-flight delegation state
        deleg = bs.get("delegation")
        if deleg:
            session.delegation = DelegationState(
                agent_type=deleg["agentType"],
                system_prompt=deleg["systemPrompt"],
                max_turns=deleg.get("maxTurns", 6),
                turns_used=deleg.get("turnsUsed", 0),
                topic=deleg.get("topic", ""),
                instructions=deleg.get("instructions", ""),
            )

        # Restore in-flight assessment agent state
        assess = bs.get("assessmentAgent")
        if assess:
            session.assessment = AssessmentState(
                system_prompt=assess["systemPrompt"],
                brief=assess.get("brief", {}),
                section_title=assess.get("sectionTitle", ""),
                concepts_tested=assess.get("conceptsTested", []),
                questions_asked=assess.get("questionsAsked", 0),
                max_questions=assess.get("maxQuestions", 5),
                min_questions=assess.get("minQuestions", 3),
                turns_used=assess.get("turnsUsed", 0),
                max_turns=assess.get("maxTurns", 15),
                messages=assess.get("messages", []),
            )

        log.info("Restored session from MongoDB: %s", session_id)
        return session
    except Exception as e:
        log.warning("Failed to restore session from MongoDB: %s", e)
        return None
