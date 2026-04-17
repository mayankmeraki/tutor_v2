"""Output-format contract tests.

Focus: given valid inputs with real ingested content, the strings returned
by the unified retrieval tools are shaped for direct LLM consumption —
citations, reusable refs, reasonable caps. These are the guarantees the
tutor's prompt relies on.
"""

from __future__ import annotations

import json
import re

import pytest

from app.tools import execute_tutor_tool
from byo.processing.chunker import chunk_markdown
from byo.processing.embedder import embed_segments_batch
from byo.processing.indexer import index_chunks_and_segments


pytestmark = pytest.mark.asyncio


# A fixture with both timestamp anchors (video) and page anchors (pdf)
VIDEO_MD = """# Entanglement Lecture

[00:00] Welcome to the entanglement lecture. We cover EPR pairs and Bell.

[00:45] An entangled state cannot be written as a product of single-particle
states. Measurements show correlations no local hidden variable theory
can reproduce.

[01:30] Bell's theorem proves this. CHSH provides a testable bound.
"""

PDF_MD = """# Quantum Primer

<!-- page 1 -->
Quantum mechanics describes nature at the smallest scales.

<!-- page 2 -->
The state is a vector in a Hilbert space. Measurements return eigenvalues.

<!-- page 3 -->
Superposition lets systems exist in linear combinations of basis states.
"""


async def _seed(db, user_id="u-1", collection_id="col-1"):
    # Two resources: video (timestamps) + pdf (pages)
    await db.collections.insert_one({
        "collection_id": collection_id,
        "user_id": user_id,
        "title": "QM Study",
        "stats": {"resources": 2, "chunks": 0},
    })
    specs = [
        ("res-vid", "Entanglement Lecture.mp4", "video/mp4", VIDEO_MD),
        ("res-pdf", "Quantum Primer.pdf", "application/pdf", PDF_MD),
    ]
    for rid, name, mime, md in specs:
        await db.byo_resources.insert_one({
            "resource_id": rid,
            "collection_id": collection_id,
            "user_id": user_id,
            "original_name": name,
            "mime_type": mime,
            "status": "ready",
            "chunk_count": 0,
        })
        parents, segments = await chunk_markdown(
            md,
            resource_id=rid,
            collection_id=collection_id,
            user_id=user_id,
            mime_type=mime,
        )
        for p in parents:
            c = (p.get("content") or "").lower()
            if "entangle" in c or "bell" in c:
                p["topics"] = ["entanglement"]
            elif "superposition" in c:
                p["topics"] = ["superposition"]
        await embed_segments_batch(segments)
        await index_chunks_and_segments(
            resource_id=rid,
            collection_id=collection_id,
            user_id=user_id,
            parents=parents,
            segments=segments,
        )


def _ctx(user_email="u-1", collection_id="col-1"):
    return {
        "studentProfile": json.dumps({"userEmail": user_email}),
        "sessionContext": json.dumps({"collection_id": collection_id}),
    }


# ── search format ─────────────────────────────────────────────────────────


_REF_RE = re.compile(r"chunk:[a-zA-Z0-9\-]+")


async def test_search_output_contains_fetchable_refs(fake_db):
    await _seed(fake_db)
    out = await execute_tutor_tool(
        "search",
        {"query": "entanglement", "scope": "collection", "collection_id": "col-1", "k": 3},
        context_data=_ctx(),
    )
    refs = _REF_RE.findall(out)
    assert refs, (
        f"search output must include `chunk:` refs for the tutor to fetch, got:\n{out}"
    )
    # Every ref shape should round-trip into fetch without parse errors.
    for r in refs[:2]:
        back = await execute_tutor_tool("fetch", {"ref": r}, context_data=_ctx())
        assert isinstance(back, str)
        assert not back.lower().startswith("error"), f"fetch({r}) errored: {back!r}"


async def test_search_output_is_capped(fake_db):
    """No 10k-char spam — each result is truncated."""
    await _seed(fake_db)
    out = await execute_tutor_tool(
        "search",
        {"query": "quantum superposition entanglement wave", "scope": "collection",
         "collection_id": "col-1", "k": 5},
        context_data=_ctx(),
    )
    assert len(out) < 10_000, f"search output should be capped; got {len(out)} chars"


async def test_search_output_has_citations(fake_db):
    """Each hit should carry the source resource name."""
    await _seed(fake_db)
    out = await execute_tutor_tool(
        "search",
        {"query": "entanglement", "scope": "collection", "collection_id": "col-1", "k": 3},
        context_data=_ctx(),
    )
    # At least one of the seed resource names appears.
    assert ("Entanglement Lecture.mp4" in out) or ("Quantum Primer.pdf" in out), (
        f"search output missing source citations:\n{out}"
    )


# ── fetch format ──────────────────────────────────────────────────────────


async def test_fetch_output_has_source_citation(fake_db):
    await _seed(fake_db)
    parent = await fake_db.byo_chunks.find_one({"user_id": "u-1"})
    out = await execute_tutor_tool(
        "fetch",
        {"ref": f"chunk:{parent['chunk_id']}"},
        context_data=_ctx(),
    )
    # fetch output concludes with a Source line carrying the resource name.
    assert "Source:" in out
    assert ("Entanglement Lecture.mp4" in out) or ("Quantum Primer.pdf" in out)


async def test_fetch_video_output_includes_timestamp(fake_db):
    """Video chunks carry a start_time anchor → citation shows m:ss."""
    await _seed(fake_db)
    # Pick a chunk from the video resource specifically.
    parent = await fake_db.byo_chunks.find_one({"resource_id": "res-vid", "index": 0})
    assert parent
    out = await execute_tutor_tool(
        "fetch",
        {"ref": f"chunk:{parent['chunk_id']}"},
        context_data=_ctx(),
    )
    # Expect an m:ss style timestamp in the citation line.
    assert re.search(r"\b\d+:\d{2}\b", out), (
        f"video fetch output missing timestamp citation: {out!r}"
    )


async def test_fetch_pdf_output_includes_page(fake_db):
    """PDF chunks carry a page anchor → citation shows 'p. N'."""
    await _seed(fake_db)
    parent = await fake_db.byo_chunks.find_one({"resource_id": "res-pdf"})
    assert parent
    out = await execute_tutor_tool(
        "fetch",
        {"ref": f"chunk:{parent['chunk_id']}"},
        context_data=_ctx(),
    )
    assert "p. " in out, f"pdf fetch output missing page citation: {out!r}"


# ── nearby format ─────────────────────────────────────────────────────────


async def test_nearby_output_ordered_by_anchor(fake_db):
    """nearby output should be anchor-ordered (pages ascending for PDFs)."""
    await _seed(fake_db)
    parent = await fake_db.byo_chunks.find_one({"resource_id": "res-pdf", "index": 0})
    out = await execute_tutor_tool(
        "nearby",
        {"ref": f"chunk:{parent['chunk_id']}", "window": 3},
        context_data=_ctx(),
    )
    # Extract page numbers from the citation lines.
    pages = [int(m.group(1)) for m in re.finditer(r"p\.\s*(\d+)", out)]
    if len(pages) >= 2:
        assert pages == sorted(pages), f"nearby pages not ascending: {pages}"


async def test_nearby_output_multiple_chunks_separated(fake_db):
    """nearby output prints one block per chunk (multi-line, separated)."""
    await _seed(fake_db)
    parent = await fake_db.byo_chunks.find_one({"resource_id": "res-pdf", "index": 0})
    out = await execute_tutor_tool(
        "nearby",
        {"ref": f"chunk:{parent['chunk_id']}", "window": 2},
        context_data=_ctx(),
    )
    # Each block leads with "chunk:<id>" — there should be at least one.
    assert out.count("chunk:") >= 1


# ── list_contents format ─────────────────────────────────────────────────


async def test_list_contents_output_includes_ref_per_resource(fake_db):
    await _seed(fake_db)
    out = await execute_tutor_tool(
        "list_contents",
        {"scope": "collection", "collection_id": "col-1", "group_by": "resource"},
        context_data=_ctx(),
    )
    # Two resources seeded → two resource: refs
    assert out.count("resource:") == 2, (
        f"expected 2 resource refs in list_contents, got:\n{out}"
    )
    # And both original_names should appear
    assert "Entanglement Lecture.mp4" in out
    assert "Quantum Primer.pdf" in out
