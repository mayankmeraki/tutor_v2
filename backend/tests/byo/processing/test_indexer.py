"""Unit tests for byo.processing.indexer.index_chunks_and_segments.

Uses the FakeMongoDB from conftest — no real MongoDB. Covers collection
writes, idempotency on re-index, chunk_count propagation, and topic
denormalization from parents onto segments.
"""

from __future__ import annotations

import pytest

from byo.processing.indexer import index_chunks_and_segments


def _parent(i: int, chunk_id: str = None, topics: list[str] = None) -> dict:
    return {
        "chunk_id": chunk_id or f"par-{i}",
        "collection_id": "c1",
        "resource_id": "r1",
        "user_id": "u1",
        "index": i,
        "level": "parent",
        "content": f"parent content {i}",
        "tokens": 100,
        "anchor": {"page": i + 1},
        "modality": "text",
        "retrieval_mode": "semantic",
        "labels": [],
        "topics": topics or [],
        "attachments": [],
    }


def _segment(i: int, parent_id: str, segment_id: str = None) -> dict:
    return {
        "segment_id": segment_id or f"seg-{i}",
        "parent_chunk_id": parent_id,
        "collection_id": "c1",
        "resource_id": "r1",
        "user_id": "u1",
        "index": i,
        "content": f"segment content {i}",
        "tokens": 25,
        "questions": [],
        "anchor": {"page": 1},
        "modality": "text",
        "retrieval_mode": "semantic",
        "topics": [],
        "embedding": [0.0] * 1536,
    }


class TestIndexChunksAndSegments:

    async def test_writes_parents_to_byo_chunks(self, fake_mongo):
        parents = [_parent(i) for i in range(3)]
        segments = [
            _segment(0, "par-0"), _segment(1, "par-1"), _segment(2, "par-2")
        ]
        n_par, n_seg = await index_chunks_and_segments(
            resource_id="r1", collection_id="c1", user_id="u1",
            parents=parents, segments=segments,
        )
        assert n_par == 3
        assert n_seg == 3
        docs = await fake_mongo.byo_chunks.count_documents({})
        assert docs == 3

    async def test_writes_segments_to_byo_segments(self, fake_mongo):
        parents = [_parent(0)]
        segments = [_segment(i, "par-0") for i in range(5)]
        await index_chunks_and_segments(
            resource_id="r1", collection_id="c1", user_id="u1",
            parents=parents, segments=segments,
        )
        assert await fake_mongo.byo_segments.count_documents({}) == 5

    async def test_updates_resource_chunk_count(self, fake_mongo):
        # Seed the resource record.
        await fake_mongo.byo_resources.insert_one(
            {"resource_id": "r1", "chunk_count": 0}
        )
        parents = [_parent(i) for i in range(4)]
        await index_chunks_and_segments(
            resource_id="r1", collection_id="c1", user_id="u1",
            parents=parents, segments=[],
        )
        doc = await fake_mongo.byo_resources.find_one({"resource_id": "r1"})
        assert doc["chunk_count"] == 4

    async def test_segment_parent_refs_match(self, fake_mongo):
        parents = [_parent(0, chunk_id="PARENT-A"), _parent(1, chunk_id="PARENT-B")]
        segments = [
            _segment(0, "PARENT-A"),
            _segment(1, "PARENT-A"),
            _segment(2, "PARENT-B"),
        ]
        await index_chunks_and_segments(
            resource_id="r1", collection_id="c1", user_id="u1",
            parents=parents, segments=segments,
        )

        # Every segment in the DB must point at a parent that is in the DB.
        parent_docs = [d async for d in fake_mongo.byo_chunks.find({})]
        parent_ids = {p["chunk_id"] for p in parent_docs}
        segment_docs = [d async for d in fake_mongo.byo_segments.find({})]
        for s in segment_docs:
            assert s["parent_chunk_id"] in parent_ids

    async def test_idempotent_re_index(self, fake_mongo):
        parents = [_parent(i) for i in range(3)]
        segments = [_segment(i, f"par-{i}") for i in range(3)]
        await index_chunks_and_segments(
            resource_id="r1", collection_id="c1", user_id="u1",
            parents=parents, segments=segments,
        )
        # Run again with a fresh set (new ids).
        new_parents = [_parent(i, chunk_id=f"NEW-{i}") for i in range(2)]
        new_segments = [_segment(i, f"NEW-{i}") for i in range(2)]
        await index_chunks_and_segments(
            resource_id="r1", collection_id="c1", user_id="u1",
            parents=new_parents, segments=new_segments,
        )
        # Only the new records should remain.
        par_docs = [d async for d in fake_mongo.byo_chunks.find({})]
        seg_docs = [d async for d in fake_mongo.byo_segments.find({})]
        assert len(par_docs) == 2
        assert len(seg_docs) == 2
        assert {p["chunk_id"] for p in par_docs} == {"NEW-0", "NEW-1"}

    async def test_idempotent_only_affects_same_resource(self, fake_mongo):
        # Other resource's records shouldn't be touched.
        await fake_mongo.byo_chunks.insert_one({
            "chunk_id": "OTHER-1", "resource_id": "r-other", "collection_id": "c1",
            "user_id": "u1", "index": 0, "level": "parent", "content": "x",
            "tokens": 10, "anchor": {}, "modality": None, "retrieval_mode": None,
            "labels": [], "topics": [], "attachments": [],
        })
        await index_chunks_and_segments(
            resource_id="r1", collection_id="c1", user_id="u1",
            parents=[_parent(0)], segments=[_segment(0, "par-0")],
        )
        other = await fake_mongo.byo_chunks.find_one({"resource_id": "r-other"})
        assert other is not None

    async def test_empty_parents_still_syncs_chunk_count(self, fake_mongo):
        await fake_mongo.byo_resources.insert_one(
            {"resource_id": "r1", "chunk_count": 99}
        )
        n_p, n_s = await index_chunks_and_segments(
            resource_id="r1", collection_id="c1", user_id="u1",
            parents=[], segments=[],
        )
        assert n_p == 0 and n_s == 0
        doc = await fake_mongo.byo_resources.find_one({"resource_id": "r1"})
        assert doc["chunk_count"] == 0

    async def test_topics_propagate_parent_to_segments(self, fake_mongo):
        parents = [
            _parent(0, chunk_id="PA", topics=["physics", "kinematics"]),
            _parent(1, chunk_id="PB", topics=["chemistry"]),
        ]
        segments = [
            _segment(0, "PA"),
            _segment(1, "PA"),
            _segment(2, "PB"),
        ]
        await index_chunks_and_segments(
            resource_id="r1", collection_id="c1", user_id="u1",
            parents=parents, segments=segments,
        )
        docs = [d async for d in fake_mongo.byo_segments.find({})]
        by_pid = {d["segment_id"]: d for d in docs}
        assert set(by_pid["seg-0"]["topics"]) == {"physics", "kinematics"}
        assert set(by_pid["seg-1"]["topics"]) == {"physics", "kinematics"}
        assert set(by_pid["seg-2"]["topics"]) == {"chemistry"}

    async def test_preserves_existing_segment_topics(self, fake_mongo):
        """If a segment already has topics, don't overwrite."""
        parents = [_parent(0, chunk_id="PA", topics=["from-parent"])]
        seg = _segment(0, "PA")
        seg["topics"] = ["already-set"]
        await index_chunks_and_segments(
            resource_id="r1", collection_id="c1", user_id="u1",
            parents=parents, segments=[seg],
        )
        out = await fake_mongo.byo_segments.find_one({"segment_id": "seg-0"})
        assert out["topics"] == ["already-set"]

    async def test_preserves_embedding_in_stored_doc(self, fake_mongo):
        parents = [_parent(0)]
        segments = [_segment(0, "par-0")]
        segments[0]["embedding"] = [0.25] * 1536
        await index_chunks_and_segments(
            resource_id="r1", collection_id="c1", user_id="u1",
            parents=parents, segments=segments,
        )
        doc = await fake_mongo.byo_segments.find_one({"segment_id": "seg-0"})
        assert doc["embedding"] == [0.25] * 1536
