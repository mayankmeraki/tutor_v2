"""End-to-end: chunk → embed → index.

Exercises the real chunker (no mocks), the embedder with Haiku + OpenAI
stubbed out, and the indexer against the in-memory FakeDatabase. The
assertions are on the shape/counts of what lands in Mongo, not on
ranking quality — that's covered by retrieval unit tests.
"""

from __future__ import annotations

import pytest

from byo.processing.chunker import chunk_markdown
from byo.processing.embedder import embed_segments_batch
from byo.processing.indexer import index_chunks_and_segments


pytestmark = pytest.mark.asyncio


# A short but structurally varied markdown: headers, paragraphs, a code
# block, a table. The chunker should produce ≥ 1 parent and emit ≥ 1
# segment per parent.
SAMPLE_MD = """# Photosynthesis

Photosynthesis is how plants convert light into chemical energy. It takes
place in the chloroplasts. Chlorophyll is the primary pigment that absorbs
light — mostly blue and red, reflecting green.

## Light-dependent reactions

In the thylakoid membranes, water is split, oxygen is released, and ATP
and NADPH are produced. The electron transport chain drives the proton
gradient used to make ATP via ATP synthase.

```python
def atp_yield(photons: int) -> float:
    # Roughly one ATP per 3 protons pumped.
    return photons / 3.0
```

## Calvin cycle

The Calvin cycle happens in the stroma. It uses ATP and NADPH from the
light reactions to fix CO2 into G3P. Rubisco is the key enzyme; it is
notoriously slow.

| Step    | Input  | Output |
|---------|--------|--------|
| Fixation| CO2    | 3-PGA  |
| Reduction| 3-PGA | G3P    |
| Regen    | G3P   | RuBP   |

This is the regeneration phase. G3P is partially used for sugar
synthesis and partially recycled to RuBP.
"""


async def test_full_pipeline_writes_parents_and_children(fake_db):
    """One resource → chunker → embedder → indexer → byo_chunks + byo_segments.

    Assertions:
      - N parents in byo_chunks (N ≥ 1)
      - M segments in byo_segments (N ≤ M ≤ 5N)
      - Every segment's parent_chunk_id matches a parent's chunk_id
      - Every segment has a non-empty embedding
      - byo_resources.chunk_count reflects parent count
    """
    user_id = "u-1"
    collection_id = "col-1"
    resource_id = "res-1"

    # Seed the resource so the indexer's update_one({resource_id:...}) has a
    # document to patch chunk_count on.
    await fake_db.byo_resources.insert_one({
        "resource_id": resource_id,
        "collection_id": collection_id,
        "user_id": user_id,
        "original_name": "biology-notes.md",
        "mime_type": "text/markdown",
        "status": "ready",
        "chunk_count": 0,
    })

    # 1) Chunk
    parents, segments = await chunk_markdown(
        SAMPLE_MD,
        resource_id=resource_id,
        collection_id=collection_id,
        user_id=user_id,
        mime_type="text/markdown",
    )
    assert len(parents) >= 1, "chunker should emit at least one parent"
    assert len(segments) >= len(parents), (
        "expected at least one segment per parent "
        f"(parents={len(parents)}, segments={len(segments)})"
    )
    assert len(segments) <= 5 * len(parents), (
        "segments should not explode beyond ~5x parents; "
        f"got parents={len(parents)}, segments={len(segments)}"
    )

    # Segments reference real parents (small-to-big invariant)
    parent_ids = {p["chunk_id"] for p in parents}
    for s in segments:
        assert s["parent_chunk_id"] in parent_ids, (
            f"orphan segment {s['segment_id']} → {s['parent_chunk_id']}"
        )

    # 2) Embed (Haiku + embeddings stubbed in the fixture)
    await embed_segments_batch(segments)
    for s in segments:
        assert s.get("embedding"), f"segment {s['segment_id']} has no embedding"
        assert len(s["embedding"]) == 128, "fake embedder produces 128-d vectors"

    # 3) Index into fake Mongo
    n_parents, n_segments = await index_chunks_and_segments(
        resource_id=resource_id,
        collection_id=collection_id,
        user_id=user_id,
        parents=parents,
        segments=segments,
    )
    assert n_parents == len(parents)
    assert n_segments == len(segments)

    # Verify byo_chunks + byo_segments state
    chunk_count = await fake_db.byo_chunks.count_documents({"resource_id": resource_id})
    assert chunk_count == len(parents)
    seg_count = await fake_db.byo_segments.count_documents({"resource_id": resource_id})
    assert seg_count == len(segments)

    # Every persisted segment must have an embedding after indexing
    cursor = fake_db.byo_segments.find({"resource_id": resource_id})
    async for s in cursor:
        assert s.get("embedding"), "persisted segment lost its embedding"

    # chunk_count on the resource was synced
    res = await fake_db.byo_resources.find_one({"resource_id": resource_id})
    assert res["chunk_count"] == len(parents)


async def test_reindex_is_idempotent(fake_db):
    """Re-running the pipeline for the same resource converges to one clean
    state — no duplicates, no orphans. The indexer deletes existing chunks
    and segments before re-inserting.
    """
    user_id = "u-1"
    collection_id = "col-1"
    resource_id = "res-1"
    await fake_db.byo_resources.insert_one({
        "resource_id": resource_id,
        "collection_id": collection_id,
        "user_id": user_id,
        "chunk_count": 0,
    })

    for _ in range(2):
        parents, segments = await chunk_markdown(
            SAMPLE_MD,
            resource_id=resource_id,
            collection_id=collection_id,
            user_id=user_id,
            mime_type="text/markdown",
        )
        await embed_segments_batch(segments)
        await index_chunks_and_segments(
            resource_id=resource_id,
            collection_id=collection_id,
            user_id=user_id,
            parents=parents,
            segments=segments,
        )

    # After two runs, expect counts equal to one run's output (not doubled).
    parents_once, segments_once = await chunk_markdown(
        SAMPLE_MD,
        resource_id=resource_id,
        collection_id=collection_id,
        user_id=user_id,
        mime_type="text/markdown",
    )
    chunk_count = await fake_db.byo_chunks.count_documents({"resource_id": resource_id})
    seg_count = await fake_db.byo_segments.count_documents({"resource_id": resource_id})
    assert chunk_count == len(parents_once)
    assert seg_count == len(segments_once)


async def test_empty_markdown_writes_nothing(fake_db):
    """Empty input is a no-op: no parents, no segments, no crashes."""
    parents, segments = await chunk_markdown(
        "   \n\n   ",
        resource_id="res-empty",
        collection_id="col-1",
        user_id="u-1",
        mime_type="text/markdown",
    )
    assert parents == []
    assert segments == []
