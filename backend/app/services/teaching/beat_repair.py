"""Heuristic repair + Haiku completion for truncated voice beats.

When the LLM runs out of tokens mid-animation code, the <vb> tag is
never closed. This module:
  1. Heuristically closes braces to make the code parseable (instant)
  2. Optionally calls Haiku to COMPLETE the truncated code (5s)

The heuristic gives a static scene (geometry visible, no animation loop).
Haiku restores the animation loop (rotation, breathing, shimmer effects).
"""

from __future__ import annotations

import asyncio
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


async def try_haiku_completion(accumulated_text: str, beat_detector: StreamingBeatDetector, slog=None) -> list[dict]:
    """Try Haiku completion first, fall back to heuristic repair.

    1. Extract the truncated animation code from the accumulated text
    2. Call Haiku to complete it (8s timeout)
    3. If Haiku succeeds: use the completed code
    4. If Haiku fails/times out: fall back to heuristic (close braces)
    """
    # First, find the truncated code
    scene_text = accumulated_text[beat_detector._scene_start:]
    last_vb_start = -1
    pos = 0
    while True:
        idx = scene_text.find('<vb ', pos)
        if idx < 0:
            break
        close_idx = scene_text.find('/>', idx)
        if close_idx < 0:
            last_vb_start = idx
            break
        pos = close_idx + 2

    if last_vb_start < 0:
        return [{"type": "VOICE_SCENE_END"}]

    partial_tag = scene_text[last_vb_start:]

    # Extract the truncated code string from the draw JSON
    code_match = re.search(r'"code"\s*:\s*"', partial_tag)
    truncated_code = None
    if code_match:
        # Extract everything after "code":" up to end (it's truncated)
        code_start = code_match.end()
        # Unescape the JSON string content for Haiku
        raw = partial_tag[code_start:]
        # This is still JSON-escaped (\n, \\, etc.) — decode common escapes
        raw = raw.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\')
        truncated_code = raw

    # Try Haiku completion if we have code to complete
    completed_code = None
    if truncated_code and len(truncated_code) > 100:
        if slog:
            slog.log_event("HAIKU_ATTEMPT", f"completing {len(truncated_code)} chars of truncated code")
        try:
            completed_code = await haiku_complete_truncated_code(truncated_code)
            if completed_code and slog:
                slog.log_event("HAIKU_SUCCESS", f"{len(truncated_code)} → {len(completed_code)} chars")
        except Exception as e:
            if slog:
                slog.log_error("HAIKU_FAILED", str(e))

    if completed_code:
        # Haiku succeeded — rebuild the beat with completed code
        # Re-escape for JSON
        escaped_code = completed_code.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')

        # Extract other attributes from the partial tag (cmd, id, title, legend)
        cmd_match = re.search(r'"cmd"\s*:\s*"([^"]*)"', partial_tag)
        id_match = re.search(r'"id"\s*:\s*"([^"]*)"', partial_tag)
        title_match = re.search(r'"title"\s*:\s*"([^"]*)"', partial_tag)
        say_match = re.search(r"say=['\"]([^'\"]*)", partial_tag)

        cmd_name = cmd_match.group(1) if cmd_match else "animation"
        anim_id = id_match.group(1) if id_match else "recovered-anim"
        title = title_match.group(1) if title_match else "Animation"
        say_text = say_match.group(1) if say_match else "Here's the visualization."

        draw_json = json.dumps({
            "cmd": cmd_name,
            "id": anim_id,
            "title": title,
            "code": completed_code,
        })
        repaired_tag = f"<vb draw='{draw_json}' say=\"{say_text}\" />"

        m = re.match(r'<vb\s+([\s\S]*?)/>', repaired_tag)
        if m:
            beat_data = parse_beat_attrs(m.group(1))
            beat_num = beat_detector.total_beats + 1
            beat_detector.total_beats = beat_num
            return [
                {"type": "VOICE_BEAT", "beat": beat_num, "data": beat_data},
                {"type": "VOICE_SCENE_END"},
            ]

    # Haiku failed — fall back to heuristic
    if slog:
        slog.log_event("HEURISTIC_FALLBACK", "Haiku failed, using brace-balancing repair")
    return repair_truncated_beat(accumulated_text, beat_detector)


# ═══════════════════════════════════════════════════════════════
#  HAIKU COMPLETION — complete the truncated animation code
# ═══════════════════════════════════════════════════════════════

HAIKU_COMPLETION_PROMPT = """You are completing TRUNCATED Three.js animation code.

THE SITUATION:
The code below was generated but CUT OFF mid-stream due to a token limit.
All the geometry, materials, groups, and scene.add() calls are CORRECT.
The code was truncated somewhere in the animation loop at the end.

YOUR TASK — COMPLETE THE CODE:
1. Output the ENTIRE code — the existing part UNCHANGED + your completion.
2. Do NOT modify ANY existing line. Not a single variable name, color,
   material, geometry, or position. Copy them EXACTLY as-is.
3. ONLY add what's missing after the cut-off point:
   - Close any open function/braces/parens
   - Complete the animation loop (requestAnimationFrame tick function)
   - Add simple rotation/breathing/oscillation for visual polish
4. Keep the completion SHORT — under 20 lines. Just close the loop.
5. Return ONLY the JavaScript code. No markdown, no explanation.

TEMPLATE for a typical completion (adapt variable names to match the code):
```
  // ... existing code ends here, you continue:
  })();
  // or if the tick function body was cut off:
  (function tick() {
    requestAnimationFrame(tick);
    time += 0.005;
    group.rotation.y = Math.sin(time * 0.3) * 0.15;
  })();
```

REMEMBER: the ENTIRE existing code must appear first, UNCHANGED."""


async def haiku_complete_truncated_code(truncated_code: str, code_type: str = "threejs") -> str | None:
    """Call Haiku to complete truncated animation code.

    Returns the full completed code, or None if completion failed.
    Timeout: 8 seconds.
    """
    from app.core.config import settings
    import httpx

    api_key = settings.OPENROUTER_API_KEY or settings.ANTHROPIC_API_KEY
    if not api_key:
        return None

    is_openrouter = bool(settings.OPENROUTER_API_KEY)
    base_url = "https://openrouter.ai/api/v1" if is_openrouter else "https://api.anthropic.com/v1"
    model = "anthropic/claude-haiku-4.5" if is_openrouter else "claude-haiku-4-5-20251001"

    user_msg = f"TRUNCATED CODE (complete this — copy existing lines exactly, only add the missing ending):\n\n{truncated_code[-3500:]}"

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            if is_openrouter:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": HAIKU_COMPLETION_PROMPT},
                            {"role": "user", "content": user_msg},
                        ],
                        "max_tokens": 4000,
                        "temperature": 0,
                    },
                )
                if resp.status_code != 200:
                    log.warning("[BeatRepair] Haiku completion failed: %d", resp.status_code)
                    return None
                data = resp.json()
                completed = data["choices"][0]["message"]["content"]
            else:
                resp = await client.post(
                    f"{base_url}/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "system": HAIKU_COMPLETION_PROMPT,
                        "messages": [{"role": "user", "content": user_msg}],
                        "max_tokens": 4000,
                        "temperature": 0,
                    },
                )
                if resp.status_code != 200:
                    log.warning("[BeatRepair] Haiku completion failed: %d", resp.status_code)
                    return None
                data = resp.json()
                completed = data["content"][0]["text"]

        # Strip markdown fences
        completed = completed.strip()
        if completed.startswith("```"):
            completed = completed.split("\n", 1)[1] if "\n" in completed else completed[3:]
        if completed.endswith("```"):
            completed = completed[:-3].rstrip()

        # Validate: completed code should be LONGER than truncated
        if len(completed) < len(truncated_code) * 0.8:
            log.warning("[BeatRepair] Haiku returned shorter code (%d < %d) — rejecting",
                        len(completed), len(truncated_code))
            return None

        log.info("[BeatRepair] Haiku completed: %d → %d chars (+%d)",
                 len(truncated_code), len(completed), len(completed) - len(truncated_code))
        return completed

    except asyncio.TimeoutError:
        log.warning("[BeatRepair] Haiku completion timed out (8s)")
        return None
    except Exception as e:
        log.warning("[BeatRepair] Haiku completion error: %s", e)
        return None
