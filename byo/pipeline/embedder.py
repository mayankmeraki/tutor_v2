"""Embedding generator — batch API calls for chunk vectors.

Uses text-embedding-3-small via OpenRouter. Processes in batches
of 50 to maximize throughput while staying within rate limits.

Cost: ~$0.02 per 1M tokens (~$0.0003 for 100 chunks).
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 50
EMBED_MODEL = "text-embedding-3-small"


async def embed_chunks_batch(chunks: list[dict]):
    """Generate embeddings for all chunks. Modifies chunks in-place.

    Each chunk gets an "embedding" field (1536-dim vector).
    Processes in batches of EMBED_BATCH_SIZE.
    """
    if not chunks:
        return

    for i in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[i:i + EMBED_BATCH_SIZE]
        texts = [c.get("content", "")[:2000] for c in batch]  # cap at 2000 chars

        embeddings = await _generate_embeddings(texts)

        for j, embedding in enumerate(embeddings):
            batch[j]["embedding"] = embedding

    log.info("Embedded %d chunks in %d batches",
            len(chunks), (len(chunks) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE)


async def _generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    try:
        import httpx
        from backend.app.core.config import settings

        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            log.warning("No API key for embeddings")
            return [[] for _ in texts]

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": EMBED_MODEL, "input": texts},
            )

            if resp.status_code != 200:
                log.warning("Embedding API error: %d", resp.status_code)
                return [[] for _ in texts]

            data = resp.json()
            # Sort by index to maintain order
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in sorted_data]

    except Exception as e:
        log.error("Embedding generation failed: %s", e)
        return [[] for _ in texts]
