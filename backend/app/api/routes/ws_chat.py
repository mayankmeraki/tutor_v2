"""WebSocket chat endpoint — streams voice beats + audio to the client.

Replaces the SSE-based /api/chat for voice mode.
"""

from __future__ import annotations

import asyncio
import logging

from starlette.websockets import WebSocket, WebSocketDisconnect

from app.services.session_router import SessionRouter

log = logging.getLogger(__name__)


async def ws_chat(ws: WebSocket):
    """WebSocket handler — one persistent connection per browser tab.

    Runs two concurrent loops:
    1. Receive loop: reads client messages (MESSAGE, INTERRUPT, CANCEL)
    2. Drain loop: sends events from the active TurnQueue to the client

    These MUST run concurrently so INTERRUPT can arrive while drain is sending.
    """
    await ws.accept()

    try:
        user = _authenticate_ws(ws)
    except Exception as e:
        await ws.send_json({"type": "RUN_ERROR", "message": f"Auth failed: {e}"})
        await ws.close(code=4001, reason="Authentication failed")
        return

    router = SessionRouter(ws)
    router.user = user
    log.info("[WS] Connected: %s", user.get("email", "anon"))

    try:
        # Run receive loop — router handles drain internally via background tasks
        while True:
            raw = await ws.receive_json()
            msg_type = raw.get("type", "")

            if msg_type == "MESSAGE":
                # This starts a new turn and begins draining in background
                # It does NOT block — returns immediately so we can receive INTERRUPT
                await router.handle_message(
                    text=raw.get("text", ""),
                    context=raw.get("context"),
                    session_id=raw.get("sessionId"),
                    is_session_start=raw.get("isSessionStart", False),
                    messages=raw.get("messages"),
                )

            elif msg_type == "INTERRUPT":
                await router.handle_interrupt()

            elif msg_type == "CANCEL":
                await router.handle_cancel()

            elif msg_type == "VOICE_MODE":
                router.voice_enabled = raw.get("enabled", True)

            elif msg_type == "PING":
                await ws.send_json({"type": "PONG"})

    except WebSocketDisconnect:
        log.info("[WS] Disconnected: %s", user.get("email", "anon"))
    except Exception as e:
        log.exception("[WS] Error: %s", e)
    finally:
        await router.cleanup()


def _authenticate_ws(ws: WebSocket) -> dict:
    token = ws.query_params.get("token", "")
    if not token:
        raise ValueError("Missing token")
    from app.api.routes.auth import decode_mockup_token
    claims = decode_mockup_token(token)
    return {"email": claims["sub"], "name": claims.get("name", ""), "role": claims.get("role", "")}
