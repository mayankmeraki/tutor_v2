"""Pipeline orchestrator — job queue for BYO resource processing.

Stateless workers pull jobs from MongoDB. Each job is self-contained
with all metadata needed to process and store results.

Usage:
    # Submit a job (returns immediately with job_id)
    job_id = await submit_processing_job(resource_id, collection_id, user_id)

    # Poll status
    status = await get_job_status(job_id)

    # Worker loop (runs in background)
    await run_worker()
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Any

from byo.models import ResourceStatus

log = logging.getLogger(__name__)


# ── Job schema ──────────────────────────────────────────────────────────

class JobState:
    QUEUED = "queued"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    CLASSIFYING = "classifying"
    EMBEDDING = "embedding"
    STORING = "storing"
    COMPLETE = "complete"
    FAILED = "failed"

PIPELINE_STEPS = [
    JobState.EXTRACTING,
    JobState.CHUNKING,
    JobState.CLASSIFYING,
    JobState.EMBEDDING,
    JobState.STORING,
]


def _new_job(resource_id: str, collection_id: str, user_id: str, meta: dict | None = None) -> dict:
    """Create a new job document for MongoDB."""
    return {
        "job_id": str(uuid.uuid4()),
        "resource_id": resource_id,
        "collection_id": collection_id,
        "user_id": user_id,
        "state": JobState.QUEUED,
        "step_index": 0,
        "progress": 0.0,
        "error": None,
        "retries": 0,
        "max_retries": 3,
        "meta": meta or {},  # extra context (mime_type, source_url, etc.)
        "result": {},  # step outputs accumulate here
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "started_at": None,
        "completed_at": None,
        "locked_by": None,  # worker ID that claimed this job
        "lock_expires": None,
    }


# ── Job queue operations ────────────────────────────────────────────────

def _get_db():
    """Get MongoDB database. Import here to avoid circular deps."""
    from app.core.mongodb import get_mongo_db
    return get_mongo_db()


async def submit_processing_job(
    resource_id: str,
    collection_id: str,
    user_id: str,
    meta: dict | None = None,
) -> str:
    """Submit a resource for processing. Returns job_id immediately.

    The job is stored in MongoDB and picked up by a worker.
    """
    db = _get_db()
    job = _new_job(resource_id, collection_id, user_id, meta)
    await db.byo_jobs.insert_one(job)

    # Update resource status
    await db.byo_resources.update_one(
        {"resource_id": resource_id},
        {"$set": {"status": ResourceStatus.PROCESSING, "updated_at": datetime.utcnow()}},
    )

    log.info("Job submitted: %s for resource %s", job["job_id"][:8], resource_id[:8])
    return job["job_id"]


async def get_job_status(job_id: str) -> dict | None:
    """Get current job status. Used for polling."""
    db = _get_db()
    job = await db.byo_jobs.find_one(
        {"job_id": job_id},
        {"_id": 0, "job_id": 1, "state": 1, "step_index": 1, "progress": 1,
         "error": 1, "created_at": 1, "completed_at": 1},
    )
    return job


async def get_jobs_for_collection(collection_id: str) -> list[dict]:
    """Get all jobs for a collection (for status dashboard)."""
    db = _get_db()
    cursor = db.byo_jobs.find(
        {"collection_id": collection_id},
        {"_id": 0, "job_id": 1, "resource_id": 1, "state": 1, "progress": 1, "error": 1},
    ).sort("created_at", 1)
    return [doc async for doc in cursor]


# ── Worker ──────────────────────────────────────────────────────────────

WORKER_ID = str(uuid.uuid4())[:8]
LOCK_DURATION_SECONDS = 300  # 5 min lock per job
POLL_INTERVAL_SECONDS = 2
MAX_CONCURRENT_JOBS = 3  # per worker
RATE_LIMIT_PER_USER = 5  # max concurrent jobs per user


async def _claim_job(db) -> dict | None:
    """Atomically claim the next available job.

    Uses MongoDB findOneAndUpdate for atomic locking.
    Only claims jobs that aren't locked or whose locks expired.
    """
    now = datetime.utcnow()
    job = await db.byo_jobs.find_one_and_update(
        {
            "state": {"$in": [JobState.QUEUED, *PIPELINE_STEPS]},
            "$or": [
                {"locked_by": None},
                {"lock_expires": {"$lt": now}},  # expired lock
            ],
        },
        {
            "$set": {
                "locked_by": WORKER_ID,
                "lock_expires": now + timedelta(seconds=LOCK_DURATION_SECONDS),
                "started_at": {"$cond": [{"$eq": ["$started_at", None]}, now, "$started_at"]},
                "updated_at": now,
            }
        },
        sort=[("created_at", 1)],  # FIFO
        return_document=True,
    )
    # findOneAndUpdate with $cond in $set doesn't work in all MongoDB versions.
    # Simplified: just set started_at if it's the first time
    if job and not job.get("started_at"):
        await db.byo_jobs.update_one(
            {"job_id": job["job_id"]},
            {"$set": {"started_at": now}},
        )
    return job


async def _update_job(db, job_id: str, updates: dict):
    """Update job state in MongoDB."""
    updates["updated_at"] = datetime.utcnow()
    await db.byo_jobs.update_one(
        {"job_id": job_id},
        {"$set": updates},
    )


async def _process_job(job: dict):
    """Execute the pipeline for one job.

    Steps: extract → chunk → classify → embed → store
    Each step is idempotent — if we crash and retry, the step
    picks up from where it left off using job["result"].
    """
    db = _get_db()
    job_id = job["job_id"]
    step_index = job.get("step_index", 0)
    result = job.get("result", {})

    try:
        for i, step in enumerate(PIPELINE_STEPS):
            if i < step_index:
                continue  # already completed this step

            log.info("Job %s step %d: %s", job_id[:8], i, step)
            await _update_job(db, job_id, {
                "state": step,
                "step_index": i,
                "progress": i / len(PIPELINE_STEPS),
            })

            # Also update resource progress
            await db.byo_resources.update_one(
                {"resource_id": job["resource_id"]},
                {"$set": {"progress": i / len(PIPELINE_STEPS), "status": "processing"}},
            )

            # Renew lock
            await _update_job(db, job_id, {
                "lock_expires": datetime.utcnow() + timedelta(seconds=LOCK_DURATION_SECONDS),
            })

            # Execute step
            if step == JobState.EXTRACTING:
                result["extraction"] = await _step_extract(job)
            elif step == JobState.CHUNKING:
                result["chunks"] = await _step_chunk(job, result.get("extraction", {}))
            elif step == JobState.CLASSIFYING:
                result["classifications"] = await _step_classify(result.get("chunks", []))
            elif step == JobState.EMBEDDING:
                result["embeddings_done"] = await _step_embed(result.get("chunks", []))
            elif step == JobState.STORING:
                await _step_store(job, result)

            # Save intermediate result
            await _update_job(db, job_id, {"result": result, "step_index": i + 1})

        # Complete
        await _update_job(db, job_id, {
            "state": JobState.COMPLETE,
            "progress": 1.0,
            "completed_at": datetime.utcnow(),
            "locked_by": None,
        })
        await db.byo_resources.update_one(
            {"resource_id": job["resource_id"]},
            {"$set": {"status": ResourceStatus.READY, "progress": 1.0}},
        )

        # Update collection stats
        await _update_collection_stats(db, job["collection_id"])

        log.info("Job %s complete", job_id[:8])

    except Exception as e:
        retries = job.get("retries", 0)
        max_retries = job.get("max_retries", 3)

        if retries < max_retries:
            # Retry with exponential backoff
            delay = 2 ** retries
            log.warning("Job %s failed (attempt %d/%d), retrying in %ds: %s",
                       job_id[:8], retries + 1, max_retries, delay, e)
            await _update_job(db, job_id, {
                "retries": retries + 1,
                "locked_by": None,
                "lock_expires": datetime.utcnow() + timedelta(seconds=delay),
                "error": str(e),
            })
        else:
            log.error("Job %s permanently failed after %d retries: %s",
                     job_id[:8], max_retries, e)
            await _update_job(db, job_id, {
                "state": JobState.FAILED,
                "error": f"{str(e)}\n{traceback.format_exc()[:500]}",
                "locked_by": None,
            })
            await db.byo_resources.update_one(
                {"resource_id": job["resource_id"]},
                {"$set": {"status": ResourceStatus.ERROR, "error": str(e)[:200]}},
            )


# ── Pipeline steps ──────────────────────────────────────────────────────

async def _step_extract(job: dict) -> dict:
    """Extract content from the resource using the appropriate processor."""
    from byo.pipeline.processors import get_processor

    mime_type = job["meta"].get("mime_type", "")
    source_url = job["meta"].get("source_url")
    storage_path = job["meta"].get("storage_path")

    processor = get_processor(mime_type)
    result = await processor.extract(
        resource_id=job["resource_id"],
        mime_type=mime_type,
        source_url=source_url,
        storage_path=storage_path,
        meta=job["meta"],
    )
    return result.model_dump() if hasattr(result, "model_dump") else result


async def _step_chunk(job: dict, extraction: dict) -> list[dict]:
    """Split extracted content into chunks."""
    from byo.pipeline.chunker import chunk_markdown

    markdown = extraction.get("markdown", "")
    resource_meta = extraction.get("meta", {})

    chunks = await chunk_markdown(
        markdown=markdown,
        resource_id=job["resource_id"],
        collection_id=job["collection_id"],
        resource_meta=resource_meta,
    )
    return chunks


async def _step_classify(chunks: list[dict]) -> list[dict]:
    """Classify chunks using batch LLM call."""
    from byo.pipeline.classifier import classify_chunks_batch

    if not chunks:
        return []

    classifications = await classify_chunks_batch(chunks)

    # Merge classifications back into chunks
    for chunk, cls in zip(chunks, classifications):
        chunk["labels"] = cls.get("labels", [])
        chunk["topics"] = cls.get("topics", [])

    return [{"labels": c.get("labels", []), "topics": c.get("topics", [])} for c in classifications]


async def _step_embed(chunks: list[dict]) -> bool:
    """Generate embeddings for all chunks. Batch API call."""
    from byo.pipeline.embedder import embed_chunks_batch

    if not chunks:
        return True

    await embed_chunks_batch(chunks)
    return True


async def _step_store(job: dict, result: dict):
    """Store processed chunks in MongoDB."""
    db = _get_db()
    chunks = result.get("chunks", [])
    classifications = result.get("classifications", [])

    if not chunks:
        return

    # Merge classifications into chunks
    for i, chunk in enumerate(chunks):
        if i < len(classifications):
            chunk["labels"] = classifications[i].get("labels", [])
            chunk["topics"] = classifications[i].get("topics", [])

    # Bulk insert chunks
    docs = []
    for chunk in chunks:
        doc = {
            "chunk_id": chunk.get("chunk_id", str(uuid.uuid4())),
            "collection_id": job["collection_id"],
            "resource_id": job["resource_id"],
            "index": chunk.get("index", 0),
            "content": chunk.get("content", ""),
            "tokens": chunk.get("tokens", 0),
            "anchor": chunk.get("anchor", {}),
            "labels": chunk.get("labels", []),
            "topics": chunk.get("topics", []),
            "attachments": chunk.get("attachments", []),
            "embedding": chunk.get("embedding"),
            "created_at": datetime.utcnow(),
        }
        docs.append(doc)

    if docs:
        await db.byo_chunks.insert_many(docs)

    # Update resource chunk count
    await db.byo_resources.update_one(
        {"resource_id": job["resource_id"]},
        {"$set": {"chunk_count": len(docs)}},
    )


async def _update_collection_stats(db, collection_id: str):
    """Recalculate collection stats from resources and chunks."""
    resource_count = await db.byo_resources.count_documents({"collection_id": collection_id})
    chunk_count = await db.byo_chunks.count_documents({"collection_id": collection_id})

    # Aggregate unique topics
    pipeline = [
        {"$match": {"collection_id": collection_id}},
        {"$unwind": "$topics"},
        {"$group": {"_id": "$topics"}},
    ]
    topics = [doc["_id"] async for doc in db.byo_chunks.aggregate(pipeline)]

    # Determine collection status
    statuses = []
    async for res in db.byo_resources.find({"collection_id": collection_id}, {"status": 1}):
        statuses.append(res.get("status"))

    if all(s == "ready" for s in statuses):
        col_status = "ready"
    elif any(s == "ready" for s in statuses):
        col_status = "partial"
    else:
        col_status = "processing"

    await db.collections.update_one(
        {"collection_id": collection_id},
        {"$set": {
            "status": col_status,
            "stats.resources": resource_count,
            "stats.chunks": chunk_count,
            "stats.topics": topics[:50],  # cap at 50
            "updated_at": datetime.utcnow(),
        }},
    )


# ── Worker loop ─────────────────────────────────────────────────────────

async def run_worker(max_iterations: int | None = None):
    """Main worker loop. Runs continuously, polling for jobs.

    In production, run multiple workers for parallelism.
    Each worker processes up to MAX_CONCURRENT_JOBS simultaneously.
    """
    log.info("BYO worker %s started (max_concurrent=%d)", WORKER_ID, MAX_CONCURRENT_JOBS)

    db = _get_db()
    active_tasks: set[asyncio.Task] = set()
    iterations = 0

    while max_iterations is None or iterations < max_iterations:
        iterations += 1

        # Clean up completed tasks
        done = {t for t in active_tasks if t.done()}
        for t in done:
            try:
                t.result()  # raise any exceptions
            except Exception as e:
                log.error("Worker task failed: %s", e)
        active_tasks -= done

        # Claim new jobs if under capacity
        if len(active_tasks) < MAX_CONCURRENT_JOBS:
            job = await _claim_job(db)
            if job:
                task = asyncio.create_task(_process_job(job))
                active_tasks.add(task)
                continue  # try to claim more immediately

        # No jobs available or at capacity — poll
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    # Wait for remaining tasks
    if active_tasks:
        await asyncio.gather(*active_tasks, return_exceptions=True)

    log.info("BYO worker %s stopped", WORKER_ID)
