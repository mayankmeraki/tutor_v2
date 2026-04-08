"""Factory for creating content adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from .protocol import ContentProvider


def create_adapter(course_id: int, db: "AsyncSession") -> "ContentProvider":
    """Create the appropriate ContentProvider for a course.

    Currently returns CapacityCourseAdapter for all courses.
    Future: inspect course type and return different adapters.
    """
    from .course_adapter import CapacityCourseAdapter

    return CapacityCourseAdapter(course_id, db)
