"""Cross-encoder rerank via OpenRouter.

Uses OpenRouter's /rerank endpoint with `cohere/rerank-4-fast` — a
multilingual cross-encoder tuned for low latency. Single API key shared
with the rest of the LLM stack (OPENROUTER_API_KEY).

Graceful degradation: if the key is missing or the request fails,
returns the input unchanged so retrieval always yields something.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from byo.shared.results import RetrievedChunk

log = logging.getLogger(__name__)


RERANK_URL = "https://openrouter.ai/api/v1/rerank"
RERANK_MODEL = "cohere/rerank-4-fast"
TIMEOUT_SECONDS = 5.0


def _settings():
    # Lazy import so importing this module doesn't require settings at import time
    from app.core.config import settings
    return settings


async def cohere_rerank(
    query: str,
    hits: list[RetrievedChunk],
    top_n: int,
) -> list[RetrievedChunk]:
    """Re-rank `hits` with OpenRouter's rerank endpoint. Returns up to `top_n`.

    On any failure (no key, timeout, network, unexpected payload) returns
    `hits[:top_n]` unchanged with rerank_score left as-is.
    """
    if not hits:
        return []
    top_n = max(1, min(top_n, len(hits)))

    api_key = _settings().OPENROUTER_API_KEY
    if not api_key:
        log.warning("OPENROUTER_API_KEY not set — skipping rerank")
        return hits[:top_n]

    documents = [h.content for h in hits]
    payload: dict[str, Any] = {
        "model": RERANK_MODEL,
        "query": query,
        "documents": documents,
        "top_n": top_n,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.post(
                RERANK_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code != 200:
                log.warning(
                    "Cohere rerank non-200 (%d): %s — returning input order",
                    resp.status_code,
                    resp.text[:200],
                )
                return hits[:top_n]
            body = resp.json()
    except httpx.TimeoutException:
        log.warning("Cohere rerank timed out — returning input order")
        return hits[:top_n]
    except Exception as e:
        log.warning("Cohere rerank failed: %s — returning input order", e)
        return hits[:top_n]

    results = body.get("results") or []
    if not results:
        return hits[:top_n]

    reordered: list[RetrievedChunk] = []
    for r in results:
        idx = r.get("index")
        if idx is None or idx < 0 or idx >= len(hits):
            continue
        hit = hits[idx]
        score = r.get("relevance_score")
        if score is not None:
            try:
                hit.rerank_score = float(score)
            except (TypeError, ValueError):
                pass
        reordered.append(hit)

    if not reordered:
        return hits[:top_n]
    return reordered[:top_n]
