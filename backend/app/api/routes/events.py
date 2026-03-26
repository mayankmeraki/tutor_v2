"""Persistent SSE endpoint — agent lifecycle events.

GET /api/events/{session_id} opens a long-lived SSE stream that pushes
AGENT_SPAWNED, AGENT_COMPLETE, AGENT_ERROR, and HEARTBEAT events to the
frontend so it can show progress indicators and auto-trigger delivery.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.routes.auth import get_optional_user

from app.agents.agent_runtime import AgentRuntime
from app.agents.session import get_or_create_session
from app.api.routes import sse as _sse

log = logging.getLogger(__name__)

router = APIRouter()

HEARTBEAT_INTERVAL = 15  # seconds


@router.get("/api/events/{session_id}")
async def agent_events(session_id: str, request: Request, user: dict = Depends(get_optional_user)):
    session, _ = await get_or_create_session(session_id)

    # Ensure the session has an AgentRuntime (may not exist yet if no agents spawned)
    if not session.agent_runtime:
        session.agent_runtime = AgentRuntime(session_id=session_id)

    queue = session.agent_runtime.event_queue
    log.info("SSE events connected — session: %s", session_id[:8])

    async def generate():
        yield _sse({"type": "EVENTS_CONNECTED"})

        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                yield _sse(event)
            except asyncio.TimeoutError:
                yield _sse({"type": "HEARTBEAT"})

        log.info("SSE events disconnected — session: %s", session_id[:8])

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
