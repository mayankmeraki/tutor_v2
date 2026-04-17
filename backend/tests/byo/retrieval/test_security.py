"""Security tests: user_id is the non-negotiable boundary everywhere.

Most positive-path security is verified inside `test_filters.py` (every
`to_mongo()` carries user_id) and `test_dense.py`/`test_sparse.py` (both
rankers pipe `filters.to_mongo()` straight into the $vectorSearch filter
or the post-`$search` $match — so the same invariant holds).

This file adds cross-user leakage tests: a Mongo double seeded with docs
from two users asserts that a search with user_A never returns user_B's
docs, even when `collection_id` matches."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from byo.retrieval import service as svc_mod
from byo.retrieval.rankers import dense as dense_mod
from byo.retrieval.rankers import sparse as sparse_mod
from byo.retrieval.service import search
from byo.shared.results import SearchFilters

from .conftest import AsyncDocsCursor, FakeAggCollection, FakeDB


pytestmark = pytest.mark.asyncio


class FilteringAggCollection:
    """Mongo-collection double whose aggregate() *actually* applies the
    service's user-scoped filter by honouring the pipeline's $match stage
    (for sparse) or $vectorSearch filter (for dense).

    Seeded with a raw list of docs from multiple users; tests assert that
    a cross-user search leaks nothing.
    """

    def __init__(self, docs):
        self._docs = list(docs)
        self.find_one_doc = self._docs[0] if self._docs else None

    async def find_one(self, *a, **kw):
        return self.find_one_doc

    def aggregate(self, pipeline, *a, **kw):
        # Extract filter from first stage
        filt = {}
        stage0 = pipeline[0]
        if "$vectorSearch" in stage0:
            filt = stage0["$vectorSearch"].get("filter") or {}
        # Also look for a $match stage (sparse)
        for s in pipeline:
            if "$match" in s:
                filt = s["$match"]
                break

        filtered = [d for d in self._docs if _matches(d, filt)]
        return AsyncDocsCursor(filtered)

    def find(self, *a, **kw):
        # find(filter, proj, sort=...) — first positional is filter
        if a:
            filt = a[0] or {}
        else:
            filt = {}
        filtered = [d for d in self._docs if _matches(d, filt)]
        return AsyncDocsCursor(filtered)


def _matches(doc: dict, filt: dict) -> bool:
    """Minimal $eq / $in filter matcher — enough for user/collection/resource."""
    for k, v in filt.items():
        if k.startswith("$"):
            # skip $or/$and for this naive matcher
            continue
        doc_v = doc.get(k)
        if isinstance(v, dict) and "$in" in v:
            if doc_v not in v["$in"]:
                return False
        else:
            if doc_v != v:
                return False
    return True


async def test_dense_ranker_excludes_other_users(monkeypatch):
    """Dense: Qdrant receives user_id in the filter, so only user_A's
    segments are returned — user_B's are excluded at the Qdrant layer."""
    calls = []
    def mock_search(query_vector, **kw):
        calls.append(kw)
        # Simulate Qdrant correctly filtering — only user_A's segment
        if kw.get("user_id") == "user_A":
            return [("s_a1", "p_a1", 0.9)]
        return [("s_b1", "p_b1", 0.95)]
    monkeypatch.setattr("byo.shared.qdrant.search_vectors", mock_search)

    filters = SearchFilters(user_id="user_A", collection_id="shared")
    out = await dense_mod.dense_search([0.1] * 8, filters, k=5)

    seg_ids = [sid for sid, _, _ in out]
    assert "s_a1" in seg_ids
    assert "s_b1" not in seg_ids
    # Verify user_id was actually passed to Qdrant
    assert calls[0]["user_id"] == "user_A"


async def test_sparse_ranker_excludes_other_users(monkeypatch):
    segs = FilteringAggCollection(
        [
            {
                "segment_id": "s_a1",
                "parent_chunk_id": "p_a1",
                "score": 1.0,
                "user_id": "user_A",
                "collection_id": "shared",
            },
            {
                "segment_id": "s_b1",
                "parent_chunk_id": "p_b1",
                "score": 2.0,
                "user_id": "user_B",
                "collection_id": "shared",
            },
        ]
    )
    db = FakeDB({"byo_segments": segs})
    monkeypatch.setattr(sparse_mod, "_get_db", lambda: db)

    filters = SearchFilters(user_id="user_A", collection_id="shared")
    out = await sparse_mod.sparse_search("query", filters, k=5)
    seg_ids = [sid for sid, _, _ in out]
    assert "s_a1" in seg_ids
    assert "s_b1" not in seg_ids


async def test_service_search_excludes_other_users(monkeypatch):
    """End-to-end: search with user_A only returns user_A's content,
    even though user_B has content in the same collection."""
    import app.services.content.embedding_service as es
    from byo.shared._memory_store import MemoryContentStore
    import byo.shared.store as store_mod

    _emb = [0.0] * 1536; _emb[0] = 1.0
    monkeypatch.setattr(es, "generate_embedding", AsyncMock(return_value=_emb))

    mem = MemoryContentStore()
    # Both users have content in same collection
    await mem.upsert(resource_id="r_a", collection_id="shared", user_id="user_A",
        resource_name="a.pdf",
        parents=[{"chunk_id": "p_a1", "content": "A's content", "index": 0, "anchor": {}, "topics": [], "labels": []}],
        segments=[{"segment_id": "s_a1", "parent_chunk_id": "p_a1", "content": "A's content",
            "embedding": _emb, "anchor": {}, "topics": [], "index": 0, "modality": "", "retrieval_mode": ""}])
    await mem.upsert(resource_id="r_b", collection_id="shared", user_id="user_B",
        resource_name="b.pdf",
        parents=[{"chunk_id": "p_b1", "content": "B's content", "index": 0, "anchor": {}, "topics": [], "labels": []}],
        segments=[{"segment_id": "s_b1", "parent_chunk_id": "p_b1", "content": "B's content",
            "embedding": _emb, "anchor": {}, "topics": [], "index": 0, "modality": "", "retrieval_mode": ""}])
    monkeypatch.setattr(store_mod, "_store", mem)

    out = await search(
        "q", user_id="user_A", collection_id="shared", k=5, rerank=False,
    )
    contents = " ".join(h.content for h in out)
    assert "B's content" not in contents
    assert any(h.chunk_id == "p_a1" for h in out)


async def test_fetch_is_user_scoped(monkeypatch):
    """fetch('chunk:p_b1', user_id='user_A') must not return user_B's chunk."""
    from byo.shared._memory_store import MemoryContentStore
    import byo.shared.store as store_mod

    _emb = [0.0] * 1536; _emb[0] = 1.0
    mem = MemoryContentStore()
    await mem.upsert(resource_id="r_b", collection_id="shared", user_id="user_B",
        resource_name="b.pdf",
        parents=[{"chunk_id": "p_b1", "content": "B secret", "index": 0, "anchor": {}, "topics": [], "labels": []}],
        segments=[{"segment_id": "s_b1", "parent_chunk_id": "p_b1", "content": "B secret",
            "embedding": _emb, "anchor": {}, "topics": [], "index": 0, "modality": "", "retrieval_mode": ""}])
    monkeypatch.setattr(store_mod, "_store", mem)
    from byo.retrieval.service import fetch

    out = await fetch("chunk:p_b1", user_id="user_A")
    assert out is None


async def test_dense_filter_includes_user_id_in_qdrant_call(monkeypatch):
    """Belt-and-braces: user_id is always passed to Qdrant search."""
    calls = []
    def mock_search(query_vector, **kw):
        calls.append(kw)
        return []
    monkeypatch.setattr("byo.shared.qdrant.search_vectors", mock_search)
    monkeypatch.setattr(dense_mod, "_get_db", lambda: MagicMock())

    await dense_mod.dense_search(
        [0.1],
        SearchFilters(user_id="user_A", collection_id="c"),
        k=5,
    )
    assert calls[0]["user_id"] == "user_A"


async def test_sparse_filter_includes_user_id_in_pipeline(monkeypatch):
    segs = FakeAggCollection(aggregate_docs=[], find_one_doc={"_id": "x"})
    db = FakeDB({"byo_segments": segs})
    monkeypatch.setattr(sparse_mod, "_get_db", lambda: db)

    await sparse_mod.sparse_search(
        "q",
        SearchFilters(user_id="user_A", collection_id="c"),
        k=5,
    )
    pipeline = segs.aggregate_calls[0][0][0]
    match = next(s["$match"] for s in pipeline if "$match" in s)
    assert match["user_id"] == "user_A"
