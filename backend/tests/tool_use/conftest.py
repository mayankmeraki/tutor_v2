"""Fixtures for tool-use tests.

We reuse the integration/byo/conftest fakes (FakeDatabase + stubbed external
APIs) by bouncing through it. The tool tests go through execute_tutor_tool,
which calls into byo.retrieval.service, so the fake_db fixture has to patch
the same helpers.
"""

from __future__ import annotations

import os
import sys

import pytest

# Repo root for byo.*
_here = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_here, "..", "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


# Reuse the integration fake DB / stubs so tool handlers exercise the same
# wiring path.
from tests.integration.byo.conftest import (  # noqa: E402 (after sys.path tweak)
    FakeDatabase,
    _fake_embed,
)


@pytest.fixture
def fake_db(monkeypatch):
    db = FakeDatabase()

    def _get_db():
        return db

    import byo.processing.indexer as indexer_mod
    import app.core.mongodb as mongo_mod

    monkeypatch.setattr(indexer_mod, "_get_db", _get_db)
    monkeypatch.setattr(mongo_mod, "get_mongo_db", _get_db)
    return db


@pytest.fixture(autouse=True)
def _mock_external_apis(monkeypatch):
    """Stub Haiku, embeddings, Cohere — mirrors integration conftest."""
    # Return the same unit vector as seed data so cosine = 1.0
    _fixed = [0.0] * 1536; _fixed[0] = 1.0
    async def _fake_service_embed(text: str):
        return _fixed

    import app.services.content.embedding_service as emb_mod
    monkeypatch.setattr(emb_mod, "generate_embedding", _fake_service_embed)

    async def _fake_gen_questions(segments):
        for s in segments:
            s["questions"] = [f"What is {(s.get('content') or '')[:40]}?"]

    async def _fake_embed_batch(texts):
        return [_fake_embed(t) for t in texts]

    import byo.processing.embedder as embedder_mod
    monkeypatch.setattr(embedder_mod, "_generate_questions", _fake_gen_questions)
    monkeypatch.setattr(embedder_mod, "_generate_embeddings", _fake_embed_batch)

    async def _passthrough_rerank(query, hits, top_n):
        return hits[:top_n]

    import byo.retrieval.rerank as rerank_mod
    monkeypatch.setattr(rerank_mod, "cohere_rerank", _passthrough_rerank)

    async def _noop_hyde(q):
        return q

    import byo.retrieval.query as query_mod
    monkeypatch.setattr(query_mod, "hyde_expand", _noop_hyde)

    # Inject MemoryContentStore with seed data for tool tests
    from byo.shared._memory_store import MemoryContentStore
    import byo.shared.store as store_mod
    import asyncio

    mem_store = MemoryContentStore()

    # Seed with test data so search/fetch/list return results
    _emb = [0.0] * 1536; _emb[0] = 1.0
    asyncio.get_event_loop().run_until_complete(mem_store.upsert(
        resource_id="r-test", collection_id="c-test", user_id="test@test.com",
        resource_name="test_notes.pdf",
        parents=[{
            "chunk_id": "p-test-1", "content": "Schrodinger equation describes quantum states",
            "index": 0, "anchor": {"page": 1}, "topics": ["quantum"], "labels": ["explanation"],
        }, {
            "chunk_id": "p-test-2", "content": "Eigenvalues of the Hamiltonian operator",
            "index": 1, "anchor": {"page": 2}, "topics": ["eigenvalue"], "labels": ["definition"],
        }],
        segments=[{
            "segment_id": "s-test-1", "parent_chunk_id": "p-test-1",
            "content": "Schrodinger equation describes quantum states", "embedding": _emb,
            "anchor": {"page": 1}, "topics": ["quantum"], "index": 0,
            "modality": "pdf_digital", "retrieval_mode": "exact_plus_semantic",
        }, {
            "segment_id": "s-test-2", "parent_chunk_id": "p-test-2",
            "content": "Eigenvalues of the Hamiltonian operator", "embedding": _emb,
            "anchor": {"page": 2}, "topics": ["eigenvalue"], "index": 1,
            "modality": "pdf_digital", "retrieval_mode": "exact_plus_semantic",
        }],
    ))

    monkeypatch.setattr(store_mod, "_store", mem_store)

    import byo.shared.qdrant as qdrant_mod
    monkeypatch.setattr(qdrant_mod, "get_qdrant_client", lambda: None)
