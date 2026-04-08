"""CapacityCourseAdapter — wraps Capacity's PostgreSQL + MongoDB course store.

Implements ContentProvider by delegating to existing content_service functions
and tool handlers. Refs use the format "lesson:{id}:section:{idx}".
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)


def _fmt_time(seconds: float) -> str:
    m = math.floor(seconds / 60)
    s = round(seconds % 60)
    return f"{m}:{s:02d}"


class CapacityCourseAdapter:
    """ContentProvider for Capacity's curated courses (Postgres + MongoDB)."""

    def __init__(self, course_id: int, db: AsyncSession):
        self.course_id = course_id
        self.db = db

    # ── Protocol methods ──────────────────────────────────────────────

    async def content_map(self) -> str:
        from app.services.content.content_service import (
            get_course_with_hierarchy,
            get_course_concepts,
            get_learning_tools_for_course,
        )

        hierarchy = await get_course_with_hierarchy(self.db, self.course_id)
        if not hierarchy:
            return "No course data found."

        course = hierarchy["course"]
        lines = [course["title"]]
        if course.get("description"):
            lines.append(course["description"][:200])
        lines.append("")

        for mod in hierarchy.get("modules", []):
            mod_lessons = sorted(
                [l for l in hierarchy.get("lessons", []) if l["module_id"] == mod["id"]],
                key=lambda x: x.get("order", 0),
            )
            lines.append(f"── {mod['title']} ({len(mod_lessons)} lessons) ──")
            for l in mod_lessons:
                dur = f"{l.get('duration', '')} min" if l.get("duration") else ""
                vid = " [video]" if l.get("video_url") else ""
                lines.append(f"  lesson:{l['id']}  {l['title']} ({dur}){vid}")
            lines.append("")

        # Concepts (compact list of names)
        try:
            concepts = await get_course_concepts(self.course_id)
            if concepts:
                names = sorted({c.get("name", "") for c in concepts if c.get("name")})
                if names:
                    lines.append(f"Concepts: {', '.join(names[:30])}")
        except Exception:
            log.debug("Failed to load concepts for course %d", self.course_id, exc_info=True)

        # Simulations
        try:
            tools = await get_learning_tools_for_course(self.course_id)
            sims = [t for t in tools if t.get("tool_type") == "simulation"]
            if sims:
                sim_strs = [
                    f'sim:{t.get("_id", t.get("id"))} "{t.get("title", "")}"'
                    for t in sims
                ]
                lines.append(f"Simulations: {', '.join(sim_strs)}")
        except Exception:
            log.debug("Failed to load sims for course %d", self.course_id, exc_info=True)

        return "\n".join(lines)

    async def content_read(self, ref: str) -> str:
        kind, ids = self._parse_ref(ref)

        if kind == "section":
            from app.tools.handlers import get_section_content
            return await get_section_content(ids["lesson_id"], ids["section_index"])

        if kind == "lesson":
            return await self._read_lesson(ids["lesson_id"])

        if kind == "simulation":
            from app.tools.handlers import get_simulation_details
            return await get_simulation_details(ids["simulation_id"])

        return f"Unknown ref format: {ref}. Use lesson:ID:section:IDX or lesson:ID."

    async def content_peek(self, ref: str) -> str:
        kind, ids = self._parse_ref(ref)

        if kind == "section":
            from app.tools.handlers import get_section_brief
            return await get_section_brief(ids["lesson_id"], ids["section_index"])

        if kind == "lesson":
            return await self._peek_lesson(ids["lesson_id"])

        if kind == "simulation":
            from app.services.content.content_service import get_learning_tool_by_id
            data = await get_learning_tool_by_id(ids["simulation_id"])
            if not data:
                return f"Simulation {ids['simulation_id']} not found."
            return f"{data.get('title', '')} — {data.get('description', '')[:150]}"

        return f"Unknown ref format: {ref}. Use lesson:ID:section:IDX or lesson:ID."

    async def content_search(self, query: str, limit: int = 5) -> str:
        from app.services.content.content_service import search_content

        results = await search_content(query, limit=limit)
        if not results:
            return "No results found."

        lines = []
        for r in results:
            ref = f"lesson:{r['lessonId']}" if r.get("lessonId") else ""
            desc = (r.get("description") or "")[:100]
            lines.append(f"  {ref}  [{r.get('type', '?')}] {r.get('title', '?')}")
            if desc:
                lines.append(f"         {desc}")
        return f'Search results for "{query}":\n' + "\n".join(lines)

    # ── Ref parsing ───────────────────────────────────────────────────

    @staticmethod
    def _parse_ref(ref: str) -> tuple[str, dict]:
        """Parse opaque ref strings into (kind, ids).

        Formats:
          lesson:3:section:2  -> ("section", {"lesson_id": 3, "section_index": 2})
          lesson:3            -> ("lesson",  {"lesson_id": 3})
          simulation:abc123   -> ("simulation", {"simulation_id": "abc123"})
          sim:abc123          -> ("simulation", {"simulation_id": "abc123"})
        """
        parts = ref.strip().split(":")

        if len(parts) >= 4 and parts[0] == "lesson" and parts[2] == "section":
            try:
                return "section", {"lesson_id": int(parts[1]), "section_index": int(parts[3])}
            except ValueError:
                pass

        if len(parts) == 2 and parts[0] == "lesson":
            try:
                return "lesson", {"lesson_id": int(parts[1])}
            except ValueError:
                pass

        if len(parts) == 2 and parts[0] in ("simulation", "sim"):
            return "simulation", {"simulation_id": parts[1]}

        return "unknown", {"raw": ref}

    # ── Helpers ───────────────────────────────────────────────────────

    async def _peek_lesson(self, lesson_id: int) -> str:
        """Return section listing for a lesson (compact, with refs)."""
        from app.services.content.content_service import get_lesson_sections_lightweight

        sections = await get_lesson_sections_lightweight(lesson_id)
        if not sections:
            return f"No sections found for lesson {lesson_id}."

        lines = [f"Lesson {lesson_id} — {len(sections)} sections:"]
        for s in sections:
            idx = s.get("index", 0)
            title = s.get("title", f"Section {idx}")
            start = s.get("start_seconds")
            end = s.get("end_seconds")
            ts = f" ({_fmt_time(start)}-{_fmt_time(end)})" if start is not None else ""
            lines.append(f"  lesson:{lesson_id}:section:{idx}  {title}{ts}")
        return "\n".join(lines)

    async def _read_lesson(self, lesson_id: int) -> str:
        """Return lesson overview + first section content."""
        from app.services.content.content_service import get_lesson_sections_lightweight
        from app.tools.handlers import get_section_content

        sections = await get_lesson_sections_lightweight(lesson_id)
        if not sections:
            return f"No sections found for lesson {lesson_id}."

        lines = [f"Lesson {lesson_id} — {len(sections)} sections:"]
        for s in sections:
            idx = s.get("index", 0)
            lines.append(f"  lesson:{lesson_id}:section:{idx}  {s.get('title', f'Section {idx}')}")
        lines.append("")

        # Include first section content
        first_idx = sections[0].get("index", 0)
        first_content = await get_section_content(lesson_id, first_idx)
        lines.append(f"── First section ──\n{first_content}")
        if len(sections) > 1:
            lines.append(
                f"\n(Use content_read with section refs for remaining {len(sections) - 1} sections)"
            )

        return "\n".join(lines)
