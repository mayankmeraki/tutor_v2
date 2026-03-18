"""Transcription service — cascade: YouTube captions → Deepgram fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from app.core.mongodb import get_mongo_db
from app.services.pipeline.adapters.base import Segment
from app.services.pipeline.adapters.transcription_adapters import (
    DeepgramAdapter,
    YouTubeCaptionsAdapter,
)
from app.services.pipeline.extractors.youtube import get_audio_stream_url

log = logging.getLogger(__name__)


@dataclass
class TranscriptResult:
    segments: list[Segment]
    source: str  # "youtube_captions" | "deepgram"
    full_text: str = ""
    duration: float = 0.0


async def transcribe_material(
    source_type: str,
    source_url: str,
    material_id: str,
    collection_id: str,
) -> TranscriptResult:
    """Produce timestamped transcript segments for a video material.

    Strategy cascade:
    1. YouTube captions (free, fast)
    2. Deepgram (paid, accurate fallback)
    """
    segments: list[Segment] = []
    source = "unknown"

    # Strategy 1: YouTube captions
    if source_type == "youtube_video":
        try:
            adapter = YouTubeCaptionsAdapter()
            segments = await adapter.transcribe(source_url)
            source = "youtube_captions"
            log.info("Transcribed %s via YouTube captions: %d segments", material_id, len(segments))
        except Exception as e:
            log.info("YouTube captions unavailable for %s: %s — trying Deepgram", material_id, e)

    # Strategy 2: Deepgram
    if not segments:
        try:
            audio_url = await get_audio_stream_url(source_url)
            adapter = DeepgramAdapter()
            segments = await adapter.transcribe(audio_url)
            source = "deepgram"
            log.info("Transcribed %s via Deepgram: %d segments", material_id, len(segments))
        except Exception as e:
            log.error("Deepgram transcription failed for %s: %s", material_id, e)
            raise

    # Build full text
    full_text = " ".join(s.text for s in segments)
    duration = segments[-1].end if segments else 0.0

    result = TranscriptResult(
        segments=segments,
        source=source,
        full_text=full_text,
        duration=duration,
    )

    # Store in MongoDB
    await _store_transcript(material_id, collection_id, result)

    return result


async def _store_transcript(
    material_id: str,
    collection_id: str,
    result: TranscriptResult,
) -> None:
    """Store transcript in MongoDB with GCS backup path."""
    db = get_mongo_db()

    doc = {
        "materialId": material_id,
        "collectionId": collection_id,
        "source": result.source,
        "language": "en",
        "duration": result.duration,
        "segments": [
            {
                "text": s.text,
                "start": s.start,
                "end": s.end,
                "speaker": s.speaker,
                "confidence": s.confidence,
            }
            for s in result.segments
        ],
        "fullText": result.full_text,
        "gcsPath": f"{collection_id}/transcripts/{material_id}.json",
        "createdAt": datetime.utcnow(),
    }

    await db.transcripts.replace_one(
        {"materialId": material_id},
        doc,
        upsert=True,
    )


async def get_transcript(material_id: str) -> TranscriptResult | None:
    """Load transcript from MongoDB."""
    db = get_mongo_db()
    doc = await db.transcripts.find_one({"materialId": material_id})
    if not doc:
        return None

    segments = [
        Segment(
            text=s["text"],
            start=s["start"],
            end=s["end"],
            speaker=s.get("speaker"),
            confidence=s.get("confidence", 1.0),
        )
        for s in doc.get("segments", [])
    ]

    return TranscriptResult(
        segments=segments,
        source=doc.get("source", "unknown"),
        full_text=doc.get("fullText", ""),
        duration=doc.get("duration", 0.0),
    )
