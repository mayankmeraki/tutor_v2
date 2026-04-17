"""Query expansion — HyDE (Hypothetical Document Embeddings).

For vague queries, embedding the query directly often misses. HyDE instead
asks a fast model to write a hypothetical passage answering the query, and
embeds *that*. Embeddings of passage-shaped text match passage-shaped
content better than question-shaped queries do.

Graceful degradation: on any failure, returns the original query so
retrieval never blocks on this optional enhancement.
"""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT_SECONDS = 3.0


def _settings():
    from app.core.config import settings
    return settings


async def hyde_expand(query: str) -> str:
    """Generate a hypothetical passage that would answer `query`.

    Returns the passage, or the original query on failure. Uses the
    configured fast model (Haiku by default).
    """
    if not query or not query.strip():
        return query

    s = _settings()
    api_key = s.OPENROUTER_API_KEY
    if not api_key:
        log.debug("OPENROUTER_API_KEY not set — skipping HyDE")
        return query

    model = s.MODEL_FAST
    prompt = f"Write a short hypothetical passage that would answer: {query}"

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.post(
                OPENROUTER_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://capacity.app",
                    "X-Title": "Capacity Tutor",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.2,
                },
            )
            if resp.status_code != 200:
                log.warning("HyDE non-200 (%d): %s", resp.status_code, resp.text[:200])
                return query
            data = resp.json()
    except httpx.TimeoutException:
        log.warning("HyDE timed out — using raw query")
        return query
    except Exception as e:
        log.warning("HyDE failed: %s — using raw query", e)
        return query

    try:
        passage = (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return query

    return passage or query
