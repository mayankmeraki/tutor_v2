"""Turn-scoped async queue for WebSocket streaming.

Each turn (one student message → one tutor response) gets its own TurnQueue.
Producers (LLM stream, TTS pipeline, tool executor) put events in.
The WebSocket drains events out.  On interrupt, cleanup() kills everything.
"""

from __future__ import annotations

import asyncio
import logging
import struct
from typing import Union

from starlette.websockets import WebSocket

log = logging.getLogger(__name__)


class TurnQueue:
    """Isolated event queue for a single turn."""

    __slots__ = ("turn_id", "generation", "queue", "cancelled", "tasks", "_drained", "_slog", "_sessionId")

    def __init__(self, turn_id: str, generation: int):
        self.turn_id = turn_id
        self.generation = generation
        self.queue: asyncio.Queue[Union[dict, bytes, None]] = asyncio.Queue()
        self.cancelled = asyncio.Event()
        self.tasks: list[asyncio.Task] = []
        self._drained = False

    # ── Producers call this ──────────────────────────────────────

    def put(self, event: Union[dict, bytes, None]) -> None:
        """Enqueue a JSON event, binary audio frame, or None sentinel.

        No-op if the turn has been cancelled — prevents late writes from
        background tasks that haven't noticed cancellation yet.
        """
        if self.cancelled.is_set():
            return
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            log.warning("[TurnQueue %s] Queue full — dropping event", self.turn_id)

    def put_json(self, event: dict) -> None:
        """Convenience: inject generation into JSON event and enqueue."""
        event["gen"] = self.generation
        self.put(event)

    def put_audio(self, beat_num: int, audio_bytes: bytes) -> None:
        """Pack binary audio frame: [2B beat][4B gen][audio mpeg bytes]."""
        header = struct.pack(">HI", beat_num, self.generation)
        self.put(header + audio_bytes)

    def done(self) -> None:
        """Signal that this turn is complete (sentinel)."""
        self.put(None)

    # ── WebSocket consumer ───────────────────────────────────────

    async def drain(self, ws: WebSocket) -> None:
        """Drain events to the WebSocket until sentinel or cancellation.

        Uses short timeouts on queue.get() so we check the cancellation
        event frequently — ensures cleanup() unblocks drain() within ~200ms.
        """
        try:
            while not self.cancelled.is_set():
                try:
                    event = await asyncio.wait_for(self.queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    continue

                if event is None:
                    break

                try:
                    if isinstance(event, bytes):
                        await ws.send_bytes(event)
                    else:
                        await ws.send_json(event)
                except Exception as send_err:
                    log.warning("[TurnQueue %s] send error: %s", self.turn_id, send_err)
                    break
        except Exception as e:
            log.warning("[TurnQueue %s] drain error: %s", self.turn_id, e)
        finally:
            self._drained = True

    # ── Cleanup ──────────────────────────────────────────────────

    async def cleanup(self) -> None:
        """Kill all producer tasks and flush the queue.

        Called on interrupt/cancel.  After this returns, the TurnQueue is
        dead — put() becomes a no-op, drain() exits.
        """
        if self.cancelled.is_set():
            return  # already cleaned up

        self.cancelled.set()

        # Cancel all producer tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks with a hard timeout — don't hang on stuck tasks
        if self.tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.tasks, return_exceptions=True),
                    timeout=3.0,
                )
            except asyncio.TimeoutError:
                log.warning("[TurnQueue %s] Tasks did not cancel within 3s", self.turn_id)

        # Clear task references to allow GC
        self.tasks.clear()

        # Flush remaining items
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Push sentinel to unblock drain() if it's still waiting
        try:
            self.queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

        log.info("[TurnQueue %s] cleaned up", self.turn_id)
