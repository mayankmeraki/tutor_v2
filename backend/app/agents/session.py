"""In-memory session store — sub-agent architecture.

The Tutor spawns background agents via AgentRuntime
and can delegate teaching to focused sub-agents via DelegationState.

Sessions are restored from MongoDB on cache miss (server restart).

Session phases: TRIAGE → PLAN → TEACH → ASSESS (→ loop)
"""

from __future__ import annotations

import asyncio
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
_session_locks: dict[str, asyncio.Lock] = {}


def get_session_lock(session_id: str) -> asyncio.Lock:
    """Return (or create) a per-session asyncio lock for concurrent request safety."""
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]


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
            from app.services.session_service import sync_backend_state
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
                from app.services.session_service import sync_backend_state
                await sync_backend_state(sid, session)
            except Exception as e:
                log.warning("Failed to sync capped session %s before eviction: %s", sid[:8], e)
            _sessions.pop(sid, None)
            _session_locks.pop(sid, None)
            log.info("Evicted session (cap): %s", sid[:8])


async def _try_restore_session(session_id: str) -> Session | None:
    """Attempt to restore session state from MongoDB."""
    try:
        from app.services.session_service import load_backend_state
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
            messages=bs.get("messages", []),
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
