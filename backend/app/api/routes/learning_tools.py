from fastapi import APIRouter, Depends, HTTPException

from app.api.routes.auth import get_optional_user
from app.services.content_service import (
    get_learning_tool_by_id,
    get_learning_tools_for_course,
)

router = APIRouter(prefix="/api/v1/learning-tools", tags=["learning-tools"])


@router.get("/course/{course_id}")
async def tools_for_course(course_id: int, user: dict = Depends(get_optional_user)):
    return await get_learning_tools_for_course(course_id)


@router.get("/{tool_id}")
async def tool_detail(tool_id: str, user: dict = Depends(get_optional_user)):
    doc = await get_learning_tool_by_id(tool_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Learning tool not found")
    return doc
