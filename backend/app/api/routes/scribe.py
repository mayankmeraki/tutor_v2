"""Real-time speech-to-text via ElevenLabs Scribe v2.

Browser mic → PCM16 base64 chunks → our WS → ElevenLabs Scribe WS (binary) → transcripts back.
"""

import asyncio
import base64
import json
import logging

import websockets
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.core.config import settings

log = logging.getLogger(__name__)

SCRIBE_URL = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"


async def ws_scribe(ws: WebSocket):
    await ws.accept()

    if not settings.ELEVENLABS_API_KEY:
        await ws.send_json({"type": "error", "message": "STT not configured"})
        await ws.close()
        return

    scribe_ws = None
    relay_task = None
    running = True

    try:
        url = f"{SCRIBE_URL}?model_id=scribe_v2_realtime&language_code=en&sample_rate=16000"
        log.info("[Scribe] Connecting to ElevenLabs...")

        try:
            scribe_ws = await asyncio.wait_for(
                websockets.connect(url, additional_headers={"xi-api-key": settings.ELEVENLABS_API_KEY}),
                timeout=10,
            )
        except Exception as e:
            log.error("[Scribe] Connection failed: %s", e)
            await ws.send_json({"type": "error", "message": f"STT connection failed: {e}"})
            await ws.close()
            return

        log.info("[Scribe] Connected to ElevenLabs")

        # Wait for session_started BEFORE telling browser we're ready
        try:
            init_msg = await asyncio.wait_for(scribe_ws.recv(), timeout=5)
            init_data = json.loads(init_msg)
            log.info("[Scribe] EL→ %s", init_data.get("message_type", "?"))
            if init_data.get("message_type") != "session_started":
                log.warning("[Scribe] Expected session_started, got: %s", init_data)
        except Exception as init_err:
            log.error("[Scribe] No session_started: %s", init_err)
            await ws.send_json({"type": "error", "message": "STT session failed to start"})
            await ws.close()
            return

        await ws.send_json({"type": "ready"})
        log.info("[Scribe] Session ready — browser can send audio now")

        # Relay: ElevenLabs → browser
        async def relay():
            nonlocal running
            try:
                async for raw_msg in scribe_ws:
                    if not running:
                        break
                    if isinstance(raw_msg, bytes):
                        continue
                    try:
                        d = json.loads(raw_msg)
                    except (json.JSONDecodeError, TypeError):
                        continue

                    mt = d.get("message_type", d.get("type", ""))
                    log.info("[Scribe] EL→ %s %s", mt, str(d)[:150])

                    if mt == "transcript":
                        text = d.get("text", "")
                        if d.get("is_final"):
                            await ws.send_json({"type": "committed", "text": text})
                        else:
                            await ws.send_json({"type": "partial", "text": text})
                    elif mt == "partial_transcript":
                        await ws.send_json({"type": "partial", "text": d.get("text", "")})
                    elif mt == "committed_transcript":
                        await ws.send_json({"type": "committed", "text": d.get("text", "")})
                    elif mt == "session_started":
                        log.info("[Scribe] Session: %s", d.get("session_id", "")[:12])
                    elif mt == "input_error":
                        log.warning("[Scribe] Input error: %s", d.get("error", ""))
                    elif mt == "error":
                        log.warning("[Scribe] Error: %s", d)
                        await ws.send_json({"type": "error", "message": d.get("message", str(d))})
            except websockets.ConnectionClosed:
                log.info("[Scribe] EL WS closed")
            except Exception as e:
                log.warning("[Scribe] Relay error: %s", e)

        relay_task = asyncio.create_task(relay())

        # Main loop: browser → ElevenLabs (audio as binary)
        _audio_count = 0
        while running:
            try:
                raw = await ws.receive_json()
            except WebSocketDisconnect:
                log.debug("[Scribe] Browser WS disconnected")
                break
            except Exception as recv_err:
                log.warning("[Scribe] Receive error: %s", recv_err)
                break

            msg_type = raw.get("type", "")

            if msg_type == "audio":
                audio_b64 = raw.get("data", "")
                if audio_b64 and scribe_ws:
                    try:
                        audio_bytes = base64.b64decode(audio_b64)
                        await scribe_ws.send(audio_bytes)  # Binary frame to ElevenLabs
                        _audio_count += 1
                        if _audio_count <= 3 or _audio_count % 50 == 0:
                            log.info("[Scribe] Audio chunk #%d (%d bytes → EL)", _audio_count, len(audio_bytes))
                    except websockets.ConnectionClosed as cc:
                        log.info("[Scribe] EL closed during audio send: %s", cc)
                        await ws.send_json({"type": "error", "message": "STT connection lost — click mic to restart"})
                        break
                    except Exception as e:
                        log.warning("[Scribe] Audio send error: %s", e)
            elif msg_type == "commit":
                # Trigger VAD flush
                if scribe_ws:
                    try:
                        await scribe_ws.send(json.dumps({"type": "flush"}))
                    except Exception:
                        pass
            elif msg_type == "stop":
                break

    except WebSocketDisconnect:
        log.debug("[Scribe] Browser disconnected")
    except Exception as e:
        log.error("[Scribe] Error: %s", e, exc_info=True)
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        running = False
        if relay_task:
            relay_task.cancel()
        if scribe_ws:
            try:
                await scribe_ws.close()
            except Exception:
                pass
        log.info("[Scribe] Session ended")
