"""Session router — manages turn lifecycle over WebSocket.

Routes student messages to the tutor pipeline, manages TurnQueue
lifecycle, and handles interrupt/cancel.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from starlette.websockets import WebSocket

from app.services.teaching.beat_parser import StreamingBeatDetector
from app.services.teaching.tts_service import elevenlabs_tts
from app.services.teaching.turn_queue import TurnQueue

log = logging.getLogger(__name__)


class SessionRouter:
    """One per WebSocket connection.  Manages the active turn."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.active_turn: TurnQueue | None = None
        self.generation: int = 0
        self.user: dict | None = None

    async def handle_message(
        self,
        text: str,
        context: dict | None,
        session_id: str | None,
        is_session_start: bool = False,
        messages: list | None = None,
        attachments: list | None = None,
        client_gen: int | None = None,
    ):
        """Handle a new student message — creates a new turn.

        IMPORTANT: This returns immediately (non-blocking).
        Drain runs in background so the WS receive loop stays responsive
        to INTERRUPT messages.
        """
        # Kill previous turn — cancel immediately, cleanup in background
        # The session lock is NOT used in WS path, so we don't need to wait
        if self.active_turn:
            old_turn = self.active_turn
            self.active_turn = None
            # Set cancelled flag immediately (stops put() and drain())
            old_turn.cancelled.set()
            # Let tasks die in background — don't await
            asyncio.create_task(old_turn.cleanup())

        self.generation += 1
        # Use client's generation if provided — ensures event gen matches
        # what the client expects (client gen is page-scoped, never resets)
        effective_gen = client_gen if client_gen is not None else self.generation
        turn = TurnQueue(
            turn_id=uuid4().hex[:8],
            generation=effective_gen,
        )
        self.active_turn = turn

        # Start producer (LLM stream → beat parser → TTS → events into queue)
        producer = asyncio.create_task(
            self._run_turn(turn, text, context, session_id, is_session_start, messages, attachments)
        )
        turn.tasks.append(producer)

        # Start drain in background (sends events from queue to WebSocket)
        # This runs concurrently with the receive loop
        drain_task = asyncio.create_task(turn.drain(self.ws))
        turn.tasks.append(drain_task)

    async def handle_interrupt(self):
        """Student interrupted — kill current turn immediately."""
        if self.active_turn:
            old_turn = self.active_turn
            self.active_turn = None
            old_turn.cancelled.set()
            asyncio.create_task(old_turn.cleanup())
        try:
            await self.ws.send_json({"type": "INTERRUPTED", "gen": self.generation})
        except Exception:
            pass

    async def handle_cancel(self):
        """Student clicked stop with no follow-up."""
        if self.active_turn:
            await self.active_turn.cleanup()
            self.active_turn = None
        try:
            await self.ws.send_json({"type": "CANCELLED", "gen": self.generation})
        except Exception:
            pass

    async def cleanup(self):
        """Clean up on WebSocket disconnect."""
        if self.active_turn:
            await self.active_turn.cleanup()
            self.active_turn = None

    # ── Turn execution ───────────────────────────────────────

    async def _run_turn(
        self,
        turn: TurnQueue,
        text: str,
        context: dict | None,
        session_id: str | None,
        is_session_start: bool,
        messages: list | None,
        attachments: list | None = None,
    ):
        """Run the tutor pipeline, intercept SSE events, add beat detection + TTS."""
        try:
            from app.services.teaching.pipeline import _generate_for_turn

            if not session_id:
                turn.put_json({"type": "RUN_ERROR", "message": "No session ID"})
                turn.done()
                return

            # Build messages list if only text provided
            actual_messages = messages
            if not actual_messages and text:
                actual_messages = [{"role": "user", "content": [{"type": "text", "text": text}]}]

            beat_detector = StreamingBeatDetector()
            text_parts = []  # Use list to avoid O(n²) string concat

            async for sse_str in _generate_for_turn(
                session_id=session_id,
                messages=actual_messages,
                context=context,
                is_session_start=is_session_start,
                is_disconnected=lambda: turn.cancelled.is_set(),
                attachments=attachments,
            ):
                if turn.cancelled.is_set():
                    break

                event = _parse_sse_event(sse_str)
                if event is None:
                    continue

                evt_type = event.get("type", "")

                # ── Intercept text deltas for voice beat detection ──
                if evt_type == "TEXT_MESSAGE_CONTENT":
                    delta = event.get("delta", "")
                    text_parts.append(delta)

                    # Still send text delta for client finalization
                    turn.put_json({"type": "TEXT_DELTA", "delta": delta})

                    # Detect voice beats
                    if beat_detector:
                        beat_events = beat_detector.feed("".join(text_parts))
                        for be in beat_events:
                            if turn.cancelled.is_set():
                                break

                            be_type = be["type"]
                            if be_type == "VOICE_SCENE_START":
                                turn.put_json({"type": "VOICE_SCENE_START", "title": be["title"]})
                            elif be_type == "VOICE_BEAT":
                                beat_num = be["beat"]
                                beat_data = be["data"]
                                turn.put_json({"type": "VOICE_BEAT", "beat": beat_num, "data": beat_data})

                                # Start TTS in background
                                say_text = beat_data.get("say", "")
                                if say_text and say_text.strip():
                                    tts_task = asyncio.create_task(
                                        self._produce_audio(turn, beat_num, say_text)
                                    )
                                    turn.tasks.append(tts_task)
                                else:
                                    turn.put_json({"type": "AUDIO_SKIP", "beat": beat_num})
                            elif be_type == "VOICE_SCENE_END":
                                turn.put_json({"type": "VOICE_SCENE_END"})
                                beat_detector.reset()

                    continue  # Don't forward raw TEXT_MESSAGE_CONTENT in voice mode

                # ── Non-voice text or passthrough events ──
                if evt_type == "TEXT_MESSAGE_CONTENT":
                    turn.put_json({"type": "TEXT_DELTA", "delta": event.get("delta", "")})
                elif evt_type == "RUN_FINISHED":
                    # Wait for pending TTS tasks before signaling done
                    pending = [t for t in turn.tasks if not t.done() and t != asyncio.current_task()]
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                    turn.put_json({"type": "DONE", "fullText": "".join(text_parts)})
                elif evt_type == "RUN_ERROR":
                    turn.put_json(event)
                elif evt_type == "CONNECTED":
                    pass  # Skip — WebSocket is already connected
                elif evt_type in ("TEXT_MESSAGE_START", "TEXT_MESSAGE_END"):
                    pass  # Not needed for WebSocket protocol
                else:
                    # Forward all other events as-is
                    turn.put_json(event)

        except asyncio.CancelledError:
            log.info("[Turn %s] cancelled", turn.turn_id)
        except Exception as e:
            log.exception("[Turn %s] error: %s", turn.turn_id, e)
            turn.put_json({"type": "RUN_ERROR", "message": str(e)})
        finally:
            turn.done()

    async def _produce_audio(self, turn: TurnQueue, beat_num: int, text: str):
        """Fetch TTS audio and put it into the turn queue as binary."""
        if turn.cancelled.is_set():
            return

        try:
            audio_bytes = await asyncio.wait_for(
                elevenlabs_tts(text),
                timeout=6.0,
            )

            if turn.cancelled.is_set():
                return

            if audio_bytes:
                turn.put_audio(beat_num, audio_bytes)
                del audio_bytes  # Release reference for GC
            else:
                turn.put_json({"type": "AUDIO_SKIP", "beat": beat_num})

        except asyncio.CancelledError:
            # Turn was interrupted — don't queue anything, re-raise for task cleanup
            raise
        except asyncio.TimeoutError:
            log.warning("[Turn %s] TTS timeout for beat %d", turn.turn_id, beat_num)
            if not turn.cancelled.is_set():
                turn.put_json({"type": "AUDIO_SKIP", "beat": beat_num})
        except Exception as e:
            log.warning("[Turn %s] TTS error for beat %d: %s", turn.turn_id, beat_num, e)
            if not turn.cancelled.is_set():
                turn.put_json({"type": "AUDIO_SKIP", "beat": beat_num})


def _parse_sse_event(sse_str: str) -> dict | None:
    """Parse an SSE-formatted string back into a dict."""
    import json

    if not sse_str:
        return None

    s = sse_str.strip()
    if s.startswith("data: "):
        s = s[6:]
    elif s.startswith("data:"):
        s = s[5:]
    else:
        return None

    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return None
