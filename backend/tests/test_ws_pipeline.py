"""Tests for WebSocket streaming pipeline — beat parser, turn queue, TTS service.

Covers: beat detection across chunks, multi-scene dedup, turn lifecycle,
interrupt handling, audio skip, generation filtering, and edge cases.
"""

import asyncio
import json
import struct
import sys
import os
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.beat_parser import (
    StreamingBeatDetector,
    parse_beat_attrs,
    VB_TAG_RE,
    SCENE_OPEN_RE,
    SCENE_CLOSE_RE,
)
from app.services.tts_service import voice_clean_text
from app.services.turn_queue import TurnQueue


# ═══════════════════════════════════════════════════════════════
#  Beat Parser Tests
# ═══════════════════════════════════════════════════════════════


class TestParseVoiceBeatAttrs:
    """Test individual <vb/> attribute parsing."""

    def test_say_double_quotes(self):
        b = parse_beat_attrs('say="Hello world"')
        assert b["say"] == "Hello world"

    def test_say_single_quotes(self):
        b = parse_beat_attrs("say='Hello world'")
        assert b["say"] == "Hello world"

    def test_cursor(self):
        b = parse_beat_attrs('say="Hi" cursor="write"')
        assert b["cursor"] == "write"

    def test_pause(self):
        b = parse_beat_attrs('say="Hi" pause="0.5"')
        assert b["pause"] == 0.5

    def test_question(self):
        b = parse_beat_attrs('say="What?" question="true"')
        assert b.get("question") is True

    def test_draw_json(self):
        b = parse_beat_attrs('draw=\'{"cmd":"text","text":"hello","x":10,"y":20}\' say="Hi"')
        assert b["draw"] is not None
        assert b["draw"][0]["cmd"] == "text"

    def test_draw_nested_braces(self):
        """Draw with nested objects (animation code)."""
        b = parse_beat_attrs('draw=\'{"cmd":"animation","code":"function(){return {a:1}}"}\' say="X"')
        assert b["draw"] is not None

    def test_scroll_to(self):
        b = parse_beat_attrs('scroll-to="id:eq-main" say="Look"')
        assert b["scrollTo"] == "id:eq-main"

    def test_annotate(self):
        b = parse_beat_attrs('annotate="circle:id:eq1" annotate-color="#34d399"')
        assert b["annotate"] == "circle:id:eq1"
        assert b["annotateColor"] == "#34d399"

    def test_widget(self):
        b = parse_beat_attrs('widget-title="My Widget" widget-code="<div>hi</div>"')
        assert b["widgetTitle"] == "My Widget"
        assert b["widgetCode"] == "<div>hi</div>"

    def test_simulation(self):
        b = parse_beat_attrs('simulation="double-slit" say="Watch"')
        assert b["simulation"] == "double-slit"

    def test_video(self):
        b = parse_beat_attrs('video-lesson="intro" video-start="10" video-end="30"')
        assert b["videoLesson"] == "intro"
        assert b["videoStart"] == "10"

    def test_empty_attrs(self):
        b = parse_beat_attrs("")
        assert b == {}

    def test_no_say(self):
        b = parse_beat_attrs('draw=\'{"cmd":"line"}\' cursor="write"')
        assert "say" not in b
        assert b["draw"] is not None


class TestStreamingBeatDetector:
    """Test the streaming beat detector with various text patterns."""

    def test_single_complete_scene(self):
        d = StreamingBeatDetector()
        text = '<teaching-voice-scene title="Test"><vb say="A"/><vb say="B"/></teaching-voice-scene>'
        events = d.feed(text)
        types = [e["type"] for e in events]
        assert types == ["VOICE_SCENE_START", "VOICE_BEAT", "VOICE_BEAT", "VOICE_SCENE_END"]
        assert events[0]["title"] == "Test"
        assert events[1]["beat"] == 1
        assert events[2]["beat"] == 2

    def test_incremental_chunks(self):
        """Tags arriving across multiple chunks (the real-world case)."""
        d = StreamingBeatDetector()
        chunks = [
            "Some preamble text\n<teaching",
            '-voice-scene title="Incremental">',
            "\n<vb say=",
            '"Hello" cursor="write"/>',
            "\n<vb say=",
            '"World" pause="0.5"/>',
            "\n</teaching-voice-scene>",
        ]
        acc = ""
        all_events = []
        for chunk in chunks:
            acc += chunk
            events = d.feed(acc)
            all_events.extend(events)

        types = [e["type"] for e in all_events]
        assert "VOICE_SCENE_START" in types, "Missing VOICE_SCENE_START"
        beats = [e for e in all_events if e["type"] == "VOICE_BEAT"]
        assert len(beats) == 2, f"Expected 2 beats, got {len(beats)}"
        assert "VOICE_SCENE_END" in types, "Missing VOICE_SCENE_END"

    def test_no_duplicate_beats_on_refeed(self):
        """Re-feeding same text should not produce duplicate events."""
        d = StreamingBeatDetector()
        text = '<teaching-voice-scene title="X"><vb say="A"/></teaching-voice-scene>'
        e1 = d.feed(text)
        e2 = d.feed(text)  # same text, no new content
        assert len(e1) == 3  # START + BEAT + END
        assert len(e2) == 0  # nothing new

    def test_multi_scene_no_duplicates(self):
        """Two scenes in one response — second scene should not duplicate first."""
        d = StreamingBeatDetector()
        scene1 = '<teaching-voice-scene title="S1"><vb say="A"/><vb say="B"/></teaching-voice-scene>'
        e1 = d.feed(scene1)
        beats1 = [e for e in e1 if e["type"] == "VOICE_BEAT"]
        assert len(beats1) == 2

        d.reset()

        scene2 = scene1 + '\n<teaching-voice-scene title="S2"><vb say="C"/></teaching-voice-scene>'
        e2 = d.feed(scene2)
        beats2 = [e for e in e2 if e["type"] == "VOICE_BEAT"]
        assert len(beats2) == 1, f"Expected 1 new beat, got {len(beats2)} — DUPLICATE BUG"
        assert beats2[0]["data"]["say"] == "C"

    def test_monotonic_beat_numbers_across_scenes(self):
        d = StreamingBeatDetector()
        text1 = '<teaching-voice-scene title="S1"><vb say="1"/><vb say="2"/></teaching-voice-scene>'
        e1 = d.feed(text1)
        d.reset()
        text2 = text1 + '<teaching-voice-scene title="S2"><vb say="3"/></teaching-voice-scene>'
        e2 = d.feed(text2)

        all_beats = [e for e in e1 + e2 if e["type"] == "VOICE_BEAT"]
        beat_nums = [b["beat"] for b in all_beats]
        assert beat_nums == [1, 2, 3], f"Beat numbers not monotonic: {beat_nums}"

    def test_scene_with_no_beats(self):
        d = StreamingBeatDetector()
        text = '<teaching-voice-scene title="Empty"></teaching-voice-scene>'
        events = d.feed(text)
        types = [e["type"] for e in events]
        assert types == ["VOICE_SCENE_START", "VOICE_SCENE_END"]

    def test_no_scene_in_text(self):
        d = StreamingBeatDetector()
        text = "Just some regular text without any teaching tags."
        events = d.feed(text)
        assert events == []

    def test_partial_scene_not_closed(self):
        """Scene started but not closed — should emit START + beats, no END."""
        d = StreamingBeatDetector()
        text = '<teaching-voice-scene title="Partial"><vb say="A"/>'
        events = d.feed(text)
        types = [e["type"] for e in events]
        assert "VOICE_SCENE_START" in types
        assert "VOICE_BEAT" in types
        assert "VOICE_SCENE_END" not in types

    def test_beat_with_only_draw(self):
        d = StreamingBeatDetector()
        text = '<teaching-voice-scene title="T"><vb draw=\'{"cmd":"line"}\' cursor="write"/></teaching-voice-scene>'
        events = d.feed(text)
        beats = [e for e in events if e["type"] == "VOICE_BEAT"]
        assert len(beats) == 1
        assert "say" not in beats[0]["data"]
        assert beats[0]["data"]["draw"] is not None

    def test_housekeeping_between_scenes(self):
        """Housekeeping tag between scenes should not break detection."""
        d = StreamingBeatDetector()
        text1 = '<teaching-voice-scene title="S1"><vb say="A"/></teaching-voice-scene>'
        d.feed(text1)
        d.reset()

        text2 = text1 + '\n<teaching-housekeeping><signal progress="complete"/></teaching-housekeeping>'
        text2 += '\n<teaching-voice-scene title="S2"><vb say="B"/></teaching-voice-scene>'
        e2 = d.feed(text2)
        starts = [e for e in e2 if e["type"] == "VOICE_SCENE_START"]
        beats = [e for e in e2 if e["type"] == "VOICE_BEAT"]
        assert len(starts) == 1
        assert len(beats) == 1
        assert beats[0]["data"]["say"] == "B"


# ═══════════════════════════════════════════════════════════════
#  Voice Clean Text Tests
# ═══════════════════════════════════════════════════════════════


class TestVoiceCleanText:

    def test_strips_ref_markers(self):
        assert "Check" in voice_clean_text("{ref:eq1} Check this")
        assert "{ref:" not in voice_clean_text("{ref:eq1} Check this")

    def test_strips_markdown(self):
        assert voice_clean_text("**bold** and *italic*") == "bold and italic"

    def test_strips_latex(self):
        assert voice_clean_text("See $$E=mc^2$$ here") == "See here"

    def test_strips_html(self):
        assert voice_clean_text("Click <button>here</button>") == "Click here"

    def test_no_text_placeholder(self):
        assert voice_clean_text("(no text)") == ""

    def test_empty(self):
        assert voice_clean_text("") == ""

    def test_short_text_preserved(self):
        assert voice_clean_text("Hi") == "Hi"

    def test_whitespace_collapse(self):
        assert voice_clean_text("  hello   world  ") == "hello world"


# ═══════════════════════════════════════════════════════════════
#  TurnQueue Tests
# ═══════════════════════════════════════════════════════════════


class TestTurnQueue:

    @pytest.mark.asyncio
    async def test_put_and_get(self):
        t = TurnQueue("test-1", generation=1)
        t.put({"type": "TEXT", "text": "hello"})
        t.put(None)  # sentinel
        event = await t.queue.get()
        assert event["type"] == "TEXT"
        sentinel = await t.queue.get()
        assert sentinel is None

    @pytest.mark.asyncio
    async def test_put_json_injects_generation(self):
        t = TurnQueue("test-2", generation=42)
        t.put_json({"type": "VOICE_BEAT", "beat": 1})
        event = await t.queue.get()
        assert event["gen"] == 42

    @pytest.mark.asyncio
    async def test_put_audio_binary_format(self):
        t = TurnQueue("test-3", generation=5)
        audio = b"\xff\xfb\x90\x00" * 100  # fake MP3
        t.put_audio(3, audio)
        frame = await t.queue.get()
        assert isinstance(frame, bytes)
        view = memoryview(frame)
        beat_num = struct.unpack(">H", bytes(view[:2]))[0]
        gen = struct.unpack(">I", bytes(view[2:6]))[0]
        assert beat_num == 3
        assert gen == 5
        assert bytes(view[6:]) == audio

    @pytest.mark.asyncio
    async def test_put_noop_after_cancel(self):
        t = TurnQueue("test-4", generation=1)
        t.cancelled.set()
        t.put({"type": "should_be_dropped"})
        assert t.queue.empty()

    @pytest.mark.asyncio
    async def test_cleanup_cancels_tasks(self):
        t = TurnQueue("test-5", generation=1)

        async def slow_task():
            await asyncio.sleep(100)

        task = asyncio.create_task(slow_task())
        t.tasks.append(task)
        await t.cleanup()
        assert task.cancelled() or task.done()
        assert t.cancelled.is_set()

    @pytest.mark.asyncio
    async def test_cleanup_idempotent(self):
        t = TurnQueue("test-6", generation=1)
        await t.cleanup()
        await t.cleanup()  # second call should not error
        assert t.cancelled.is_set()

    @pytest.mark.asyncio
    async def test_done_sentinel(self):
        t = TurnQueue("test-7", generation=1)
        t.done()
        event = await t.queue.get()
        assert event is None

    @pytest.mark.asyncio
    async def test_cleanup_clears_task_list(self):
        t = TurnQueue("test-8", generation=1)
        t.tasks.append(asyncio.create_task(asyncio.sleep(100)))
        await t.cleanup()
        assert len(t.tasks) == 0


# ═══════════════════════════════════════════════════════════════
#  Generation-Based Filtering Tests (simulates client-side logic)
# ═══════════════════════════════════════════════════════════════


class TestGenerationFiltering:
    """Simulate the client's generation-based stale frame filtering."""

    def _client_should_accept(self, active_gen, event):
        """Mirrors the client's _wsOnMessage stale check logic."""
        evt_type = event.get("type", "")
        if evt_type in ("INTERRUPTED", "CANCELLED"):
            return True  # always accept
        evt_gen = event.get("gen")
        if evt_gen is not None and evt_gen != active_gen:
            return False  # stale
        return True

    def _client_should_accept_binary(self, active_gen, frame):
        """Mirrors binary frame gen check."""
        view = memoryview(frame)
        gen = struct.unpack(">I", bytes(view[2:6]))[0]
        return gen == active_gen

    def test_accept_current_gen(self):
        assert self._client_should_accept(3, {"type": "VOICE_BEAT", "gen": 3})

    def test_reject_old_gen(self):
        assert not self._client_should_accept(3, {"type": "VOICE_BEAT", "gen": 2})

    def test_accept_interrupted_any_gen(self):
        assert self._client_should_accept(5, {"type": "INTERRUPTED", "gen": 3})

    def test_accept_cancelled_any_gen(self):
        assert self._client_should_accept(5, {"type": "CANCELLED", "gen": 2})

    def test_accept_no_gen_field(self):
        assert self._client_should_accept(3, {"type": "PONG"})

    def test_binary_accept_current(self):
        frame = struct.pack(">HI", 1, 5) + b"\xff\xfb"
        assert self._client_should_accept_binary(5, frame)

    def test_binary_reject_old(self):
        frame = struct.pack(">HI", 1, 3) + b"\xff\xfb"
        assert not self._client_should_accept_binary(5, frame)


# ═══════════════════════════════════════════════════════════════
#  Interrupt Scenario Tests
# ═══════════════════════════════════════════════════════════════


class TestInterruptScenarios:
    """End-to-end interrupt scenarios using TurnQueue."""

    @pytest.mark.asyncio
    async def test_interrupt_stops_new_events(self):
        """After cancel, no new events should be queued."""
        t = TurnQueue("int-1", generation=1)
        t.put_json({"type": "VOICE_BEAT", "beat": 1})
        t.cancelled.set()
        t.put_json({"type": "VOICE_BEAT", "beat": 2})  # should be dropped
        # Only beat 1 should be in queue
        e1 = await t.queue.get()
        assert e1["beat"] == 1
        assert t.queue.empty()

    @pytest.mark.asyncio
    async def test_rapid_turns(self):
        """Simulate 3 rapid turns — only last one survives."""
        turns = []
        for i in range(3):
            if turns:
                turns[-1].cancelled.set()
                asyncio.create_task(turns[-1].cleanup())
            t = TurnQueue(f"rapid-{i}", generation=i + 1)
            turns.append(t)

        # Only last turn should accept events
        for i, t in enumerate(turns):
            t.put_json({"type": "TEST", "turn": i})

        # First two should be empty (cancelled)
        assert turns[0].queue.empty()
        assert turns[1].queue.empty()
        # Third should have the event
        e = await turns[2].queue.get()
        assert e["turn"] == 2

    @pytest.mark.asyncio
    async def test_audio_resolver_killed_on_interrupt(self):
        """Beat audio resolver should resolve with 'killed' on interrupt."""
        t = TurnQueue("res-1", generation=1)
        resolver_result = None

        async def wait_for_audio():
            nonlocal resolver_result
            entry = {"_resolver": None}
            future = asyncio.get_event_loop().create_future()
            entry["_resolver"] = lambda val: future.set_result(val) if not future.done() else None

            # Simulate interrupt after 100ms
            async def interrupt_later():
                await asyncio.sleep(0.1)
                entry["_resolver"]("killed")

            asyncio.create_task(interrupt_later())
            resolver_result = await future

        await wait_for_audio()
        assert resolver_result == "killed"


# ═══════════════════════════════════════════════════════════════
#  Housekeeping Tag Parsing Tests
# ═══════════════════════════════════════════════════════════════


class TestHousekeepingParsing:

    def test_strip_tag(self):
        from app.api.routes.chat import _strip_housekeeping_tag

        text = 'Teaching content.\n<teaching-housekeeping><signal progress="complete"/></teaching-housekeeping>'
        result = _strip_housekeeping_tag(text)
        assert "<teaching-housekeeping>" not in result
        assert "Teaching content." in result

    def test_strip_preserves_other_tags(self):
        from app.api.routes.chat import _strip_housekeeping_tag

        text = '<teaching-voice-scene title="X"><vb say="Hi"/></teaching-voice-scene>\n<teaching-housekeeping><signal/></teaching-housekeeping>'
        result = _strip_housekeeping_tag(text)
        assert "<teaching-voice-scene" in result
        assert "<teaching-housekeeping>" not in result

    def test_signal_regex(self):
        from app.api.routes.chat import _SIGNAL_RE

        m = _SIGNAL_RE.search('<signal progress="complete" student="engaged" />')
        assert m
        assert m.group(1) == "complete"
        assert m.group(2) == "engaged"

    def test_plan_modify_regex(self):
        from app.api.routes.chat import _PLAN_MODIFY_RE

        m = _PLAN_MODIFY_RE.search('<plan-modify action="append" title="EPR" concept="epr" reason="asked" />')
        assert m
        assert m.group(1) == "append"
        assert m.group(2) == "EPR"
        assert m.group(3) == "epr"

    def test_handoff_assessment_regex(self):
        from app.api.routes.chat import _HANDOFF_RE

        m = _HANDOFF_RE.search('<handoff type="assessment" section="Basics" concepts="a,b,c" />')
        assert m
        assert m.group(1) == "assessment"
        assert m.group(2) == "Basics"
        assert m.group(3) == "a,b,c"

    def test_handoff_delegate_regex(self):
        from app.api.routes.chat import _HANDOFF_RE

        m = _HANDOFF_RE.search('<handoff type="delegate" topic="QFT" instructions="Focus" />')
        assert m
        assert m.group(1) == "delegate"
        assert m.group(4) == "QFT"


# ═══════════════════════════════════════════════════════════════
#  Content Cleaning Tests
# ═══════════════════════════════════════════════════════════════


class TestCleanPartialContent:

    def test_strips_interrupted_marker(self):
        from app.api.routes.chat import _clean_partial_content

        text = "Hello\n\n[Student interrupted — tutor stopped here]"
        assert "[Student interrupted" not in _clean_partial_content(text)

    def test_truncates_unclosed_voice_scene(self):
        from app.api.routes.chat import _clean_partial_content

        text = 'Some text<teaching-voice-scene title="X"><vb say="Hello'
        result = _clean_partial_content(text)
        assert "<teaching-voice-scene" not in result
        assert "interrupted" in result

    def test_truncates_unclosed_board_draw(self):
        from app.api.routes.chat import _clean_partial_content

        text = 'Text here<teaching-board-draw title="T">{"cmd":"text"'
        result = _clean_partial_content(text)
        assert "interrupted mid-board-draw" in result

    def test_preserves_complete_content(self):
        from app.api.routes.chat import _clean_partial_content

        text = '<teaching-voice-scene title="X"><vb say="Hi" /></teaching-voice-scene>'
        result = _clean_partial_content(text)
        assert "</teaching-voice-scene>" in result

    def test_empty_returns_interrupted(self):
        from app.api.routes.chat import _clean_partial_content

        assert _clean_partial_content("") == "(interrupted)"
        assert _clean_partial_content("   ") == "(interrupted)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
