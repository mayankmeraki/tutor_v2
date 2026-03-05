"""TopicManager — coordinates Director (producer) and Tutor (consumer).

The Director streams JSONL output: plan line → topic lines → section_done → done.
Topics are the atomic teaching unit (1 concept, 1-3 steps). The TopicManager
buffers them and lets the Tutor consume one at a time via async events.

Lazy generation: when the Tutor is 2+ sections behind the Director, the
Director pauses to save tokens. It resumes when the Tutor catches up.

Backward compat: SectionManager is aliased to TopicManager at module level.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# How many sections ahead of the Tutor the Director can buffer before pausing
LAZY_BUFFER_AHEAD = 2


@dataclass
class TopicEntry:
    """A single topic produced by the Director."""
    section_index: int
    topic_index: int
    title: str
    concept: str
    data: dict  # full topic JSON (steps, assets, tutor_notes, etc.)
    status: str = "pending"  # pending | active | done


@dataclass
class SectionState:
    """Aggregated state for one section."""
    index: int
    title: str
    modality: str = ""
    covers: str = ""
    learning_outcome: str = ""
    activity: str = ""
    topic_count_estimate: int = 0  # from the plan outline
    topic_count_actual: int | None = None  # set when section_done arrives
    topics: list[TopicEntry] = field(default_factory=list)
    status: str = "pending"  # pending | active | done


@dataclass
class TopicManager:
    # State
    plan: dict | None = None
    sections: list[SectionState] = field(default_factory=list)
    current_section_index: int = 0
    current_topic_index: int = -1  # -1 = no topic consumed yet
    director_done: bool = False
    director_task: asyncio.Task | None = None
    error: str | None = None
    session_status: str = "active"
    completion_reason: str | None = None

    # Async coordination
    _plan_ready: asyncio.Event = field(default_factory=asyncio.Event)
    _topic_events: dict[tuple[int, int], asyncio.Event] = field(default_factory=dict)
    _section_done_events: dict[int, asyncio.Event] = field(default_factory=dict)

    # Lazy generation
    _generation_paused: bool = False
    _resume_generation: asyncio.Event = field(default_factory=asyncio.Event)

    # Prefetch
    _needs_prefetch: bool = False

    # ─── Producer methods (called by Director streaming parser) ───

    def set_plan(self, plan: dict) -> None:
        """Director emitted the plan line. Store it, initialize section shells."""
        self.plan = plan
        plan_sections = plan.get("sections", [])
        self.sections = []
        for i, sec in enumerate(plan_sections):
            topics_outline = sec.get("topics", [])
            section_state = SectionState(
                index=i,
                title=sec.get("title", f"Section {i + 1}"),
                modality=sec.get("modality", ""),
                covers=sec.get("covers", ""),
                learning_outcome=sec.get("learning_outcome", ""),
                activity=sec.get("activity", ""),
                topic_count_estimate=len(topics_outline),
            )
            self.sections.append(section_state)
        self._plan_ready.set()
        log.info(
            "TopicManager: plan received — %s (%d sections)",
            plan.get("session_objective", "?")[:80],
            len(self.sections),
        )

    def add_topic(self, topic_data: dict) -> None:
        """Director emitted a topic line. Buffer it, fire event."""
        sec_idx = topic_data.get("section_index", 0)
        top_idx = topic_data.get("topic_index", 0)

        # Ensure section exists
        while sec_idx >= len(self.sections):
            self.sections.append(SectionState(index=len(self.sections), title=f"Section {len(self.sections) + 1}"))

        section = self.sections[sec_idx]
        entry = TopicEntry(
            section_index=sec_idx,
            topic_index=top_idx,
            title=topic_data.get("title", ""),
            concept=topic_data.get("concept", ""),
            data=topic_data,
        )
        section.topics.append(entry)

        # Fire the event for this specific topic
        self._get_topic_event(sec_idx, top_idx).set()

        log.info(
            "TopicManager: topic (%d,%d) buffered — %s [concept=%s, %d steps]",
            sec_idx, top_idx, entry.title[:60],
            entry.concept[:30] if entry.concept else "none",
            len(topic_data.get("steps", [])),
        )

    def mark_section_done(self, section_index: int, topic_count: int) -> None:
        """Director signals all topics for a section have been emitted."""
        if section_index < len(self.sections):
            section = self.sections[section_index]
            section.topic_count_actual = topic_count
            log.info(
                "TopicManager: section %d done — %d topics (estimate was %d)",
                section_index, topic_count, section.topic_count_estimate,
            )
        self._get_section_done_event(section_index).set()
        # Also fire topic events past the actual count so waiters unblock
        for i in range(topic_count, topic_count + 3):
            self._get_topic_event(section_index, i).set()

    def mark_done(self, session_status: str, completion_reason: str | None = None) -> None:
        """Director finished streaming everything."""
        self.director_done = True
        self.session_status = session_status
        self.completion_reason = completion_reason
        # Unblock all potential waiters
        for sec_idx in range(len(self.sections) + 3):
            self._get_section_done_event(sec_idx).set()
            for top_idx in range(10):
                self._get_topic_event(sec_idx, top_idx).set()
        # Resume generation if paused (so the Director task can exit)
        if self._generation_paused:
            self._resume_generation.set()
        log.info(
            "TopicManager: director done — status=%s, %d sections total",
            session_status, len(self.sections),
        )

    def set_error(self, error: str) -> None:
        """Director failed. Unblock all waiters."""
        self.error = error
        self._plan_ready.set()
        for evt in self._topic_events.values():
            evt.set()
        for evt in self._section_done_events.values():
            evt.set()
        if self._generation_paused:
            self._resume_generation.set()
        log.error("TopicManager: error — %s", error[:200])

    # ─── Consumer methods (called by Tutor via tool handlers) ───

    async def wait_for_plan(self) -> dict:
        """Block until plan arrives. Returns plan dict or raises on error."""
        log.info("TopicManager: waiting for plan (timeout=60s)...")
        t0 = asyncio.get_event_loop().time()
        try:
            await asyncio.wait_for(self._plan_ready.wait(), timeout=60)
        except asyncio.TimeoutError:
            log.error("TopicManager: timed out waiting for plan after 60s")
            raise
        elapsed = asyncio.get_event_loop().time() - t0
        if self.error:
            log.error("TopicManager: plan wait unblocked with error after %.1fs — %s", elapsed, self.error)
            raise RuntimeError(self.error)
        log.info("TopicManager: plan received after %.1fs — %s", elapsed, self.plan.get("session_objective", "?")[:80])
        return self.plan

    async def get_next_topic(self) -> dict[str, Any]:
        """Advance to the next topic. Returns structured result.

        Returns: {
            "topic": TopicEntry | None,
            "has_more": bool,
            "completed_topic": tuple[int,int] | None,  # (sec_idx, top_idx)
            "section_completed": int | None,  # sec_idx if crossing boundary
        }
        """
        completed_topic = None
        section_completed = None

        # Mark current topic as done
        current = self._get_current_topic()
        if current:
            current.status = "done"
            completed_topic = (current.section_index, current.topic_index)
            log.info(
                "TopicManager: marking topic (%d,%d) done — %s",
                current.section_index, current.topic_index, current.title[:60],
            )

        # Advance
        self.current_topic_index += 1
        next_sec = self.current_section_index
        next_top = self.current_topic_index

        # Check if we've passed all topics in the current section
        if next_sec < len(self.sections):
            section = self.sections[next_sec]
            section_exhausted = False

            if section.topic_count_actual is not None:
                # Director told us exact count
                section_exhausted = next_top >= section.topic_count_actual
            elif next_top >= len(section.topics) and self._is_section_done(next_sec):
                # section_done event fired and we're past all buffered topics
                section_exhausted = True

            if section_exhausted:
                # Mark section done
                section.status = "done"
                section_completed = next_sec
                log.info("TopicManager: section %d completed — %s", next_sec, section.title[:60])

                # Move to next section
                self.current_section_index += 1
                self.current_topic_index = 0
                next_sec = self.current_section_index
                next_top = 0

                # Check if we should resume Director generation
                self._check_lazy_generation()

        # Check if there are more sections
        if next_sec >= len(self.sections):
            if self.director_done:
                log.info("TopicManager: no more sections — director done, status=%s", self.session_status)
                self._check_prefetch()
                return {
                    "topic": None,
                    "has_more": False,
                    "completed_topic": completed_topic,
                    "section_completed": section_completed,
                }
            else:
                # Wait for more sections from Director
                log.info("TopicManager: waiting for section %d from Director...", next_sec)
                try:
                    await asyncio.wait_for(
                        self._get_topic_event(next_sec, 0).wait(), timeout=120
                    )
                except asyncio.TimeoutError:
                    log.warning("TopicManager: timed out waiting for section %d", next_sec)
                    return {
                        "topic": None,
                        "has_more": False,
                        "completed_topic": completed_topic,
                        "section_completed": section_completed,
                    }

        # Try to get the topic from buffer
        if next_sec < len(self.sections):
            section = self.sections[next_sec]

            # Mark section active if pending
            if section.status == "pending":
                section.status = "active"

            if next_top < len(section.topics):
                topic = section.topics[next_top]
                topic.status = "active"
                log.info(
                    "TopicManager: advancing to topic (%d,%d) — %s (%d steps)",
                    next_sec, next_top, topic.title[:60],
                    len(topic.data.get("steps", [])),
                )
                return {
                    "topic": topic,
                    "has_more": True,
                    "completed_topic": completed_topic,
                    "section_completed": section_completed,
                }

            # Topic not buffered yet — wait for Director
            if not self.director_done:
                log.info(
                    "TopicManager: topic (%d,%d) not buffered — waiting for Director (timeout=120s)",
                    next_sec, next_top,
                )
                t0 = asyncio.get_event_loop().time()
                try:
                    await asyncio.wait_for(
                        self._get_topic_event(next_sec, next_top).wait(), timeout=120
                    )
                except asyncio.TimeoutError:
                    log.warning(
                        "TopicManager: timed out waiting for topic (%d,%d) after 120s",
                        next_sec, next_top,
                    )
                    return {
                        "topic": None,
                        "has_more": False,
                        "completed_topic": completed_topic,
                        "section_completed": section_completed,
                    }
                elapsed = asyncio.get_event_loop().time() - t0
                log.info("TopicManager: topic (%d,%d) wait unblocked after %.1fs", next_sec, next_top, elapsed)

                if self.error:
                    raise RuntimeError(self.error)

                if next_top < len(section.topics):
                    topic = section.topics[next_top]
                    topic.status = "active"
                    log.info(
                        "TopicManager: topic (%d,%d) now available — %s",
                        next_sec, next_top, topic.title[:60],
                    )
                    return {
                        "topic": topic,
                        "has_more": True,
                        "completed_topic": completed_topic,
                        "section_completed": section_completed,
                    }

        # Fell through — no topic available
        log.info("TopicManager: no topic available at (%d,%d)", next_sec, next_top)
        self._check_prefetch()
        return {
            "topic": None,
            "has_more": False,
            "completed_topic": completed_topic,
            "section_completed": section_completed,
        }

    # Backward-compatible alias
    async def get_next_section(self) -> dict[str, Any]:
        """Alias for get_next_topic that wraps result in section-like format."""
        result = await self.get_next_topic()
        topic = result["topic"]
        completed_idx = None
        if result.get("section_completed") is not None:
            completed_idx = result["section_completed"]
        elif result.get("completed_topic"):
            completed_idx = result["completed_topic"][0]

        if topic:
            return {
                "section": topic.data,
                "has_more": result["has_more"],
                "completed_index": completed_idx,
            }
        return {
            "section": None,
            "has_more": result["has_more"],
            "completed_index": completed_idx,
        }

    # ─── Lazy generation ───

    def should_pause_generation(self) -> bool:
        """Check if Director should pause. True when 2+ sections buffered ahead."""
        if self.director_done:
            return False

        # Count how many sections have at least one topic buffered ahead of tutor
        tutor_sec = self.current_section_index
        buffered_ahead = 0
        for sec in self.sections:
            if sec.index > tutor_sec and len(sec.topics) > 0:
                buffered_ahead += 1

        should = buffered_ahead >= LAZY_BUFFER_AHEAD
        if should and not self._generation_paused:
            log.info(
                "TopicManager: pausing generation — %d sections buffered ahead (tutor on section %d)",
                buffered_ahead, tutor_sec,
            )
        return should

    async def wait_if_paused(self) -> None:
        """Called by Director loop between rounds. Blocks if Tutor is far behind."""
        if not self.should_pause_generation():
            return

        self._generation_paused = True
        self._resume_generation.clear()
        log.info("TopicManager: Director blocking — waiting for Tutor to catch up")

        try:
            await asyncio.wait_for(self._resume_generation.wait(), timeout=300)
        except asyncio.TimeoutError:
            log.warning("TopicManager: Director resume timed out after 300s — continuing anyway")

        self._generation_paused = False
        log.info("TopicManager: Director resumed")

    def _check_lazy_generation(self) -> None:
        """Called when Tutor advances. Resume Director if buffer is low."""
        if not self._generation_paused:
            return

        tutor_sec = self.current_section_index
        buffered_ahead = sum(
            1 for sec in self.sections
            if sec.index > tutor_sec and len(sec.topics) > 0
        )

        if buffered_ahead < LAZY_BUFFER_AHEAD:
            log.info(
                "TopicManager: resuming generation — only %d sections buffered ahead",
                buffered_ahead,
            )
            self._resume_generation.set()

    # ─── Lifecycle ───

    def reset_for_new_plan(self) -> None:
        """Cancel current Director, clear all state for request_new_plan."""
        had_task = self.director_task and not self.director_task.done()
        if had_task:
            self.director_task.cancel()
        log.info(
            "TopicManager: reset for new plan (cancelled_task=%s, had_plan=%s, sections=%d)",
            had_task, self.plan is not None, len(self.sections),
        )
        self.plan = None
        self.sections = []
        self.current_section_index = 0
        self.current_topic_index = -1
        self.director_done = False
        self.error = None
        self.session_status = "active"
        self.completion_reason = None
        self._plan_ready = asyncio.Event()
        self._topic_events = {}
        self._section_done_events = {}
        self._generation_paused = False
        self._resume_generation = asyncio.Event()
        self._needs_prefetch = False

    # ─── Serialization (for DB persistence) ───

    def serialize(self) -> dict:
        """Serialize manager state for MongoDB persistence.

        Called at topic/section boundaries (fire-and-forget) and on session save.
        Returns a dict that can be stored directly in the session document.
        """
        return {
            "plan": self.plan,
            "session_status": self.session_status,
            "completion_reason": self.completion_reason,
            "current_section_index": self.current_section_index,
            "current_topic_index": self.current_topic_index,
            "director_done": self.director_done,
            "sections": [
                {
                    "index": sec.index,
                    "title": sec.title,
                    "modality": sec.modality,
                    "covers": sec.covers,
                    "learning_outcome": sec.learning_outcome,
                    "activity": sec.activity,
                    "status": sec.status,
                    "topic_count": sec.topic_count_actual or len(sec.topics),
                    "topics": [
                        {
                            "topic_index": t.topic_index,
                            "title": t.title,
                            "concept": t.concept,
                            "status": t.status,
                            "steps_count": len(t.data.get("steps", [])),
                        }
                        for t in sec.topics
                    ],
                }
                for sec in self.sections
            ],
        }

    # ─── Internal helpers ───

    def _get_current_topic(self) -> TopicEntry | None:
        """Get the currently active topic, if any."""
        if self.current_topic_index < 0:
            return None
        sec_idx = self.current_section_index
        top_idx = self.current_topic_index
        if sec_idx < len(self.sections):
            section = self.sections[sec_idx]
            if top_idx < len(section.topics):
                return section.topics[top_idx]
        return None

    def _is_section_done(self, sec_idx: int) -> bool:
        """Check if section_done event has been fired for this section."""
        key = sec_idx
        return key in self._section_done_events and self._section_done_events[key].is_set()

    def _check_prefetch(self) -> None:
        """If Tutor reached end of all sections and Director is done, signal prefetch."""
        if (
            self.director_done
            and self.current_section_index >= len(self.sections)
            and self.session_status not in ("complete", "paused")
            and (self.director_task is None or self.director_task.done())
        ):
            self._needs_prefetch = True
            log.info(
                "TopicManager: prefetch triggered — past all %d sections, status=%s",
                len(self.sections), self.session_status,
            )

    def _get_topic_event(self, sec_idx: int, top_idx: int) -> asyncio.Event:
        key = (sec_idx, top_idx)
        if key not in self._topic_events:
            self._topic_events[key] = asyncio.Event()
        return self._topic_events[key]

    def _get_section_done_event(self, sec_idx: int) -> asyncio.Event:
        if sec_idx not in self._section_done_events:
            self._section_done_events[sec_idx] = asyncio.Event()
        return self._section_done_events[sec_idx]


# Backward-compatible alias
SectionManager = TopicManager
