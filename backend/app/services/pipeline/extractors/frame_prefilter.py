"""CPU-only frame pre-filtering to reduce vision API calls.

Runs 3 stages before any LLM/vision calls:
  1. Perceptual hash dedup — drop near-identical adjacent frames
  2. Histogram blank detection — drop mostly-black/white frames
  3. Edge density + skin heuristic — drop obvious talking-head frames
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from io import BytesIO

from PIL import Image

from app.services.pipeline.extractors.frame_extractor import FramePath

log = logging.getLogger(__name__)


@dataclass
class PreFilterStats:
    input_count: int = 0
    after_dedup: int = 0
    after_blank: int = 0
    after_skin: int = 0
    dropped_dedup: int = 0
    dropped_blank: int = 0
    dropped_skin: int = 0


def _to_pil(frame: FramePath) -> Image.Image | None:
    """Convert frame bytes to PIL Image, return None on failure."""
    if not frame.image_bytes:
        return None
    try:
        return Image.open(BytesIO(frame.image_bytes))
    except Exception:
        return None


# ── Stage 1: Perceptual hash dedup ─────────────────────────────────────────

def _phash(img: Image.Image, hash_size: int = 8) -> int:
    """Compute a 64-bit perceptual hash (DCT-free approximation using resize)."""
    # Resize to (hash_size+1) x hash_size grayscale
    small = img.convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS)
    pixels = list(small.getdata())
    width = hash_size + 1

    # Compare adjacent horizontal pixels → 64-bit hash
    bit = 0
    hash_val = 0
    for y in range(hash_size):
        for x in range(hash_size):
            idx = y * width + x
            if pixels[idx] < pixels[idx + 1]:
                hash_val |= (1 << bit)
            bit += 1
    return hash_val


def _hamming_distance(h1: int, h2: int) -> int:
    return bin(h1 ^ h2).count("1")


def _dedup_by_phash(
    frames: list[FramePath],
    images: dict[int, Image.Image],
    max_hamming: int = 5,
) -> list[FramePath]:
    """Drop adjacent frames with >92% perceptual similarity (hamming <= 5 on 64-bit hash)."""
    if not frames:
        return []

    result = [frames[0]]
    prev_hash = _phash(images[0]) if 0 in images else 0

    for i, frame in enumerate(frames[1:], start=1):
        if i not in images:
            result.append(frame)
            continue
        h = _phash(images[i])
        if _hamming_distance(h, prev_hash) > max_hamming:
            result.append(frame)
        prev_hash = h

    return result


# ── Stage 2: Histogram blank detection ─────────────────────────────────────

def _is_mostly_blank(img: Image.Image, dark_threshold: float = 0.85, bright_threshold: float = 0.85) -> bool:
    """Check if frame is mostly black (>85% dark) or mostly white (>85% bright)."""
    gray = img.convert("L")
    pixels = list(gray.getdata())
    total = len(pixels)
    if total == 0:
        return True

    dark_count = sum(1 for p in pixels if p < 30)
    bright_count = sum(1 for p in pixels if p > 225)

    return (dark_count / total) > dark_threshold or (bright_count / total) > bright_threshold


def _remove_blanks(
    frames: list[FramePath],
    images: dict[int, Image.Image],
) -> list[FramePath]:
    """Drop mostly-black or mostly-white frames."""
    result = []
    # Build a lookup from frame identity to index in the original indexed images
    frame_to_img_idx = {}
    for i, f in enumerate(frames):
        # Find this frame's index in the images dict by matching the object
        for idx, img in images.items():
            if _frame_matches_image_index(f, idx, images, frames):
                frame_to_img_idx[i] = idx
                break

    # Simpler approach: re-index images for current frame list
    for i, frame in enumerate(frames):
        img = _to_pil(frame)
        if img is None:
            result.append(frame)
            continue
        if not _is_mostly_blank(img):
            result.append(frame)

    return result


def _frame_matches_image_index(f, idx, images, frames):
    """Helper — not actually needed, simplified approach above."""
    return False


# ── Stage 3: Edge density + skin-tone heuristic ───────────────────────────

def _edge_density(img: Image.Image) -> float:
    """Compute edge density using simple Laplacian-like filter via Pillow."""
    from PIL import ImageFilter

    gray = img.convert("L").resize((160, 120), Image.LANCZOS)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    pixels = list(edges.getdata())
    if not pixels:
        return 0.0
    # Fraction of pixels with significant edge response
    return sum(1 for p in pixels if p > 30) / len(pixels)


def _warm_color_ratio(img: Image.Image) -> float:
    """Estimate fraction of pixels with skin-like warm tones (HSV heuristic via RGB)."""
    small = img.convert("RGB").resize((80, 60), Image.LANCZOS)
    pixels = list(small.getdata())
    if not pixels:
        return 0.0

    warm_count = 0
    for r, g, b in pixels:
        # Skin-tone heuristic: R > 95, G > 40, B > 20, R > G, R > B, |R-G| > 15
        if r > 95 and g > 40 and b > 20 and r > g and r > b and abs(r - g) > 15:
            warm_count += 1

    return warm_count / len(pixels)


def _is_likely_talking_head(img: Image.Image) -> bool:
    """Conservative talking-head detection: low edges + dominant warm colors."""
    edge_d = _edge_density(img)
    warm_r = _warm_color_ratio(img)
    # Only flag as talking head if BOTH conditions met (conservative)
    return edge_d < 0.08 and warm_r > 0.35


def _remove_talking_heads(frames: list[FramePath]) -> list[FramePath]:
    """Drop frames that are likely just a talking head (no content)."""
    result = []
    for frame in frames:
        img = _to_pil(frame)
        if img is None:
            result.append(frame)
            continue
        if not _is_likely_talking_head(img):
            result.append(frame)

    return result


# ── Public API ──────────────────────────────────────────────────────────────

def pre_filter_frames(frames: list[FramePath]) -> tuple[list[FramePath], PreFilterStats]:
    """Run 3-stage CPU-only pre-filtering. Returns (filtered_frames, stats).

    Expected reduction: ~70-80% of frames dropped (300 → 60-80).
    """
    stats = PreFilterStats(input_count=len(frames))

    if not frames:
        return frames, stats

    # Pre-compute PIL images for phash stage (reused across stages)
    images: dict[int, Image.Image] = {}
    for i, frame in enumerate(frames):
        img = _to_pil(frame)
        if img is not None:
            images[i] = img

    # Stage 1: Perceptual hash dedup
    after_dedup = _dedup_by_phash(frames, images)
    stats.after_dedup = len(after_dedup)
    stats.dropped_dedup = len(frames) - len(after_dedup)

    # Stage 2: Blank detection
    after_blank = _remove_blanks(after_dedup, images)
    stats.after_blank = len(after_blank)
    stats.dropped_blank = len(after_dedup) - len(after_blank)

    # Stage 3: Talking head detection
    after_skin = _remove_talking_heads(after_blank)
    stats.after_skin = len(after_skin)
    stats.dropped_skin = len(after_blank) - len(after_skin)

    log.info(
        "Frame pre-filter: %d → %d (dedup -%d, blank -%d, talking_head -%d)",
        stats.input_count, stats.after_skin,
        stats.dropped_dedup, stats.dropped_blank, stats.dropped_skin,
    )

    return after_skin, stats
