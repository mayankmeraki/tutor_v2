"""Fixtures and helpers for byo.retrieval unit tests.

The BYO package lives one directory above `backend/` (i.e. at the mockup
repo root). At runtime `app.main` prepends that path to `sys.path`; for
tests we do the same here so `import byo.*` resolves.
"""

from __future__ import annotations

import os
import sys

# Ensure mockup repo root is importable for `byo.*` packages
_repo_root = os.path.dirname(
    os.path.dirname(  # backend/
        os.path.dirname(  # backend/tests/
            os.path.dirname(  # backend/tests/byo/
                os.path.dirname(os.path.abspath(__file__))
            )
        )
    )
)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import pytest


# Use in-memory content store for all retrieval tests — no Qdrant, no Mongo.
@pytest.fixture(autouse=True)
def _use_memory_store(monkeypatch):
    """Inject MemoryContentStore so tests don't hit real Qdrant or Mongo."""
    from byo.shared._memory_store import MemoryContentStore
    import byo.shared.store as store_mod
    import byo.shared.qdrant as qdrant_mod

    mem_store = MemoryContentStore()
    monkeypatch.setattr(store_mod, "_store", mem_store)
    monkeypatch.setattr(qdrant_mod, "get_qdrant_client", lambda: None)


# ---------------------------------------------------------------------------
# Async Mongo cursor / collection / database helpers
# ---------------------------------------------------------------------------


class AsyncDocsCursor:
    """Async iterator over a fixed list of docs, used as the return of
    `collection.aggregate(...)` or `collection.find(...)` in the mocks.

    Supports chained `.sort()` / `.limit()` calls (no-ops for assertion
    purposes — tests verify the pipeline we feed to `aggregate`, not
    that sort/limit are re-applied client-side).
    """

    def __init__(self, docs):
        self._docs = list(docs)

    # chainables
    def sort(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    # async iter
    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._docs):
            raise StopAsyncIteration
        doc = self._docs[self._idx]
        self._idx += 1
        return doc


class FakeAggCollection:
    """Minimal Motor-collection double supporting find/find_one/aggregate.

    Callers pre-seed per-method return values; every call also records
    the positional args/kwargs so tests can assert pipelines & filters.
    """

    def __init__(
        self,
        *,
        aggregate_docs=None,
        find_docs=None,
        find_one_doc=None,
    ):
        self.aggregate_docs = list(aggregate_docs or [])
        self.find_docs = list(find_docs or [])
        self.find_one_doc = find_one_doc

        self.aggregate_calls: list[tuple[tuple, dict]] = []
        self.find_calls: list[tuple[tuple, dict]] = []
        self.find_one_calls: list[tuple[tuple, dict]] = []

    def aggregate(self, pipeline, *args, **kwargs):
        self.aggregate_calls.append(((pipeline, *args), kwargs))
        return AsyncDocsCursor(self.aggregate_docs)

    def find(self, *args, **kwargs):
        self.find_calls.append((args, kwargs))
        return AsyncDocsCursor(self.find_docs)

    async def find_one(self, *args, **kwargs):
        self.find_one_calls.append((args, kwargs))
        return self.find_one_doc


class FakeDB:
    """Dict-like DB double returning FakeAggCollection instances.

    Preferred usage: pass a mapping {collection_name: FakeAggCollection}.
    Also supports attribute-style access (`db.byo_chunks`) by proxying
    to the same mapping.
    """

    def __init__(self, collections=None):
        self._collections: dict[str, FakeAggCollection] = dict(collections or {})

    def __getitem__(self, name: str) -> FakeAggCollection:
        if name not in self._collections:
            self._collections[name] = FakeAggCollection()
        return self._collections[name]

    def __getattr__(self, name: str):
        # only called when attribute isn't a regular one
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]
