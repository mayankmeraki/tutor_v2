"""Tests for byo.retrieval.service — store-based architecture.

All tests use MemoryContentStore (injected via conftest autouse fixture).
No Qdrant, no Mongo, no network calls.
"""

from __future__ import annotations

import pytest

from byo.shared.store import set_content_store
from byo.shared._memory_store import MemoryContentStore
from byo.retrieval.service import (
    search, fetch, peek, nearby, list_contents, read_resource,
)

pytestmark = pytest.mark.asyncio


# ── Fixtures ─────────────────────────────────────────────────────────────

def _make_segment(sid, pid, content, emb=None, resource_id="r1",
                  resource_name="test.pdf", user_id="u1", cid="c1",
                  page=None, index=0, topics=None):
    if emb is None:
        emb = [0.0] * 1536
        emb[0] = 1.0
    return {
        "segment_id": sid,
        "parent_chunk_id": pid,
        "content": content,
        "embedding": emb,
        "resource_id": resource_id,
        "resource_name": resource_name,
        "user_id": user_id,
        "collection_id": cid,
        "modality": "pdf_digital",
        "retrieval_mode": "exact_plus_semantic",
        "anchor": {"page": page, "section": None},
        "topics": topics or [],
        "index": index,
    }


def _make_parent(pid, content, index=0, page=None, resource_id="r1",
                 topics=None, labels=None):
    return {
        "chunk_id": pid,
        "content": content,
        "index": index,
        "anchor": {"page": page},
        "resource_id": resource_id,
        "topics": topics or [],
        "labels": labels or [],
    }


@pytest.fixture
async def seeded_store():
    store = MemoryContentStore()
    set_content_store(store)

    parents = [
        _make_parent("p1", "Parent chunk about calculus derivatives", index=0, page=1,
                     topics=["calculus"], labels=["explanation"]),
        _make_parent("p2", "Parent chunk about integration by parts", index=1, page=3,
                     topics=["integration"]),
        _make_parent("p3", "Parent chunk about matrices", index=2, page=5,
                     topics=["linear_algebra"]),
    ]
    segments = [
        _make_segment("s1", "p1", "derivative of sin(x) is cos(x)", page=1, index=0,
                      topics=["calculus"]),
        _make_segment("s2", "p2", "integration by parts formula: integral u dv", page=3, index=1,
                      topics=["integration"]),
        _make_segment("s3", "p3", "matrix multiplication row by column", page=5, index=2,
                      topics=["linear_algebra"]),
    ]
    await store.upsert(
        resource_id="r1", collection_id="c1", user_id="u1",
        resource_name="math_notes.pdf", parents=parents, segments=segments,
    )
    return store


class TestSearch:
    async def test_empty_query_returns_empty(self, seeded_store):
        out = await search("", user_id="u1", scope="collection", collection_id="c1")
        assert out == []

    async def test_missing_user_raises(self, seeded_store):
        with pytest.raises(ValueError, match="user_id"):
            await search("test", user_id="", scope="collection", collection_id="c1")

    async def test_returns_results(self, seeded_store, monkeypatch):
        async def fake_embed(text):
            v = [0.0] * 1536; v[0] = 1.0; return v
        monkeypatch.setattr("app.services.content.embedding_service.generate_embedding", fake_embed)

        out = await search(
            "calculus", user_id="u1", scope="collection",
            collection_id="c1", k=3, rerank=False,
        )
        assert len(out) > 0
        assert out[0].resource_name == "math_notes.pdf"

    async def test_wrong_user_returns_empty(self, seeded_store, monkeypatch):
        async def fake_embed(text):
            v = [0.0] * 1536; v[0] = 1.0; return v
        monkeypatch.setattr("app.services.content.embedding_service.generate_embedding", fake_embed)

        out = await search(
            "calculus", user_id="other_user", scope="collection",
            collection_id="c1", k=3, rerank=False,
        )
        assert out == []


class TestFetch:
    async def test_fetch_by_chunk_id(self, seeded_store):
        hit = await fetch("chunk:p1", user_id="u1")
        assert hit is not None
        assert hit.resource_name == "math_notes.pdf"

    async def test_fetch_nonexistent_returns_none(self, seeded_store):
        hit = await fetch("chunk:nonexistent", user_id="u1")
        assert hit is None

    async def test_fetch_wrong_user_returns_none(self, seeded_store):
        hit = await fetch("chunk:p1", user_id="other")
        assert hit is None

    async def test_fetch_resource_ref(self, seeded_store):
        hit = await fetch("resource:r1", user_id="u1")
        assert hit is not None


class TestPeek:
    async def test_peek_returns_summary(self, seeded_store):
        out = await peek("chunk:p1", user_id="u1")
        assert out is not None
        assert "resource_name" in out
        assert "snippet" in out

    async def test_peek_missing(self, seeded_store):
        out = await peek("chunk:missing", user_id="u1")
        assert out is None


class TestNearby:
    async def test_returns_adjacent_chunks(self, seeded_store):
        out = await nearby("chunk:p2", user_id="u1", window=1)
        assert len(out) >= 2  # p1 + p2 at minimum

    async def test_missing_chunk_returns_empty(self, seeded_store):
        out = await nearby("chunk:missing", user_id="u1")
        assert out == []


class TestListContents:
    async def test_returns_grouped_by_resource(self, seeded_store):
        out = await list_contents("c1", user_id="u1", group_by="resource")
        assert len(out) > 0
        assert "resource" in out[0]
        assert "chunks" in out[0]

    async def test_wrong_user_returns_empty(self, seeded_store):
        out = await list_contents("c1", user_id="other", group_by="resource")
        assert out == []

    async def test_flat_list(self, seeded_store):
        out = await list_contents("c1", user_id="u1", group_by="none")
        assert len(out) == 3
        assert "ref" in out[0]


class TestReadResource:
    async def test_returns_all_chunks_in_order(self, seeded_store):
        out = await read_resource("r1", user_id="u1")
        assert len(out) == 3

    async def test_page_filter(self, seeded_store):
        out = await read_resource("r1", user_id="u1", page_start=3, page_end=5)
        pages = [c.anchor.page for c in out if c.anchor and c.anchor.page]
        assert all(3 <= p <= 5 for p in pages)

    async def test_wrong_user_returns_empty(self, seeded_store):
        out = await read_resource("r1", user_id="other")
        assert out == []
