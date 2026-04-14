"""ElevenLabs TTS service — server-side audio generation.

Extracted from the /api/tts proxy endpoint.  Used by the WebSocket
streaming pipeline to generate audio for voice beats.
"""

from __future__ import annotations

import logging
import re

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)

# ── Voice config ─────────────────────────────────────────────
VOICE_ID = "UgBBYS2sOqTuMpoF3BR0"
MODEL_ID = "eleven_turbo_v2_5"
VOICE_SETTINGS = {"stability": 0.55, "similarity_boost": 0.75, "style": 0.2}
OPTIMIZE_STREAMING_LATENCY = 4
MAX_TEXT_LENGTH = 490  # ElevenLabs limit is 500, leave margin
MIN_TEXT_LENGTH = 3    # Don't TTS very short strings
TTS_TIMEOUT = 8.0      # seconds — generous for slow responses


def voice_clean_text(text: str) -> str:
    """Clean text for TTS — strip markup that shouldn't be spoken.

    Python port of the frontend's voiceCleanText + additional fixes
    for server-side processing.
    """
    if not text:
        return ""

    s = text
    # Strip {ref:elementId} markers
    s = re.sub(r'\{ref:[^}]+\}', '', s)
    # Strip markdown bold/italic
    s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
    s = re.sub(r'\*(.+?)\*', r'\1', s)
    # Strip inline code
    s = re.sub(r'`(.+?)`', r'\1', s)
    # Strip HTML/XML tags
    s = re.sub(r'<[^>]+>', '', s)
    # Strip display math (remove entirely — can't speak equations)
    s = re.sub(r'\$\$[\s\S]+?\$\$', '', s)
    # Strip inline math (keep content — often readable)
    s = re.sub(r'\$(.+?)\$', r'\1', s)
    # Strip [bracketed] annotations
    s = re.sub(r'\[[^\]]*\]\s*', '', s)
    # Replace em-dashes and multi-hyphens with natural pauses (commas)
    # TTS engines mispronounce "--" and "—" as literal characters
    s = re.sub(r'\s*[—–]\s*', ', ', s)   # em-dash / en-dash → comma pause
    s = re.sub(r'\s*-{2,}\s*', ', ', s)  # -- or --- → comma pause
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    # Clean up double commas from replacements
    s = re.sub(r',\s*,', ',', s)
    # Filter out "(no text)" placeholder from backend serialization
    if s == "(no text)":
        return ""
    return s


async def elevenlabs_tts(text: str, voice_id: str | None = None) -> tuple[bytes | None, int]:
    """Call ElevenLabs streaming TTS.

    Returns (mp3_bytes, char_count). char_count is the actual number of
    characters sent to the API (after cleaning + truncation) — used for
    cost tracking. Returns (None, 0) on failure.
    """
    if not settings.ELEVENLABS_API_KEY:
        return None, 0

    clean = voice_clean_text(text)
    if not clean or len(clean) < MIN_TEXT_LENGTH:
        return None, 0

    # Truncate to stay within ElevenLabs limit
    if len(clean) > MAX_TEXT_LENGTH:
        clean = clean[:MAX_TEXT_LENGTH - 3] + "..."

    vid = voice_id or VOICE_ID
    char_count = len(clean)

    try:
        async with httpx.AsyncClient(timeout=TTS_TIMEOUT) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/stream",
                headers={
                    "xi-api-key": settings.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": clean,
                    "model_id": MODEL_ID,
                    "voice_settings": VOICE_SETTINGS,
                    "optimize_streaming_latency": OPTIMIZE_STREAMING_LATENCY,
                },
            )

            if resp.status_code == 429:
                log.warning("ElevenLabs rate limited (429)")
                return None, 0

            if resp.status_code != 200:
                log.warning("ElevenLabs error: %d", resp.status_code)
                return None, 0

            # Prefer exact count from response header; fallback to our clean text length
            header_count = resp.headers.get("x-character-count")
            if header_count and header_count.isdigit():
                char_count = int(header_count)

            return resp.content, char_count

    except httpx.TimeoutException:
        log.warning("ElevenLabs timeout for text: %s...", clean[:50])
        return None, 0
    except Exception as e:
        log.warning("ElevenLabs TTS failed: %s", e)
        return None, 0
