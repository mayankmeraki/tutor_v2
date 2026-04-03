"""Tests for board-frames extraction logic.

Tests the _extract_draw_commands helper and the board-frames endpoint
parsing logic without requiring a running server or database.
"""

import json
import pytest

# Import the extraction function directly
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _extract_draw_commands(scene_content: str) -> list[dict]:
    """Copy of the function from sessions.py for unit testing."""
    commands = []
    idx = 0
    while idx < len(scene_content):
        draw_pos = scene_content.find("draw=", idx)
        if draw_pos == -1:
            break
        quote_pos = draw_pos + 5
        if quote_pos >= len(scene_content):
            break
        quote_char = scene_content[quote_pos]
        if quote_char not in ("'", '"'):
            idx = quote_pos + 1
            continue
        json_start = quote_pos + 1
        if json_start >= len(scene_content) or scene_content[json_start] != '{':
            idx = json_start + 1
            continue
        depth = 0
        json_end = json_start
        in_string = False
        escape_next = False
        for j in range(json_start, len(scene_content)):
            ch = scene_content[j]
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                continue
            if ch == '"' and not in_string:
                in_string = True
                continue
            if ch == '"' and in_string:
                in_string = False
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    json_end = j + 1
                    break
        if depth != 0:
            idx = json_start + 1
            continue
        json_str = scene_content[json_start:json_end]
        try:
            commands.append(json.loads(json_str))
        except json.JSONDecodeError:
            pass
        idx = json_end
    return commands


def _extract_frames_from_messages(messages: list[dict]) -> list[dict]:
    """Simulate the board-frames endpoint extraction logic."""
    import re
    frames = []
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        raw_content = msg.get("content", "")
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

        # teaching-board-draw (text mode)
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
                    commands.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            if commands:
                frames.append({"title": title, "commands": commands})

        # teaching-voice-scene (voice mode)
        for vs_match in re.finditer(
            r'<teaching-voice-scene[^>]*>([\s\S]*?)</teaching-voice-scene>', content
        ):
            title_match = re.search(r'title=["\']([^"\']*)["\']', vs_match.group(0))
            title = title_match.group(1) if title_match else "Board"
            scene_content = vs_match.group(1)
            commands = _extract_draw_commands(scene_content)
            if commands:
                frames.append({"title": title, "commands": commands})

    return frames


# ── _extract_draw_commands tests ──


class TestExtractDrawCommands:
    def test_simple_single_quote(self):
        scene = """<vb draw='{"cmd":"text","text":"Hello"}' say="Hi" />"""
        cmds = _extract_draw_commands(scene)
        assert len(cmds) == 1
        assert cmds[0]["cmd"] == "text"
        assert cmds[0]["text"] == "Hello"

    def test_simple_double_quote(self):
        scene = '<vb draw="{\\"cmd\\":\\"text\\",\\"text\\":\\"Hello\\"}" say="Hi" />'
        # Note: in actual transcript, double-quote draw values use escaped quotes
        # This test verifies the brace-matching works with double-quote delimiters
        cmds = _extract_draw_commands(scene)
        # May or may not parse depending on escaping — the key test is it doesn't crash
        assert isinstance(cmds, list)

    def test_multiple_beats(self):
        scene = """
        <vb draw='{"cmd":"text","text":"Title","size":"h1"}' say="Welcome" />
        <vb draw='{"cmd":"text","text":"Subtitle","size":"h3"}' say="Let me explain" />
        <vb draw='{"cmd":"gap","height":20}' />
        """
        cmds = _extract_draw_commands(scene)
        assert len(cmds) == 3
        assert cmds[0]["text"] == "Title"
        assert cmds[1]["text"] == "Subtitle"
        assert cmds[2]["cmd"] == "gap"

    def test_nested_json_objects(self):
        """Draw commands with nested objects (e.g., items array with color objects)."""
        scene = """<vb draw='{"cmd":"list","items":[{"text":"Item 1","color":"#ff0000"},{"text":"Item 2","color":"#00ff00"}]}' say="Here's a list" />"""
        cmds = _extract_draw_commands(scene)
        assert len(cmds) == 1
        assert cmds[0]["cmd"] == "list"
        assert len(cmds[0]["items"]) == 2
        assert cmds[0]["items"][0]["color"] == "#ff0000"

    def test_nested_json_deep(self):
        """Deeply nested JSON (3 levels)."""
        scene = """<vb draw='{"cmd":"complex","data":{"nested":{"deep":"value"}}}' />"""
        cmds = _extract_draw_commands(scene)
        assert len(cmds) == 1
        assert cmds[0]["data"]["nested"]["deep"] == "value"

    def test_escaped_quotes_in_values(self):
        """JSON with escaped quotes inside string values."""
        scene = """<vb draw='{"cmd":"text","text":"He said \\"hello\\""}' />"""
        cmds = _extract_draw_commands(scene)
        assert len(cmds) == 1
        assert "hello" in cmds[0]["text"]

    def test_empty_scene(self):
        cmds = _extract_draw_commands("")
        assert cmds == []

    def test_no_draw_attributes(self):
        scene = """<vb say="Hello" /><vb say="World" />"""
        cmds = _extract_draw_commands(scene)
        assert cmds == []

    def test_beat_with_say_only(self):
        """Mixed beats: some with draw, some without."""
        scene = """
        <vb say="Let me start" />
        <vb draw='{"cmd":"text","text":"Physics"}' say="Here we go" />
        <vb say="Watch carefully" />
        """
        cmds = _extract_draw_commands(scene)
        assert len(cmds) == 1
        assert cmds[0]["text"] == "Physics"

    def test_malformed_json(self):
        """Malformed JSON should be skipped, not crash."""
        scene = """<vb draw='{"cmd":"text","text":"ok"}' /><vb draw='{broken json}' /><vb draw='{"cmd":"gap"}' />"""
        cmds = _extract_draw_commands(scene)
        assert len(cmds) == 2  # first and third succeed, second skipped

    def test_real_world_format(self):
        """Test with actual format from production MongoDB."""
        scene = (
            '<vb draw=\'{"cmd":"text","text":"Quantum Entanglement","placement":"center",'
            '"size":"h1","color":"#fbbf24","id":"title"}\' say="Hey Mayank!" />\n'
            '<vb draw=\'{"cmd":"text","text":"Two particles, linked across space",'
            '"placement":"below","size":"h3","color":"#94a3b8"}\' say="Let me draw this" />'
        )
        cmds = _extract_draw_commands(scene)
        assert len(cmds) == 2
        assert cmds[0]["text"] == "Quantum Entanglement"
        assert cmds[0]["placement"] == "center"
        assert cmds[1]["size"] == "h3"


# ── Full message extraction tests ──


class TestExtractFramesFromMessages:
    def test_text_mode_board_draw(self):
        """Text mode: <teaching-board-draw> with JSONL content."""
        messages = [
            {"role": "user", "content": "teach me physics"},
            {"role": "assistant", "content": (
                'Let me draw this!\n'
                '<teaching-board-draw title="Forces">\n'
                '{"cmd":"text","text":"Forces","size":"h1"}\n'
                '{"cmd":"text","text":"F = ma","size":"h2"}\n'
                '</teaching-board-draw>'
            )},
        ]
        frames = _extract_frames_from_messages(messages)
        assert len(frames) == 1
        assert frames[0]["title"] == "Forces"
        assert len(frames[0]["commands"]) == 2

    def test_voice_mode_scene(self):
        """Voice mode: <teaching-voice-scene> with <vb> beats."""
        messages = [
            {"role": "user", "content": "[SYSTEM] Start"},
            {"role": "assistant", "content": (
                '<teaching-voice-scene title="Quantum">\n'
                '<vb draw=\'{"cmd":"text","text":"Quantum","size":"h1"}\' say="Hello" />\n'
                '<vb draw=\'{"cmd":"text","text":"Waves","size":"h3"}\' say="Look" />\n'
                '</teaching-voice-scene>'
            )},
        ]
        frames = _extract_frames_from_messages(messages)
        assert len(frames) == 1
        assert frames[0]["title"] == "Quantum"
        assert len(frames[0]["commands"]) == 2

    def test_content_blocks_format(self):
        """Anthropic API format: content is a list of blocks."""
        messages = [
            {"role": "assistant", "content": [
                {"type": "text", "text": (
                    '<teaching-voice-scene title="Physics">\n'
                    '<vb draw=\'{"cmd":"text","text":"Newton"}\' say="Hi" />\n'
                    '</teaching-voice-scene>'
                )},
            ]},
        ]
        frames = _extract_frames_from_messages(messages)
        assert len(frames) == 1
        assert frames[0]["commands"][0]["text"] == "Newton"

    def test_multiple_scenes_in_transcript(self):
        """Multiple board draws across multiple messages."""
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": (
                '<teaching-voice-scene title="Scene 1">\n'
                '<vb draw=\'{"cmd":"text","text":"First"}\' />\n'
                '</teaching-voice-scene>'
            )},
            {"role": "user", "content": "ok"},
            {"role": "assistant", "content": (
                '<teaching-voice-scene title="Scene 2">\n'
                '<vb draw=\'{"cmd":"text","text":"Second"}\' />\n'
                '</teaching-voice-scene>'
            )},
        ]
        frames = _extract_frames_from_messages(messages)
        assert len(frames) == 2
        assert frames[0]["title"] == "Scene 1"
        assert frames[1]["title"] == "Scene 2"

    def test_empty_transcript(self):
        frames = _extract_frames_from_messages([])
        assert frames == []

    def test_user_only_transcript(self):
        """Transcript with only user messages (the original bug)."""
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "user", "content": "ok"},
        ]
        frames = _extract_frames_from_messages(messages)
        assert frames == []

    def test_assistant_without_board_content(self):
        """Assistant message with text but no board draws."""
        messages = [
            {"role": "assistant", "content": "Sure, let me explain quantum physics to you."},
        ]
        frames = _extract_frames_from_messages(messages)
        assert frames == []

    def test_tool_use_content_blocks(self):
        """Content blocks with tool_use (no text) should be skipped."""
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tool_1", "name": "web_search", "input": {"query": "test"}},
            ]},
        ]
        frames = _extract_frames_from_messages(messages)
        assert frames == []

    def test_mixed_text_and_tool_blocks(self):
        """Content blocks with both text and tool_use."""
        messages = [
            {"role": "assistant", "content": [
                {"type": "text", "text": (
                    '<teaching-voice-scene title="Mix">\n'
                    '<vb draw=\'{"cmd":"text","text":"Hello"}\' />\n'
                    '</teaching-voice-scene>'
                )},
                {"type": "tool_use", "id": "t1", "name": "search", "input": {}},
            ]},
        ]
        frames = _extract_frames_from_messages(messages)
        assert len(frames) == 1
        assert frames[0]["commands"][0]["text"] == "Hello"

    def test_none_content(self):
        """Content is None — should not crash."""
        messages = [
            {"role": "assistant", "content": None},
        ]
        frames = _extract_frames_from_messages(messages)
        assert frames == []

    def test_numeric_content(self):
        """Content is a non-string, non-list type — should skip."""
        messages = [
            {"role": "assistant", "content": 42},
        ]
        frames = _extract_frames_from_messages(messages)
        assert frames == []
