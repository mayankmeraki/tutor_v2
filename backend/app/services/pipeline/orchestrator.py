"""Pipeline orchestrator — coordinates the 9-step processing pipeline.

Steps:
  0. VALIDATE — Pre-flight checks (format, size, educational relevance)
  1. EXTRACT — Get raw content from source
  2. TRANSCRIBE — Speech to text (video only)
  3. FRAME EXTRACT — Keyframes from video
  4. CLASSIFY — Material type + subject detection
  4b. QUALITY GATE — Reject low-quality / non-educational material
  5. CHUNK — Semantic section splitting
  6. ENRICH — Per-chunk concept/formula extraction
  7. EXERCISES — Problem extraction
  8. MERGE INDEXES — Incremental cross-material organization
  9. SEQUENCE — Flow map generation

Material becomes "ready" after step 6. Steps 7-9 run in background.
"""

from __future__ import annotations

import asyncio
import logging
import re
import traceback
import uuid
from datetime import datetime

from app.core.mongodb import get_mongo_db
from app.services.pipeline.adapters.anthropic_llm import AnthropicLLMAdapter
from app.services.pipeline.adapters.base import PipelineAdapters
from app.services.pipeline.adapters.claude_vision import ClaudeVisionClassifier, ClaudeVisionOCR
from app.services.pipeline.adapters.gcs_storage import GCSStorageAdapter
from app.services.pipeline.adapters.transcription_adapters import YouTubeCaptionsAdapter
from app.services.pipeline.extractors.frame_classifier import ClassifiedFrame, classify_and_filter_frames
from app.services.pipeline.extractors.frame_extractor import extract_frames_ffmpeg
from app.services.pipeline.extractors.pdf import extract_pdf
from app.services.pipeline.extractors.text import extract_text
from app.services.pipeline.extractors.youtube import PlaylistResult, extract_youtube
from app.services.pipeline.processors.chunker import chunk_material
from app.services.pipeline.processors.classifier import Classification, classify_material
from app.services.pipeline.processors.enricher import enrich_all_chunks
from app.services.pipeline.processors.exercise_extractor import extract_exercises, store_exercises
from app.services.pipeline.processors.index_builder import build_indexes, merge_into_indexes
from app.services.pipeline.processors.sequencer import generate_flow_map
from app.services.pipeline.transcribers.transcription import transcribe_material

log = logging.getLogger(__name__)

# Maximum video duration we'll process (4 hours in seconds)
MAX_VIDEO_DURATION_SECONDS = 4 * 60 * 60


def _get_adapters() -> PipelineAdapters:
    """Create pipeline adapter instances."""
    llm = AnthropicLLMAdapter()
    return PipelineAdapters(
        llm=llm,
        vision=ClaudeVisionClassifier(llm),
        ocr=ClaudeVisionOCR(llm),
        storage=GCSStorageAdapter(),
        transcription=YouTubeCaptionsAdapter(),
    )


async def _update_material_status(
    material_id: str, status: str, error: str | None = None, reject_reason: str | None = None,
) -> None:
    """Update material processing status in MongoDB."""
    db = get_mongo_db()
    update: dict = {"status": status, "updatedAt": datetime.utcnow()}
    if error:
        update["errorDetail"] = error
    if reject_reason:
        update["rejectReason"] = reject_reason
    if status == "ready":
        update["readyAt"] = datetime.utcnow()
    await db.materials.update_one({"materialId": material_id}, {"$set": update})


async def _update_collection_progress(collection_id: str) -> None:
    """Update collection processing progress. Counts 'rejected' as done."""
    db = get_mongo_db()
    total = await db.materials.count_documents({"collectionId": collection_id})
    ready = await db.materials.count_documents({"collectionId": collection_id, "status": "ready"})
    rejected = await db.materials.count_documents({"collectionId": collection_id, "status": "rejected"})
    errors = await db.materials.count_documents({"collectionId": collection_id, "status": "error"})

    done = ready + rejected + errors
    status = "ready" if done == total else ("partial" if ready > 0 else "processing")
    if errors == total:
        status = "error"

    await db.content_collections.update_one(
        {"collectionId": collection_id},
        {"$set": {
            "status": status,
            "processingProgress.processedMaterials": ready,
            "processingProgress.rejectedMaterials": rejected,
            "processingProgress.totalMaterials": total,
            "updatedAt": datetime.utcnow(),
        }},
    )


# ── Validation & Quality Gates ──────────────────────────────────────────────

def validate_material(material: dict) -> tuple[bool, str]:
    """Pre-flight validation BEFORE extraction. Returns (is_valid, reason)."""
    source_type = material["source"]["type"]
    source_url = material["source"].get("_originalUrl", "")

    if source_type == "youtube_video":
        # URL must look like a YouTube link
        if not re.search(r"(youtube\.com|youtu\.be)", source_url):
            return False, "URL does not appear to be a YouTube link"

    elif source_type == "pdf":
        file_bytes = material["source"].get("_fileBytes")
        gcs_path = material["source"].get("_gcsPath", "")
        if not file_bytes and not gcs_path:
            return False, "No PDF file data or GCS path provided"
        # If we have bytes, do a quick PyMuPDF check
        if file_bytes:
            try:
                import fitz
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                if doc.is_encrypted:
                    return False, "PDF is encrypted"
                if doc.page_count == 0:
                    return False, "PDF has 0 pages"
                # Check for extractable text
                total_text = ""
                for page_num in range(min(doc.page_count, 3)):
                    total_text += doc[page_num].get_text()
                if len(total_text.strip()) < 100:
                    return False, f"PDF has very little extractable text ({len(total_text.strip())} chars in first 3 pages)"
                doc.close()
            except Exception as e:
                return False, f"PDF cannot be opened: {e}"

    elif source_type == "text":
        raw_text = material["source"].get("_rawText", "")
        if len(raw_text.strip()) < 50:
            return False, f"Text too short ({len(raw_text.strip())} chars, minimum 50)"
        # Check alphanumeric ratio to catch binary/gibberish
        alnum_count = sum(1 for c in raw_text if c.isalnum() or c.isspace())
        ratio = alnum_count / max(len(raw_text), 1)
        if ratio < 0.5:
            return False, f"Text appears to be binary or gibberish ({ratio:.0%} alphanumeric)"

    return True, ""


def quality_gate(
    classification: Classification,
    full_text: str,
    source_type: str,
    duration: float | None = None,
) -> tuple[bool, str]:
    """Post-classification quality gate. Returns (passes, reason)."""
    # Classification confidence too low
    if classification.confidence < 0.4:
        return False, f"Classification confidence too low ({classification.confidence:.2f})"

    # Too little extractable content
    if len(full_text.strip()) < 200:
        return False, f"Extracted text too short ({len(full_text.strip())} chars, minimum 200)"

    # Non-educational material
    if classification.educational_quality == "non_educational":
        return False, "Material classified as non-educational"

    # YouTube duration check
    if source_type == "youtube_video" and duration and duration > MAX_VIDEO_DURATION_SECONDS:
        hours = duration / 3600
        return False, f"Video too long ({hours:.1f} hours, maximum 4 hours)"

    return True, ""


# ── Main Pipeline ────────────────────────────────────────────────────────────

async def process_material(material_id: str, collection_id: str) -> None:
    """Run the full processing pipeline for a single material.

    This is designed to be called as a background task via asyncio.create_task().
    """
    db = get_mongo_db()
    adapters = _get_adapters()

    material = await db.materials.find_one({"materialId": material_id})
    if not material:
        log.error("Material %s not found", material_id)
        return

    source_type = material["source"]["type"]
    source_url = material["source"].get("_originalUrl", "")

    try:
        # ── Step 0: VALIDATE ──────────────────────────────────────────
        is_valid, reject_reason = validate_material(material)
        if not is_valid:
            log.warning("Material %s rejected: %s", material_id, reject_reason)
            await _update_material_status(material_id, "rejected", reject_reason=reject_reason)
            await _update_collection_progress(collection_id)
            return

        # ── Step 1: EXTRACT ──────────────────────────────────────────
        await _update_material_status(material_id, "extracting")
        full_text = ""
        title = material.get("title", "Untitled")
        duration: float | None = None

        if source_type == "youtube_video":
            result = await extract_youtube(source_url)
            if isinstance(result, PlaylistResult):
                # Create separate materials for each video in playlist
                for video in result.videos:
                    await create_material(collection_id, "youtube_video", url=video["url"], title=video.get("title"))
                await _update_material_status(material_id, "ready")
                return

            title = result.title or title
            duration = result.duration
            await db.materials.update_one(
                {"materialId": material_id},
                {"$set": {
                    "title": title,
                    "duration": result.duration,
                    "thumbnailUrl": result.thumbnail_url,
                }},
            )

            # Duration check after extraction
            if duration and duration > MAX_VIDEO_DURATION_SECONDS:
                hours = duration / 3600
                reason = f"Video too long ({hours:.1f} hours, maximum 4 hours)"
                log.warning("Material %s rejected: %s", material_id, reason)
                await _update_material_status(material_id, "rejected", reject_reason=reason)
                await _update_collection_progress(collection_id)
                return

        elif source_type == "pdf":
            file_bytes = material["source"].get("_fileBytes")
            if not file_bytes:
                gcs_path = material["source"].get("_gcsPath", "")
                file_bytes = await adapters.storage.download(gcs_path)

            pdf_result = await extract_pdf(
                file_bytes, material_id, collection_id, adapters.storage,
                original_filename=material["source"].get("_originalFilename", "doc.pdf"),
            )
            title = pdf_result.title or title
            full_text = pdf_result.full_text
            await db.materials.update_one(
                {"materialId": material_id},
                {"$set": {"title": title, "pageCount": pdf_result.page_count}},
            )

        elif source_type == "text":
            raw_text = material["source"].get("_rawText", "")
            text_result = await extract_text(raw_text, title)
            full_text = text_result.text
            title = text_result.title or title

        # ── Step 2: TRANSCRIBE (video only) ──────────────────────────
        transcript_segments = None
        if source_type == "youtube_video":
            await _update_material_status(material_id, "transcribing")
            transcript_result = await transcribe_material(
                source_type, source_url, material_id, collection_id,
            )
            transcript_segments = transcript_result.segments
            full_text = transcript_result.full_text

        # ── Step 3: FRAME EXTRACT (video only) ───────────────────────
        classified_frames: list[ClassifiedFrame] = []
        if source_type == "youtube_video":
            await _update_material_status(material_id, "framing")
            raw_frames = await extract_frames_ffmpeg(source_url, material_id)
            if raw_frames:
                classified_frames = await classify_and_filter_frames(raw_frames, adapters)
                # Store frame metadata
                for frame in classified_frames:
                    frame.material_id = material_id
                    frame.collection_id = collection_id
                    frame.frame_id = str(uuid.uuid4())
                    # Upload to GCS
                    if frame.image_bytes:
                        gcs_path = f"{collection_id}/frames/{material_id}/frame_{frame.timestamp:06.0f}.jpg"
                        frame.gcs_url = await adapters.storage.upload(frame.image_bytes, gcs_path, "image/jpeg")
                        frame.gcs_path = gcs_path
                    # Store in MongoDB
                    await db.extracted_frames.insert_one({
                        "frameId": frame.frame_id,
                        "materialId": material_id,
                        "collectionId": collection_id,
                        "timestamp": frame.timestamp,
                        "displayTime": frame.display_time,
                        "classification": frame.classification,
                        "contentDescription": frame.content_description,
                        "ocr": {
                            "fullText": frame.ocr.text if frame.ocr else "",
                            "elements": [
                                {"type": e.type, "text": e.text, "confidence": e.confidence}
                                for e in (frame.ocr.elements if frame.ocr else [])
                            ],
                        },
                        "gcsPath": frame.gcs_path,
                        "gcsUrl": frame.gcs_url,
                        "quality": frame.quality,
                        "isKeyFrame": True,
                    })

        # ── Step 4: CLASSIFY ─────────────────────────────────────────
        await _update_material_status(material_id, "classifying")
        classification = await classify_material(full_text, adapters.llm)
        await db.materials.update_one(
            {"materialId": material_id},
            {"$set": {
                "classification": {
                    "type": classification.type,
                    "subjects": classification.subjects,
                    "difficulty": classification.difficulty,
                    "hasExercises": classification.has_exercises,
                    "isStructured": classification.is_structured,
                    "language": classification.language,
                    "confidence": classification.confidence,
                    "educationalQuality": classification.educational_quality,
                },
                "title": title if title != "Untitled" else (classification.title_suggestion or title),
            }},
        )

        # ── Step 4b: QUALITY GATE ────────────────────────────────────
        passes, gate_reason = quality_gate(classification, full_text, source_type, duration)
        if not passes:
            log.warning("Material %s rejected at quality gate: %s", material_id, gate_reason)
            await _update_material_status(material_id, "rejected", reject_reason=gate_reason)
            await _update_collection_progress(collection_id)
            return

        # ── Step 5: CHUNK ────────────────────────────────────────────
        await _update_material_status(material_id, "chunking")
        raw_chunks = await chunk_material(
            source_type=source_type,
            classification_type=classification.type,
            is_structured=classification.is_structured,
            full_text=full_text,
            transcript_segments=transcript_segments,
            llm=adapters.llm,
        )

        # ── Step 6: ENRICH ───────────────────────────────────────────
        await _update_material_status(material_id, "enriching")
        enriched_chunks = await enrich_all_chunks(
            raw_chunks, source_type, classified_frames, adapters.llm,
        )

        # Store chunks in MongoDB
        for chunk in enriched_chunks:
            chunk.chunk_id = str(uuid.uuid4())
            chunk.material_id = material_id
            chunk.collection_id = collection_id
            await db.chunks.insert_one({
                "chunkId": chunk.chunk_id,
                "materialId": material_id,
                "collectionId": collection_id,
                "index": chunk.index,
                "title": chunk.title,
                "anchor": chunk.anchor,
                "content": chunk.content,
                "segments": chunk.segments,
                "linkedFrameIds": chunk.linked_frame_ids,
                "media": chunk.media,
            })

        # Update chunk count
        await db.materials.update_one(
            {"materialId": material_id},
            {"$set": {"chunkCount": len(enriched_chunks)}},
        )

        # ── Material is now READY ────────────────────────────────────
        await _update_material_status(material_id, "ready")
        await _update_collection_progress(collection_id)
        log.info("Material %s ready: %d chunks", material_id, len(enriched_chunks))

        # ── Step 7: EXERCISES (background) ───────────────────────────
        exercises = await extract_exercises(
            enriched_chunks, classified_frames, material_id, collection_id, adapters.llm,
        )
        if exercises:
            await store_exercises(exercises)

        # ── Step 8-9: INCREMENTAL INDEX MERGE + SEQUENCE ─────────────
        # Merge this material's data into collection indexes immediately
        # (no waiting for all materials — incremental)
        await merge_into_indexes(collection_id, material_id, adapters.llm)
        log.info("Indexes merged for material %s in collection %s", material_id, collection_id)

    except Exception as e:
        log.error("Pipeline error for material %s: %s\n%s", material_id, e, traceback.format_exc())
        await _update_material_status(material_id, "error", str(e)[:500])
        await _update_collection_progress(collection_id)


async def create_collection(user_id: str, title: str, collection_type: str = "byo") -> str:
    """Create a new content collection."""
    db = get_mongo_db()
    collection_id = str(uuid.uuid4())

    await db.content_collections.insert_one({
        "collectionId": collection_id,
        "userId": user_id,
        "type": collection_type,
        "title": title,
        "status": "processing",
        "processingProgress": {
            "totalMaterials": 0,
            "processedMaterials": 0,
            "rejectedMaterials": 0,
            "currentStep": "created",
            "errors": [],
        },
        "subjects": [],
        "stats": {"totalMaterials": 0, "totalChunks": 0, "totalConcepts": 0, "totalExercises": 0},
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    })

    return collection_id


async def create_material(
    collection_id: str,
    source_type: str,
    url: str | None = None,
    title: str = "Untitled",
    file_bytes: bytes | None = None,
    original_filename: str | None = None,
    raw_text: str | None = None,
) -> str:
    """Create a material document and kick off processing."""
    db = get_mongo_db()
    material_id = str(uuid.uuid4())

    source: dict = {"type": source_type}
    if url:
        source["_originalUrl"] = url
    if original_filename:
        source["_originalFilename"] = original_filename
    if file_bytes:
        # Upload original to GCS
        adapters = _get_adapters()
        ext = (original_filename or "file").rsplit(".", 1)[-1]
        gcs_path = f"{collection_id}/originals/{material_id}.{ext}"
        await adapters.storage.upload(file_bytes, gcs_path)
        source["_gcsPath"] = gcs_path
    if raw_text:
        source["_rawText"] = raw_text

    await db.materials.insert_one({
        "materialId": material_id,
        "collectionId": collection_id,
        "source": source,
        "status": "uploaded",
        "errorDetail": None,
        "rejectReason": None,
        "classification": None,
        "title": title,
        "chunkCount": 0,
        "duration": None,
        "pageCount": None,
        "thumbnailUrl": None,
        "addedAt": datetime.utcnow(),
        "readyAt": None,
    })

    # Update collection material count
    await db.content_collections.update_one(
        {"collectionId": collection_id},
        {"$inc": {"processingProgress.totalMaterials": 1}},
    )

    # Start processing in background
    asyncio.create_task(process_material(material_id, collection_id))

    return material_id
