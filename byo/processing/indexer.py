"""MongoDB indexer — writes parents + segments atomically per resource.

Extracted from the orchestrator so the pipeline's storage policy lives in
one place and can be reused (e.g. by a backfill script).

Collections:
  - byo_chunks:   parent `Chunk` docs (no embedding).
  - byo_segments: child `Segment` docs (with embedding).
  - byo_resources.chunk_count ← number of parents for the resource.

Idempotency:
  On every call we delete existing parents + segments for the resource
  BEFORE inserting. That way a retried job (or a re-embed) converges to
  a single clean state — there's no possibility of duplicated ids or
  orphaned children from a previous attempt.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

log = logging.getLogger(__name__)


# Mongo write batching. On shared Atlas tiers a single insert_many of ~150+
# segments (each with a 1536-float embedding ≈ 12 KB) can blow past the
# 30 s socketTimeoutMS during index build + journal commit. 50-doc batches
# keep each call well under 1 MB and under ~5 s wall time.
INSERT_BATCH = 50
INSERT_RETRIES = 3


def _get_db():
    """Get MongoDB database. Import here to avoid circular deps."""
    from app.core.mongodb import get_mongo_db
    return get_mongo_db()


async def _insert_many_batched(coll, docs: list[dict], *, label: str) -> int:
    """insert_many in bounded batches with exponential-backoff retry.

    Returns number of docs inserted. Raises if every retry exhausted on a
    batch — callers propagate to the orchestrator's retry loop.
    """
    import time as _time
    if not docs:
        return 0
    total = 0
    n_batches = (len(docs) + INSERT_BATCH - 1) // INSERT_BATCH
    for i in range(0, len(docs), INSERT_BATCH):
        batch = docs[i:i + INSERT_BATCH]
        batch_num = (i // INSERT_BATCH) + 1
        last_err: Exception | None = None
        for attempt in range(INSERT_RETRIES):
            t0 = _time.time()
            try:
                await coll.insert_many(batch, ordered=False)
                ms = int((_time.time() - t0) * 1000)
                log.info(
                    "[INDEXER] %s batch=%d/%d size=%d ms=%d attempt=%d",
                    label, batch_num, n_batches, len(batch), ms, attempt + 1,
                    extra={"event": "IDX_BATCH_OK", "label": label,
                           "batch": batch_num, "total_batches": n_batches,
                           "size": len(batch), "elapsed_ms": ms,
                           "attempt": attempt + 1},
                )
                total += len(batch)
                last_err = None
                break
            except Exception as e:  # noqa: BLE001 — surface + retry
                last_err = e
                delay = 2 ** attempt
                ms = int((_time.time() - t0) * 1000)
                log.warning(
                    "[INDEXER] %s batch=%d/%d size=%d attempt=%d/%d ms=%d err=%s — retry in %ds",
                    label, batch_num, n_batches, len(batch),
                    attempt + 1, INSERT_RETRIES, ms, repr(e), delay,
                    extra={"event": "IDX_BATCH_RETRY", "label": label,
                           "batch": batch_num, "attempt": attempt + 1,
                           "max_attempts": INSERT_RETRIES,
                           "elapsed_ms": ms, "error": repr(e),
                           "delay_s": delay},
                )
                await asyncio.sleep(delay)
        if last_err is not None:
            log.error(
                "[INDEXER] %s batch=%d/%d EXHAUSTED after %d attempts: %s",
                label, batch_num, n_batches, INSERT_RETRIES, repr(last_err),
                extra={"event": "IDX_BATCH_FAILED", "label": label,
                       "batch": batch_num, "error": repr(last_err)},
            )
            raise last_err
    return total


async def index_chunks_and_segments(
    *,
    resource_id: str,
    collection_id: str,
    user_id: str,
    parents: list[dict],
    segments: list[dict],
    resource_name: str = "",
) -> tuple[int, int]:
    """Persist parents + segments to MongoDB + Qdrant.

    Returns `(parents_written, segments_written)`.

    `resource_name` is the original filename (e.g., "21MAT11set1.pdf").
    Propagated to Qdrant payload so the tutor can cite which file a
    chunk came from without an extra DB lookup.
    """
    import time as _time
    db = _get_db()
    t0 = _time.time()

    # Resolve resource_name from DB if caller didn't provide it
    if not resource_name:
        res_doc = await db.byo_resources.find_one(
            {"resource_id": resource_id},
            {"original_name": 1},
        )
        resource_name = (res_doc.get("original_name", "") if res_doc else "") or ""

    log.info(
        "[INDEXER] start resource=%s collection=%s parents=%d segments=%d",
        resource_id[:8], collection_id[:8], len(parents), len(segments),
        extra={"event": "IDX_START", "resource_id": resource_id,
               "collection_id": collection_id,
               "parents": len(parents), "segments": len(segments)},
    )

    if not parents:
        await db.byo_resources.update_one(
            {"resource_id": resource_id},
            {"$set": {"chunk_count": 0}},
        )
        log.info("[INDEXER] empty result — no parents to write, resource=%s", resource_id[:8])
        return 0, 0

    # Propagate classification labels/topics from parent → its segments.
    topic_map: dict[str, list[str]] = {}
    for p in parents:
        topic_map[p["chunk_id"]] = list(p.get("topics") or [])

    for s in segments:
        pid = s.get("parent_chunk_id")
        if pid and pid in topic_map and not s.get("topics"):
            s["topics"] = list(topic_map[pid])
        if resource_name and not s.get("resource_name"):
            s["resource_name"] = resource_name

    # ── Qdrant: the ONLY content store ──────────────────────────
    # All retrieval reads go through Qdrant. No MongoDB backup for chunks.
    # If this fails, the job retries — resource is NOT marked "ready".
    from byo.shared.store import get_content_store
    store = get_content_store()
    store_parents, store_segs = await store.upsert(
        resource_id=resource_id,
        collection_id=collection_id,
        user_id=user_id,
        resource_name=resource_name,
        parents=parents,
        segments=segments,
    )
    log.info(
        "[INDEXER] Qdrant upserted resource=%s parents=%d segments=%d",
        resource_id[:8], store_parents, store_segs,
        extra={"event": "IDX_STORE_UPSERT",
               "parents": store_parents, "segments": store_segs},
    )

    # Aggregate topics + build TOC from parents → store on resource doc
    all_topics = set()
    toc = []
    for p in parents:
        all_topics.update(p.get("topics") or [])
        toc.append({
            "index": p.get("index", 0),
            "title": p.get("title", f"Section {p.get('index', 0) + 1}"),
            "section": (p.get("anchor") or {}).get("section", ""),
            "page": (p.get("anchor") or {}).get("page"),
            "tokens": p.get("tokens", 0),
            "chunk_id": p.get("chunk_id", ""),
        })

    await db.byo_resources.update_one(
        {"resource_id": resource_id},
        {"$set": {
            "chunk_count": store_parents,
            "segment_count": store_segs,
            "topics": sorted(all_topics),
            "toc": toc,
        }},
    )

    total_ms = int((_time.time() - t0) * 1000)
    log.info(
        "[INDEXER] done resource=%s parents=%d segments=%d total_ms=%d",
        resource_id[:8], store_parents, store_segs, total_ms,
        extra={"event": "IDX_DONE", "parents": store_parents,
               "segments": store_segs, "elapsed_ms": total_ms},
    )
    return store_parents, store_segs
