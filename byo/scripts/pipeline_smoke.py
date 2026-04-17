"""End-to-end pipeline smoke test against REAL services.

Uses actual Atlas + OpenRouter + rerank — no fakes — so a failure in this
script reproduces the exact production failure mode. Prints per-step
timing and data-shape info so you can see where a job dies.

Usage:
    # Run against a sample PDF, using real Mongo + OpenRouter
    python -m byo.scripts.pipeline_smoke /path/to/file.pdf

    # Run retrieval queries after ingest
    python -m byo.scripts.pipeline_smoke /path/to/file.pdf --queries \
        "what is the hardest question" "integration formula"

    # Skip ingest, only run queries against existing resource
    python -m byo.scripts.pipeline_smoke --resource-id <rid> --queries "..."

    # Clean up resources written by this script
    python -m byo.scripts.pipeline_smoke --cleanup

Requires `backend/.env` with MONGODB_URI + OPENROUTER_API_KEY populated.
"""

from __future__ import annotations

import argparse
import asyncio
import mimetypes
import os
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

# Load .env so downstream settings (MongoDB, OpenRouter) are configured.
_env = REPO / "backend" / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.environ.setdefault("MOCKUP_JWT_SECRET", "smoke")
os.environ.setdefault("MOCKUP_ADMIN_EMAILS", "smoke@test")

# ── Structured console log formatter (picks up `extra=` fields) ─────────
import logging
import json


class _KVFormatter(logging.Formatter):
    """Render log records with structured `extra` fields appended."""
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        skip = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process",
            "getMessage", "message", "taskName",
        }
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in skip and not k.startswith("_")
        }
        if extras:
            try:
                base += " " + json.dumps(extras, default=str, separators=(",", ":"))
            except Exception:
                base += " " + repr(extras)
        return base


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(_KVFormatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                                    "%H:%M:%S"))
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)


# ── Imports from the app after env + logging are set up ─────────────────
from byo.processing.processors import get_processor  # noqa: E402
from byo.processing.chunker import chunk_markdown  # noqa: E402
from byo.processing.classifier import classify_chunks_batch  # noqa: E402
from byo.processing.embedder import embed_segments_batch  # noqa: E402
from byo.processing.indexer import index_chunks_and_segments  # noqa: E402
from byo.retrieval.service import search, list_contents  # noqa: E402
from byo.shared.storage import default_storage  # noqa: E402
from app.core.mongodb import get_mongo_db  # noqa: E402

log = logging.getLogger("pipeline_smoke")

SMOKE_USER = os.environ.get("SMOKE_USER", "smoke-user@test")
SMOKE_COLLECTION = os.environ.get("SMOKE_COLLECTION", "smoke-collection")


# ── Step helpers ────────────────────────────────────────────────────────

async def _ensure_collection(db, collection_id: str, user_id: str) -> None:
    col = await db.collections.find_one({"collection_id": collection_id, "user_id": user_id})
    if col:
        return
    from datetime import datetime as _dt
    await db.collections.insert_one({
        "collection_id": collection_id,
        "user_id": user_id,
        "title": "Smoke test collection",
        "status": "processing",
        "stats": {"resources": 0, "chunks": 0, "topics": []},
        "tags": [],
        "created_at": _dt.utcnow(),
        "updated_at": _dt.utcnow(),
    })


async def _ensure_resource(db, resource_id: str, path: Path, mime: str, user_id: str) -> None:
    """Upload file to storage + upsert a resource row."""
    from datetime import datetime as _dt
    data = path.read_bytes()
    storage_path = await default_storage.save(data, user_id, SMOKE_COLLECTION, path.name)
    await db.byo_resources.update_one(
        {"resource_id": resource_id},
        {"$set": {
            "resource_id": resource_id,
            "collection_id": SMOKE_COLLECTION,
            "user_id": user_id,
            "source_type": "file",
            "mime_type": mime,
            "original_name": path.name,
            "source_url": None,
            "storage_path": storage_path,
            "file_size": len(data),
            "status": "queued",
            "progress": 0.0,
            "meta": {},
            "chunk_count": 0,
            "created_at": _dt.utcnow(),
        }},
        upsert=True,
    )
    return storage_path, mime


async def _run_ingest(path: Path) -> str:
    """Run the whole pipeline synchronously (not via the queue) so we
    can see every step's output and timing. Returns the resource_id.
    """
    db = get_mongo_db()
    user_id = SMOKE_USER
    await _ensure_collection(db, SMOKE_COLLECTION, user_id)

    resource_id = str(uuid.uuid4())
    mime = mimetypes.guess_type(path.name)[0] or "application/pdf"
    log.info("── STEP 0: uploading file and creating resource ──")
    t0 = time.time()
    storage_path, mime = await _ensure_resource(db, resource_id, path, mime, user_id)
    log.info("upload done bytes=%d storage=%s ms=%d",
             path.stat().st_size, storage_path, int((time.time() - t0) * 1000))

    # Each of the 5 steps in the order the orchestrator runs them —
    # done inline here so a failure shows exactly where.
    log.info("── STEP 1: extract ──")
    t1 = time.time()
    processor = get_processor(mime)
    try:
        # Processors expect a local path or a gs:// URI. If storage saved
        # locally, storage_path is already a path; if GCS, download to /tmp.
        local_path = str(path)
        if storage_path and storage_path.startswith("gs://"):
            import tempfile
            data = await default_storage.read(storage_path)
            ext = os.path.splitext(storage_path)[1] or ".bin"
            fd, local_path = tempfile.mkstemp(suffix=ext)
            os.write(fd, data)
            os.close(fd)
        extraction = await processor.extract(
            resource_id=resource_id, mime_type=mime,
            source_url=None, storage_path=local_path,
            meta={"mime_type": mime},
        )
        extract_dict = extraction.model_dump() if hasattr(extraction, "model_dump") else extraction
    except Exception as e:
        log.error("EXTRACT FAILED: %s", e)
        log.error(traceback.format_exc())
        raise
    log.info("extract done chars=%d images=%d ms=%d",
             len(extract_dict.get("markdown", "") or ""),
             len(extract_dict.get("images", []) or []),
             int((time.time() - t1) * 1000))

    log.info("── STEP 2: chunk ──")
    t2 = time.time()
    try:
        parents, segments = await chunk_markdown(
            markdown=extract_dict.get("markdown", ""),
            resource_id=resource_id,
            collection_id=SMOKE_COLLECTION,
            resource_meta=extract_dict.get("meta", {}),
            user_id=user_id,
            mime_type=mime,
            use_structure_llm=True,
        )
    except Exception as e:
        log.error("CHUNK FAILED: %s", e); raise
    log.info("chunk done parents=%d segments=%d modality=%s mode=%s ms=%d",
             len(parents), len(segments),
             parents[0].get("modality") if parents else "?",
             parents[0].get("retrieval_mode") if parents else "?",
             int((time.time() - t2) * 1000))

    log.info("── STEP 3: classify ──")
    t3 = time.time()
    try:
        classifications = await classify_chunks_batch(parents)
        for p, c in zip(parents, classifications):
            p["labels"] = c.get("labels", [])
            p["topics"] = c.get("topics", [])
    except Exception as e:
        log.error("CLASSIFY FAILED: %s", e); raise
    log.info("classify done ms=%d", int((time.time() - t3) * 1000))

    log.info("── STEP 4: embed ──")
    t4 = time.time()
    try:
        await embed_segments_batch(segments)
    except Exception as e:
        log.error("EMBED FAILED: %s", e); raise
    n_emb = sum(1 for s in segments if s.get("embedding"))
    log.info("embed done embedded=%d/%d ms=%d",
             n_emb, len(segments), int((time.time() - t4) * 1000))

    log.info("── STEP 5: index (write to Mongo) ──")
    t5 = time.time()
    try:
        await index_chunks_and_segments(
            resource_id=resource_id, collection_id=SMOKE_COLLECTION,
            user_id=user_id, parents=parents, segments=segments,
        )
    except Exception as e:
        log.error("INDEX FAILED: %s", e); raise
    log.info("index done ms=%d", int((time.time() - t5) * 1000))

    # Finally mark resource ready so retrieval tests don't complain.
    await db.byo_resources.update_one(
        {"resource_id": resource_id},
        {"$set": {"status": "ready", "progress": 1.0, "chunk_count": len(parents)}},
    )

    total = int((time.time() - t0) * 1000)
    log.info("── INGEST COMPLETE resource=%s total_ms=%d ──", resource_id[:8], total)
    return resource_id


async def _run_queries(queries: list[str], resource_id: str | None) -> None:
    """Fire each query through the real retrieval service and print hits."""
    if not queries:
        queries = [
            "hardest question in the exam",
            "show me a sample problem",
            "explain the key concept",
        ]

    log.info("── RETRIEVAL TEST ── (%d queries)", len(queries))
    for q in queries:
        log.info("▶ query=%r", q)
        try:
            hits = await search(
                q,
                user_id=SMOKE_USER,
                scope="resource" if resource_id else "collection",
                collection_id=SMOKE_COLLECTION,
                resource_id=resource_id,
                k=3,
                rerank=True,
                use_hyde=False,
                min_rerank_score=0.25,
            )
        except Exception as e:
            log.error("  query failed: %s", e)
            continue
        if not hits:
            log.info("  (no hits)")
            continue
        for i, h in enumerate(hits, 1):
            page = h.anchor.page if h.anchor else None
            d = f"d={h.dense_score:.2f}" if h.dense_score is not None else "d=-"
            s = f"s={h.sparse_score:.1f}" if h.sparse_score is not None else "s=-"
            r = f"r={h.rerank_score:.3f}" if h.rerank_score is not None else "r=-"
            preview = (h.content or "").strip()[:180].replace("\n", " ")
            log.info("  #%d fused=%.4f %s %s %s page=%s", i, h.score, d, s, r, page)
            log.info("      %s", preview)


async def _cleanup() -> None:
    """Remove everything this script wrote."""
    db = get_mongo_db()
    n1 = (await db.byo_chunks.delete_many({"collection_id": SMOKE_COLLECTION})).deleted_count
    n2 = (await db.byo_segments.delete_many({"collection_id": SMOKE_COLLECTION})).deleted_count
    n3 = (await db.byo_resources.delete_many({"collection_id": SMOKE_COLLECTION})).deleted_count
    n4 = (await db.collections.delete_many({"collection_id": SMOKE_COLLECTION})).deleted_count
    log.info(
        "cleanup done chunks=%d segments=%d resources=%d collections=%d",
        n1, n2, n3, n4,
    )


# ── CLI entry point ─────────────────────────────────────────────────────

async def _main():
    parser = argparse.ArgumentParser(description="End-to-end BYO pipeline smoke test")
    parser.add_argument("path", nargs="?", help="Path to a file to ingest")
    parser.add_argument("--resource-id", help="Skip ingest, run queries against this resource")
    parser.add_argument("--queries", nargs="*", default=[], help="Queries to run")
    parser.add_argument("--cleanup", action="store_true", help="Delete smoke-test docs and exit")
    args = parser.parse_args()

    if args.cleanup:
        await _cleanup()
        return

    resource_id = args.resource_id
    if args.path:
        p = Path(args.path).expanduser().resolve()
        if not p.exists():
            log.error("File not found: %s", p)
            sys.exit(1)
        resource_id = await _run_ingest(p)
    elif not resource_id:
        log.error("Provide either a file path OR --resource-id")
        sys.exit(1)

    await _run_queries(args.queries, resource_id)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
