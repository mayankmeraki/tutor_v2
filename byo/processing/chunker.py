"""Structure-aware parent-child chunker.

Produces TWO outputs per resource (small-to-big pattern):

  - Parent chunks (`Chunk`): ~800 tok, returned to the LLM.
    NOT embedded. Stored in `byo_chunks`.
  - Child segments (`Segment`): ~200 tok, embedded for retrieval.
    Each segment's `parent_chunk_id` resolves back to its parent.
    Stored in `byo_segments`.

Strategy:
  1. Split markdown by headers into sections.
  2. Walk paragraphs within each section, accreting into a parent until it
     hits the parent target (~800 tok). Headings, code fences, and tables
     stay atomic — they NEVER straddle a parent boundary.
  3. For each parent, walk its paragraphs again and split into children at
     paragraph boundaries (150-300 tok target), again keeping atomic blocks
     whole. Children inherit the parent's anchor, modality, and retrieval
     mode (small-to-big: the child matches, the parent is served).
  4. Detect page / timestamp / section anchors per parent and propagate.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from byo.shared.models import ChunkLevel, Modality, RetrievalMode

log = logging.getLogger(__name__)

# Parent target: what the LLM reads.
PARENT_TARGET = 800
PARENT_MAX = 1000
PARENT_MIN = 200  # merge stragglers under this into the previous parent

# Child target: what gets embedded.
CHILD_TARGET = 200
CHILD_MAX = 300
CHILD_MIN = 80  # absorb tiny children into the previous one

# Token ~= chars / 4 (matches processors.base._count_tokens; keep consistent).
def _tok(s: str) -> int:
    return len(s) // 4


# ── Modality + retrieval-mode detection ────────────────────────────────

def _detect_modality(mime_type: str, resource_meta: dict[str, Any]) -> Modality:
    """Pick a Modality from the processor's output.

    The `resource_meta` here is `ProcessResult.meta` — the flexible dict the
    processor populated during extract. Fall back to mime_type inspection
    when the meta is sparse.
    """
    mt = (mime_type or "").lower()
    source = resource_meta.get("source", "")

    # PDFs — digital vs scanned heuristic: PyMuPDF flags low_text_pages; the
    # marker-pdf path doesn't (assume digital). If most pages were image-only,
    # treat as scanned so retrieval uses visual_description mode.
    if mt == "application/pdf":
        low_text = resource_meta.get("low_text_pages", 0) or 0
        pages = resource_meta.get("pages", 0) or 0
        if pages and low_text and low_text >= max(1, pages // 2):
            return Modality.PDF_SCANNED
        return Modality.PDF_DIGITAL

    if mt.startswith("video/") or source in ("youtube_captions", "elevenlabs_stt") or resource_meta.get("video_id"):
        # STT of an audio-only file still lands here; we don't have a
        # reliable signal to separate AUDIO from VIDEO at this layer, and
        # the retrieval behavior (TEMPORAL) is identical. Keep as VIDEO.
        return Modality.VIDEO

    if mt.startswith("audio/"):
        return Modality.AUDIO

    if mt.startswith("image/"):
        return Modality.IMAGE

    if mt == "text/html" or resource_meta.get("source_url"):
        return Modality.WEBPAGE

    return Modality.TEXT


def _detect_retrieval_mode(modality: Modality) -> RetrievalMode:
    """Default retrieval mode per modality.

    Kept simple — later we may branch on `meta` (e.g. code fence density
    inside a TEXT → SYMBOLIC) but for now the modality carries it.
    """
    if modality in (Modality.VIDEO, Modality.AUDIO):
        return RetrievalMode.TEMPORAL
    if modality in (Modality.IMAGE, Modality.PDF_SCANNED, Modality.HANDWRITTEN):
        # The extracted content is an LLM description of the visual; skip
        # question generation and embed the description directly.
        return RetrievalMode.VISUAL_DESCRIPTION
    if modality == Modality.CODE:
        return RetrievalMode.SYMBOLIC
    # PDF_DIGITAL, WEBPAGE, TEXT, SLIDES — benefit from exact match on
    # terms + semantic match on paraphrases.
    return RetrievalMode.EXACT_PLUS_SEMANTIC


def _extract_title(content: str, heading: str | None = None, index: int = 0) -> str:
    """Extract a short title from chunk content for TOC display."""
    if heading:
        return heading.strip()[:120]
    lines = [l.strip() for l in content.split("\n") if l.strip() and not l.strip().startswith("<!--")]
    if not lines:
        return f"Section {index + 1}"
    first = lines[0].lstrip("#").strip()
    # Skip image descriptions and metadata lines
    if first.startswith("[Image:") or first.startswith("[Decorative"):
        first = lines[1].lstrip("#").strip() if len(lines) > 1 else first
    return first[:120] if first else f"Section {index + 1}"


# ── Public API ─────────────────────────────────────────────────────────

async def chunk_markdown(
    markdown: str,
    resource_id: str,
    collection_id: str,
    resource_meta: dict[str, Any] | None = None,
    *,
    user_id: str = "",
    mime_type: str = "",
    use_structure_llm: bool = True,
) -> tuple[list[dict], list[dict]]:
    """Split markdown into parents + children.

    Returns `(parents, segments)` as plain dicts ready for the indexer:

      parents: chunk_id, collection_id, resource_id, user_id, index, level,
               content, tokens, anchor, modality, retrieval_mode,
               labels, topics, attachments.
      segments: segment_id, parent_chunk_id, collection_id, resource_id,
                user_id, index, content, tokens, questions, anchor,
                modality, retrieval_mode, topics, embedding.

    Two chunking strategies, selected by an LLM classifier:
      - "prose" → paragraph-granular packing (current default).
      - "discrete_items"/"mixed" → LLM-detected semantic boundaries, one
        parent per unit (one segment per parent for small units).

    `use_structure_llm=False` disables the LLM call (tests, offline mode);
    in that case we always use the paragraph-granular path.

    `resource_meta` is the processor's `ProcessResult.meta` — used to
    detect modality + retrieval_mode. Kept optional so tests can call
    without a processor.
    """
    if not markdown.strip():
        return [], []

    resource_meta = resource_meta or {}
    modality = _detect_modality(mime_type, resource_meta)
    retrieval_mode = _detect_retrieval_mode(modality)

    # Ask the LLM to classify structure — ONE cheap call. If it says
    # "discrete_items" or "mixed", the boundary-driven chunker runs next.
    # On any LLM failure, we silently fall through to the prose path.
    if use_structure_llm:
        from byo.processing.structure import classify_structure
        try:
            struct = await classify_structure(markdown)
        except Exception as e:  # noqa: BLE001
            log.warning("classify_structure raised: %s", e)
            struct = {"structure": "unknown"}

        if struct.get("structure") in ("discrete_items", "mixed"):
            log.info(
                "Chunked %s: structure=%s (hint=%r); using LLM-driven boundaries",
                resource_id[:8], struct["structure"], struct.get("unit_hint", "")[:80],
            )
            return await _chunk_by_llm_boundaries(
                markdown, resource_id, collection_id, user_id,
                modality, retrieval_mode, struct,
            )

    # 1) Header split → parent packs respecting atomic blocks.
    sections = _split_by_headers(markdown)
    parent_packs: list[dict] = []
    for sec in sections:
        parent_packs.extend(_pack_parents(sec))

    # 2) Merge too-small parents into the previous one.
    parent_packs = _merge_small_parents(parent_packs)

    # 3) Materialize parent dicts + segment dicts.
    parents: list[dict] = []
    segments: list[dict] = []

    for p_index, pack in enumerate(parent_packs):
        content = pack["content"].strip()
        if not content:
            continue

        page_range = _detect_page_range(content)
        timestamp_range = _detect_timestamp_range(content)

        anchor = {
            "page": page_range[0] if page_range else None,
            "page_end": page_range[1] if page_range else None,
            "start_time": timestamp_range[0] if timestamp_range else None,
            "end_time": timestamp_range[1] if timestamp_range else None,
            "section": pack.get("heading"),
        }

        parent_id = str(uuid.uuid4())
        parents.append({
            "chunk_id": parent_id,
            "collection_id": collection_id,
            "resource_id": resource_id,
            "user_id": user_id,
            "index": p_index,
            "level": ChunkLevel.PARENT.value,
            "title": _extract_title(content, pack.get("heading"), p_index),
            "content": content,
            "tokens": _tok(content),
            "anchor": anchor,
            "modality": modality.value,
            "retrieval_mode": retrieval_mode.value,
            "labels": [],
            "topics": [],
            "attachments": [],
        })

        # 4) Split this parent into child segments.
        child_packs = _pack_children(pack["paragraphs"])
        for c_index, child in enumerate(child_packs):
            c_content = child["content"].strip()
            if not c_content:
                continue
            segments.append({
                "segment_id": str(uuid.uuid4()),
                "parent_chunk_id": parent_id,
                "collection_id": collection_id,
                "resource_id": resource_id,
                "user_id": user_id,
                "index": c_index,
                "content": c_content,
                "tokens": _tok(c_content),
                "questions": [],
                "anchor": anchor,  # inherit from parent
                "modality": modality.value,
                "retrieval_mode": retrieval_mode.value,
                "topics": [],
                "embedding": None,
            })

    log.info(
        "Chunked %s: %d parents / %d segments from %d chars (modality=%s mode=%s)",
        resource_id[:8], len(parents), len(segments), len(markdown),
        modality.value, retrieval_mode.value,
    )
    return parents, segments


# ── LLM-boundary chunker (for discrete_items / mixed docs) ─────────────

async def _chunk_by_llm_boundaries(
    markdown: str,
    resource_id: str,
    collection_id: str,
    user_id: str,
    modality: Modality,
    retrieval_mode: RetrievalMode,
    struct: dict,
) -> tuple[list[dict], list[dict]]:
    """Run the LLM boundary detector over windows of the markdown; treat
    each detected unit as one parent chunk.

    For small units (< PARENT_MAX tokens) we emit one segment == the
    parent content (no further splitting). For larger units we reuse the
    paragraph-level child splitter so context is preserved.
    """
    from byo.processing.structure import (
        BOUNDARY_WINDOW,
        BOUNDARY_OVERLAP,
        detect_boundaries,
    )

    unit_hint = struct.get("unit_hint", "")
    # 1) Walk the markdown in overlapping windows, collect units.
    units: list[str] = []
    i = 0
    while i < len(markdown):
        window = markdown[i:i + BOUNDARY_WINDOW]
        try:
            offsets = await detect_boundaries(window, unit_hint=unit_hint)
        except Exception as e:  # noqa: BLE001
            log.warning("detect_boundaries raised on window @%d: %s", i, e)
            offsets = [0]

        # Convert offsets to (start, end) pairs within the window.
        bounds = sorted(set(offsets))
        if not bounds:
            bounds = [0]
        if bounds[-1] != len(window):
            bounds.append(len(window))
        for s, e in zip(bounds, bounds[1:]):
            piece = window[s:e].strip()
            if piece:
                units.append(piece)

        # Advance — leave overlap so a unit straddling the window edge
        # gets a clean cut next time.
        if i + BOUNDARY_WINDOW >= len(markdown):
            break
        i += BOUNDARY_WINDOW - BOUNDARY_OVERLAP

    # 2) Merge adjacent micro-units (< MIN_TOKENS/2) — defends against
    # an over-eager LLM that splits too finely.
    units = _merge_micro_units(units)

    # 3) Materialize parents + segments from the unit list.
    parents: list[dict] = []
    segments: list[dict] = []

    for p_index, unit in enumerate(units):
        content = unit.strip()
        if not content:
            continue

        page_range = _detect_page_range(content)
        timestamp_range = _detect_timestamp_range(content)
        anchor = {
            "page": page_range[0] if page_range else None,
            "page_end": page_range[1] if page_range else None,
            "start_time": timestamp_range[0] if timestamp_range else None,
            "end_time": timestamp_range[1] if timestamp_range else None,
            "section": None,
        }

        parent_id = str(uuid.uuid4())
        parents.append({
            "chunk_id": parent_id,
            "collection_id": collection_id,
            "resource_id": resource_id,
            "user_id": user_id,
            "index": p_index,
            "level": ChunkLevel.PARENT.value,
            "title": _extract_title(content, None, p_index),
            "content": content,
            "tokens": _tok(content),
            "anchor": anchor,
            "modality": modality.value,
            "retrieval_mode": retrieval_mode.value,
            "labels": [],
            "topics": [],
            "attachments": [],
        })

        # If the unit is small (fits a single segment), emit one segment
        # that IS the unit — retrieval precision wins here. Otherwise,
        # split into children using the paragraph-granular rules.
        if _tok(content) <= PARENT_MAX:
            segments.append({
                "segment_id": str(uuid.uuid4()),
                "parent_chunk_id": parent_id,
                "collection_id": collection_id,
                "resource_id": resource_id,
                "user_id": user_id,
                "index": 0,
                "content": content,
                "tokens": _tok(content),
                "questions": [],
                "anchor": anchor,
                "modality": modality.value,
                "retrieval_mode": retrieval_mode.value,
                "topics": [],
                "embedding": None,
            })
        else:
            # Large unit — paragraph-granular children inside it.
            paragraphs = _split_paragraphs(content.split("\n"))
            for c_index, child in enumerate(_pack_children(paragraphs)):
                c_content = child["content"].strip()
                if not c_content:
                    continue
                segments.append({
                    "segment_id": str(uuid.uuid4()),
                    "parent_chunk_id": parent_id,
                    "collection_id": collection_id,
                    "resource_id": resource_id,
                    "user_id": user_id,
                    "index": c_index,
                    "content": c_content,
                    "tokens": _tok(c_content),
                    "questions": [],
                    "anchor": anchor,
                    "modality": modality.value,
                    "retrieval_mode": retrieval_mode.value,
                    "topics": [],
                    "embedding": None,
                })

    log.info(
        "Chunked %s: %d LLM-bounded parents / %d segments from %d chars",
        resource_id[:8], len(parents), len(segments), len(markdown),
    )
    return parents, segments


def _merge_micro_units(units: list[str]) -> list[str]:
    """Merge consecutive micro-units (below CHILD_MIN/2 tokens) into the
    previous unit. Protects against over-eager LLM splits.
    """
    if not units:
        return []
    out: list[str] = [units[0]]
    for u in units[1:]:
        if _tok(u) < CHILD_MIN // 2 and out:
            out[-1] = out[-1] + "\n\n" + u
        else:
            out.append(u)
    return out


# ── Internals ──────────────────────────────────────────────────────────

_HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)")


def _split_by_headers(markdown: str) -> list[dict]:
    """Split markdown by h1/h2/h3 boundaries.

    Each section is `{"heading": str|None, "lines": [str, ...]}`. Lines
    include the header line itself so the parent content starts with it.
    """
    sections: list[dict] = []
    current: dict = {"heading": None, "lines": []}
    in_code_fence = False

    for line in markdown.split("\n"):
        # Don't treat `#` inside a fenced block as a header.
        if line.startswith("```"):
            in_code_fence = not in_code_fence
        if not in_code_fence:
            m = _HEADER_RE.match(line)
            if m:
                if current["lines"]:
                    sections.append(current)
                current = {"heading": m.group(2).strip(), "lines": [line]}
                continue
        current["lines"].append(line)

    if current["lines"]:
        sections.append(current)

    # Guard: if the doc has no headers at all, the first "section" has
    # heading=None and all the content — still valid.
    return sections


def _split_paragraphs(lines: list[str]) -> list[dict]:
    """Split section lines into paragraph units while keeping atomic blocks
    (fenced code, markdown tables) intact.

    Returns `[{"text": str, "atomic": bool}, ...]`.
    """
    paragraphs: list[dict] = []
    buf: list[str] = []
    in_code = False
    in_table = False

    def _flush(atomic: bool = False):
        nonlocal buf
        if buf:
            text = "\n".join(buf).strip("\n")
            if text:
                paragraphs.append({"text": text, "atomic": atomic})
            buf = []

    for line in lines:
        if line.startswith("```"):
            # Entering or leaving a fenced block — flush the prior paragraph
            # on enter, then flush the code block on exit.
            if not in_code:
                _flush(atomic=False)
                in_code = True
                buf.append(line)
            else:
                buf.append(line)
                in_code = False
                _flush(atomic=True)
            continue

        if in_code:
            buf.append(line)
            continue

        # Markdown table: a run of lines starting with `|`.
        is_table_line = line.lstrip().startswith("|")
        if is_table_line and not in_table:
            _flush(atomic=False)
            in_table = True
            buf.append(line)
            continue
        if in_table:
            if is_table_line or line.strip() == "":
                buf.append(line)
                if line.strip() == "":
                    in_table = False
                    _flush(atomic=True)
                continue
            else:
                # Table ended without a blank line.
                in_table = False
                _flush(atomic=True)
                # Fall through to normal handling of `line`.

        if line.strip() == "":
            _flush(atomic=False)
        else:
            buf.append(line)

    # Flush trailing buffer — mark atomic if we never closed a fence/table.
    _flush(atomic=in_code or in_table)
    return paragraphs


def _pack_parents(section: dict) -> list[dict]:
    """Accrete paragraphs of a section into parent-sized packs.

    Each returned pack: `{"heading": str|None, "content": str,
    "tokens": int, "paragraphs": [{"text", "atomic"}, ...]}`.
    Atomic paragraphs never straddle a pack boundary — if adding one
    would overflow, we close the current pack first (unless the atomic
    block alone exceeds PARENT_MAX, in which case it stands alone).
    """
    heading = section.get("heading")
    paragraphs = _split_paragraphs(section["lines"])
    if not paragraphs:
        return []

    packs: list[dict] = []
    cur_paras: list[dict] = []
    cur_tokens = 0

    def _close():
        nonlocal cur_paras, cur_tokens
        if not cur_paras:
            return
        content = "\n\n".join(p["text"] for p in cur_paras)
        packs.append({
            "heading": heading,
            "content": content,
            "tokens": _tok(content),
            "paragraphs": cur_paras,
        })
        cur_paras = []
        cur_tokens = 0

    for para in paragraphs:
        p_tok = _tok(para["text"])

        # Atomic block that fits in a fresh parent on its own: keep
        # it whole by closing the current pack first if needed.
        if para["atomic"]:
            if cur_tokens and cur_tokens + p_tok > PARENT_MAX:
                _close()
            cur_paras.append(para)
            cur_tokens += p_tok
            if cur_tokens >= PARENT_TARGET:
                _close()
            continue

        # Normal paragraph: close when we'd overflow target.
        if cur_tokens + p_tok > PARENT_TARGET and cur_tokens >= PARENT_MIN:
            _close()
        cur_paras.append(para)
        cur_tokens += p_tok

        # Hard cap — never exceed PARENT_MAX.
        if cur_tokens >= PARENT_MAX:
            _close()

    _close()
    return packs


def _merge_small_parents(packs: list[dict]) -> list[dict]:
    """Merge packs under PARENT_MIN into the previous pack (if one exists)."""
    merged: list[dict] = []
    for pack in packs:
        if merged and pack["tokens"] < PARENT_MIN:
            prev = merged[-1]
            prev["content"] = prev["content"] + "\n\n" + pack["content"]
            prev["tokens"] = _tok(prev["content"])
            prev["paragraphs"].extend(pack["paragraphs"])
        else:
            merged.append(pack)
    return merged


def _pack_children(paragraphs: list[dict]) -> list[dict]:
    """Paragraph-granular child segmentation.

    Rationale — blank-line paragraphs are the most universal semantic
    signal across document types, languages, and formats. Packing
    multiple paragraphs into a single child mixes independent topics
    and dilutes embedding specificity (observed empirically). So:

      - Default: each paragraph = one child.
      - Merge tiny paragraphs (< CHILD_MIN) into the preceding child.
      - Split oversize paragraphs (> CHILD_MAX) at sentence boundaries
        into CHILD_TARGET-sized sub-children.
      - Atomic blocks (code fences, tables) stay whole — never split,
        never merged.

    No format-specific detection (no exam regex, no FAQ patterns). The
    chunker treats every document the same; modality- or density-
    specific behavior belongs in retrieval, not here.
    """
    if not paragraphs:
        return []

    packs: list[dict] = []

    def _emit(content: str, atomic: bool = False):
        content = content.strip()
        if not content:
            return
        packs.append({"content": content, "tokens": _tok(content), "atomic": atomic})

    def _merge_or_emit(content: str):
        """Emit a new child, OR if content is tiny, absorb it into the
        previous non-atomic child — but only while that child is still
        below CHILD_TARGET so we don't grow a child unboundedly."""
        content = content.strip()
        if not content:
            return
        t = _tok(content)
        if (
            packs
            and t < CHILD_MIN
            and not packs[-1].get("atomic")
            and packs[-1]["tokens"] < CHILD_TARGET
        ):
            prev = packs[-1]
            prev["content"] = prev["content"] + "\n\n" + content
            prev["tokens"] = _tok(prev["content"])
            return
        _emit(content, atomic=False)

    for para in paragraphs:
        text = para["text"]
        if para.get("atomic"):
            _emit(text, atomic=True)
            continue

        p_tok = _tok(text)

        if p_tok <= CHILD_MAX:
            _merge_or_emit(text)
            continue

        # Oversize paragraph — split at sentence boundaries into
        # CHILD_TARGET-sized sub-children.
        for piece in _sentence_split(text, target=CHILD_TARGET, hard_max=CHILD_MAX):
            _merge_or_emit(piece)

    # Absorb trailing sliver into the previous non-atomic child.
    if (
        len(packs) >= 2
        and not packs[-1].get("atomic")
        and packs[-1]["tokens"] < CHILD_MIN
        and not packs[-2].get("atomic")
    ):
        tail = packs.pop()
        prev = packs[-1]
        prev["content"] = prev["content"] + "\n\n" + tail["content"]
        prev["tokens"] = _tok(prev["content"])

    # Degenerate: whole parent was empty after trimming. Fall back to the
    # raw text so retrieval has at least one unit per parent.
    if not packs:
        content = "\n\n".join(p["text"] for p in paragraphs).strip()
        if content:
            _emit(content)

    # Drop the transient "atomic" flag before returning.
    return [{"content": p["content"], "tokens": p["tokens"]} for p in packs]


# Universal sentence terminators — period, question mark, exclamation, plus
# CJK full-stops for multilingual content. Whitespace after the terminator
# is required so URLs/decimals don't split (e.g. "3.14").
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+")


def _sentence_split(text: str, *, target: int, hard_max: int) -> list[str]:
    """Split an oversize paragraph into ~target-token chunks at sentence
    boundaries. Format-agnostic — just uses sentence-terminator + whitespace.
    Accepts some false positives (e.g. "Dr. Smith") in exchange for not
    taking a dependency on NLTK/spaCy.
    """
    sentences = _SENTENCE_SPLIT_RE.split(text)
    out: list[str] = []
    buf: list[str] = []
    buf_tokens = 0

    def _flush():
        nonlocal buf, buf_tokens
        if buf:
            out.append(" ".join(buf).strip())
            buf = []
            buf_tokens = 0

    for s in sentences:
        s_tok = _tok(s)
        # A single sentence that exceeds hard_max on its own — emit as-is.
        # (Rare; better than silently splitting mid-sentence.)
        if s_tok > hard_max:
            _flush()
            out.append(s.strip())
            continue
        if buf_tokens + s_tok > target and buf:
            _flush()
        buf.append(s)
        buf_tokens += s_tok

    _flush()
    return out


# ── Anchor detection ───────────────────────────────────────────────────

_PAGE_RE = re.compile(r"<!--\s*page\s+(\d+)\s*-->")
_TIMESTAMP_RE = re.compile(r"\[(\d+):(\d{2})\]")


def _detect_page_range(content: str) -> tuple[int, int] | None:
    """Return (first, last) page numbers referenced by this parent, if any."""
    pages = [int(m.group(1)) for m in _PAGE_RE.finditer(content)]
    if not pages:
        return None
    return (min(pages), max(pages))


def _detect_timestamp_range(content: str) -> tuple[float, float] | None:
    """Return (first, last) timestamps in seconds, if any."""
    matches = _TIMESTAMP_RE.findall(content)
    if not matches:
        return None
    if len(matches) == 1:
        t = int(matches[0][0]) * 60 + int(matches[0][1])
        return (float(t), float(t + 30))  # assume ~30s window
    first = int(matches[0][0]) * 60 + int(matches[0][1])
    last = int(matches[-1][0]) * 60 + int(matches[-1][1])
    return (float(first), float(last))
