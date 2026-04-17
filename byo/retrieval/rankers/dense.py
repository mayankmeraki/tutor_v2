"""Dense ranker — vector search over BYO segment embeddings.

Primary path: Qdrant (dedicated vector DB, fast, always-indexed).
Fallback 1:   Atlas $vectorSearch (if Qdrant unavailable + Atlas index exists).
Fallback 2:   Python-side cosine over Mongo segments (no index needed, <200ms).

Returns [(segment_id, parent_chunk_id, score)] — the caller does small-to-big
expansion and Mongo joins to parent Chunk records.
"""

from __future__ import annotations

import logging
from typing import Any

from byo.shared.results import SearchFilters

log = logging.getLogger(__name__)


SEGMENTS_COLLECTION = "byo_segments"
CHUNKS_COLLECTION = "byo_chunks"
SEGMENTS_VECTOR_INDEX = "byo_segments_vector"
LEGACY_VECTOR_INDEX = "byo_chunks_vector"


def _get_db():
    from app.core.mongodb import get_mongo_db
    return get_mongo_db()


async def _segments_populated(db) -> bool:
    """Check if the new byo_segments collection has any documents.

    Cheap existence probe — caches via collection listing. If empty or
    missing, callers fall back to the legacy `byo_chunks.embedding` path.
    """
    try:
        doc = await db[SEGMENTS_COLLECTION].find_one({}, {"_id": 1})
        return doc is not None
    except Exception as e:
        log.debug("byo_segments existence probe failed: %s", e)
        return False


async def dense_search(
    query_embedding: list[float],
    filters: SearchFilters,
    k: int,
    *,
    min_score: float = 0.35,
) -> list[tuple[str, str, float]]:
    """Vector search over segments. Returns
    [(segment_id, parent_chunk_id, score)] sorted by score desc.

    Paths tried in order:
      1. Qdrant (dedicated vector DB — fast, always indexed)
      2. Python-side cosine over Mongo segments (safety net, <200ms)
    """
    if not filters.user_id:
        raise ValueError("SearchFilters.user_id is required (security boundary)")
    if not query_embedding:
        return []

    # ── Path 1: Qdrant ────────────────────────────────────────────────
    try:
        from byo.shared.qdrant import search_vectors
        qdrant_hits = search_vectors(
            query_embedding,
            user_id=filters.user_id,
            collection_id=filters.collection_id,
            resource_id=filters.resource_id,
            modality=[m.value for m in filters.modality] if filters.modality else None,
            limit=k,
            score_threshold=min_score,
        )
        if qdrant_hits:
            log.info(
                "[DENSE] qdrant hits=%d top=%.3f",
                len(qdrant_hits), qdrant_hits[0][2],
                extra={"event": "DENSE_QDRANT", "hits": len(qdrant_hits)},
            )
            return qdrant_hits
        # Qdrant returned 0 — collection might not be populated yet.
        # Fall through to Mongo cosine.
    except Exception as e:
        log.warning("[DENSE] qdrant failed: %s — falling back to Mongo cosine", e)

    # ── Path 2: Python-side cosine over Mongo segments ────────────────
    db = _get_db()
    mongo_filter = filters.to_mongo()
    try:
        return await _cosine_fallback(
            db, query_embedding, mongo_filter, k, min_score, SEGMENTS_COLLECTION,
        )
    except Exception as e:
        log.warning("[DENSE] Mongo cosine fallback failed: %s", e)

    # ── Path 3: Legacy byo_chunks (inline embedding) ──────────────────
    try:
        return await _cosine_fallback(
            db, query_embedding, mongo_filter, k, min_score, CHUNKS_COLLECTION,
        )
    except Exception as e:
        log.warning("[DENSE] legacy cosine also failed: %s", e)
        return []


async def _cosine_fallback(
    db,
    query_embedding: list[float],
    mongo_filter: dict,
    k: int,
    min_score: float,
    collection_name: str,
) -> list[tuple[str, str, float]]:
    """Client-side cosine similarity — safety net when Atlas Vector Search
    index is missing. Fetches all docs with embeddings in the filtered set,
    computes dot-product cosine, returns top-k.

    For student collections this is typically <500 docs and <200ms.
    """
    import time as _time
    t0 = _time.time()

    id_field = "segment_id" if collection_name == SEGMENTS_COLLECTION else "chunk_id"
    parent_field = "parent_chunk_id" if collection_name == SEGMENTS_COLLECTION else None

    cursor = db[collection_name].find(
        {**mongo_filter, "embedding": {"$exists": True, "$ne": None}},
        {"_id": 0, id_field: 1, "embedding": 1,
         **({"parent_chunk_id": 1} if parent_field else {})},
    )

    # Normalise query vector once.
    import math
    q_norm = math.sqrt(sum(x * x for x in query_embedding)) or 1e-9

    scored: list[tuple[str, str, float]] = []
    doc_count = 0
    async for doc in cursor:
        doc_count += 1
        emb = doc.get("embedding")
        if not emb:
            continue
        # Cosine similarity via dot product (embeddings from text-embedding-3-small
        # are already L2-normalised, but we normalise anyway for safety).
        dot = sum(a * b for a, b in zip(query_embedding, emb))
        e_norm = math.sqrt(sum(x * x for x in emb)) or 1e-9
        score = dot / (q_norm * e_norm)
        if score < min_score:
            continue
        sid = doc.get(id_field, "")
        pid = doc.get("parent_chunk_id", sid) if parent_field else sid
        scored.append((sid, pid, score))

    scored.sort(key=lambda x: -x[2])
    result = scored[:k]

    ms = int((_time.time() - t0) * 1000)
    log.info(
        "[DENSE] cosine fallback collection=%s docs_scanned=%d hits=%d ms=%d (Atlas index missing?)",
        collection_name, doc_count, len(result), ms,
        extra={"event": "DENSE_COSINE_FALLBACK", "collection": collection_name,
               "docs_scanned": doc_count, "hits": len(result), "elapsed_ms": ms},
    )
    return result
