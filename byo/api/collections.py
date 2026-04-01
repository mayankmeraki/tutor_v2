"""Collection + Resource REST API.

Endpoints:
  POST   /api/v1/byo/collections              — Create collection
  GET    /api/v1/byo/collections               — List user's collections
  GET    /api/v1/byo/collections/:id           — Collection detail + resources
  DELETE /api/v1/byo/collections/:id           — Delete collection

  POST   /api/v1/byo/collections/:id/resources — Add resource (file upload or URL)
  GET    /api/v1/byo/collections/:id/resources — List resources with status
  DELETE /api/v1/byo/collections/:id/resources/:rid — Remove resource

  GET    /api/v1/byo/jobs/:job_id              — Poll processing status
"""

from __future__ import annotations

import mimetypes
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/byo", tags=["byo"])


def _validate_local_path(storage_path: str) -> bool:
    """Validate that a local storage path is safe to serve (no path traversal)."""
    import os
    from byo.storage.local import UPLOAD_DIR
    resolved = os.path.realpath(storage_path)
    base = os.path.realpath(UPLOAD_DIR)
    return resolved.startswith(base + os.sep) or resolved.startswith(base)


def _get_db():
    from app.core.mongodb import get_mongo_db
    return get_mongo_db()


def _get_storage():
    from byo.storage import default_storage
    return default_storage


async def _get_user(request: Request) -> dict:
    """Extract authenticated user. Reuses main app's auth."""
    from app.api.routes.auth import get_optional_user
    user = await get_optional_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


# ── Collections ────────────────────────────────────────────────────────


@router.post("/collections")
async def create_collection(request: Request, user: dict = Depends(_get_user)):
    """Create a new collection."""
    body = await request.json()
    db = _get_db()

    collection_id = str(uuid.uuid4())[:12]
    doc = {
        "collection_id": collection_id,
        "user_id": user["email"],
        "title": body.get("title", "Untitled Collection"),
        "description": body.get("description", ""),
        "intent": body.get("intent", ""),
        "status": "processing",
        "stats": {"resources": 0, "chunks": 0, "topics": []},
        "tags": body.get("tags", []),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    await db.collections.insert_one(doc)

    log.info("Collection created: %s by %s", collection_id, user["email"])
    return {"collection_id": collection_id, "status": "created"}


@router.get("/collections")
async def list_collections(request: Request, user: dict = Depends(_get_user)):
    """List user's collections."""
    db = _get_db()
    cursor = db.collections.find(
        {"user_id": user["email"]},
        {"_id": 0},
    ).sort("created_at", -1)
    return [doc async for doc in cursor]


@router.get("/collections/{collection_id}")
async def get_collection(collection_id: str, request: Request, user: dict = Depends(_get_user)):
    """Get collection detail with resources."""
    db = _get_db()
    col = await db.collections.find_one(
        {"collection_id": collection_id, "user_id": user["email"]},
        {"_id": 0},
    )
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Include resources
    resources = []
    async for res in db.byo_resources.find(
        {"collection_id": collection_id},
        {"_id": 0, "embedding": 0},
    ).sort("created_at", 1):
        resources.append(res)

    col["resources"] = resources
    return col


@router.delete("/collections/{collection_id}")
async def delete_collection(collection_id: str, request: Request, user: dict = Depends(_get_user)):
    """Delete a collection and all its resources/chunks."""
    db = _get_db()

    # Verify ownership
    col = await db.collections.find_one({"collection_id": collection_id, "user_id": user["email"]})
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Delete chunks, resources, jobs, collection
    await db.byo_chunks.delete_many({"collection_id": collection_id})
    await db.byo_resources.delete_many({"collection_id": collection_id})
    await db.byo_jobs.delete_many({"collection_id": collection_id})
    await db.collections.delete_one({"collection_id": collection_id})

    # TODO: delete files from storage

    log.info("Collection deleted: %s", collection_id)
    return {"ok": True}


# ── Resources ──────────────────────────────────────────────────────────


@router.post("/collections/{collection_id}/resources")
async def add_resource(
    collection_id: str,
    request: Request,
    file: UploadFile | None = File(None),
    url: str = Form(""),
    text: str = Form(""),
    title: str = Form(""),
    user: dict = Depends(_get_user),
):
    """Add a resource to a collection.

    Three modes:
      - File upload (multipart form)
      - URL (YouTube, article, etc.)
      - Inline text

    Returns job_id for status polling.
    """
    db = _get_db()

    # Verify collection exists and belongs to user
    col = await db.collections.find_one(
        {"collection_id": collection_id, "user_id": user["email"]},
    )
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")

    resource_id = str(uuid.uuid4())
    storage = _get_storage()
    meta = {}

    if file:
        # File upload
        contents = await file.read()
        if len(contents) > 50 * 1024 * 1024:  # 50MB limit
            raise HTTPException(status_code=413, detail="File too large (max 50MB)")

        # Deduplicate: hash file content, skip if same file already in collection
        import hashlib
        file_hash = hashlib.sha256(contents).hexdigest()
        existing = await db.byo_resources.find_one(
            {"collection_id": collection_id, "file_hash": file_hash, "status": {"$ne": "error"}},
            {"resource_id": 1, "original_name": 1},
        )
        if existing:
            return {
                "resource_id": existing["resource_id"],
                "job_id": None,
                "status": "duplicate",
                "message": f"This file was already uploaded as '{existing.get('original_name', '?')}'",
            }

        mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
        storage_path = await storage.save(contents, user["email"], collection_id, file.filename or "upload")

        doc = {
            "resource_id": resource_id,
            "collection_id": collection_id,
            "user_id": user["email"],
            "source_type": "file",
            "mime_type": mime,
            "original_name": file.filename or "upload",
            "source_url": None,
            "storage_path": storage_path,
            "file_size": len(contents),
            "file_hash": file_hash,
            "status": "queued",
            "progress": 0.0,
            "meta": {},
            "chunk_count": 0,
            "created_at": datetime.utcnow(),
        }
        meta = {"mime_type": mime, "storage_path": storage_path}

    elif url:
        # URL (YouTube, article)
        mime = "application/x-youtube" if "youtube" in url or "youtu.be" in url else "text/html"
        doc = {
            "resource_id": resource_id,
            "collection_id": collection_id,
            "user_id": user["email"],
            "source_type": "url",
            "mime_type": mime,
            "original_name": title or url[:60],
            "source_url": url,
            "storage_path": None,
            "file_size": 0,
            "status": "queued",
            "progress": 0.0,
            "meta": {},
            "chunk_count": 0,
            "created_at": datetime.utcnow(),
        }
        meta = {"mime_type": mime, "source_url": url}

    elif text:
        # Inline text
        doc = {
            "resource_id": resource_id,
            "collection_id": collection_id,
            "user_id": user["email"],
            "source_type": "text",
            "mime_type": "text/plain",
            "original_name": title or "Pasted text",
            "source_url": None,
            "storage_path": None,
            "file_size": len(text),
            "status": "queued",
            "progress": 0.0,
            "meta": {"text": text},
            "chunk_count": 0,
            "created_at": datetime.utcnow(),
        }
        meta = {"mime_type": "text/plain", "text": text}

    else:
        raise HTTPException(status_code=400, detail="Provide file, url, or text")

    await db.byo_resources.insert_one(doc)

    # Increment collection resource count immediately (so frontend sees "1 file" right away)
    await db.collections.update_one(
        {"collection_id": collection_id},
        {"$inc": {"stats.resources": 1}, "$set": {"updated_at": datetime.utcnow()}},
    )

    # Submit processing job (wrapped in try/except — resource already exists)
    job_id = None
    try:
        from byo.pipeline.orchestrator import submit_processing_job
        job_id = await submit_processing_job(resource_id, collection_id, user["email"], meta)
    except Exception as e:
        log.error("Failed to submit processing job for %s: %s", resource_id[:8], e)
        await db.byo_resources.update_one(
            {"resource_id": resource_id},
            {"$set": {"status": "error", "error": f"Job submission failed: {str(e)[:200]}"}},
        )

    log.info("Resource added: %s to collection %s, job %s",
            resource_id[:8], collection_id[:8], (job_id or "FAILED")[:8])

    return {
        "resource_id": resource_id,
        "job_id": job_id,
        "status": "queued" if job_id else "error",
    }


@router.get("/collections/{collection_id}/resources")
async def list_resources(collection_id: str, request: Request, user: dict = Depends(_get_user)):
    """List resources in a collection with their processing status."""
    db = _get_db()
    cursor = db.byo_resources.find(
        {"collection_id": collection_id, "user_id": user["email"]},
        {"_id": 0, "embedding": 0},
    ).sort("created_at", 1)
    return [doc async for doc in cursor]


@router.delete("/collections/{collection_id}/resources/{resource_id}")
async def delete_resource(collection_id: str, resource_id: str, request: Request, user: dict = Depends(_get_user)):
    """Remove a resource, its chunks, and the underlying file."""
    db = _get_db()

    # Get the storage path before deleting
    resource = await db.byo_resources.find_one(
        {"resource_id": resource_id, "user_id": user["email"]},
        {"storage_path": 1},
    )

    await db.byo_chunks.delete_many({"resource_id": resource_id})
    await db.byo_resources.delete_one({"resource_id": resource_id, "user_id": user["email"]})

    # Delete the actual file from storage
    if resource and resource.get("storage_path"):
        try:
            storage = _get_storage()
            await storage.delete(resource["storage_path"])
        except Exception as e:
            log.warning("Failed to delete file %s: %s", resource["storage_path"][:40], e)

    return {"ok": True}


# ── Job status ─────────────────────────────────────────────────────────


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request, user: dict = Depends(_get_user)):
    """Poll processing job status."""
    from byo.pipeline.orchestrator import get_job_status
    status = await get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


# ── File serving ──────────────────────────────────────────────────────


@router.get("/audio/{audio_id}")
async def serve_audio(audio_id: str, request: Request, user: dict = Depends(_get_user)):
    """Serve generated audio artifacts (TTS output)."""
    import os
    from fastapi.responses import RedirectResponse
    db = _get_db()

    resource = await db.byo_resources.find_one(
        {"resource_id": audio_id, "user_id": user["email"]},
        {"storage_path": 1, "mime_type": 1, "original_name": 1},
    )
    if not resource:
        raise HTTPException(status_code=404, detail="Audio not found")

    storage_path = resource.get("storage_path", "")
    if storage_path.startswith("gs://"):
        storage = _get_storage()
        from byo.storage.gcs import GCSStorage
        if isinstance(storage, GCSStorage):
            signed_url = storage.generate_signed_url(storage_path, content_type="audio/mpeg")
            return RedirectResponse(url=signed_url, status_code=302)

    if not _validate_local_path(storage_path) or not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(path=storage_path, media_type="audio/mpeg", filename=resource.get("original_name", "audio.mp3"))


@router.get("/resources/{resource_id}/file")
async def serve_resource_file(resource_id: str, request: Request, user: dict = Depends(_get_user)):
    """Serve the original uploaded file for viewing in the browser.

    - GCS storage: redirects to a signed URL (1-hour expiry)
    - Local storage: serves file directly with FileResponse

    Works for: PDF, video, audio, images, text, DOCX, etc.
    """
    import os
    from fastapi.responses import RedirectResponse
    db = _get_db()

    resource = await db.byo_resources.find_one(
        {"resource_id": resource_id, "user_id": user["email"]},
        {"storage_path": 1, "mime_type": 1, "original_name": 1},
    )
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    storage_path = resource.get("storage_path")
    if not storage_path:
        raise HTTPException(status_code=404, detail="No file path recorded")

    mime_type = resource.get("mime_type", "application/octet-stream")

    # GCS path (gs://...) → redirect to signed URL
    if storage_path.startswith("gs://"):
        storage = _get_storage()
        from byo.storage.gcs import GCSStorage
        if isinstance(storage, GCSStorage):
            signed_url = storage.generate_signed_url(storage_path, content_type=mime_type)
            return RedirectResponse(url=signed_url, status_code=302)
        raise HTTPException(status_code=500, detail="GCS storage not configured")

    # Local path → validate + serve directly
    if not _validate_local_path(storage_path) or not os.path.exists(storage_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=storage_path,
        media_type=mime_type,
        filename=resource.get("original_name", "file"),
    )
