"""Tests for byo.retrieval.rankers.sparse.sparse_search."""

from __future__ import annotations

import pytest

from byo.retrieval.rankers import sparse as sparse_mod
from byo.retrieval.rankers.sparse import (
    CHUNKS_COLLECTION,
    SEGMENTS_COLLECTION,
    sparse_search,
)
from byo.shared.results import SearchFilters

from .conftest import FakeAggCollection, FakeDB


pytestmark = pytest.mark.asyncio


@pytest.fixture
def filters():
    return SearchFilters(user_id="u-1", collection_id="c-1")


async def test_search_stage_shape(monkeypatch, filters):
    segs = FakeAggCollection(
        aggregate_docs=[
            {"segment_id": "s1", "parent_chunk_id": "p1", "score": 2.0},
            {"segment_id": "s2", "parent_chunk_id": "p2", "score": 1.5},
        ],
        find_one_doc={"_id": "stub"},
    )
    db = FakeDB({SEGMENTS_COLLECTION: segs})
    monkeypatch.setattr(sparse_mod, "_get_db", lambda: db)

    out = await sparse_search("photosynthesis", filters, k=4)

    pipeline = segs.aggregate_calls[0][0][0]
    # [ $search, $match, $limit, $project ]
    assert "$search" in pipeline[0]
    search = pipeline[0]["$search"]
    assert search["index"] == sparse_mod.SEGMENTS_TEXT_INDEX
    should = search["compound"]["should"]
    # content + topics (topics is boosted)
    paths = [s["text"]["path"] for s in should]
    assert "content" in paths
    assert "topics" in paths
    for s in should:
        assert s["text"]["query"] == "photosynthesis"
    assert search["compound"]["minimumShouldMatch"] == 1

    # $match stage uses the filters
    assert pipeline[1]["$match"] == filters.to_mongo()
    # $limit stage matches k
    assert pipeline[2]["$limit"] == 4
    # Returns
    assert out == [("s1", "p1", 2.0), ("s2", "p2", 1.5)]


async def test_empty_query_short_circuits(monkeypatch, filters):
    segs = FakeAggCollection(find_one_doc={"_id": "stub"})
    db = FakeDB({SEGMENTS_COLLECTION: segs})
    monkeypatch.setattr(sparse_mod, "_get_db", lambda: db)

    assert await sparse_search("", filters, k=5) == []
    assert await sparse_search("   ", filters, k=5) == []
    assert segs.aggregate_calls == []


async def test_missing_user_id_raises(monkeypatch):
    with pytest.raises(ValueError):
        await sparse_search("hi", SearchFilters(user_id=""), k=5)


async def test_match_includes_time_range_or(monkeypatch):
    filters = SearchFilters(
        user_id="u-1",
        collection_id="c-1",
        time_range=(5.0, 20.0),
    )
    segs = FakeAggCollection(
        aggregate_docs=[{"segment_id": "s1", "parent_chunk_id": "p1", "score": 1.0}],
        find_one_doc={"_id": "stub"},
    )
    db = FakeDB({SEGMENTS_COLLECTION: segs})
    monkeypatch.setattr(sparse_mod, "_get_db", lambda: db)

    await sparse_search("q", filters, k=3)
    match = segs.aggregate_calls[0][0][0][1]["$match"]
    assert "$or" in match
    assert len(match["$or"]) == 3


async def test_legacy_fallback_when_segments_empty(monkeypatch, filters):
    segs = FakeAggCollection(find_one_doc=None)
    chunks = FakeAggCollection(
        aggregate_docs=[{"chunk_id": "cA", "score": 1.1}]
    )
    db = FakeDB({SEGMENTS_COLLECTION: segs, CHUNKS_COLLECTION: chunks})
    monkeypatch.setattr(sparse_mod, "_get_db", lambda: db)

    out = await sparse_search("q", filters, k=5)
    assert segs.aggregate_calls == []
    # legacy pipeline uses legacy text index
    pipeline = chunks.aggregate_calls[0][0][0]
    assert pipeline[0]["$search"]["index"] == sparse_mod.LEGACY_TEXT_INDEX
    assert out == [("cA", "cA", 1.1)]


async def test_drops_rows_missing_ids(monkeypatch, filters):
    segs = FakeAggCollection(
        aggregate_docs=[
            {"segment_id": "", "parent_chunk_id": "p1", "score": 1.0},
            {"segment_id": "s2", "parent_chunk_id": "", "score": 0.9},
            {"segment_id": "s3", "parent_chunk_id": "p3", "score": 0.8},
        ],
        find_one_doc={"_id": "stub"},
    )
    db = FakeDB({SEGMENTS_COLLECTION: segs})
    monkeypatch.setattr(sparse_mod, "_get_db", lambda: db)

    out = await sparse_search("q", filters, k=5)
    assert out == [("s3", "p3", 0.8)]


async def test_legacy_failure_returns_empty(monkeypatch, filters):
    segs = FakeAggCollection(find_one_doc=None)

    class ExplodingChunks:
        def aggregate(self, *a, **kw):
            class _Boom:
                def __aiter__(self):
                    return self

                async def __anext__(self):
                    raise RuntimeError("text index missing")

            return _Boom()

        async def find_one(self, *a, **kw):
            return None

    db = FakeDB({SEGMENTS_COLLECTION: segs, CHUNKS_COLLECTION: ExplodingChunks()})
    monkeypatch.setattr(sparse_mod, "_get_db", lambda: db)
    assert await sparse_search("q", filters, k=5) == []
