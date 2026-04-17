"""Shared fixtures for BYO processing pipeline unit tests.

- Puts the repo root on sys.path so `import byo.*` resolves when pytest is
  invoked from `backend/`.
- Provides a FakeMongoDB with the subset of Motor-ish operations the
  indexer + orchestrator actually use (insert_many, delete_many,
  update_one, find_one, find_one_and_update, count_documents, aggregate).
- Overrides the global autouse `mock_mongodb` fixture from the parent
  conftest — our tests don't want the app.main import chain.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest

# Repo root (two levels up from backend/) so `byo` is importable.
_here = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_here, "..", "..", "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


# ── Disable LLM structure classifier in unit tests ────────────────────
# The real classifier would hit OpenRouter for every test case — expensive,
# slow, flaky. Tests target chunker LOGIC (paragraph packing, atomic-block
# preservation, anchor detection), not the LLM routing decision.
@pytest.fixture(autouse=True)
def _stub_structure_llm(monkeypatch):
    async def _unknown_structure(markdown):  # noqa: ARG001
        return {
            "structure": "unknown",
            "unit_hint": "",
            "recommended_granularity": "medium",
            "confidence": 0.0,
        }
    import byo.processing.structure as struct_mod
    monkeypatch.setattr(struct_mod, "classify_structure", _unknown_structure)


# ── Fake Mongo ────────────────────────────────────────────────────────

class FakeCursor:
    def __init__(self, docs: list[dict]):
        self._docs = list(docs)

    def sort(self, *args, **kwargs):
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._docs:
            raise StopAsyncIteration
        return self._docs.pop(0)


class FakeCollection:
    def __init__(self):
        self._docs: list[dict] = []

    async def insert_one(self, doc: dict):
        doc = dict(doc)
        doc.setdefault("_id", f"id_{len(self._docs)}")
        self._docs.append(doc)
        result = MagicMock()
        result.inserted_id = doc["_id"]
        return result

    async def insert_many(self, docs: list[dict], *args, **kwargs):
        # Accept optional ordered=False and other Motor kwargs.
        for d in docs:
            await self.insert_one(d)
        result = MagicMock()
        result.inserted_ids = [d["_id"] for d in self._docs[-len(docs):]]
        return result

    def _match(self, doc: dict, query: dict) -> bool:
        for k, v in query.items():
            if k == "$or":
                if not any(self._match(doc, sub) for sub in v):
                    return False
                continue
            if k.startswith("$"):
                continue
            dv = doc.get(k)
            if isinstance(v, dict):
                for op, opv in v.items():
                    if op == "$in":
                        if dv not in opv:
                            return False
                    elif op == "$lt":
                        if dv is None or not (dv < opv):
                            return False
                    elif op == "$gt":
                        if dv is None or not (dv > opv):
                            return False
                    elif op == "$ne":
                        if dv == opv:
                            return False
                    else:
                        return False
            else:
                if dv != v:
                    return False
        return True

    async def find_one(self, query: dict, projection=None):
        for d in self._docs:
            if self._match(d, query):
                return dict(d)
        return None

    def find(self, query: dict = None, projection=None):
        query = query or {}
        matched = [dict(d) for d in self._docs if self._match(d, query)]
        return FakeCursor(matched)

    async def find_one_and_update(self, query, update, sort=None, return_document=False, **kwargs):
        for d in self._docs:
            if self._match(d, query):
                if "$set" in update:
                    d.update(update["$set"])
                return dict(d)
        return None

    async def update_one(self, query, update, upsert=False):
        for d in self._docs:
            if self._match(d, query):
                if "$set" in update:
                    d.update(update["$set"])
                result = MagicMock()
                result.modified_count = 1
                result.matched_count = 1
                return result
        if upsert and "$set" in update:
            new = dict(query)
            new.update(update["$set"])
            await self.insert_one(new)
            result = MagicMock()
            result.modified_count = 0
            result.matched_count = 0
            result.upserted_id = "upsert_id"
            return result
        result = MagicMock()
        result.modified_count = 0
        result.matched_count = 0
        return result

    async def delete_many(self, query):
        before = len(self._docs)
        self._docs = [d for d in self._docs if not self._match(d, query)]
        result = MagicMock()
        result.deleted_count = before - len(self._docs)
        return result

    async def count_documents(self, query):
        return sum(1 for d in self._docs if self._match(d, query))

    def aggregate(self, pipeline):
        # Minimal aggregation for the orchestrator's topic extraction.
        docs = list(self._docs)
        for stage in pipeline:
            if "$match" in stage:
                docs = [d for d in docs if self._match(d, stage["$match"])]
            elif "$unwind" in stage:
                field = stage["$unwind"].lstrip("$")
                expanded = []
                for d in docs:
                    for v in d.get(field, []) or []:
                        nd = dict(d)
                        nd[field] = v
                        expanded.append(nd)
                docs = expanded
            elif "$group" in stage:
                group = stage["$group"]
                by = group["_id"]
                seen = {}
                for d in docs:
                    key = d.get(by.lstrip("$")) if isinstance(by, str) and by.startswith("$") else None
                    if key not in seen:
                        seen[key] = {"_id": key}
                docs = list(seen.values())
        return FakeCursor(docs)

    async def create_index(self, *args, **kwargs):
        pass


class FakeDatabase:
    def __init__(self):
        self._collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self._collections:
            self._collections[name] = FakeCollection()
        return self._collections[name]

    def __getattr__(self, name: str) -> FakeCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]


@pytest.fixture
def fake_mongo(monkeypatch):
    """Fresh in-memory Mongo patched into byo.processing modules."""
    db = FakeDatabase()

    def _get_db():
        return db

    # Patch both modules' local _get_db helpers.
    import byo.processing.indexer as indexer_mod
    import byo.processing.orchestrator as orch_mod
    monkeypatch.setattr(indexer_mod, "_get_db", _get_db)
    monkeypatch.setattr(orch_mod, "_get_db", _get_db)
    return db


@pytest.fixture(autouse=True)
def _override_parent_mongodb_patch(monkeypatch):
    """The repo-level conftest autouse-patches app.core.mongodb which
    imports the full backend app chain; we don't need that here. We still
    rely on the autouse from the parent for test isolation but stub it
    to a no-op inside this subtree.
    """
    # Nothing to do — the parent autouse fixture already provides a fake
    # tutor_db via patching; it won't collide with our get_mongo_db patch.
    yield
