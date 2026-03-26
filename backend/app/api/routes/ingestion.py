"""Ingestion API — Collection and Material CRUD + upload endpoints.

Handles:
- YouTube URLs (single + playlist)
- PDF file uploads
- Text paste
- Mixed uploads (multiple types in one collection)
- Incremental addition (add materials to existing collections)
- Duplicate detection
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from app.api.routes.auth import get_optional_user

from app.core.mongodb import get_mongo_db
from app.services.pipeline.orchestrator import (
    create_collection,
    create_material,
    process_material,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/collections", tags=["ingestion"])


# ── Collection CRUD ──────────────────────────────────────────────────────────

@router.post("")
async def create_new_collection(request: Request, user: dict = Depends(get_optional_user)):
    """Create a new BYO content collection.

    Body: { title: str, userId: str }
    """
    body = await request.json()
    title = body.get("title", "My Collection")
    user_id = body.get("userId", "anonymous")

    collection_id = await create_collection(user_id, title)

    return JSONResponse(
        status_code=201,
        content={"collectionId": collection_id, "title": title, "status": "created"},
    )


@router.get("")
async def list_collections(request: Request, user: dict = Depends(get_optional_user)):
    """List collections for a user.

    Query: ?userId=...
    """
    user_id = request.query_params.get("userId", "")
    db = get_mongo_db()

    query = {}
    if user_id:
        query["userId"] = user_id

    collections = await db.content_collections.find(
        query,
        {"_id": 0, "collectionId": 1, "title": 1, "status": 1, "type": 1,
         "stats": 1, "subjects": 1, "processingProgress": 1,
         "createdAt": 1, "updatedAt": 1},
    ).sort("createdAt", -1).to_list(100)

    # Serialize datetime objects
    for c in collections:
        for key in ("createdAt", "updatedAt"):
            if isinstance(c.get(key), datetime):
                c[key] = c[key].isoformat()

    return {"collections": collections}


@router.get("/{collection_id}")
async def get_collection(collection_id: str):
    """Get collection details including all materials."""
    db = get_mongo_db()

    collection = await db.content_collections.find_one(
        {"collectionId": collection_id}, {"_id": 0},
    )
    if not collection:
        return JSONResponse(status_code=404, content={"error": "Collection not found"})

    materials = await db.materials.find(
        {"collectionId": collection_id},
        {"_id": 0, "materialId": 1, "title": 1, "status": 1, "source.type": 1,
         "classification": 1, "chunkCount": 1, "duration": 1, "pageCount": 1,
         "thumbnailUrl": 1, "addedAt": 1, "readyAt": 1, "errorDetail": 1},
    ).sort("addedAt", 1).to_list(None)

    # Serialize datetimes
    for key in ("createdAt", "updatedAt"):
        if isinstance(collection.get(key), datetime):
            collection[key] = collection[key].isoformat()
    for m in materials:
        for key in ("addedAt", "readyAt"):
            if isinstance(m.get(key), datetime):
                m[key] = m[key].isoformat()

    return {"collection": collection, "materials": materials}


@router.get("/{collection_id}/status")
async def get_collection_status(collection_id: str):
    """Get processing status for a collection."""
    db = get_mongo_db()

    collection = await db.content_collections.find_one(
        {"collectionId": collection_id},
        {"_id": 0, "collectionId": 1, "status": 1, "processingProgress": 1, "stats": 1},
    )
    if not collection:
        return JSONResponse(status_code=404, content={"error": "Collection not found"})

    # Per-material status
    materials = await db.materials.find(
        {"collectionId": collection_id},
        {"_id": 0, "materialId": 1, "title": 1, "status": 1, "errorDetail": 1},
    ).to_list(None)

    return {
        "collection": collection,
        "materials": materials,
    }


# ── Material Upload ──────────────────────────────────────────────────────────

@router.post("/{collection_id}/materials")
async def add_material(collection_id: str, request: Request):
    """Add a material to a collection.

    Supports three input types:
    - YouTube URL: { type: "youtube_video", url: "https://..." }
    - Text: { type: "text", title: "...", content: "..." }
    - Multiple URLs: { type: "batch", items: [{type, url/content, title?}, ...] }

    For PDF uploads, use the /upload endpoint below.
    """
    db = get_mongo_db()

    # Verify collection exists
    collection = await db.content_collections.find_one({"collectionId": collection_id})
    if not collection:
        return JSONResponse(status_code=404, content={"error": "Collection not found"})

    body = await request.json()
    material_type = body.get("type", "")

    # ── Batch upload ──
    if material_type == "batch":
        items = body.get("items", [])
        results = []
        for item in items:
            item_type = item.get("type", "")
            if item_type == "youtube_video":
                # Duplicate check
                dup = await _check_duplicate(collection_id, url=item.get("url"))
                if dup:
                    results.append({"status": "duplicate", "existingId": dup, "url": item.get("url")})
                    continue
                mid = await create_material(
                    collection_id, "youtube_video",
                    url=item.get("url"), title=item.get("title", "Untitled"),
                )
                results.append({"materialId": mid, "status": "processing"})
            elif item_type == "text":
                mid = await create_material(
                    collection_id, "text",
                    title=item.get("title", "Untitled"),
                    raw_text=item.get("content", ""),
                )
                results.append({"materialId": mid, "status": "processing"})

        return JSONResponse(
            status_code=201,
            content={"results": results, "count": len(results)},
        )

    # ── Single YouTube video ──
    if material_type == "youtube_video":
        url = body.get("url", "")
        if not url:
            return JSONResponse(status_code=400, content={"error": "url is required"})

        # Duplicate check
        dup = await _check_duplicate(collection_id, url=url)
        if dup:
            return JSONResponse(
                status_code=409,
                content={"error": "duplicate", "existingMaterialId": dup},
            )

        material_id = await create_material(
            collection_id, "youtube_video",
            url=url, title=body.get("title", "Untitled"),
        )
        return JSONResponse(
            status_code=201,
            content={"materialId": material_id, "status": "processing"},
        )

    # ── Text paste ──
    if material_type == "text":
        content = body.get("content", "")
        if not content:
            return JSONResponse(status_code=400, content={"error": "content is required"})

        material_id = await create_material(
            collection_id, "text",
            title=body.get("title", "Untitled"),
            raw_text=content,
        )
        return JSONResponse(
            status_code=201,
            content={"materialId": material_id, "status": "processing"},
        )

    return JSONResponse(
        status_code=400,
        content={"error": f"Unknown material type: {material_type}. Use 'youtube_video', 'text', or 'batch'."},
    )


@router.post("/{collection_id}/upload")
async def upload_file_material(
    collection_id: str,
    file: UploadFile = File(...),
    title: str = Form(None),
):
    """Upload a PDF or other file to a collection."""
    db = get_mongo_db()

    collection = await db.content_collections.find_one({"collectionId": collection_id})
    if not collection:
        return JSONResponse(status_code=404, content={"error": "Collection not found"})

    # Enforce file size limit (50MB)
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024
    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_SIZE:
        return JSONResponse(status_code=413, content={"error": f"File too large. Max {MAX_UPLOAD_SIZE // (1024*1024)}MB."})
    filename = file.filename or "upload"
    file_title = title or filename.rsplit(".", 1)[0]

    # Determine type from extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        source_type = "pdf"
    elif ext in ("txt", "md"):
        source_type = "text"
    else:
        source_type = "pdf"  # Default to PDF processing

    if source_type == "text":
        material_id = await create_material(
            collection_id, "text",
            title=file_title,
            raw_text=file_bytes.decode("utf-8", errors="replace"),
        )
    else:
        material_id = await create_material(
            collection_id, "pdf",
            title=file_title,
            file_bytes=file_bytes,
            original_filename=filename,
        )

    return JSONResponse(
        status_code=201,
        content={"materialId": material_id, "status": "processing", "filename": filename},
    )


# ── Re-index endpoint (for incremental updates) ─────────────────────────────

@router.post("/{collection_id}/reindex")
async def reindex_collection(collection_id: str):
    """Rebuild indexes for a collection.

    Use after adding new materials to re-detect topics, deduplicate concepts,
    and regenerate the flow map. Only processes materials that are "ready".
    """
    import asyncio
    from app.services.pipeline.adapters.anthropic_llm import AnthropicLLMAdapter
    from app.services.pipeline.processors.index_builder import build_indexes
    from app.services.pipeline.processors.sequencer import generate_flow_map

    db = get_mongo_db()

    collection = await db.content_collections.find_one({"collectionId": collection_id})
    if not collection:
        return JSONResponse(status_code=404, content={"error": "Collection not found"})

    # Run in background
    async def _reindex():
        try:
            llm = AnthropicLLMAdapter()
            await build_indexes(collection_id, llm)
            await generate_flow_map(collection_id, llm, version_increment=True)
            await db.content_collections.update_one(
                {"collectionId": collection_id},
                {"$set": {"status": "ready", "updatedAt": datetime.utcnow()}},
            )
            log.info("Reindex complete for %s", collection_id)
        except Exception as e:
            log.error("Reindex failed for %s: %s", collection_id, e)

    asyncio.create_task(_reindex())

    return {"status": "reindexing", "collectionId": collection_id}


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _check_duplicate(collection_id: str, url: str | None = None) -> str | None:
    """Check if a material with the same URL already exists. Returns materialId or None."""
    if not url:
        return None

    db = get_mongo_db()

    # Normalize URL
    normalized = url.strip().rstrip("/")
    if "youtu.be/" in normalized:
        # Convert short URLs to standard format
        import re
        match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', normalized)
        if match:
            normalized = f"https://www.youtube.com/watch?v={match.group(1)}"

    existing = await db.materials.find_one(
        {
            "collectionId": collection_id,
            "source._originalUrl": {"$regex": f"^{url.strip().rstrip('/')}$", "$options": "i"},
        },
        {"materialId": 1},
    )

    return existing["materialId"] if existing else None
