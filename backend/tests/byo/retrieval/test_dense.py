"""Tests for byo.retrieval.rankers.dense.dense_search.

Tests cover the three retrieval paths:
  1. Qdrant (primary) — via mocked search_vectors
  2. Mongo cosine fallback — via FakeDB with find()
  3. Both fail → returns []
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest

from byo.retrieval.rankers import dense as dense_mod
from byo.retrieval.rankers.dense import dense_search
from byo.shared.results import SearchFilters

pytestmark = pytest.mark.asyncio


@pytest.fixture
def embedding():
    v = [0.0] * 1536
    v[0] = 1.0  # unit vector for predictable cosine
    return v


@pytest.fixture
def filters():
    return SearchFilters(user_id="u-1", collection_id="c-1")


# ── Helpers ──────────────────────────────────────────────────────────────

class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)
    def __aiter__(self):
        return self
    async def __anext__(self):
        if not self._docs:
            raise StopAsyncIteration
        return self._docs.pop(0)


class FakeCollection:
    def __init__(self, docs=None):
        self._docs = list(docs or [])

    async def find_one(self, *a, **kw):
        return self._docs[0] if self._docs else None

    def find(self, query=None, projection=None):
        return FakeCursor(self._docs)

    def aggregate(self, pipeline):
        return FakeCursor([])  # $vectorSearch returns empty (no Atlas index)


class FakeDB:
    def __init__(self, collections=None):
        self._c = collections or {}
    def __getitem__(self, name):
        return self._c.get(name, FakeCollection())
    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]


def _make_segment(sid, pid, emb, user="u-1", cid="c-1"):
    return {
        "segment_id": sid,
        "parent_chunk_id": pid,
        "embedding": emb,
        "user_id": user,
        "collection_id": cid,
    }


# ── Path 1: Qdrant happy path ───────────────────────────────────────────

async def test_qdrant_returns_hits(monkeypatch, embedding, filters):
    def mock_search(query_vector, **kw):
        return [("s1", "p1", 0.95), ("s2", "p2", 0.80)]
    monkeypatch.setattr("byo.shared.qdrant.search_vectors", mock_search)
    out = await dense_search(embedding, filters, k=5)
    assert out == [("s1", "p1", 0.95), ("s2", "p2", 0.80)]


async def test_qdrant_passes_filters(monkeypatch, embedding, filters):
    calls = []
    def mock_search(query_vector, **kw):
        calls.append(kw)
        return [("s1", "p1", 0.9)]
    monkeypatch.setattr("byo.shared.qdrant.search_vectors", mock_search)
    await dense_search(embedding, filters, k=3)
    assert calls[0]["user_id"] == "u-1"
    assert calls[0]["collection_id"] == "c-1"
    assert calls[0]["limit"] == 3


async def test_qdrant_score_threshold(monkeypatch, embedding, filters):
    calls = []
    def mock_search(query_vector, **kw):
        calls.append(kw)
        return []
    monkeypatch.setattr("byo.shared.qdrant.search_vectors", mock_search)
    monkeypatch.setattr(dense_mod, "_get_db", lambda: FakeDB())
    await dense_search(embedding, filters, k=3, min_score=0.5)
    assert calls[0]["score_threshold"] == 0.5


# ── Path 2: Qdrant empty → Mongo cosine fallback ────────────────────────

async def test_qdrant_empty_falls_to_cosine(monkeypatch, embedding, filters):
    monkeypatch.setattr("byo.shared.qdrant.search_vectors", lambda **kw: [])

    # Set up Mongo with segments that have embeddings
    seg = _make_segment("s1", "p1", embedding)
    db = FakeDB({"byo_segments": FakeCollection([seg])})
    monkeypatch.setattr(dense_mod, "_get_db", lambda: db)

    out = await dense_search(embedding, filters, k=3, min_score=0.0)
    assert len(out) == 1
    assert out[0][0] == "s1"
    assert out[0][2] > 0.99  # self-similarity ≈ 1.0


async def test_cosine_respects_min_score(monkeypatch, embedding, filters):
    monkeypatch.setattr("byo.shared.qdrant.search_vectors", lambda **kw: [])

    low_vec = [0.0] * 1536
    low_vec[1] = 1.0  # orthogonal to query → cosine ≈ 0
    seg = _make_segment("s1", "p1", low_vec)
    db = FakeDB({"byo_segments": FakeCollection([seg])})
    monkeypatch.setattr(dense_mod, "_get_db", lambda: db)

    out = await dense_search(embedding, filters, k=3, min_score=0.5)
    assert out == []  # orthogonal vector below threshold


async def test_cosine_returns_sorted_by_score(monkeypatch, embedding, filters):
    monkeypatch.setattr("byo.shared.qdrant.search_vectors", lambda **kw: [])

    v_high = list(embedding)  # identical → score ≈ 1.0
    v_mid = [0.0] * 1536
    v_mid[0] = 0.7; v_mid[1] = 0.714  # cosine with [1,0,...] ≈ 0.7
    db = FakeDB({"byo_segments": FakeCollection([
        _make_segment("slow", "p_slow", v_mid),
        _make_segment("fast", "p_fast", v_high),
    ])})
    monkeypatch.setattr(dense_mod, "_get_db", lambda: db)

    out = await dense_search(embedding, filters, k=5, min_score=0.0)
    assert out[0][0] == "fast"  # higher score first


# ── Path 3: Everything fails → [] ───────────────────────────────────────

async def test_all_fail_returns_empty(monkeypatch, embedding, filters):
    def boom(**kw):
        raise RuntimeError("qdrant down")
    monkeypatch.setattr("byo.shared.qdrant.search_vectors", boom)
    # FakeDB with no find() → cosine fallback also fails
    monkeypatch.setattr(dense_mod, "_get_db", lambda: MagicMock())
    out = await dense_search(embedding, filters, k=3)
    assert out == []


# ── Input validation ────────────────────────────────────────────────────

async def test_empty_embedding_returns_empty(filters):
    out = await dense_search([], filters, k=3)
    assert out == []


async def test_missing_user_id_raises():
    with pytest.raises(ValueError, match="user_id"):
        await dense_search([0.1]*1536, SearchFilters(user_id=""), k=3)
