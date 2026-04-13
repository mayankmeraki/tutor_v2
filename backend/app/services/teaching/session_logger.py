"""Per-session generation logger.

Writes LLM generations and beat events to per-session log files in /tmp/euler_logs/.
Each session gets its own file. Files rotate (deleted after 3 days).
Claude Code can read these directly for debugging.

Usage:
    from app.services.teaching.session_logger import SessionLogger

    logger = SessionLogger(session_id)
    logger.log_delta(delta_text)        # accumulate streaming text
    logger.log_beat(beat_num, beat_data) # log parsed beat
    logger.log_event(event_type, data)   # log any event
    logger.flush_generation(gen_num)     # write accumulated text to file
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR = Path("/tmp/euler_logs")
MAX_AGE_DAYS = 3


def _ensure_dir():
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _cleanup_old_logs():
    """Delete log files older than MAX_AGE_DAYS."""
    try:
        cutoff = time.time() - MAX_AGE_DAYS * 86400
        for f in LOG_DIR.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
    except Exception:
        pass


class SessionLogger:
    def __init__(self, session_id: str):
        _ensure_dir()
        _cleanup_old_logs()
        self.session_id = session_id
        safe_id = session_id.replace("/", "_")[:60]
        self.path = LOG_DIR / f"{safe_id}.log"
        self._accumulated = []
        self._gen = 0
        self._write(f"\n{'='*70}\n SESSION {session_id}\n Started: {datetime.now().isoformat()}\n{'='*70}\n")

    def _write(self, text: str):
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass

    def log_delta(self, delta: str):
        """Accumulate streaming text delta."""
        self._accumulated.append(delta)

    def flush_generation(self, gen: int):
        """Write the full accumulated generation text to the log file."""
        self._gen = gen
        full_text = "".join(self._accumulated)
        self._accumulated.clear()
        ts = datetime.now().strftime("%H:%M:%S")
        self._write(
            f"\n{'─'*70}\n"
            f" GEN {gen} | {ts} | {len(full_text)} chars\n"
            f"{'─'*70}\n"
            f"{full_text}\n"
        )

    def log_beat(self, beat_num: int, beat_data: dict):
        """Log a parsed beat with its draw commands and say text."""
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        say = beat_data.get("say", "")[:80]
        draw = beat_data.get("draw", [])
        cmds = ", ".join(d.get("cmd", "?") for d in draw if isinstance(d, dict))
        code_len = 0
        for d in draw:
            if isinstance(d, dict) and "code" in d:
                code_len = len(d["code"])

        line = f"  [{ts}] BEAT #{beat_num} | draw:[{cmds}]"
        if code_len > 0:
            line += f" | code:{code_len}chars"
        line += f' | say:"{say}"'
        if beat_data.get("question"):
            line += " | QUESTION"
        self._write(line + "\n")

    def log_scene_start(self, title: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._write(f"\n  [{ts}] ▶ SCENE START: {title}\n")

    def log_scene_end(self):
        ts = datetime.now().strftime("%H:%M:%S")
        self._write(f"  [{ts}] ■ SCENE END\n")

    def log_event(self, event_type: str, data: str = ""):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._write(f"  [{ts}] {event_type} {data[:200]}\n")

    def log_error(self, context: str, error: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._write(f"  [{ts}] ❌ ERROR [{context}]: {error}\n")

    def log_truncation_warning(self, accumulated_len: int):
        """Log when a generation ends with unclosed beats."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._write(
            f"  [{ts}] ⚠️ GENERATION ENDED WITH UNCLOSED BEAT\n"
            f"           accumulated text: {accumulated_len} chars\n"
            f"           This usually means animation code was too long\n"
            f"           and the LLM ran out of tokens mid-<vb> tag.\n"
        )
