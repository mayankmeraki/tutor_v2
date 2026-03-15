"""Simple in-memory per-IP rate limiter."""

import time
from collections import defaultdict

from fastapi import HTTPException, Request

_rate_buckets: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 20       # max requests
RATE_WINDOW = 60.0    # per 60 seconds


async def check_rate_limit(request: Request):
    """Dependency that enforces per-IP rate limiting."""
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _rate_buckets[ip]
    _rate_buckets[ip] = bucket = [t for t in bucket if now - t < RATE_WINDOW]
    if len(bucket) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")
    bucket.append(now)
