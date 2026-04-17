"""Integration fixtures for BYO end-to-end tests.

Extends the FakeDB from backend/tests/byo/processing/conftest.py with
Atlas aggregation-stage simulations ($vectorSearch + $search) so the full
retrieval pipeline can run against an in-memory Mongo.

The simulations aren't ranking-quality — they're plumbing-quality:

  $vectorSearch: match on cosine-overlap between query vector and doc
                 embedding. Since tests use tiny bag-of-words vectors
                 this is effectively term overlap.
  $search      : bag-of-words overlap against the `content` / `topics`
                 fields using the same term index.

Good enough to test that data flows through ingestion → dense+sparse →
fusion → parent expansion → citation-formatted output.

No real httpx calls: Haiku (question generation), embeddings, and Cohere
rerank are all stubbed out at module level via autouse fixtures.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

# Repo root (three levels up from backend/tests/integration/byo/) so
# `import byo.*` resolves.
_here = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_here, "..", "..", "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


# ── Shared tokeniser + vectoriser ─────────────────────────────────────────

_TOKEN_RE = re.compile(r"[A-Za-z]{2,}")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _fake_embed(text: str, dim: int = 128) -> list[float]:
    """Stable bag-of-words-ish vector.

    Each token increments a bucket picked by the token's MD5 hash. The
    resulting vector carries term identity (for overlap-based dense
    search simulation) without needing an embedding API.
    """
    vec = [0.0] * dim
    for tok in _tokens(text):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    # L2 normalize so dot product ≈ cosine similarity
    n = sum(v * v for v in vec) ** 0.5
    if n > 0:
        vec = [v / n for v in vec]
    return vec


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    m = min(len(a), len(b))
    return sum(a[i] * b[i] for i in range(m))


# A tiny English stopword set — filters the words that otherwise dominate
# bag-of-words overlap scores and ruin ranking.
_STOPWORDS = {
    "the", "is", "at", "of", "on", "and", "a", "an", "to", "in", "for",
    "with", "as", "by", "from", "that", "this", "it", "be", "or", "are",
    "was", "were", "which", "what", "how", "who", "when", "where", "why",
    "can", "do", "does", "did", "has", "have", "had", "i", "you", "he",
    "she", "we", "they", "them", "us", "our", "your", "his", "her",
    "its", "not", "but", "if", "so", "than", "then", "there", "here",
    "each", "some", "such", "into", "more", "most", "all", "any", "one",
    "two", "three", "about",
}


def _bm25ish(
    query: str,
    text: str,
    topics: list[str] | None = None,
    *,
    idf: dict[str, float] | None = None,
    avg_len: float = 100.0,
) -> float:
    """BM25-style sparse score with IDF + length normalization.

    `idf` is computed over the corpus for query terms only (see
    `_stage_search`). When not provided (isolated unit tests), falls
    back to a uniform weight of 1.0 per term. Stopwords are filtered.

    Rare terms dominate — this is the whole point of IDF. Without it,
    tests that query "antonym of protagonist" got outranked by long
    documents that matched "of" many times.
    """
    q_tokens = {t for t in _tokens(query) if t not in _STOPWORDS}
    if not q_tokens:
        return 0.0

    c_tokens = _tokens(text)
    if not c_tokens:
        return 0.0
    c_len = len(c_tokens)

    k1, b = 1.5, 0.75
    score = 0.0
    for t in q_tokens:
        tf = c_tokens.count(t)
        if tf == 0:
            continue
        w = (idf or {}).get(t, 1.0)
        # BM25 term score
        score += w * tf * (k1 + 1) / (tf + k1 * (1 - b + b * c_len / max(avg_len, 1)))

    # Topic boost — still helpful.
    for top in (topics or []):
        for tt in _tokens(top):
            if tt in q_tokens:
                score += (idf or {}).get(tt, 1.0) * 0.5

    return score


# ── Fake Mongo with Atlas-stage simulations ───────────────────────────────


class FakeCursor:
    def __init__(self, docs: list[dict]):
        self._docs = list(docs)

    def sort(self, *args, **kwargs):
        # Best-effort: support sort by list of (key, dir) tuples.
        if args and isinstance(args[0], list):
            for key, direction in reversed(args[0]):
                self._docs.sort(
                    key=lambda d, k=key: _nested_get(d, k) if _nested_get(d, k) is not None else 0,
                    reverse=(direction == -1),
                )
        elif args and isinstance(args[0], str):
            key = args[0]
            direction = args[1] if len(args) > 1 else 1
            self._docs.sort(
                key=lambda d: _nested_get(d, key) if _nested_get(d, key) is not None else 0,
                reverse=(direction == -1),
            )
        return self

    def limit(self, n: int):
        self._docs = self._docs[:n]
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._docs:
            raise StopAsyncIteration
        return self._docs.pop(0)


def _nested_get(doc: dict, path: str):
    parts = path.split(".")
    cur: Any = doc
    for p in parts:
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    return cur


class FakeCollection:
    """Motor-collection double with enough breadth for the full pipeline.

    Supports: insert_one/many, find (sync, returning cursor), find_one,
    find_one_and_update, update_one (+upsert), delete_many, count_documents,
    create_index, aggregate (including $vectorSearch + $search simulations).
    """

    def __init__(self, name: str = ""):
        self.name = name
        self._docs: list[dict] = []

    # ── writes ────────────────────────────────────────────────────────
    async def insert_one(self, doc: dict):
        doc = dict(doc)
        doc.setdefault("_id", f"id_{len(self._docs)}")
        self._docs.append(doc)
        result = MagicMock()
        result.inserted_id = doc["_id"]
        return result

    async def insert_many(self, docs: list[dict], *args, **kwargs):
        for d in docs:
            await self.insert_one(d)
        result = MagicMock()
        result.inserted_ids = [d["_id"] for d in self._docs[-len(docs):]]
        return result

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

    async def find_one_and_update(self, query, update, sort=None, return_document=False, **kwargs):
        for d in self._docs:
            if self._match(d, query):
                if "$set" in update:
                    d.update(update["$set"])
                return dict(d)
        return None

    async def delete_many(self, query):
        before = len(self._docs)
        self._docs = [d for d in self._docs if not self._match(d, query)]
        result = MagicMock()
        result.deleted_count = before - len(self._docs)
        return result

    async def create_index(self, *args, **kwargs):
        return "fake_index"

    # ── reads ─────────────────────────────────────────────────────────
    def _match(self, doc: dict, query: dict) -> bool:
        for k, v in query.items():
            if k == "$or":
                if not any(self._match(doc, sub) for sub in v):
                    return False
                continue
            if k == "$and":
                if not all(self._match(doc, sub) for sub in v):
                    return False
                continue
            if k.startswith("$"):
                continue
            dv = _nested_get(doc, k)
            if isinstance(v, dict):
                for op, opv in v.items():
                    if op == "$in":
                        if dv not in opv:
                            return False
                    elif op == "$lt":
                        if dv is None or not (dv < opv):
                            return False
                    elif op == "$lte":
                        if dv is None or not (dv <= opv):
                            return False
                    elif op == "$gt":
                        if dv is None or not (dv > opv):
                            return False
                    elif op == "$gte":
                        if dv is None or not (dv >= opv):
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

    async def find_one(self, query: dict = None, projection=None, sort=None):
        query = query or {}
        matched = [d for d in self._docs if self._match(d, query)]
        if sort:
            key, direction = sort[0]
            matched.sort(
                key=lambda d: _nested_get(d, key) if _nested_get(d, key) is not None else 0,
                reverse=(direction == -1),
            )
        if not matched:
            return None
        return dict(matched[0])

    def find(self, query: dict = None, projection=None, sort=None):
        query = query or {}
        matched = [dict(d) for d in self._docs if self._match(d, query)]
        cursor = FakeCursor(matched)
        if sort:
            cursor.sort(sort)
        return cursor

    async def count_documents(self, query):
        return sum(1 for d in self._docs if self._match(d, query))

    # ── aggregation (inc. Atlas $vectorSearch / $search) ──────────────
    def aggregate(self, pipeline):
        docs = [dict(d) for d in self._docs]
        for stage in pipeline:
            if "$vectorSearch" in stage:
                docs = self._stage_vector_search(docs, stage["$vectorSearch"])
            elif "$search" in stage:
                docs = self._stage_search(docs, stage["$search"])
            elif "$match" in stage:
                docs = [d for d in docs if self._match(d, stage["$match"])]
            elif "$project" in stage:
                # Shallow project: pass-through; we rely on existing fields.
                # Compute $meta scores requested by retrieval rankers.
                proj = stage["$project"]
                out = []
                for d in docs:
                    nd = dict(d)
                    for k, spec in proj.items():
                        if isinstance(spec, dict) and "$meta" in spec:
                            meta_kind = spec["$meta"]
                            if meta_kind == "vectorSearchScore":
                                nd["score"] = d.get("_score", 0.0)
                            elif meta_kind == "searchScore":
                                nd["score"] = d.get("_score", 0.0)
                    out.append(nd)
                docs = out
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
                bucket: dict[Any, dict] = {}
                for d in docs:
                    key = d.get(by.lstrip("$")) if isinstance(by, str) and by.startswith("$") else None
                    if key not in bucket:
                        bucket[key] = {"_id": key}
                        for gk, gspec in group.items():
                            if gk == "_id":
                                continue
                            if isinstance(gspec, dict) and "$sum" in gspec:
                                bucket[key][gk] = 0
                    for gk, gspec in group.items():
                        if gk == "_id":
                            continue
                        if isinstance(gspec, dict) and "$sum" in gspec:
                            incr = gspec["$sum"]
                            if isinstance(incr, (int, float)):
                                bucket[key][gk] += incr
                            else:
                                bucket[key][gk] += 1
                docs = list(bucket.values())
            elif "$sort" in stage:
                sort_spec = stage["$sort"]
                for k, direction in reversed(list(sort_spec.items())):
                    docs.sort(
                        key=lambda d, kk=k: _nested_get(d, kk) if _nested_get(d, kk) is not None else 0,
                        reverse=(direction == -1),
                    )
            elif "$limit" in stage:
                docs = docs[: stage["$limit"]]
        return FakeCursor(docs)

    # ── Atlas stage simulations ───────────────────────────────────────
    def _stage_vector_search(self, docs: list[dict], spec: dict) -> list[dict]:
        q_vec: list[float] = spec.get("queryVector") or []
        mongo_filter: dict = spec.get("filter") or {}
        limit: int = int(spec.get("limit") or 10)
        scored: list[tuple[float, dict]] = []
        for d in docs:
            if not self._match(d, mongo_filter):
                continue
            emb = d.get("embedding")
            if not emb:
                continue
            s = _cosine(q_vec, emb)
            if s <= 0:
                continue
            nd = dict(d)
            nd["_score"] = s
            scored.append((s, nd))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:limit]]

    def _stage_search(self, docs: list[dict], spec: dict) -> list[dict]:
        import math

        compound = spec.get("compound") or {}
        should = compound.get("should") or []
        if not should:
            return []
        query_str = None
        for clause in should:
            t = clause.get("text") or {}
            q = t.get("query")
            if q:
                query_str = q
                break
        if not query_str:
            return []

        # Compute IDF for query terms across the (filtered) corpus.
        q_tokens = {t for t in _tokens(query_str) if t not in _STOPWORDS}
        if not q_tokens:
            return []
        N = max(len(docs), 1)
        df: dict[str, int] = {t: 0 for t in q_tokens}
        total_len = 0
        for d in docs:
            doc_tokens = _tokens(d.get("content") or "")
            total_len += len(doc_tokens)
            seen = set(doc_tokens)
            for t in q_tokens:
                if t in seen:
                    df[t] += 1
        idf = {
            t: math.log(((N - df[t] + 0.5) / (df[t] + 0.5)) + 1.0)
            for t in q_tokens
        }
        avg_len = total_len / N if N else 100.0

        scored: list[tuple[float, dict]] = []
        for d in docs:
            content = d.get("content") or ""
            topics = d.get("topics") or []
            s = _bm25ish(query_str, content, topics, idf=idf, avg_len=avg_len)
            if s <= 0:
                continue
            nd = dict(d)
            nd["_score"] = s
            scored.append((s, nd))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored]


class FakeDatabase:
    def __init__(self):
        self._collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self._collections:
            self._collections[name] = FakeCollection(name)
        return self._collections[name]

    def __getattr__(self, name: str) -> FakeCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def fake_db(monkeypatch):
    """A single FakeDatabase threaded into everything that calls get_mongo_db()
    — indexer, retrieval service, retrieval rankers, filters helpers.

    Also injects a MemoryContentStore as the BYO content store so the
    retrieval service uses it instead of Qdrant.
    """
    db = FakeDatabase()

    def _get_db():
        return db

    # Patch Mongo access for operational data (indexer writes, resource lookups)
    import byo.processing.indexer as indexer_mod
    import app.core.mongodb as mongo_mod

    monkeypatch.setattr(indexer_mod, "_get_db", _get_db)
    monkeypatch.setattr(mongo_mod, "get_mongo_db", _get_db)

    # Inject MemoryContentStore for retrieval
    from byo.shared._memory_store import MemoryContentStore
    import byo.shared.store as store_mod
    mem_store = MemoryContentStore()
    monkeypatch.setattr(store_mod, "_store", mem_store)

    # Disable Qdrant client
    import byo.shared.qdrant as qdrant_mod
    monkeypatch.setattr(qdrant_mod, "get_qdrant_client", lambda: None)

    return db


@pytest.fixture(autouse=True)
def _mock_external_apis(monkeypatch):
    """Stub out Haiku (question generation), OpenAI embeddings, Cohere rerank.

    Every network call is replaced with a deterministic in-process fn so the
    pipeline exercises wiring, not network behavior.
    """
    # 1) Embedding service (used by service.search)
    async def _fake_service_embed(text: str):
        return _fake_embed(text)

    import app.services.content.embedding_service as emb_mod
    monkeypatch.setattr(emb_mod, "generate_embedding", _fake_service_embed)

    # 2) Embedder question generation + embedding batch
    async def _fake_gen_questions(segments):
        for s in segments:
            # Generate one plausible question to exercise the branch.
            s["questions"] = [f"What is {(s.get('content') or '')[:40]}?"]

    async def _fake_embed_batch(texts):
        return [_fake_embed(t) for t in texts]

    import byo.processing.embedder as embedder_mod
    monkeypatch.setattr(embedder_mod, "_generate_questions", _fake_gen_questions)
    monkeypatch.setattr(embedder_mod, "_generate_embeddings", _fake_embed_batch)

    # 3) Cohere rerank — no-op preserving order
    async def _passthrough_rerank(query, hits, top_n):
        return hits[:top_n]

    import byo.retrieval.rerank as rerank_mod
    monkeypatch.setattr(rerank_mod, "cohere_rerank", _passthrough_rerank)

    # 4) HyDE — return query unchanged (no OpenRouter call)
    async def _noop_hyde(q):
        return q

    import byo.retrieval.query as query_mod
    monkeypatch.setattr(query_mod, "hyde_expand", _noop_hyde)


# ── Re-exports for test bodies ────────────────────────────────────────────

__all__ = [
    "FakeDatabase",
    "FakeCollection",
    "_fake_embed",
    "_tokens",
]
