"""Per-IP and per-user rate limiter with LRU cleanup.

Supports tiered limits for different endpoint categories.
Uses X-Forwarded-For behind load balancers (Cloud Run, nginx).
"""

import os
import time
from collections import OrderedDict

from fastapi import HTTPException, Request

# ── Configuration ────────────────────────────────────────

RATE_LIMIT_TTS = int(os.getenv("RATE_LIMIT_TTS", "30"))         # TTS requests per window
RATE_LIMIT_AUTH = int(os.getenv("RATE_LIMIT_AUTH", "10"))        # login/signup per window
RATE_LIMIT_GENERAL = int(os.getenv("RATE_LIMIT_GENERAL", "60")) # other API calls per window
RATE_WINDOW = float(os.getenv("RATE_WINDOW", "60"))             # window in seconds
MAX_BUCKETS = 5000  # max tracked IPs before LRU eviction


# ── Bucket Store (LRU-evicting) ──────────────────────────

class RateBuckets:
    """In-memory rate limit buckets with LRU eviction."""

    def __init__(self, max_size: int = MAX_BUCKETS):
        self._buckets: OrderedDict[str, list[float]] = OrderedDict()
        self._max_size = max_size

    def check(self, key: str, limit: int, window: float = RATE_WINDOW) -> bool:
        """Returns True if request is allowed, False if rate limited."""
        now = time.time()

        # Prune old entries
        if key in self._buckets:
            self._buckets[key] = [t for t in self._buckets[key] if now - t < window]
            self._buckets.move_to_end(key)
        else:
            self._buckets[key] = []

        # LRU eviction
        while len(self._buckets) > self._max_size:
            self._buckets.popitem(last=False)

        if len(self._buckets[key]) >= limit:
            return False

        self._buckets[key].append(now)
        return True


_buckets = RateBuckets()


# ── Client Identity ──────────────────────────────────────

def _get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For behind load balancers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in chain is the real client
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Rate Limit Dependencies ──────────────────────────────

async def check_rate_limit(request: Request):
    """General rate limit — 60 req/min per IP."""
    ip = _get_client_ip(request)
    if not _buckets.check(f"gen:{ip}", RATE_LIMIT_GENERAL):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")


async def check_rate_limit_tts(request: Request):
    """TTS rate limit — 30 req/min per IP."""
    ip = _get_client_ip(request)
    if not _buckets.check(f"tts:{ip}", RATE_LIMIT_TTS):
        raise HTTPException(status_code=429, detail="TTS rate limit reached. Please wait.")


async def check_rate_limit_auth(request: Request):
    """Auth rate limit — 10 req/min per IP (brute force protection)."""
    ip = _get_client_ip(request)
    if not _buckets.check(f"auth:{ip}", RATE_LIMIT_AUTH):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please wait.")
