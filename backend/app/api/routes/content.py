from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.content_service import (
    get_course_concepts,
    get_course_with_hierarchy,
    get_lesson_sections_lightweight,
    get_section_full,
)

router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.get("/courses/{course_id}")
async def course_map(course_id: int, db: AsyncSession = Depends(get_db)):
    result = await get_course_with_hierarchy(db, course_id)
    if not result:
        raise HTTPException(status_code=404, detail="Course not found")
    return result


@router.get("/lessons/{lesson_id}/sections")
async def lesson_sections(lesson_id: int):
    return await get_lesson_sections_lightweight(lesson_id)


@router.get("/sections/{lesson_id}/{section_index}")
async def section_detail(lesson_id: int, section_index: int):
    doc = await get_section_full(lesson_id, section_index)
    if not doc:
        raise HTTPException(status_code=404, detail="Section not found")
    return doc


@router.get("/courses/{course_id}/concepts")
async def course_concepts(course_id: int):
    return await get_course_concepts(course_id)
