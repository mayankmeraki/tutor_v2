"""REST endpoints for session lifecycle — tutor_v2.sessions collection."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.routes.auth import get_current_user, get_optional_user
from app.services.session_service import (
    create_session,
    get_session,
    get_sessions_for_student,
    get_sessions_for_user,
    get_sessions_with_headlines,
    get_sessions_with_headlines_by_email,
    search_sessions_semantic,
    summarize_section,
    update_session,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("")
async def create(request: Request, user: dict = Depends(get_optional_user)):
    """Create a new session document."""
    body = await request.json()
    session_id = body.get("sessionId")
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId is required")
    doc = await create_session(body)
    log.info("Session created: %s (student=%s, course=%s)", session_id, body.get("studentName"), body.get("courseId"))
    return doc


# ─── Auth-based routes (must come before /{session_id} to avoid conflict) ───

@router.get("/me/{course_id}")
async def my_sessions(course_id: int, user: dict = Depends(get_optional_user)):
    """Get all sessions for the authenticated user + course."""
    docs = await get_sessions_for_user(course_id, user["email"])
    return docs


@router.get("/me/{course_id}/with-headlines")
async def my_sessions_with_headlines(course_id: int, user: dict = Depends(get_optional_user)):
    """Get all sessions for the authenticated user + course with AI headlines."""
    docs = await get_sessions_with_headlines_by_email(course_id, user["email"])
    return docs


@router.get("/student/{course_id}/{student_name}")
async def student_sessions(course_id: int, student_name: str, user: dict = Depends(get_optional_user)):
    """Get all sessions for a student+course, newest first."""
    docs = await get_sessions_for_student(course_id, student_name)
    return docs


@router.get("/student/{course_id}/{student_name}/with-headlines")
async def student_sessions_with_headlines(course_id: int, student_name: str, user: dict = Depends(get_optional_user)):
    """Get all sessions for a student+course with AI-generated headlines."""
    docs = await get_sessions_with_headlines(course_id, student_name)
    return docs


@router.get("/search/{course_id}")
async def search(course_id: int, q: str = "", user: dict = Depends(get_optional_user)):
    """Semantic search across sessions — text + vector matching."""
    if not q or len(q.strip()) < 2:
        return []
    results = await search_sessions_semantic(course_id, user["email"], q.strip())
    return results


@router.get("/{session_id}")
async def get(session_id: str, user: dict = Depends(get_optional_user)):
    """Get a session by sessionId."""
    doc = await get_session(session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    return doc


@router.patch("/{session_id}")
async def patch(session_id: str, request: Request, user: dict = Depends(get_optional_user)):
    """Partial update of a session (transcript, sections, metrics, status, etc.)."""
    body = await request.json()
    doc = await update_session(session_id, body)
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@router.post("/{session_id}/summarize-section")
async def summarize(session_id: str, request: Request, user: dict = Depends(get_optional_user)):
    """Generate an LLM summary for a completed section."""
    body = await request.json()
    section_index = body.get("sectionIndex")
    if section_index is None:
        raise HTTPException(status_code=400, detail="sectionIndex is required")
    try:
        summary = await summarize_section(session_id, section_index)
        return {"ok": True, "summary": summary}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
