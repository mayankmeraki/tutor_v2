"""Sparse ranker — Atlas $search (BM25-ish) on `byo_segments`.

Matches the query against `content` and `topics` fields. The text analyzer
is configured in the Atlas index (`byo_segments_text`); we issue a compound
`should` so the ranker can match either field.

Filters are applied via a `$match` stage after `$search` — Atlas supports
`filter` inside compound, but `$match` is simpler and works for the whole
filter set (including `$or` time-range clauses) without special-casing.

Legacy path: if `byo_segments` is empty, search `byo_chunks` with the
`byo_chunks_text` index, using chunk_id as both segment_id and parent_chunk_id.
"""

from __future__ import annotations

import logging
from typing import Any

from byo.shared.results import SearchFilters

log = logging.getLogger(__name__)


SEGMENTS_COLLECTION = "byo_segments"
CHUNKS_COLLECTION = "byo_chunks"
SEGMENTS_TEXT_INDEX = "byo_segments_text"
LEGACY_TEXT_INDEX = "byo_chunks_text"


def _get_db():
    from app.core.mongodb import get_mongo_db
    return get_mongo_db()


async def _segments_populated(db) -> bool:
    try:
        doc = await db[SEGMENTS_COLLECTION].find_one({}, {"_id": 1})
        return doc is not None
    except Exception:
        return False


def _build_search_stage(index: str, query: str) -> dict[str, Any]:
    return {
        "$search": {
            "index": index,
            "compound": {
                "should": [
                    {"text": {"query": query, "path": "content"}},
                    {"text": {"query": query, "path": "topics", "score": {"boost": {"value": 2.0}}}},
                ],
                "minimumShouldMatch": 1,
            },
        }
    }


async def sparse_search(
    query: str,
    filters: SearchFilters,
    k: int,
) -> list[tuple[str, str, float]]:
    """Text search over segments (or legacy chunks). Returns
    [(segment_id, parent_chunk_id, score)] sorted by score desc.

    Three paths (mirroring the dense ranker):
      1. Atlas $search on byo_segments (requires text index)
      2. Atlas $search on byo_chunks (legacy)
      3. Client-side regex term-match fallback (no Atlas index needed)
    """
    if not filters.user_id:
        raise ValueError("SearchFilters.user_id is required (security boundary)")
    if not query or not query.strip():
        return []

    db = _get_db()
    mongo_filter = filters.to_mongo()

    use_segments = await _segments_populated(db)

    if use_segments:
        pipeline: list[dict[str, Any]] = [
            _build_search_stage(SEGMENTS_TEXT_INDEX, query),
            {"$match": mongo_filter},
            {"$limit": k},
            {
                "$project": {
                    "_id": 0,
                    "segment_id": 1,
                    "parent_chunk_id": 1,
                    "score": {"$meta": "searchScore"},
                }
            },
        ]
        try:
            out: list[tuple[str, str, float]] = []
            async for doc in db[SEGMENTS_COLLECTION].aggregate(pipeline):
                seg_id = doc.get("segment_id") or ""
                parent_id = doc.get("parent_chunk_id") or ""
                if not seg_id or not parent_id:
                    continue
                out.append((seg_id, parent_id, float(doc.get("score") or 0.0)))
            if out:
                return out
        except Exception as e:
            log.warning("sparse_search $search failed: %s — trying regex fallback", e)

        # Regex fallback — works without Atlas Search index.
        return await _regex_fallback(db, query, mongo_filter, k, SEGMENTS_COLLECTION)

    # Legacy $search
    pipeline = [
        _build_search_stage(LEGACY_TEXT_INDEX, query),
        {"$match": mongo_filter},
        {"$limit": k},
        {"$project": {"_id": 0, "chunk_id": 1, "score": {"$meta": "searchScore"}}},
    ]
    try:
        out = []
        async for doc in db[CHUNKS_COLLECTION].aggregate(pipeline):
            chunk_id = doc.get("chunk_id") or ""
            if not chunk_id:
                continue
            out.append((chunk_id, chunk_id, float(doc.get("score") or 0.0)))
        if out:
            return out
    except Exception as e:
        log.warning("sparse_search legacy $search failed: %s", e)

    return await _regex_fallback(db, query, mongo_filter, k, CHUNKS_COLLECTION)


import re

_STOP = {
    "the", "is", "at", "of", "on", "and", "a", "an", "to", "in", "for",
    "with", "as", "by", "from", "that", "this", "it", "be", "or", "are",
    "was", "were", "which", "what", "how", "who", "when", "where", "can",
    "do", "does", "has", "have", "had", "not", "but", "if", "so", "than",
    "there", "here", "each", "some", "such", "into", "more", "all", "any",
}


async def _regex_fallback(
    db,
    query: str,
    mongo_filter: dict,
    k: int,
    collection_name: str,
) -> list[tuple[str, str, float]]:
    """Client-side text-match — safety net when Atlas $search index is missing.

    Extracts non-stop query words, builds a regex `$or` over `content` and
    `topics`, counts term hits per doc, and returns top-k. Cheap for student
    collections (<500 docs).
    """
    import time as _time
    t0 = _time.time()

    words = [w.lower() for w in re.findall(r"[A-Za-z]{2,}", query) if w.lower() not in _STOP]
    if not words:
        return []

    id_field = "segment_id" if collection_name == SEGMENTS_COLLECTION else "chunk_id"
    parent_field = "parent_chunk_id" if collection_name == SEGMENTS_COLLECTION else None

    # Build $or with case-insensitive regex per word on content + topics
    or_clauses = []
    for w in words[:8]:  # cap to avoid pathological queries
        pat = re.escape(w)
        or_clauses.append({"content": {"$regex": pat, "$options": "i"}})
        or_clauses.append({"topics": {"$regex": pat, "$options": "i"}})

    combined_filter = {**mongo_filter, "$or": or_clauses}

    cursor = db[collection_name].find(
        combined_filter,
        {"_id": 0, id_field: 1, "content": 1, "topics": 1,
         **({"parent_chunk_id": 1} if parent_field else {})},
    ).limit(k * 3)  # over-fetch then rank

    scored: list[tuple[str, str, float]] = []
    doc_count = 0
    async for doc in cursor:
        doc_count += 1
        content_lower = (doc.get("content") or "").lower()
        topics_str = " ".join(doc.get("topics") or []).lower()
        hits = sum(1 for w in words if w in content_lower or w in topics_str)
        if hits == 0:
            continue
        score = float(hits) / len(words)  # 0-1 coverage
        sid = doc.get(id_field, "")
        pid = doc.get("parent_chunk_id", sid) if parent_field else sid
        scored.append((sid, pid, score))

    scored.sort(key=lambda x: -x[2])
    result = scored[:k]

    ms = int((_time.time() - t0) * 1000)
    log.info(
        "[SPARSE] regex fallback collection=%s words=%s docs_scanned=%d hits=%d ms=%d",
        collection_name, words[:5], doc_count, len(result), ms,
        extra={"event": "SPARSE_REGEX_FALLBACK", "collection": collection_name,
               "words": words[:5], "docs_scanned": doc_count,
               "hits": len(result), "elapsed_ms": ms},
    )
    return result
