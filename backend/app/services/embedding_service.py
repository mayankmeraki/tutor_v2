"""Embedding service — generates vector embeddings via OpenRouter.

Uses OpenRouter's embeddings API with text-embedding-3-small for fast,
cheap embeddings. Stores metadata about the embedding model used.

Used by:
- knowledge_state.py: embed student notes for vector search
- student_note_index: materialized flat index for MongoDB Atlas Vector Search
"""

import logging
from typing import Optional

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)

# Model config — fastest + cheapest OpenAI embedding via OpenRouter
EMBEDDING_MODEL = "openai/text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
EMBEDDING_PROVIDER = "openrouter"

# OpenRouter embeddings endpoint
OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"


async def generate_embedding(text: str) -> Optional[list[float]]:
    """Generate a vector embedding for a single text string.

    Returns a 1536-dimensional float vector, or None on failure.
    Uses OpenRouter with text-embedding-3-small (fast, cheap, good quality).
    """
    if not text or not text.strip():
        return None

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        log.warning("No OPENROUTER_API_KEY — cannot generate embeddings")
        return None

    # Truncate very long texts (embedding model has ~8K token limit)
    clean_text = text.strip()[:8000]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                OPENROUTER_EMBEDDINGS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": EMBEDDING_MODEL,
                    "input": clean_text,
                },
            )

            if resp.status_code != 200:
                log.warning("Embedding API error: %d %s", resp.status_code, resp.text[:200])
                return None

            data = resp.json()
            embedding = data["data"][0]["embedding"]

            if len(embedding) != EMBEDDING_DIMENSIONS:
                log.warning("Unexpected embedding dimension: %d (expected %d)",
                            len(embedding), EMBEDDING_DIMENSIONS)

            return embedding

    except httpx.TimeoutException:
        log.warning("Embedding request timed out")
        return None
    except Exception as e:
        log.warning("Embedding generation failed: %s", e)
        return None


async def generate_embeddings_batch(texts: list[str]) -> list[Optional[list[float]]]:
    """Generate embeddings for multiple texts in a single API call.

    Returns a list of embeddings (same order as input).
    Failed items are None.
    """
    if not texts:
        return []

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        return [None] * len(texts)

    # Clean and truncate
    clean_texts = [t.strip()[:8000] for t in texts if t and t.strip()]
    if not clean_texts:
        return [None] * len(texts)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                OPENROUTER_EMBEDDINGS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": EMBEDDING_MODEL,
                    "input": clean_texts,
                },
            )

            if resp.status_code != 200:
                log.warning("Batch embedding error: %d", resp.status_code)
                return [None] * len(texts)

            data = resp.json()
            return [item["embedding"] for item in data["data"]]

    except Exception as e:
        log.warning("Batch embedding failed: %s", e)
        return [None] * len(texts)


def get_embedding_metadata() -> dict:
    """Return metadata about the embedding model used — stored alongside vectors."""
    return {
        "model": EMBEDDING_MODEL,
        "dimensions": EMBEDDING_DIMENSIONS,
        "provider": EMBEDDING_PROVIDER,
    }
