"""Frame classification using vision model and OCR extraction."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.pipeline.adapters.base import (
    FrameClassification,
    OCRAdapter,
    OcrResult,
    PipelineAdapters,
    VisionClassifierAdapter,
)
from app.services.pipeline.extractors.frame_extractor import FramePath
from app.services.pipeline.extractors.frame_prefilter import pre_filter_frames

log = logging.getLogger(__name__)

# Classifications considered "content-rich" (kept after filtering)
CONTENT_CLASSIFICATIONS = {"board", "equation", "diagram", "slide", "chart", "table"}

# Classifications discarded as noise
NOISE_CLASSIFICATIONS = {"talking_head", "transition", "other"}


@dataclass
class ClassifiedFrame:
    frame_id: str = ""
    material_id: str = ""
    collection_id: str = ""
    timestamp: float = 0.0
    display_time: str = ""
    classification: str = ""
    content_description: str = ""
    image_bytes: bytes | None = None
    ocr: OcrResult | None = None
    transcript_context: str = ""
    transcript_start: float = 0.0
    transcript_end: float = 0.0
    gcs_path: str = ""
    gcs_url: str = ""
    quality: str = "medium"
    is_key_frame: bool = True


def _format_time(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


async def classify_and_filter_frames(
    frames: list[FramePath],
    adapters: PipelineAdapters,
    batch_size: int = 5,
) -> list[ClassifiedFrame]:
    """Classify frames, filter noise, deduplicate, and run OCR on content frames."""

    if not frames:
        return []

    # Step 0: CPU-only pre-filtering (dedup, blank, talking-head removal)
    filtered_frames, pf_stats = pre_filter_frames(frames)
    log.info(
        "Pre-filter: %d → %d frames before vision API",
        pf_stats.input_count, len(filtered_frames),
    )

    if not filtered_frames:
        return []

    # Step 1: Classify in batches — track original indices to avoid mismatch
    classifications_by_index: dict[int, FrameClassification] = {}
    for i in range(0, len(filtered_frames), batch_size):
        batch = filtered_frames[i:i + batch_size]
        # Track which original indices have image_bytes
        batch_with_bytes = [(j, f) for j, f in enumerate(batch, start=i) if f.image_bytes]
        if not batch_with_bytes:
            continue
        batch_indices, batch_frames = zip(*batch_with_bytes)
        batch_bytes = [f.image_bytes for f in batch_frames]
        classifications = await adapters.vision.classify_frames(batch_bytes)
        # Map classifications back to correct frame indices
        for idx, clf in zip(batch_indices, classifications):
            classifications_by_index[idx] = clf

    # Step 2: Filter — keep only content-rich frames
    content_frames: list[ClassifiedFrame] = []
    for i, frame in enumerate(filtered_frames):
        clf = classifications_by_index.get(i)
        if clf is None:
            continue
        if clf.classification not in CONTENT_CLASSIFICATIONS:
            continue

        content_frames.append(ClassifiedFrame(
            timestamp=frame.timestamp,
            display_time=_format_time(frame.timestamp),
            classification=clf.classification,
            content_description=clf.content_description,
            image_bytes=frame.image_bytes,
        ))

    # Step 3: Deduplicate — remove frames within 5 seconds of each other
    deduped = _deduplicate_frames(content_frames, threshold_seconds=5.0)

    # Step 4: OCR on content frames
    for frame in deduped:
        if frame.image_bytes:
            try:
                frame.ocr = await adapters.ocr.extract_text(frame.image_bytes)
                # Mark quality based on OCR confidence
                if frame.ocr.confidence >= 0.8:
                    frame.quality = "high"
                elif frame.ocr.confidence >= 0.5:
                    frame.quality = "medium"
                else:
                    frame.quality = "low"
            except Exception as e:
                log.warning("OCR failed for frame at %.1fs: %s", frame.timestamp, e)

    log.info(
        "Frame classification: %d input → %d pre-filtered → %d content → %d deduped",
        len(frames), len(filtered_frames), len(content_frames), len(deduped),
    )
    return deduped


def _deduplicate_frames(frames: list[ClassifiedFrame], threshold_seconds: float = 5.0) -> list[ClassifiedFrame]:
    """Remove near-duplicate frames (close in time with same classification)."""
    if not frames:
        return []

    frames.sort(key=lambda f: f.timestamp)
    result = [frames[0]]

    for frame in frames[1:]:
        last = result[-1]
        # Skip if same classification and within threshold
        if (frame.classification == last.classification
                and abs(frame.timestamp - last.timestamp) < threshold_seconds):
            continue
        result.append(frame)

    return result
