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

from byo.shared.models import ResourceStatus

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
                {"lock_expires": {"$lt": now}},
            ],
        },
        {
            "$set": {
                "locked_by": WORKER_ID,
                "lock_expires": now + timedelta(seconds=LOCK_DURATION_SECONDS),
                "updated_at": now,
            }
        },
        sort=[("created_at", 1)],
        return_document=True,
    )
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
    rid = job["resource_id"][:8]
    job_start = time.time()

    log.info(
        "[BYO] job start job=%s resource=%s collection=%s user=%s step_index=%d",
        job_id[:8], rid, job["collection_id"][:8], job["user_id"][:12], step_index,
        extra={
            "event": "BYO_JOB_START", "job_id": job_id, "resource_id": job["resource_id"],
            "collection_id": job["collection_id"], "user_id": job["user_id"],
            "step_index": step_index,
        },
    )

    try:
        for i, step in enumerate(PIPELINE_STEPS):
            if i < step_index:
                continue  # already completed this step
            step_start = time.time()

            log.info(
                "[BYO] step begin job=%s step=%s (%d/%d)",
                job_id[:8], step, i + 1, len(PIPELINE_STEPS),
                extra={"event": "BYO_STEP_BEGIN", "job_id": job_id, "step": step,
                       "step_num": i + 1, "step_total": len(PIPELINE_STEPS)},
            )
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
                extraction = result["extraction"]
                md_chars = len(extraction.get("markdown", "") or "")
                img_count = len(extraction.get("images", []) or [])
                extract_meta = extraction.get("meta", {}) or {}
                log.info(
                    "[BYO] extract done job=%s chars=%d images=%d extractor=%s pages=%s error=%s",
                    job_id[:8], md_chars, img_count,
                    extract_meta.get("extractor", "?"),
                    extract_meta.get("pages", "?"),
                    extract_meta.get("error", ""),
                    extra={"event": "BYO_EXTRACT_DONE", "job_id": job_id,
                           "markdown_chars": md_chars, "images": img_count,
                           "extract_meta": extract_meta},
                )
                images = extraction.get("images", [])
                if images:
                    described = await _describe_images(images, job["resource_id"])
                    extraction["images"] = described
                    extraction["markdown"] = _merge_image_descriptions(
                        extraction.get("markdown", ""), described
                    )
                    result["extraction"] = extraction
                    log.info(
                        "[BYO] images described job=%s total=%d with_desc=%d",
                        job_id[:8], len(images),
                        sum(1 for im in described if (im or {}).get("description")),
                        extra={"event": "BYO_IMAGES_DESCRIBED", "job_id": job_id},
                    )
            elif step == JobState.CHUNKING:
                parents, segments = await _step_chunk(job, result.get("extraction", {}))
                result["chunks"] = parents
                result["segments"] = segments
                modality = parents[0].get("modality") if parents else None
                retrieval_mode = parents[0].get("retrieval_mode") if parents else None
                log.info(
                    "[BYO] chunk done job=%s parents=%d segments=%d modality=%s mode=%s",
                    job_id[:8], len(parents), len(segments), modality, retrieval_mode,
                    extra={"event": "BYO_CHUNK_DONE", "job_id": job_id,
                           "parents": len(parents), "segments": len(segments),
                           "modality": modality, "retrieval_mode": retrieval_mode},
                )
            elif step == JobState.CLASSIFYING:
                result["classifications"] = await _step_classify(result.get("chunks", []))
                labeled = sum(
                    1 for c in result.get("chunks", [])
                    if (c.get("labels") or c.get("topics"))
                )
                log.info(
                    "[BYO] classify done job=%s chunks=%d labeled=%d",
                    job_id[:8], len(result.get("chunks", [])), labeled,
                    extra={"event": "BYO_CLASSIFY_DONE", "job_id": job_id,
                           "chunks": len(result.get("chunks", [])), "labeled": labeled},
                )
            elif step == JobState.EMBEDDING:
                result["embeddings_done"] = await _step_embed(result.get("segments", []))
                segs = result.get("segments", []) or []
                embedded = sum(1 for s in segs if s.get("embedding"))
                with_q = sum(1 for s in segs if s.get("questions"))
                log.info(
                    "[BYO] embed done job=%s segments=%d embedded=%d with_questions=%d",
                    job_id[:8], len(segs), embedded, with_q,
                    extra={"event": "BYO_EMBED_DONE", "job_id": job_id,
                           "segments": len(segs), "embedded": embedded,
                           "with_questions": with_q},
                )
            elif step == JobState.STORING:
                await _step_store(job, result)
                log.info(
                    "[BYO] store done job=%s parents=%d segments=%d",
                    job_id[:8], len(result.get("chunks", [])),
                    len(result.get("segments", [])),
                    extra={"event": "BYO_STORE_DONE", "job_id": job_id},
                )

            step_ms = int((time.time() - step_start) * 1000)
            log.info(
                "[BYO] step end   job=%s step=%s ms=%d",
                job_id[:8], step, step_ms,
                extra={"event": "BYO_STEP_END", "job_id": job_id,
                       "step": step, "elapsed_ms": step_ms},
            )

            # Save intermediate result
            await _update_job(db, job_id, {"result": result, "step_index": i + 1})

        # Check if extraction actually produced content
        chunks = result.get("chunks", [])
        extraction = result.get("extraction", {})
        extraction_error = extraction.get("meta", {}).get("error") if isinstance(extraction, dict) else None

        if not chunks and extraction_error:
            # Extraction failed — mark as error, not ready
            log.warning("Job %s completed but extraction failed: %s", job_id[:8], extraction_error)
            await _update_job(db, job_id, {
                "state": JobState.COMPLETE,
                "progress": 1.0,
                "completed_at": datetime.utcnow(),
                "locked_by": None,
                "error": f"Extraction failed: {extraction_error}",
            })
            await db.byo_resources.update_one(
                {"resource_id": job["resource_id"]},
                {"$set": {
                    "status": ResourceStatus.ERROR,
                    "progress": 1.0,
                    "error": f"Content extraction failed: {extraction_error}",
                }},
            )
        elif not chunks:
            # No chunks produced — this is an ERROR, not ready
            log.warning("Job %s completed with 0 chunks — marking as error", job_id[:8])
            await _update_job(db, job_id, {
                "state": JobState.FAILED,
                "progress": 1.0,
                "completed_at": datetime.utcnow(),
                "locked_by": None,
                "error": "No extractable content. The document may be scanned images, encrypted, or empty.",
            })
            await db.byo_resources.update_one(
                {"resource_id": job["resource_id"]},
                {"$set": {
                    "status": ResourceStatus.ERROR,
                    "progress": 1.0,
                    "chunk_count": 0,
                    "error": "No extractable content found. Try re-uploading or use a different file format.",
                }},
            )
        else:
            # Normal completion with chunks
            await _update_job(db, job_id, {
                "state": JobState.COMPLETE,
                "progress": 1.0,
                "completed_at": datetime.utcnow(),
                "locked_by": None,
            })
            await db.byo_resources.update_one(
                {"resource_id": job["resource_id"]},
                {"$set": {
                    "status": ResourceStatus.READY,
                    "progress": 1.0,
                    "chunk_count": len(chunks),
                    "segment_count": len(result.get("segments", [])),
                }},
            )

        # Update collection stats
        await _update_collection_stats(db, job["collection_id"])

        log.info("Job %s complete (%d chunks)", job_id[:8], len(chunks))

        # Job succeeded — log total elapsed.
        total_ms = int((time.time() - job_start) * 1000)
        log.info(
            "[BYO] job end job=%s total_ms=%d parents=%d segments=%d",
            job_id[:8], total_ms,
            len(result.get("chunks", [])), len(result.get("segments", [])),
            extra={"event": "BYO_JOB_END", "job_id": job_id,
                   "elapsed_ms": total_ms,
                   "parents": len(result.get("chunks", [])),
                   "segments": len(result.get("segments", []))},
        )

    except Exception as e:
        retries = job.get("retries", 0)
        max_retries = job.get("max_retries", 3)
        current_step = PIPELINE_STEPS[job.get("step_index", 0)] if job.get("step_index", 0) < len(PIPELINE_STEPS) else "unknown"
        tb_short = traceback.format_exc()[:2000]

        if retries < max_retries:
            # Retry with exponential backoff
            delay = 2 ** retries
            log.warning(
                "[BYO] job retry job=%s step=%s attempt=%d/%d delay=%ds err=%s",
                job_id[:8], current_step, retries + 1, max_retries, delay, repr(e),
                extra={"event": "BYO_JOB_RETRY", "job_id": job_id,
                       "step": current_step, "attempt": retries + 1,
                       "max_retries": max_retries, "delay_s": delay,
                       "error": repr(e), "traceback": tb_short},
                exc_info=True,  # full stack in the log viewer
            )
            await _update_job(db, job_id, {
                "retries": retries + 1,
                "locked_by": None,
                "lock_expires": datetime.utcnow() + timedelta(seconds=delay),
                "error": f"[{current_step}] {str(e)}",
            })
        else:
            log.error(
                "[BYO] job FAILED job=%s step=%s attempts=%d err=%s",
                job_id[:8], current_step, max_retries, repr(e),
                extra={"event": "BYO_JOB_FAILED", "job_id": job_id,
                       "step": current_step, "max_retries": max_retries,
                       "error": repr(e), "traceback": tb_short},
                exc_info=True,
            )
            await _update_job(db, job_id, {
                "state": JobState.FAILED,
                "error": f"[{current_step}] {str(e)}\n{tb_short[:500]}",
                "locked_by": None,
            })
            await db.byo_resources.update_one(
                {"resource_id": job["resource_id"]},
                {"$set": {"status": ResourceStatus.ERROR, "error": f"[{current_step}] {str(e)[:180]}"}},
            )
            # Roll the collection status forward so the UI reflects the
            # failure (was previously only refreshed on the success path,
            # leaving the collection stuck at 'processing').
            try:
                await _update_collection_stats(db, job["collection_id"])
            except Exception as _stats_err:  # noqa: BLE001
                log.warning("post-failure stats update errored: %s", _stats_err)


# ── Pipeline steps ──────────────────────────────────────────────────────

async def _describe_images(images: list[dict], resource_id: str) -> list[dict]:
    """Describe images using a vision LLM. Runs pages in parallel batches.

    Each image gets a text description that captures: diagrams, equations,
    graphs, tables, handwriting, or any visual content relevant to learning.
    """
    import base64
    import httpx
    from app.core.config import settings

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        log.warning("No API key for image description — skipping")
        return images

    # Filter to images with actual data
    describable = [(i, img) for i, img in enumerate(images) if img.get("data")]
    if not describable:
        return images

    log.info("Describing %d images for %s", len(describable), resource_id[:8])

    async def _describe_one(img: dict) -> str:
        """Describe a single image using vision LLM."""
        data = img["data"]
        if isinstance(data, bytes):
            b64 = base64.b64encode(data).decode("utf-8")
        else:
            b64 = data  # already base64

        ext = img.get("path", "").rsplit(".", 1)[-1] or "png"
        media_type = f"image/{ext}" if ext in ("png", "jpg", "jpeg", "gif", "webp") else "image/png"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "openai/gpt-5.4-nano",
                        "max_tokens": 500,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{media_type};base64,{b64}"},
                                },
                                {
                                    "type": "text",
                                    "text": (
                                        "Describe this image from a study document. Focus on: "
                                        "diagrams, equations, graphs, tables, flowcharts, or any "
                                        "educational content. Be specific about what's shown — "
                                        "label values, axis names, relationships. "
                                        "If it's a math equation, write it in LaTeX. "
                                        "If it's decorative or irrelevant, say 'decorative image'. "
                                        "Be concise — 2-3 sentences max."
                                    ),
                                },
                            ],
                        }],
                    },
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"].strip()
                else:
                    log.warning("Image description API error: %d", resp.status_code)
                    return ""
        except Exception as e:
            log.warning("Image description failed: %s", e)
            return ""

    # Process in parallel batches of 5 to avoid rate limits
    BATCH_SIZE = 5
    for batch_start in range(0, len(describable), BATCH_SIZE):
        batch = describable[batch_start:batch_start + BATCH_SIZE]
        descriptions = await asyncio.gather(
            *[_describe_one(img) for _, img in batch],
            return_exceptions=True,
        )
        for (idx, img), desc in zip(batch, descriptions):
            if isinstance(desc, str) and desc and desc.lower() != "decorative image":
                images[idx]["description"] = desc
                log.debug("Image %s: %s", img.get("path", "?"), desc[:60])

    described_count = sum(1 for img in images if img.get("description"))
    log.info("Described %d/%d images for %s", described_count, len(describable), resource_id[:8])
    return images


def _merge_image_descriptions(markdown: str, images: list[dict]) -> str:
    """Merge image descriptions into the markdown at the right page positions.

    Images have anchor.page indicating which page they came from.
    We insert the description after the page marker comment.
    """
    if not images:
        return markdown

    # Group descriptions by page
    by_page: dict[int, list[str]] = {}
    for img in images:
        desc = img.get("description", "")
        if not desc:
            continue
        page = img.get("anchor", {}).get("page") if isinstance(img.get("anchor"), dict) else None
        if page:
            by_page.setdefault(page, []).append(desc)

    if not by_page:
        return markdown

    # Insert descriptions after page markers
    import re
    def _insert_after_page(match):
        page_num = int(match.group(1))
        descs = by_page.get(page_num, [])
        if not descs:
            return match.group(0)
        desc_block = "\n".join(f"[Image: {d}]" for d in descs)
        return f"{match.group(0)}\n{desc_block}"

    result = re.sub(r"<!--\s*page\s+(\d+)\s*-->", _insert_after_page, markdown)

    # Any images without page anchors — append at the end
    orphans = [img["description"] for img in images
               if img.get("description") and not (isinstance(img.get("anchor"), dict) and img["anchor"].get("page"))]
    if orphans:
        result += "\n\n" + "\n".join(f"[Image: {d}]" for d in orphans)

    return result


async def _step_extract(job: dict) -> dict:
    """Extract content from the resource using the appropriate processor.

    If the file is in GCS (gs:// path), downloads to a temp file first —
    processors like PyMuPDF need local file access.
    """
    import os
    import tempfile
    from byo.processing.processors import get_processor

    mime_type = job["meta"].get("mime_type", "")
    source_url = job["meta"].get("source_url")
    storage_path = job["meta"].get("storage_path")

    # Download GCS files to temp for local processing
    temp_path = None
    if storage_path and storage_path.startswith("gs://"):
        from byo.shared.storage import default_storage
        log.info("Downloading from GCS for extraction: %s", storage_path[:60])
        try:
            data = await default_storage.read(storage_path)
        except Exception as gcs_err:
            log.error("GCS download failed for %s: %s", storage_path[:60], gcs_err)
            raise RuntimeError(f"Failed to download file from GCS: {gcs_err}") from gcs_err
        # Preserve file extension for processor detection
        ext = os.path.splitext(storage_path)[1] or ".bin"
        fd, temp_path = tempfile.mkstemp(suffix=ext)
        os.write(fd, data)
        os.close(fd)
        storage_path = temp_path

    try:
        processor = get_processor(mime_type)
        result = await processor.extract(
            resource_id=job["resource_id"],
            mime_type=mime_type,
            source_url=source_url,
            storage_path=storage_path,
            meta=job["meta"],
        )
        return result.model_dump() if hasattr(result, "model_dump") else result
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


async def _step_chunk(job: dict, extraction: dict) -> tuple[list[dict], list[dict]]:
    """Split extracted content into parent chunks + child segments.

    Returns (parents, segments). Parents are stored in byo_chunks and
    returned to the LLM; segments are embedded and stored in byo_segments.
    """
    from byo.processing.chunker import chunk_markdown

    markdown = extraction.get("markdown", "")
    resource_meta = extraction.get("meta", {})
    mime_type = job["meta"].get("mime_type", "")

    parents, segments = await chunk_markdown(
        markdown=markdown,
        resource_id=job["resource_id"],
        collection_id=job["collection_id"],
        resource_meta=resource_meta,
        user_id=job.get("user_id", ""),
        mime_type=mime_type,
    )
    return parents, segments


async def _step_classify(chunks: list[dict]) -> list[dict]:
    """Classify parent chunks using batch LLM call.

    Classification runs on PARENTS (not segments) — labels/topics describe
    the citable unit. The indexer later propagates topics onto each
    parent's segments.
    """
    from byo.processing.classifier import classify_chunks_batch

    if not chunks:
        return []

    classifications = await classify_chunks_batch(chunks)

    # Merge classifications back into parent chunks
    for chunk, cls in zip(chunks, classifications):
        chunk["labels"] = cls.get("labels", [])
        chunk["topics"] = cls.get("topics", [])

    return [{"labels": c.get("labels", []), "topics": c.get("topics", [])} for c in classifications]


async def _step_embed(segments: list[dict]) -> bool:
    """Generate embeddings for all SEGMENTS (not parents).

    Parents are not embedded in the parent-child scheme — only segments
    are. The embedder also runs HyQE (hypothetical question generation)
    on segments whose retrieval_mode isn't VISUAL_DESCRIPTION.
    """
    from byo.processing.embedder import embed_segments_batch

    if not segments:
        return True

    await embed_segments_batch(segments)
    return True


async def _step_store(job: dict, result: dict):
    """Persist parents + segments via the indexer."""
    from byo.processing.indexer import index_chunks_and_segments

    parents = result.get("chunks", [])
    segments = result.get("segments", [])
    classifications = result.get("classifications", [])

    if not parents:
        return

    # Merge classifications into parent chunks (in case classify ran on
    # a fresh retry and didn't persist back into result["chunks"] yet).
    for i, chunk in enumerate(parents):
        if i < len(classifications):
            chunk["labels"] = classifications[i].get("labels", []) or chunk.get("labels", [])
            chunk["topics"] = classifications[i].get("topics", []) or chunk.get("topics", [])

    await index_chunks_and_segments(
        resource_id=job["resource_id"],
        collection_id=job["collection_id"],
        user_id=job.get("user_id", ""),
        parents=parents,
        segments=segments,
    )


async def _update_collection_stats(db, collection_id: str):
    """Recalculate collection stats from resources (Qdrant is content store, not MongoDB)."""
    resource_count = await db.byo_resources.count_documents({"collection_id": collection_id})

    # Sum chunk_count from resource metadata (the counts come from Qdrant upsert results)
    pipeline = [
        {"$match": {"collection_id": collection_id, "status": "ready"}},
        {"$group": {"_id": None, "total_chunks": {"$sum": "$chunk_count"}}},
    ]
    agg = await db.byo_resources.aggregate(pipeline).to_list(1)
    chunk_count = agg[0]["total_chunks"] if agg else 0

    topics = []  # topics derived from Qdrant, not MongoDB

    # Determine collection status with ALL five states in play:
    # ready      — every resource ready
    # partial    — at least one ready (others still processing / errored)
    # processing — nothing ready, nothing errored (all queued/processing)
    # error      — nothing ready AND at least one errored (everything failed
    #              or a mix of failed + still-queued, with none succeeding)
    # (no resources yet) — leave as 'processing' so the card shows the
    #              right affordance while the student uploads first files.
    statuses = []
    async for res in db.byo_resources.find({"collection_id": collection_id}, {"status": 1}):
        statuses.append(res.get("status"))

    if not statuses:
        col_status = "processing"
    elif all(s == "ready" for s in statuses):
        col_status = "ready"
    elif any(s == "ready" for s in statuses):
        col_status = "partial"
    elif any(s == "error" for s in statuses):
        col_status = "error"
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
    consecutive_errors = 0

    while max_iterations is None or iterations < max_iterations:
        iterations += 1

        # Clean up completed tasks
        done = {t for t in active_tasks if t.done()}
        for t in done:
            try:
                t.result()
            except Exception as e:
                log.error("Worker task failed: %s", e)
        active_tasks -= done

        # Claim new jobs if under capacity
        if len(active_tasks) < MAX_CONCURRENT_JOBS:
            try:
                job = await _claim_job(db)
                consecutive_errors = 0
                if job:
                    task = asyncio.create_task(_process_job(job))
                    active_tasks.add(task)
                    continue
            except Exception as e:
                consecutive_errors += 1
                backoff = min(30, 2 ** consecutive_errors)
                log.warning(
                    "Worker claim failed (attempt %d, backoff %ds): %s",
                    consecutive_errors, backoff, e,
                )
                if consecutive_errors >= 10:
                    log.error("Worker: 10 consecutive claim failures — reconnecting DB")
                    try:
                        db = _get_db()
                    except Exception:
                        pass
                    consecutive_errors = 0
                await asyncio.sleep(backoff)
                continue

        # No jobs available or at capacity — poll
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    # Wait for remaining tasks
    if active_tasks:
        await asyncio.gather(*active_tasks, return_exceptions=True)

    log.info("BYO worker %s stopped", WORKER_ID)
