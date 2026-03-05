"""In-memory session store — mirrors server.js lines 53-131."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.agents.section_manager import TopicManager

log = logging.getLogger(__name__)

SESSION_HISTORY_THRESHOLD = 6000  # chars (~1500 tokens)


@dataclass
class Session:
    current_script: dict | None = None
    previous_scripts: list[dict] = field(default_factory=list)
    student_model: dict | None = None
    student_intent: str | None = None
    active_scenario: str | None = None
    tutor_notes: list[str] = field(default_factory=list)
    chat_summaries: list[str] = field(default_factory=list)
    session_history: str = ""
    director_call_count: int = 0
    turns_since_last_director: int = 0
    pending_director_call: bool = False
    pending_script: dict | None = None
    session_status: str = "active"
    completion_reason: str | None = None
    pause_note: str | None = None
    # Streaming Director
    topic_manager: TopicManager | None = None
    pending_manager: TopicManager | None = None  # Prefetched next plan


_sessions: dict[str, Session] = {}


def get_or_create_session(session_id: str | None) -> tuple[Session, str]:
    if not session_id:
        session_id = str(uuid.uuid4())
    if session_id not in _sessions:
        _sessions[session_id] = Session()
        log.info("New session created: %s", session_id)
    return _sessions[session_id], session_id


def compact_session_history(session: Session) -> None:
    parts: list[str] = []
    for i, summary in enumerate(session.chat_summaries):
        if summary:
            parts.append(f"[Director call {i + 1}] {summary}")
    full_history = "\n".join(parts)

    if len(full_history) <= SESSION_HISTORY_THRESHOLD:
        return

    kept = session.chat_summaries[-2:]
    compacted = session.chat_summaries[:-2]
    if compacted:
        compacted_text = "; ".join(
            f"Call {i + 1}: {(s or '')[:100]}" for i, s in enumerate(compacted)
        )
        session.session_history = f"[Earlier session: {compacted_text}]"
    session.chat_summaries = kept


def compact_previous_scripts(scripts: list[dict]) -> list[dict[str, Any]]:
    if len(scripts) <= 1:
        return scripts

    last = scripts[-1]
    older = scripts[:-1]
    summaries: list[str] = []
    for s in older:
        steps_text = ", ".join(
            f"{st.get('n', '?')}:[{st.get('type', '?')}]{st.get('concept', '')}"
            for st in (s.get("steps") or [])
        )
        summaries.append(f'{{ objective: "{s.get("objective", s.get("session_objective", ""))}", steps: [{steps_text}] }}')

    return [
        {"_summary": True, "text": f"[{len(summaries)} earlier script(s): {' → '.join(summaries)}]"},
        last,
    ]
