"""Heuristic repair for truncated voice beats.

When the LLM runs out of tokens mid-animation code, the <vb> tag is
never closed. This module attempts to close it so the beat can still
be parsed and the geometry (already scene.add()'d) can render.

Strategy:
  1. Find the last unclosed <vb in the accumulated text
  2. Extract the partial draw JSON
  3. Balance braces/brackets/quotes to close the code string
  4. Close the JSON object and the <vb /> tag
  5. Parse the repaired beat
  6. Also close the scene if it was open
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from .beat_parser import parse_beat_attrs, StreamingBeatDetector

log = logging.getLogger(__name__)


def _balance_js_code(code: str) -> str:
    """Close unclosed braces/brackets/parens in truncated JS code.

    The code was cut off mid-expression. We need to close everything
    so it at least compiles. The geometry is already added to the scene
    via scene.add() calls — the animation loop just won't run.
    """
    # Track nesting
    depth_brace = 0   # {}
    depth_paren = 0   # ()
    depth_bracket = 0 # []
    in_str = False
    str_char = ''
    esc = False

    for ch in code:
        if esc:
            esc = False
            continue
        if ch == '\\':
            esc = True
            continue
        if in_str:
            if ch == str_char:
                in_str = False
            continue
        if ch in ('"', "'", '`'):
            in_str = True
            str_char = ch
            continue
        if ch == '{': depth_brace += 1
        elif ch == '}': depth_brace -= 1
        elif ch == '(': depth_paren += 1
        elif ch == ')': depth_paren -= 1
        elif ch == '[': depth_bracket += 1
        elif ch == ']': depth_bracket -= 1

    # Close any open string
    if in_str:
        code += str_char

    # Close brackets/parens/braces in reverse order
    closers = ''
    closers += ']' * max(0, depth_bracket)
    closers += ')' * max(0, depth_paren)
    closers += '}' * max(0, depth_brace)

    return code + closers


def repair_truncated_beat(accumulated_text: str, beat_detector: StreamingBeatDetector) -> list[dict]:
    """Attempt to repair a truncated beat and emit events.

    Returns a list of events (VOICE_BEAT, VOICE_SCENE_END) that should
    be sent to the client.
    """
    events = []

    # Find the last unclosed <vb tag
    # Look in the scene content (after scene start)
    scene_text = accumulated_text[beat_detector._scene_start:]

    # Find the last <vb that doesn't have a closing />
    last_vb_start = -1
    pos = 0
    while True:
        idx = scene_text.find('<vb ', pos)
        if idx < 0:
            break
        # Check if this tag is closed
        close_idx = scene_text.find('/>', idx)
        if close_idx < 0:
            last_vb_start = idx
            break
        pos = close_idx + 2

    if last_vb_start < 0:
        log.info("[BeatRepair] No unclosed <vb> tag found")
        # Still close the scene
        events.append({"type": "VOICE_SCENE_END"})
        return events

    partial_tag = scene_text[last_vb_start:]
    log.info("[BeatRepair] Found unclosed <vb> tag at offset %d, %d chars", last_vb_start, len(partial_tag))

    # Try to repair the tag
    repaired_tag = _repair_vb_tag(partial_tag)
    if not repaired_tag:
        log.warning("[BeatRepair] Could not repair tag")
        events.append({"type": "VOICE_SCENE_END"})
        return events

    # Parse the repaired tag
    # Extract attributes from <vb ... />
    m = re.match(r'<vb\s+([\s\S]*?)/>', repaired_tag)
    if not m:
        log.warning("[BeatRepair] Repaired tag doesn't match pattern")
        events.append({"type": "VOICE_SCENE_END"})
        return events

    beat_data = parse_beat_attrs(m.group(1))
    beat_num = beat_detector.total_beats + 1
    beat_detector.total_beats = beat_num

    events.append({
        "type": "VOICE_BEAT",
        "beat": beat_num,
        "data": beat_data,
    })
    events.append({"type": "VOICE_SCENE_END"})

    log.info("[BeatRepair] Repaired beat #%d: draw=%s, say=%s",
             beat_num,
             [d.get('cmd') for d in beat_data.get('draw', []) if isinstance(d, dict)],
             (beat_data.get('say', '') or '')[:60])

    return events


def _repair_vb_tag(partial: str) -> str | None:
    """Try to close a truncated <vb draw='...' say='...' /> tag."""

    # Case 1: The code JSON is truncated inside draw='{"cmd":"animation","code":"...'
    # Strategy: find the draw attribute, balance the code, close the JSON, close the tag

    draw_start = partial.find("draw='")
    if draw_start < 0:
        draw_start = partial.find('draw="')

    if draw_start >= 0:
        # Find where the JSON starts
        json_start = partial.find('{', draw_start)
        if json_start < 0:
            return None

        # The JSON might contain a "code" field with a string value
        # that itself contains braces. Use bracket matching.
        json_str = partial[json_start:]

        # Check if the code field exists and is truncated
        code_match = re.search(r'"code"\s*:\s*"', json_str)
        if code_match:
            # The code string value is truncated. Find where it starts
            code_value_start = code_match.end()

            # Find the end of the code string — scan for unescaped "
            pos = code_value_start
            esc = False
            code_end = -1
            while pos < len(json_str):
                ch = json_str[pos]
                if esc:
                    esc = False
                    pos += 1
                    continue
                if ch == '\\':
                    esc = True
                    pos += 1
                    continue
                if ch == '"':
                    code_end = pos
                    break
                pos += 1

            if code_end < 0:
                # Code string is truncated — close it
                # First, balance the JS code inside the string
                code_content = json_str[code_value_start:]
                # The code is escaped (\\n for newlines, \\" for quotes)
                # We need to balance the UNESCAPED braces
                balanced = _balance_js_code(code_content)

                # Close the code string and the JSON object
                repaired_json = json_str[:code_value_start] + balanced + '"}'

                # Try to parse it
                try:
                    json.loads(repaired_json)
                except json.JSONDecodeError:
                    # Simpler approach: just close with enough closers
                    repaired_json = json_str[:code_value_start] + balanced + '"}'
                    # Replace literal newlines that break JSON
                    repaired_json = repaired_json.replace('\n', '\\n').replace('\r', '\\n').replace('\t', '\\t')
                    try:
                        json.loads(repaired_json)
                    except json.JSONDecodeError:
                        log.warning("[BeatRepair] JSON still invalid after repair")
                        # Last resort: strip the code entirely and just keep the cmd
                        repaired_json = '{"cmd":"animation","title":"Animation (recovered)","code":""}'

                # Reconstruct the tag
                # Check if say attribute exists
                say_match = re.search(r"say=['\"]([^'\"]*)", partial)
                say_text = say_match.group(1) if say_match else "Here's the visualization."

                return f"<vb draw='{repaired_json}' say=\"{say_text}\" />"

        # No code field — just balance the JSON
        balanced_json = _balance_js_code(json_str)
        # Try to find say
        say_match = re.search(r"say=['\"]([^'\"]*)", partial)
        say_text = say_match.group(1) if say_match else "Here's the visualization."
        return f"<vb draw='{balanced_json}' say=\"{say_text}\" />"

    # Case 2: draw attribute not found — the tag is very incomplete
    # Just create a minimal say-only beat
    say_match = re.search(r"say=['\"]([^'\"]*)", partial)
    if say_match:
        return f"<vb say=\"{say_match.group(1)}\" />"

    return None
