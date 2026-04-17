"""Backfill legacy `byo_chunks` records into the parent-chunk + child-segment
schema (`byo_chunks` parents, `byo_segments` children).

A legacy chunk is any document in `byo_chunks` that either lacks a `level`
field OR has an inline `embedding` field (i.e. was written by the pre-refactor
pipeline). For each such legacy chunk we:

  1. Re-chunk `content` via `byo.processing.chunker.chunk_markdown`.
  2. Embed the resulting child segments via
     `byo.processing.embedder.embed_segments_batch`.
  3. Write both parents (no embedding) and children (with embedding) via
     `byo.processing.indexer.index_chunks_and_segments`.
  4. Delete the legacy doc — ONLY after step 3 succeeds.

Idempotent: records that already have `level` set and no inline `embedding`
are skipped. Running twice is a no-op.

Usage:
    python -m byo.scripts.backfill_segments --dry-run
    python -m byo.scripts.backfill_segments --resource-id <rid>
    python -m byo.scripts.backfill_segments --batch-size 5
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from typing import Any

log = logging.getLogger("byo.backfill_segments")


# ── DB helpers ─────────────────────────────────────────────────────────────

def _get_db():
    """Resolve the Mongo database. Import locally so the module imports cleanly
    even if the backend config has not been initialised yet."""
    from app.core.mongodb import get_mongo_db
    return get_mongo_db()


async def _find_legacy(db, resource_id: str | None) -> list[dict[str, Any]]:
    """Select chunks that still need migration.

    Criteria: `level` is missing/null OR an inline `embedding` is present.
    (Post-migration, parents never carry an embedding.)
    """
    query: dict[str, Any] = {
        "$or": [
            {"level": {"$exists": False}},
            {"level": None},
            {"embedding": {"$exists": True, "$ne": None}},
        ]
    }
    if resource_id:
        query["resource_id"] = resource_id
    cursor = db.byo_chunks.find(query)
    return [doc async for doc in cursor]


async def _resolve_user_id(db, resource_id: str, fallback: str | None) -> str:
    """Look up the user_id for a resource. Falls back to the legacy chunk's
    own user_id (if present) when the resource cannot be found."""
    if resource_id:
        res = await db.byo_resources.find_one(
            {"resource_id": resource_id}, {"user_id": 1}
        )
        if res and res.get("user_id"):
            return res["user_id"]
    return fallback or ""


# ── Migration per legacy doc ───────────────────────────────────────────────

async def _migrate_one(db, legacy: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """Migrate a single legacy chunk. Returns a summary dict for logging.

    Safety: writes parents + children FIRST, deletes legacy doc LAST.
    If writing fails we leave the legacy doc untouched — no data loss.
    """
    from byo.processing.chunker import chunk_markdown
    from byo.processing.embedder import embed_segments_batch
    from byo.processing.indexer import index_chunks_and_segments

    legacy_id = legacy.get("chunk_id") or str(legacy.get("_id"))
    resource_id = legacy.get("resource_id") or ""
    collection_id = legacy.get("collection_id") or ""
    content = legacy.get("content") or ""
    user_id = await _resolve_user_id(db, resource_id, legacy.get("user_id"))

    if not content.strip():
        log.warning(
            "Skipping %s: empty content (nothing to re-chunk)", legacy_id[:8]
        )
        return {"chunk_id": legacy_id, "status": "skipped_empty"}

    # Re-chunk. The chunker returns a list of PARENTS. Each parent is then
    # split into child segments by the indexer/embedder pair. We keep the
    # interface narrow: index_chunks_and_segments does the final writes.
    parents = await chunk_markdown(
        markdown=content,
        resource_id=resource_id,
        collection_id=collection_id,
        resource_meta=legacy.get("meta") or {},
    )
    if not parents:
        log.warning(
            "Skipping %s: chunker produced 0 chunks", legacy_id[:8]
        )
        return {"chunk_id": legacy_id, "status": "skipped_nochunks"}

    # Carry forward labels/topics/anchor from the legacy doc when the
    # chunker didn't surface them (classifier runs elsewhere).
    for p in parents:
        p.setdefault("user_id", user_id)
        if legacy.get("labels") and not p.get("labels"):
            p["labels"] = legacy["labels"]
        if legacy.get("topics") and not p.get("topics"):
            p["topics"] = legacy["topics"]
        if legacy.get("modality") and not p.get("modality"):
            p["modality"] = legacy["modality"]
        if legacy.get("retrieval_mode") and not p.get("retrieval_mode"):
            p["retrieval_mode"] = legacy["retrieval_mode"]

    # Embed: the embedder splits parents into child segments and attaches
    # embeddings. Returns the list of child segment dicts.
    segments = await embed_segments_batch(parents)

    if dry_run:
        log.info(
            "[DRY] %s -> %d parents, %d segments (resource=%s user=%s)",
            legacy_id[:8], len(parents), len(segments),
            resource_id[:8] if resource_id else "?",
            user_id[:8] if user_id else "?",
        )
        return {
            "chunk_id": legacy_id,
            "status": "dry_run",
            "parents": len(parents),
            "segments": len(segments),
        }

    # Write BEFORE deleting. If this raises, the legacy doc stays put.
    try:
        await index_chunks_and_segments(
            parents=parents,
            segments=segments,
            resource_id=resource_id,
            collection_id=collection_id,
            user_id=user_id,
            replace=False,  # don't nuke siblings — we're migrating one at a time
        )
    except Exception as e:
        log.error("Write failed for %s — leaving legacy doc intact: %s",
                  legacy_id[:8], e)
        return {"chunk_id": legacy_id, "status": "error", "error": str(e)}

    # Only now is it safe to delete the legacy record.
    await db.byo_chunks.delete_one({"_id": legacy["_id"]})
    log.info(
        "Migrated %s -> %d parents, %d segments",
        legacy_id[:8], len(parents), len(segments),
    )
    return {
        "chunk_id": legacy_id,
        "status": "migrated",
        "parents": len(parents),
        "segments": len(segments),
    }


# ── Orchestration ──────────────────────────────────────────────────────────

async def _run(args: argparse.Namespace) -> int:
    db = _get_db()
    legacies = await _find_legacy(db, args.resource_id)

    if not legacies:
        log.info("Nothing to migrate — byo_chunks is already in the new shape.")
        return 0

    # Group by resource so logs are readable; still migrate concurrently.
    by_resource: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in legacies:
        by_resource[doc.get("resource_id", "?")].append(doc)

    log.info(
        "Found %d legacy chunk(s) across %d resource(s). batch_size=%d dry_run=%s",
        len(legacies), len(by_resource), args.batch_size, args.dry_run,
    )

    sem = asyncio.Semaphore(max(1, args.batch_size))
    results: list[dict[str, Any]] = []

    async def _bounded(doc: dict[str, Any]):
        async with sem:
            try:
                return await _migrate_one(db, doc, args.dry_run)
            except Exception as e:
                log.error("Unhandled failure on %s: %s",
                          (doc.get("chunk_id") or "?")[:8], e)
                return {"chunk_id": doc.get("chunk_id"),
                        "status": "error", "error": str(e)}

    tasks = [asyncio.create_task(_bounded(doc)) for doc in legacies]
    for fut in asyncio.as_completed(tasks):
        results.append(await fut)

    # Summary
    counts: dict[str, int] = defaultdict(int)
    for r in results:
        counts[r.get("status", "unknown")] += 1
    log.info("Backfill summary: %s", dict(counts))

    return 0 if counts.get("error", 0) == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill legacy byo_chunks into parent+segment schema."
    )
    parser.add_argument(
        "--resource-id",
        default=None,
        help="Limit backfill to a single resource_id.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions; do not write or delete.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Max concurrent migrations (default 5).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
