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

@router.get("/me/all")
async def all_my_sessions(user: dict = Depends(get_optional_user)):
    """Get all sessions for the authenticated user across all courses, newest first."""
    import asyncio
    from app.core.mongodb import get_tutor_db
    from app.services.session_service import _enrich_sessions_with_headlines
    db = get_tutor_db()

    # Only fetch light fields — NO transcript (huge, slow to transfer)
    cursor = db["sessions"].find(
        {"userEmail": user["email"]},
        {f: 1 for f in [
            "sessionId", "courseId", "studentName", "startedAt", "status",
            "headline", "headlineDescription", "intent", "durationSec",
            "metrics", "sections", "plan.sessionObjective",
        ]},
    ).sort("startedAt", -1).limit(20)
    docs = []
    async for doc in cursor:
        doc.pop("_id", None)
        docs.append(doc)

    # Enrich headlines (non-blocking — uses cached or fallback, fires bg tasks)
    docs = await _enrich_sessions_with_headlines(docs)

    # Attach course names — use a simple in-memory cache + parallel fetch
    course_ids = list({d["courseId"] for d in docs if d.get("courseId")})
    course_names = {}
    if course_ids:
        try:
            from app.services.content_service import get_course_title_cached
            # Fetch all course names in parallel
            results = await asyncio.gather(
                *[get_course_title_cached(cid) for cid in course_ids[:10]],
                return_exceptions=True,
            )
            for cid, name in zip(course_ids[:10], results):
                if isinstance(name, str) and name:
                    course_names[cid] = name
        except Exception as e:
            log.warning("Failed to fetch course names: %s", e)

    for d in docs:
        cid = d.get("courseId")
        if cid and cid in course_names:
            d["courseName"] = course_names[cid]

    return docs


@router.get("/search/all")
async def search_all(q: str = "", user: dict = Depends(get_optional_user)):
    """Search sessions across all courses for the authenticated user."""
    if not q or len(q.strip()) < 2:
        return []
    import re as _re
    from app.core.mongodb import get_tutor_db
    db = get_tutor_db()
    safe_query = _re.escape(q.strip())
    cursor = db["sessions"].find(
        {
            "userEmail": user["email"],
            "$or": [
                {"headline": {"$regex": safe_query, "$options": "i"}},
                {"headlineDescription": {"$regex": safe_query, "$options": "i"}},
                {"intent.raw": {"$regex": safe_query, "$options": "i"}},
                {"plan.sessionObjective": {"$regex": safe_query, "$options": "i"}},
            ],
        },
        {f: 1 for f in [
            "sessionId", "courseId", "studentName", "startedAt", "status",
            "headline", "headlineDescription", "intent", "durationSec",
        ]},
    ).sort("startedAt", -1).limit(10)
    docs = []
    async for doc in cursor:
        doc.pop("_id", None)
        docs.append(doc)
    return docs


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


@router.get("/{session_id}/board-frames")
async def get_board_frames(session_id: str, user: dict = Depends(get_optional_user)):
    """Extract board-draw frames from session transcript for restoration.

    Parses both:
    - <teaching-board-draw> JSONL content (text mode)
    - <teaching-voice-scene> with <vb draw='...' /> beats (voice mode)

    Returns last N frames as arrays of draw commands, ready to render.
    """
    import re
    import json as _json

    doc = await get_session(session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")

    transcript = doc.get("transcript", [])
    frames = []

    for msg in transcript:
        if msg.get("role") != "assistant":
            continue
        raw_content = msg.get("content", "")
        # Handle both string content and Anthropic content blocks format
        if isinstance(raw_content, list):
            content = "\n".join(
                b.get("text", "") for b in raw_content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        elif isinstance(raw_content, str):
            content = raw_content
        else:
            continue
        if not content:
            continue

        # ── Extract from <teaching-board-draw> tags (text/SSE mode) ──
        for bd_match in re.finditer(
            r'<teaching-board-draw[^>]*>([\s\S]*?)</teaching-board-draw>', content
        ):
            title_match = re.search(r'title=["\']([^"\']*)["\']', bd_match.group(0))
            title = title_match.group(1) if title_match else "Board"
            jsonl = bd_match.group(1).strip()
            commands = []
            for line in jsonl.split('\n'):
                line = line.strip()
                if not line:
                    continue
                try:
                    commands.append(_json.loads(line))
                except _json.JSONDecodeError:
                    pass
            if commands:
                frames.append({"title": title, "commands": commands})

        # ── Extract from <teaching-voice-scene> tags (voice/WS mode) ──
        for vs_match in re.finditer(
            r'<teaching-voice-scene[^>]*>([\s\S]*?)</teaching-voice-scene>', content
        ):
            title_match = re.search(r'title=["\']([^"\']*)["\']', vs_match.group(0))
            title = title_match.group(1) if title_match else "Board"
            scene_content = vs_match.group(1)
            commands = []
            # Parse <vb draw='...' /> beats
            for vb_match in re.finditer(r"draw='(\{[^']*\})'", scene_content):
                try:
                    commands.append(_json.loads(vb_match.group(1)))
                except _json.JSONDecodeError:
                    pass
            # Also try draw="..." (double quotes)
            for vb_match in re.finditer(r'draw="(\{[^"]*\})"', scene_content):
                try:
                    cmd_str = vb_match.group(1).replace('&quot;', '"')
                    commands.append(_json.loads(cmd_str))
                except _json.JSONDecodeError:
                    pass
            if commands:
                frames.append({"title": title, "commands": commands})

    # Also check activeBoardDrawContent as a fallback
    active_content = doc.get("activeBoardDrawContent")
    if active_content and isinstance(active_content, str):
        commands = []
        for line in active_content.split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                commands.append(_json.loads(line))
            except _json.JSONDecodeError:
                pass
        if commands:
            # Only add if it's different from the last frame
            if not frames or commands != frames[-1].get("commands"):
                frames.append({"title": "Active Board", "commands": commands})

    # Return last 3 frames only
    recent = frames[-3:] if len(frames) > 3 else frames
    total_cmds = sum(len(f.get("commands", [])) for f in recent)
    log.info("Board frames extracted", extra={
        "event": "BOARD_FRAMES",
        "session_id": session_id[:8],
        "total_frames": len(frames),
        "returned_frames": len(recent),
        "total_commands": total_cmds,
    })
    return {"frames": recent, "totalFrames": len(frames)}


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
