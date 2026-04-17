"""Migrate existing BYO segment embeddings from MongoDB to Qdrant.

Reads all segments from `byo_segments` in Mongo that have an embedding,
and upserts them into Qdrant. Idempotent — safe to run multiple times.

Usage:
    python -m byo.scripts.migrate_to_qdrant
    python -m byo.scripts.migrate_to_qdrant --collection-id <cid>  # single collection
    python -m byo.scripts.migrate_to_qdrant --dry-run              # count only
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

env_path = REPO / "backend" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ.setdefault("MOCKUP_JWT_SECRET", "migrate")
os.environ.setdefault("MOCKUP_ADMIN_EMAILS", "migrate@test")


async def main():
    parser = argparse.ArgumentParser(description="Migrate BYO segments to Qdrant")
    parser.add_argument("--collection-id", help="Migrate only this collection")
    parser.add_argument("--dry-run", action="store_true", help="Count segments without writing")
    args = parser.parse_args()

    from app.core.mongodb import get_mongo_db
    from byo.shared.qdrant import upsert_segments, ensure_collection, get_qdrant_client

    client = get_qdrant_client()
    if client is None:
        print("ERROR: QDRANT_URL not set. Set it in backend/.env and retry.")
        sys.exit(1)

    db = get_mongo_db()

    query: dict = {"embedding": {"$exists": True, "$ne": None}}
    if args.collection_id:
        query["collection_id"] = args.collection_id

    total = await db.byo_segments.count_documents(query)
    print(f"Found {total} segments with embeddings in Mongo")

    if args.dry_run:
        print("Dry run — exiting without writing.")
        return

    if total == 0:
        print("Nothing to migrate.")
        return

    ensure_collection()
    print(f"Qdrant collection ensured. Starting migration...")

    t0 = time.time()
    batch: list[dict] = []
    migrated = 0
    BATCH_SIZE = 100

    cursor = db.byo_segments.find(
        query,
        {
            "_id": 0, "segment_id": 1, "parent_chunk_id": 1,
            "collection_id": 1, "resource_id": 1, "user_id": 1,
            "modality": 1, "retrieval_mode": 1, "topics": 1,
            "content": 1, "embedding": 1,
        },
    )

    async for doc in cursor:
        batch.append(doc)
        if len(batch) >= BATCH_SIZE:
            n = upsert_segments(batch)
            migrated += n
            print(f"  migrated {migrated}/{total} ...", flush=True)
            batch = []

    if batch:
        n = upsert_segments(batch)
        migrated += n

    elapsed = time.time() - t0
    print(f"\nDone: {migrated} segments migrated to Qdrant in {elapsed:.1f}s")

    # Quick verification
    info = client.get_collection("byo_segments")
    print(f"Qdrant collection: {info.points_count} points")


if __name__ == "__main__":
    asyncio.run(main())
