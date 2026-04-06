"""WebSocket chat endpoint — streams voice beats + audio to the client.

Replaces the SSE-based /api/chat for voice mode.
"""

from __future__ import annotations

import logging

from starlette.websockets import WebSocket, WebSocketDisconnect

from app.core.logging_config import SessionLogger
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

    user_email = user.get("email", "anon")
    # Start with a bare slog — session_id added on first MESSAGE
    slog = SessionLogger(log, user=user_email)

    router = SessionRouter(ws)
    router.user = user
    slog.debug("WS connected", extra={"event": "WS_CONNECT"})

    try:
        while True:
            raw = await ws.receive_json()
            msg_type = raw.get("type", "")

            if msg_type == "MESSAGE":
                session_id = raw.get("sessionId", "")
                if session_id:
                    slog = SessionLogger(log, session_id=session_id, user=user_email)
                is_start = raw.get("isSessionStart", False)
                text = raw.get("text", "")
                slog.info("WS turn",
                          extra={"event": "WS_TURN", "preview": text[:50],
                                 "is_session_start": is_start})
                await router.handle_message(
                    text=text,
                    context=raw.get("context"),
                    session_id=session_id,
                    is_session_start=is_start,
                    messages=raw.get("messages"),
                    attachments=raw.get("attachments"),
                    client_gen=raw.get("gen"),
                )

            elif msg_type == "INTERRUPT":
                slog.debug("WS interrupt")
                await router.handle_interrupt()

            elif msg_type == "CANCEL":
                slog.debug("WS cancel")
                await router.handle_cancel()

            elif msg_type == "VOICE_MODE":
                router.voice_enabled = raw.get("enabled", True)

            elif msg_type == "PING":
                await ws.send_json({"type": "PONG"})

    except WebSocketDisconnect:
        slog.debug("WS disconnected", extra={"event": "WS_DISCONNECT"})
    except Exception as e:
        slog.error("WS error: %s", e, exc_info=True, extra={"event": "WS_ERROR"})
    finally:
        await router.cleanup()


def _authenticate_ws(ws: WebSocket) -> dict:
    token = ws.query_params.get("token", "")
    if not token:
        raise ValueError("Missing token")
    from app.api.routes.auth import decode_mockup_token
    claims = decode_mockup_token(token)
    return {"email": claims["sub"], "name": claims.get("name", ""), "role": claims.get("role", "")}
