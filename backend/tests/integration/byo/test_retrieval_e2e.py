"""End-to-end retrieval: ingest 3 resources, then exercise the public
byo.retrieval.service API.

We seed the FakeDatabase via the real chunker + embedder + indexer so the
test reflects what actual ingestion produces. Then we call search / fetch
/ nearby / list_contents and assert on wiring, not ranking quality:

  - search returns RetrievedChunk whose content is the PARENT content
    (small-to-big expansion worked), with citation fields populated.
  - fetch(chunk:<id>) returns the full parent content.
  - nearby(chunk:<id>, window=1) returns adjacent chunks.
  - list_contents(collection_id, group_by='resource') returns one entry
    per ingested resource.

External APIs (Haiku, OpenAI embeddings, Cohere) are stubbed in conftest.
"""

from __future__ import annotations

import pytest

from byo.processing.chunker import chunk_markdown
from byo.processing.embedder import embed_segments_batch
from byo.processing.indexer import index_chunks_and_segments
from byo.retrieval import service as svc
from byo.shared.results import RetrievedChunk, RetrievedRef


pytestmark = pytest.mark.asyncio


# ── Seed content ──────────────────────────────────────────────────────────

PDF_MD = """# Quantum Mechanics Primer

<!-- page 1 -->
Quantum mechanics describes nature at the smallest scales: atoms, photons,
electrons. Classical intuitions fail; amplitudes interfere, outcomes are
probabilistic.

<!-- page 2 -->
The state of a quantum system is a vector in a Hilbert space. Observables
are Hermitian operators; eigenvalues are the possible measurement results.

## Superposition

<!-- page 3 -->
A system can be in a linear combination of basis states. Measurement
projects onto one of those states with probability equal to the squared
amplitude.
"""


VIDEO_MD = """# Entanglement Lecture Transcript

[00:00] Hello, welcome to the entanglement lecture. Today we will discuss
EPR pairs and Bell's theorem.

[00:30] An entangled state cannot be written as a product of single-particle
states. Measurements on the two particles show correlations that no local
hidden variable theory can reproduce.

[01:15] Bell's theorem proves this rigorously. The CHSH inequality provides
an experimentally testable bound.
"""


TEXT_MD = """# Study Notes — Wave Functions

The wave function is a complex-valued function over configuration space.
Its modulus squared gives the probability density.

The Schrodinger equation governs the time evolution of the wave function.
For a free particle, plane-wave solutions are a natural basis.

The uncertainty principle ties together position and momentum: their
standard deviations cannot both be made arbitrarily small.
"""


RESOURCES = [
    ("res-pdf", "Quantum Primer.pdf", "application/pdf", PDF_MD),
    ("res-vid", "Entanglement Lecture.mp4", "video/mp4", VIDEO_MD),
    ("res-txt", "Study Notes.md", "text/markdown", TEXT_MD),
]


async def _seed(db, user_id: str, collection_id: str):
    """Run chunker → embedder → indexer for all three fixtures."""
    # Seed the collection + resource records the service queries.
    await db.collections.insert_one({
        "collection_id": collection_id,
        "user_id": user_id,
        "title": "Quantum Study",
        "stats": {"resources": len(RESOURCES), "chunks": 0},
    })

    for rid, name, mime, md in RESOURCES:
        await db.byo_resources.insert_one({
            "resource_id": rid,
            "collection_id": collection_id,
            "user_id": user_id,
            "original_name": name,
            "mime_type": mime,
            "status": "ready",
            "chunk_count": 0,
            "meta": {},
        })
        parents, segments = await chunk_markdown(
            md,
            resource_id=rid,
            collection_id=collection_id,
            user_id=user_id,
            mime_type=mime,
        )
        # Assign plausible topics so $search + group_by=topic has something
        # to find. In real life the classifier would do this.
        for p in parents:
            if "entangle" in (p.get("content") or "").lower():
                p["topics"] = ["entanglement"]
            elif "wave function" in (p.get("content") or "").lower():
                p["topics"] = ["wave function"]
            elif "superposition" in (p.get("content") or "").lower():
                p["topics"] = ["superposition"]
        await embed_segments_batch(segments)
        await index_chunks_and_segments(
            resource_id=rid,
            collection_id=collection_id,
            user_id=user_id,
            parents=parents,
            segments=segments,
        )


# ── Tests ─────────────────────────────────────────────────────────────────


async def test_search_returns_parent_chunks_with_citations(fake_db):
    user_id = "u-1"
    collection_id = "col-1"
    await _seed(fake_db, user_id, collection_id)

    hits = await svc.search(
        "entanglement Bell theorem",
        user_id=user_id,
        scope="collection",
        collection_id=collection_id,
        k=3,
        use_hyde=False,
    )
    assert hits, "expected at least one hit"
    for h in hits:
        assert isinstance(h, RetrievedChunk)
        assert h.chunk_id, "hit missing parent chunk_id"
        assert h.segment_id, "hit missing segment_id"
        # Parent content was expanded (small-to-big) — should be substantially
        # longer than the typical 200-tok child target.
        assert h.content and len(h.content) > 50
        # Citation: resource_name populated from byo_resources
        assert h.resource_name, "resource_name missing on hit"
        assert h.score >= 0.0

    # The top hit should plausibly reference entanglement somewhere —
    # our sparse + dense simulators both score term overlap.
    top_content = (hits[0].content or "").lower()
    assert "entangle" in top_content or "bell" in top_content, (
        f"top hit doesn't match query terms: {top_content[:200]}"
    )


async def test_fetch_returns_full_parent(fake_db):
    user_id = "u-1"
    collection_id = "col-1"
    await _seed(fake_db, user_id, collection_id)

    # Pick a known chunk_id from the DB.
    parent = await fake_db.byo_chunks.find_one({"user_id": user_id})
    assert parent, "seeding didn't write any parents"
    ref = f"chunk:{parent['chunk_id']}"

    hit = await svc.fetch(ref, user_id=user_id)
    assert hit is not None, f"fetch({ref}) returned None"
    assert isinstance(hit, RetrievedChunk)
    assert hit.chunk_id == parent["chunk_id"]
    # Full parent content preserved (not truncated).
    assert hit.content == parent["content"]
    assert hit.resource_name, "fetch hit must carry resource_name for citation"


async def test_fetch_segment_resolves_to_parent(fake_db):
    """fetch(segment:<id>) returns the segment's parent chunk."""
    user_id = "u-1"
    collection_id = "col-1"
    await _seed(fake_db, user_id, collection_id)

    seg = await fake_db.byo_segments.find_one({"user_id": user_id})
    assert seg, "no segments persisted"
    ref = f"segment:{seg['segment_id']}"

    hit = await svc.fetch(ref, user_id=user_id)
    assert hit is not None
    assert hit.chunk_id == seg["parent_chunk_id"]
    assert hit.segment_id == seg["segment_id"]


async def test_nearby_returns_adjacent_chunks(fake_db):
    """nearby(chunk:<id>, window=1) returns chunks in the same resource
    whose index is within ±1 of the anchor chunk.
    """
    user_id = "u-1"
    collection_id = "col-1"
    await _seed(fake_db, user_id, collection_id)

    # Use the text resource (no pages / timestamps → index-based nearby).
    parent = await fake_db.byo_chunks.find_one({
        "user_id": user_id,
        "resource_id": "res-txt",
        "index": 0,
    })
    assert parent, "need a chunk in res-txt to walk"

    hits = await svc.nearby(
        f"chunk:{parent['chunk_id']}", user_id=user_id, window=1,
    )
    # Must always include the anchor chunk itself.
    ids = [h.chunk_id for h in hits]
    assert parent["chunk_id"] in ids, f"nearby dropped the anchor itself: {ids}"
    # All hits must come from the same resource (user-scoped + resource-scoped).
    for h in hits:
        assert h.resource_id == "res-txt"


async def test_list_contents_groups_by_resource(fake_db):
    user_id = "u-1"
    collection_id = "col-1"
    await _seed(fake_db, user_id, collection_id)

    refs = await svc.list_contents(
        collection_id, user_id=user_id, group_by="resource",
    )
    assert len(refs) == len(RESOURCES), (
        f"expected {len(RESOURCES)} resource groups, got {len(refs)}"
    )
    for r in refs:
        assert isinstance(r, RetrievedRef)
        assert r.ref.startswith("resource:")
        assert r.title  # original_name


async def test_search_requires_user_id(fake_db):
    """Security: search without user_id must raise — no silent fallback."""
    with pytest.raises(ValueError):
        await svc.search("anything", user_id="", scope="user_corpus")


async def test_empty_query_returns_empty(fake_db):
    """A blank query returns [] without hitting rankers."""
    hits = await svc.search(
        "", user_id="u-1", scope="collection", collection_id="col-1",
    )
    assert hits == []


async def test_search_no_hits_for_unrelated_query(fake_db):
    """Query with zero term overlap against any seed → empty list."""
    user_id = "u-1"
    collection_id = "col-1"
    await _seed(fake_db, user_id, collection_id)

    hits = await svc.search(
        "unrelatedword zzz",
        user_id=user_id,
        scope="collection",
        collection_id=collection_id,
        k=5,
        use_hyde=False,
    )
    assert hits == [], f"expected no hits for off-topic query, got {len(hits)}"
