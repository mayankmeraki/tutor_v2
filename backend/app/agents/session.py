"""In-memory session store — sub-agent architecture.

The Tutor spawns background agents via AgentRuntime
and can delegate teaching to focused sub-agents via DelegationState.

Sessions are restored from MongoDB on cache miss (server restart).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.agents.agent_runtime import AgentRuntime, DelegationState, AssessmentState

log = logging.getLogger(__name__)


@dataclass
class Session:
    # ── Core state (kept) ──
    student_model: dict | None = None
    student_intent: str | None = None
    active_scenario: str | None = None
    tutor_notes: list[str] = field(default_factory=list)
    assistant_turn_count: int = 0
    chat_summaries: list[str] = field(default_factory=list)
    session_history: str = ""
    session_status: str = "active"
    completion_reason: str | None = None
    pause_note: str | None = None

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

    # ── Session scope ──
    session_objective: str | None = None
    session_scope: str | None = None
    scope_concepts: list[str] = field(default_factory=list)

    # ── Assets (from asset agents) ──
    available_assets: list[dict] = field(default_factory=list)

    # ── Generated visuals (from visual_gen agents) ──
    generated_visuals: dict = field(default_factory=dict)  # {visual_id: {"html": ..., "title": ...}}


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
    return _sessions[session_id], session_id


async def _try_restore_session(session_id: str) -> Session | None:
    """Attempt to restore session state from MongoDB."""
    try:
        from app.services.session_service import load_backend_state
        from app.agents.agent_runtime import DelegationState, AssessmentState

        doc = await load_backend_state(session_id)
        if not doc or not doc.get("backendState"):
            return None

        bs = doc["backendState"]
        session = Session(
            student_model=bs.get("studentModel"),
            student_intent=bs.get("studentIntent"),
            tutor_notes=bs.get("tutorNotes", []),
            assistant_turn_count=bs.get("assistantTurnCount", 0),
            session_status=bs.get("sessionStatus", "active"),
            completion_reason=bs.get("completionReason"),
            current_plan=bs.get("currentPlan"),
            current_topics=bs.get("currentTopics", []),
            current_topic_index=bs.get("currentTopicIndex", -1),
            completed_topics=bs.get("completedTopics", []),
            session_objective=bs.get("sessionObjective"),
            session_scope=bs.get("sessionScope"),
            scope_concepts=bs.get("scopeConcepts", []),
            active_scenario=bs.get("activeScenario"),
            available_assets=bs.get("availableAssets", []),
            generated_visuals=doc.get("generatedVisuals", {}),
            assessment_result=bs.get("assessmentResult"),
            pre_assessment_note=bs.get("preAssessmentNote"),
            last_assessment_summary=bs.get("lastAssessmentSummary"),
            delegation_result=bs.get("delegationResult"),
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
