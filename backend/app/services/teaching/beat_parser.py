"""Voice beat parser — extracts structured beat data from <vb/> tags.

Parses <vb say="..." draw='...' cursor="..." /> tags from LLM-generated
teaching voice scenes.  Used by the WebSocket streaming pipeline to send
pre-parsed VOICE_BEAT events to the client.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# ── Regexes ──────────────────────────────────────────────────

# Matches a complete <vb ... /> self-closing tag
VB_TAG_RE = re.compile(r'<vb\s+([\s\S]*?)/>')

# Matches <teaching-voice-scene ...> opening tag
SCENE_OPEN_RE = re.compile(r'<teaching-voice-scene[^>]*?(?:title=["\']([^"\']*)["\'])?[^>]*?>')

# Matches </teaching-voice-scene> closing tag
SCENE_CLOSE_RE = re.compile(r'</teaching-voice-scene>')

# Generic attribute extraction: attr='value' or attr="value"
def _attr(attr_str: str, name: str) -> str | None:
    """Extract a single-value attribute from an attribute string."""
    m = re.search(rf'{name}=\'([^\']*)\'|{name}="([^"]*)"', attr_str)
    if m:
        return m.group(1) if m.group(1) is not None else m.group(2)
    return None


def _attr_bool(attr_str: str, name: str) -> bool:
    return f'{name}="true"' in attr_str or f"{name}='true'" in attr_str


# ── Draw JSON parser ─────────────────────────────────────────

def _extract_draw_json(attr_str: str) -> str | None:
    """Extract draw attribute value using bracket matching.

    The draw attribute contains JSON that may have nested braces and quotes
    (especially in animation code).  Simple regex fails — use bracket
    matching to find the balanced JSON object.
    """
    draw_start = attr_str.find('draw=')
    if draw_start < 0:
        return None

    # Find opening { after draw=
    json_start = attr_str.find('{', draw_start)
    if json_start < 0:
        # Fallback: simple quote match for non-JSON values
        m = re.search(r"draw='([^']*)'", attr_str)
        return m.group(1) if m else None

    # Bracket-match to find closing }
    # Tracks both " and ' strings (animation code has JS with single quotes)
    depth = 0
    in_str = False
    str_char = ''
    esc = False
    json_end = -1

    for i in range(json_start, len(attr_str)):
        ch = attr_str[i]
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
        if ch in ('"', "'"):
            in_str = True
            str_char = ch
            continue
        if ch == '{':
            depth += 1
        if ch == '}':
            depth -= 1
            if depth == 0:
                json_end = i
                break

    if json_end > json_start:
        return attr_str[json_start:json_end + 1]

    return None


def _repair_draw_json(s: str) -> str:
    """Fix common LLM JSON issues in draw commands."""
    # Smart quotes → regular quotes
    s = s.replace('\u201c', '"').replace('\u201d', '"')
    s = s.replace('\u2018', "'").replace('\u2019', "'")
    # HTML entities
    s = s.replace('&quot;', '"').replace('&apos;', "'").replace('&#39;', "'")
    # Literal control characters inside JSON strings are invalid.
    s = s.replace('\r\n', '\\n').replace('\r', '\\n').replace('\n', '\\n')
    s = s.replace('\t', '\\t')
    s = s.replace('\x0c', '\\f')  # form feed (from LaTeX \f → 0x0c)
    s = s.replace('\x08', '\\b')  # backspace (from LaTeX \b → 0x08)
    # LaTeX backslashes: \rho, \frac, \partial etc. produce invalid JSON
    # escapes (\r=CR, \f=FF, \b=BS, \p=invalid, \m=invalid, etc.).
    # Fix: escape any lone backslash NOT followed by a valid JSON escape char.
    # Valid JSON escapes after \: " \ / b f n r t u
    import re
    s = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', s)
    return s


def _parse_draw(attr_str: str) -> list[dict] | None:
    """Parse draw attribute into list of draw command dicts."""
    draw_str = _extract_draw_json(attr_str)
    if not draw_str:
        return None

    # Try single JSON object FIRST — most common case, and safe even when
    # the text field contains \\n sequences (which JSONL split would break).
    try:
        return [json.loads(draw_str)]
    except (json.JSONDecodeError, ValueError):
        pass

    # Try with repair (literal newlines → \\n, smart quotes, etc.)
    repaired = _repair_draw_json(draw_str)
    try:
        return [json.loads(repaired)]
    except (json.JSONDecodeError, ValueError):
        pass

    # Try multi-line JSONL (one command per line) — for rare compound beats
    try:
        lines = [l.strip() for l in repaired.split('\\n') if l.strip()]
        if len(lines) > 1:
            cmds = [json.loads(l) for l in lines]
            return cmds
    except (json.JSONDecodeError, ValueError):
        pass

    # Try JSON array
    try:
        arr = json.loads(repaired)
        if isinstance(arr, list):
            return arr
    except (json.JSONDecodeError, ValueError):
        pass

    log.warning("Failed to parse draw JSON: %s...", draw_str[:150])
    # Return raw string wrapped — client has its own repair logic
    return [{"_raw": draw_str}]


# ── Beat attribute parser ────────────────────────────────────

def parse_beat_attrs(attr_str: str) -> dict[str, Any]:
    """Parse a <vb .../> tag's attribute string into a structured dict.

    Python port of frontend's _parseVoiceBeatAttrs().
    Returns all beat attributes the client needs for execution.
    """
    beat: dict[str, Any] = {}

    # say — text to speak
    say = _attr(attr_str, 'say')
    if say is not None:
        beat['say'] = say

    # draw — board drawing commands (JSON)
    draw = _parse_draw(attr_str)
    if draw:
        beat['draw'] = draw

    # cursor
    cursor = _attr(attr_str, 'cursor')
    if cursor:
        beat['cursor'] = cursor

    # pause (seconds)
    pause_str = _attr(attr_str, 'pause')
    if pause_str:
        try:
            beat['pause'] = float(pause_str)
        except ValueError:
            pass

    # question flag
    if _attr_bool(attr_str, 'question'):
        beat['question'] = True

    # widget
    wt = _attr(attr_str, 'widget-title')
    if wt:
        beat['widgetTitle'] = wt
    wc = _attr(attr_str, 'widget-code')
    if wc:
        beat['widgetCode'] = wc

    # simulation
    sim = _attr(attr_str, 'simulation')
    if sim:
        beat['simulation'] = sim

    # video
    vl = _attr(attr_str, 'video-lesson')
    if vl:
        beat['videoLesson'] = vl
    vs = _attr(attr_str, 'video-start')
    if vs:
        beat['videoStart'] = vs
    ve = _attr(attr_str, 'video-end')
    if ve:
        beat['videoEnd'] = ve

    # image
    img_src = _attr(attr_str, 'image-src')
    if img_src:
        beat['imageSrc'] = img_src
    img_cap = _attr(attr_str, 'image-caption')
    if img_cap:
        beat['imageCaption'] = img_cap

    # anim-control (JSON)
    ac = _attr(attr_str, 'anim-control')
    if ac:
        try:
            beat['animControl'] = json.loads(ac)
        except (json.JSONDecodeError, ValueError):
            pass

    # clear-before
    if _attr_bool(attr_str, 'clear-before'):
        beat['clearBefore'] = True

    # scroll-to
    st = _attr(attr_str, 'scroll-to')
    if st:
        beat['scrollTo'] = st

    # annotate
    ann = _attr(attr_str, 'annotate')
    if ann:
        beat['annotate'] = ann
    ann_color = _attr(attr_str, 'annotate-color')
    if ann_color:
        beat['annotateColor'] = ann_color
    ann_dur = _attr(attr_str, 'annotate-duration')
    if ann_dur:
        try:
            beat['annotateDuration'] = int(ann_dur)
        except ValueError:
            pass

    return beat


# ── Streaming beat detector ──────────────────────────────────

class StreamingBeatDetector:
    """Watches accumulated LLM text and detects new complete <vb/> tags.

    Tracks a text cursor so it never re-parses already-processed text.
    This prevents duplicate beats when multiple voice scenes appear in
    one response.
    """

    def __init__(self):
        self.parsed_count: int = 0       # beats in current scene
        self.total_beats: int = 0        # total across all scenes
        self.scene_started: bool = False
        self.scene_title: str | None = None
        self.scene_ended: bool = False
        self._cursor: int = 0            # where to start looking for next scene
        self._scene_start: int = 0       # where current scene's content begins

    def feed(self, accumulated_text: str) -> list[dict]:
        """Feed the full accumulated text. Returns new events since last call.

        Searches full text for tags (handles tags split across chunks)
        but uses _cursor to avoid emitting duplicate events.
        """
        events: list[dict] = []

        # Detect scene open — search full text (tag may span chunks)
        if not self.scene_started:
            # Look for scene opening AFTER cursor
            m = SCENE_OPEN_RE.search(accumulated_text, self._cursor)
            if m:
                self.scene_started = True
                self.scene_title = m.group(1) or "Teaching"
                events.append({
                    "type": "VOICE_SCENE_START",
                    "title": self.scene_title,
                })
                # Set cursor to start of this scene's content
                self._scene_start = m.end()

        if not self.scene_started:
            return events

        # Parse beats from current scene (from scene start to end of text)
        scene_text = accumulated_text[self._scene_start:]
        matches = list(VB_TAG_RE.finditer(scene_text))
        new_matches = matches[self.parsed_count:]

        for match in new_matches:
            self.parsed_count += 1
            self.total_beats += 1
            beat_data = parse_beat_attrs(match.group(1))

            # Log every beat with enough detail to debug voice issues
            say_text = beat_data.get('say', '')
            draw_cmds = beat_data.get('draw', [])
            cmd_names = ', '.join(d.get('cmd', '?') for d in draw_cmds if isinstance(d, dict)) or 'none'
            has_draw = bool(draw_cmds)
            has_say = bool(say_text and say_text.strip())
            log.info(
                "Beat #%d | draw:[%s] | say:%s | question:%s",
                self.total_beats, cmd_names,
                f'"{say_text[:60]}"' if has_say else '⚠️ EMPTY',
                beat_data.get('question', False),
            )
            if has_draw and not has_say:
                log.warning(
                    "Beat #%d has draw (%s) but EMPTY say — student will hear silence",
                    self.total_beats, cmd_names,
                )

            events.append({
                "type": "VOICE_BEAT",
                "beat": self.total_beats,
                "data": beat_data,
            })

        # Detect scene close
        if not self.scene_ended:
            close_m = SCENE_CLOSE_RE.search(scene_text)
            if close_m:
                self.scene_ended = True
                events.append({"type": "VOICE_SCENE_END"})
                # Move cursor past closing tag for next scene
                self._cursor = self._scene_start + close_m.end()

        return events

    def reset(self):
        """Reset for a new scene (within same turn if multiple scenes).

        Keeps _cursor so we don't re-scan already-processed text.
        Keeps total_beats for monotonic beat numbering.
        """
        self.parsed_count = 0
        self.scene_started = False
        self.scene_title = None
        self.scene_ended = False
        # NOTE: _cursor and total_beats are NOT reset
