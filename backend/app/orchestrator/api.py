"""Euler HTTP endpoint — SSE streaming on the Home screen.

POST /api/euler
  Body: { message, attachments?, sessionId? }
  Response: SSE stream of Euler messages

The frontend renders these inline on the Home screen.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

log = logging.getLogger(__name__)
router = APIRouter(tags=["euler"])


@router.post("/api/euler")
async def euler_endpoint(request: Request):
    """Euler endpoint — streams responses to the Home screen."""
    from app.api.routes.auth import get_optional_user

    user = await get_optional_user(request)
    if not user:
        return StreamingResponse(
            _error_stream("Authentication required"),
            media_type="text/event-stream",
        )

    body = await request.json()
    message = body.get("message", "")
    history = body.get("history", [])  # [{role: "user"|"assistant", content: "..."}]
    attachments = body.get("attachments", [])

    if not message.strip():
        return StreamingResponse(
            _error_stream("No message provided"),
            media_type="text/event-stream",
        )

    # Build user context
    user_context = await _build_user_context(user)

    # Stream Euler messages
    return StreamingResponse(
        _stream_euler(message, user_context, attachments, history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _build_user_context(user: dict) -> dict:
    """Build the user context for Euler."""
    from app.core.mongodb import get_mongo_db

    db = get_mongo_db()
    email = user.get("email", "")

    context = {
        "name": user.get("name", ""),
        "email": email,
        "student_model": None,
        "session_history": [],
        "collections": [],
    }

    # Get student model
    try:
        model_doc = await db.student_concept_mastery.find_one(
            {"userEmail": email.lower()},
            {"_id": 0, "concepts": 1, "globalProfile": 1},
        )
        if model_doc:
            context["student_model"] = model_doc
    except Exception:
        pass

    # Get recent sessions
    try:
        cursor = db.sessions.find(
            {"userEmail": email},
            {"_id": 0, "sessionId": 1, "headline": 1, "status": 1, "durationSec": 1, "createdAt": 1},
        ).sort("createdAt", -1).limit(5)
        context["session_history"] = [
            {
                "session_id": s.get("sessionId"),
                "title": s.get("headline", "Session"),
                "status": s.get("status", "?"),
                "duration": s.get("durationSec", 0),
            }
            async for s in cursor
        ]
    except Exception:
        pass

    # Get collections
    try:
        cursor = db.collections.find(
            {"user_id": email},
            {"_id": 0, "collection_id": 1, "title": 1, "status": 1, "stats": 1},
        ).sort("created_at", -1).limit(5)
        context["collections"] = [doc async for doc in cursor]
    except Exception:
        pass

    return context


async def _stream_euler(message: str, user_context: dict, attachments: list, history: list = None):
    """Generator that streams SSE events from Euler."""
    from app.orchestrator.agent import (
        orchestrate, TextDelta, ToolCallStart, ToolCallResult,
        ArtifactCreated, DocumentGenerated, SessionStart,
        NavigateUI, PermissionRequest, Done,
    )

    yield _sse({"type": "CONNECTED"})

    try:
        async for msg in orchestrate(message, user_context, attachments, history=history):
            if isinstance(msg, TextDelta):
                yield _sse({"type": "TEXT_DELTA", "text": msg.text})

            elif isinstance(msg, ToolCallStart):
                yield _sse({"type": "TOOL_START", "tool": msg.tool_name, "input": msg.tool_input})

            elif isinstance(msg, ToolCallResult):
                yield _sse({"type": "TOOL_RESULT", "tool": msg.tool_name, "result": msg.result})

            elif isinstance(msg, ArtifactCreated):
                yield _sse({
                    "type": "ARTIFACT",
                    "artifactId": msg.artifact_id,
                    "artifactType": msg.artifact_type,
                    "title": msg.title,
                    "content": msg.content,
                })

            elif isinstance(msg, DocumentGenerated):
                yield _sse({
                    "type": "DOCUMENT",
                    "documentId": msg.document_id,
                    "title": msg.title,
                    "format": msg.format,
                    "downloadUrl": msg.download_url,
                })

            elif isinstance(msg, SessionStart):
                yield _sse({
                    "type": "SESSION_START",
                    "sessionId": msg.session_id,
                    "context": msg.context,
                })

            elif isinstance(msg, NavigateUI):
                yield _sse({
                    "type": "NAVIGATE",
                    "target": msg.target,
                    "label": msg.label,
                })

            elif isinstance(msg, PermissionRequest):
                yield _sse({
                    "type": "PERMISSION",
                    "permissionId": msg.permission_id,
                    "question": msg.question,
                    "actionLabel": msg.action_label,
                    "denyLabel": msg.deny_label,
                    "context": msg.context,
                })

            elif isinstance(msg, Done):
                yield _sse({"type": "DONE", "turnsUsed": msg.turns_used})

    except Exception as e:
        log.error("Euler error: %s", e, exc_info=True)
        yield _sse({"type": "ERROR", "message": str(e)[:200]})


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _error_stream(message: str):
    yield f"data: {json.dumps({'type': 'ERROR', 'message': message})}\n\n"
