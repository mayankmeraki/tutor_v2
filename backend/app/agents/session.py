"""In-memory session store — sub-agent architecture.

The Tutor spawns background agents via AgentRuntime
and can delegate teaching to focused sub-agents via DelegationState.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.agents.agent_runtime import AgentRuntime, DelegationState

log = logging.getLogger(__name__)


@dataclass
class Session:
    # ── Core state (kept) ──
    student_model: dict | None = None
    student_intent: str | None = None
    active_scenario: str | None = None
    tutor_notes: list[str] = field(default_factory=list)
    chat_summaries: list[str] = field(default_factory=list)
    session_history: str = ""
    session_status: str = "active"
    completion_reason: str | None = None
    pause_note: str | None = None

    # ── Sub-agent architecture ──
    agent_runtime: AgentRuntime | None = None
    delegation: DelegationState | None = None
    delegation_result: dict | None = None

    # ── Teaching plan (from planning agent) ──
    current_plan: dict | None = None           # Full plan JSON
    current_topics: list[dict] = field(default_factory=list)
    current_topic_index: int = -1              # Which topic is active (-1 = none)
    completed_topics: list[dict] = field(default_factory=list)

    # ── Assets (from asset agents) ──
    available_assets: list[dict] = field(default_factory=list)


_sessions: dict[str, Session] = {}


def get_or_create_session(session_id: str | None) -> tuple[Session, str]:
    if not session_id:
        session_id = str(uuid.uuid4())
    if session_id not in _sessions:
        _sessions[session_id] = Session()
        log.info("New session created: %s", session_id)
    return _sessions[session_id], session_id
