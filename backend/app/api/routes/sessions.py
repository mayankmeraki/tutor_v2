"""REST endpoints for session lifecycle — tutor_v2.sessions collection."""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.services.session_service import (
    create_session,
    get_session,
    get_sessions_for_student,
    get_sessions_with_headlines,
    summarize_section,
    update_session,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("")
async def create(request: Request):
    """Create a new session document."""
    body = await request.json()
    session_id = body.get("sessionId")
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId is required")
    doc = await create_session(body)
    log.info("Session created: %s (student=%s, course=%s)", session_id, body.get("studentName"), body.get("courseId"))
    return doc


@router.get("/{session_id}")
async def get(session_id: str):
    """Get a session by sessionId."""
    doc = await get_session(session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    return doc


@router.patch("/{session_id}")
async def patch(session_id: str, request: Request):
    """Partial update of a session (transcript, sections, metrics, status, etc.)."""
    body = await request.json()
    doc = await update_session(session_id, body)
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@router.get("/student/{course_id}/{student_name}")
async def student_sessions(course_id: int, student_name: str):
    """Get all sessions for a student+course, newest first."""
    docs = await get_sessions_for_student(course_id, student_name)
    return docs


@router.get("/student/{course_id}/{student_name}/with-headlines")
async def student_sessions_with_headlines(course_id: int, student_name: str):
    """Get all sessions for a student+course with AI-generated headlines."""
    docs = await get_sessions_with_headlines(course_id, student_name)
    return docs


@router.post("/{session_id}/summarize-section")
async def summarize(session_id: str, request: Request):
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
