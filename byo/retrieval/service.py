"""BYO retrieval service — public API.

All retrieval goes through the content store (Qdrant by default). The
service adds embedding, reranking, and HyDE on top. No direct DB access.

Public API:
  - search(query) → semantic search → rerank → ContentHit[]
  - fetch(ref) → resolve a ref to its full chunk
  - peek(ref) → cheap summary
  - nearby(ref, window) → sequential navigation
  - list_contents(collection_id) → inventory
  - read_resource(resource_id, pages) → raw page-level access

Every call requires user_id. Every store call includes it. No exceptions.
"""

from __future__ import annotations

import logging
import time as _time
from typing import Literal

from byo.shared.models import Modality
from byo.shared.store import ContentHit, get_content_store
from byo.shared.results import RetrievedChunk

log = logging.getLogger(__name__)


Scope = Literal["collection", "resource", "user_corpus"]
GroupBy = Literal["topic", "modality", "resource", "none"]


def _hit_to_chunk(h: ContentHit) -> RetrievedChunk:
    """Convert store ContentHit → RetrievedChunk."""
    from byo.shared.models import ChunkAnchor, RetrievalMode
    return RetrievedChunk(
        chunk_id=h.chunk_id,
        segment_id=h.segment_id,
        resource_id=h.resource_id,
        collection_id=h.collection_id,
        content=h.content,
        segment_content=h.segment_content,
        title=h.title,
        anchor=ChunkAnchor(page=h.anchor_page, section=h.anchor_section),
        score=h.score,
        modality=Modality(h.modality) if h.modality else None,
        retrieval_mode=RetrievalMode(h.retrieval_mode) if h.retrieval_mode else None,
        topics=h.topics,
        labels=h.labels,
        image_refs=h.image_refs,
        source="byo",
        resource_name=h.resource_name,
    )


# ── Public API ──────────────────────────────────────────────────────────


async def search(
    query: str,
    *,
    user_id: str,
    scope: Scope = "collection",
    collection_id: str | None = None,
    resource_id: str | None = None,
    modality_filter: list[Modality] | None = None,
    k: int = 5,
    rerank: bool = True,
    use_hyde: bool = False,
    min_rerank_score: float = 0.25,
) -> list[RetrievedChunk]:
    """Semantic search → optional rerank → parent chunks."""
    t0 = _time.time()

    if not user_id:
        raise ValueError("user_id is required (security boundary)")
    if not query or not query.strip():
        return []

    log.info(
        "[RETRIEVAL] search start user=%s scope=%s collection=%s q=%r",
        user_id[:12], scope, (collection_id or "")[:12], query[:80],
        extra={"event": "RET_SEARCH_START", "user_id": user_id,
               "scope": scope, "query_preview": query[:120]},
    )

    # 1. Optional HyDE
    embed_text = query
    if use_hyde:
        try:
            from byo.retrieval.query import hyde_expand
            embed_text = await hyde_expand(query)
        except Exception as e:
            log.warning("[RETRIEVAL] HyDE failed: %s", e)

    # 2. Embed query
    from app.services.content.embedding_service import generate_embedding
    embedding = await generate_embedding(embed_text)
    if not embedding:
        log.warning("[RETRIEVAL] embedding returned empty")
        return []

    # 3. Search content store (one call — Qdrant handles everything)
    store = get_content_store()
    pool_size = k * 4 if rerank else k  # fetch more for reranking headroom
    hits = await store.search(
        embedding,
        user_id=user_id,
        collection_id=collection_id if scope in ("collection", "resource") else None,
        resource_id=resource_id if scope == "resource" else None,
        modality=[m.value for m in modality_filter] if modality_filter else None,
        k=pool_size,
        min_score=0.35,
    )

    log.info(
        "[RETRIEVAL] store returned %d hits",
        len(hits),
        extra={"event": "RET_STORE_HITS", "hits": len(hits)},
    )

    if not hits:
        log.info("[RETRIEVAL] no hits — 0 results",
                 extra={"event": "RET_NO_HITS"})
        return []

    # 4. Convert to RetrievedChunk
    chunks = [_hit_to_chunk(h) for h in hits]

    # 5. Optional Cohere rerank
    if rerank and len(chunks) > 1:
        try:
            from byo.retrieval.rerank import cohere_rerank
            chunks = await cohere_rerank(query, chunks, top_n=k)
            if min_rerank_score > 0 and any(c.rerank_score is not None for c in chunks):
                before = len(chunks)
                chunks = [c for c in chunks
                          if c.rerank_score is None or c.rerank_score >= min_rerank_score]
                log.info("[RETRIEVAL] rerank filter %d → %d (threshold=%.2f)",
                         before, len(chunks), min_rerank_score)
        except Exception as e:
            log.warning("[RETRIEVAL] rerank failed: %s", e)
            chunks = chunks[:k]
    else:
        chunks = chunks[:k]

    total_ms = int((_time.time() - t0) * 1000)
    log.info(
        "[RETRIEVAL] done returned=%d total_ms=%d",
        len(chunks), total_ms,
        extra={"event": "RET_DONE", "returned": len(chunks),
               "elapsed_ms": total_ms},
    )
    return chunks


async def fetch(ref: str, *, user_id: str) -> RetrievedChunk | None:
    """Resolve a ref to its full parent chunk."""
    if not user_id:
        raise ValueError("user_id is required")

    kind, ident = _parse_ref(ref)
    store = get_content_store()

    if kind in ("chunk", "segment"):
        hit = await store.fetch(ident, user_id=user_id)
        return _hit_to_chunk(hit) if hit else None

    if kind == "resource":
        hits = await store.read_resource(ident, user_id=user_id)
        return _hit_to_chunk(hits[0]) if hits else None

    return None


async def peek(ref: str, *, user_id: str) -> dict | None:
    """Cheap summary — title + snippet + anchor."""
    if not user_id:
        raise ValueError("user_id is required")

    kind, ident = _parse_ref(ref)
    store = get_content_store()

    if kind in ("chunk", "segment"):
        hit = await store.fetch(ident, user_id=user_id)
        if not hit:
            return None
        return {
            "ref": ref,
            "resource_name": hit.resource_name,
            "page": hit.anchor_page,
            "section": hit.anchor_section,
            "snippet": hit.content[:150],
            "topics": hit.topics[:5],
        }
    return None


async def nearby(
    ref: str,
    *,
    user_id: str,
    window: int = 1,
) -> list[RetrievedChunk]:
    """Sequential navigation — adjacent chunks by index."""
    if not user_id:
        raise ValueError("user_id is required")

    kind, ident = _parse_ref(ref)
    store = get_content_store()

    if kind not in ("chunk", "segment"):
        return []

    hits = await store.nearby(ident, user_id=user_id, window=window)
    return [_hit_to_chunk(h) for h in hits]


async def list_contents(
    collection_id: str,
    *,
    user_id: str,
    group_by: GroupBy = "resource",
    limit: int = 50,
) -> list[dict]:
    """Inventory of a collection — structured list without a query."""
    if not user_id:
        raise ValueError("user_id is required")

    store = get_content_store()
    hits = await store.list_chunks(
        user_id=user_id,
        collection_id=collection_id,
        limit=limit,
    )

    if group_by == "resource":
        groups: dict[str, list] = {}
        for h in hits:
            key = h.resource_name or h.resource_id[:8]
            groups.setdefault(key, []).append({
                "ref": f"chunk:{h.chunk_id}",
                "page": h.anchor_page,
                "section": h.anchor_section,
                "snippet": h.content[:100],
                "topics": h.topics[:3],
            })
        return [{"resource": k, "chunks": v} for k, v in groups.items()]

    return [{"ref": f"chunk:{h.chunk_id}", "resource": h.resource_name,
             "snippet": h.content[:100]} for h in hits]


async def read_resource(
    resource_id: str,
    *,
    user_id: str,
    page_start: int | None = None,
    page_end: int | None = None,
) -> list[RetrievedChunk]:
    """Raw page-level access — read the document sequentially."""
    if not user_id:
        raise ValueError("user_id is required")

    store = get_content_store()
    hits = await store.read_resource(
        resource_id, user_id=user_id,
        page_start=page_start, page_end=page_end,
    )
    return [_hit_to_chunk(h) for h in hits]


# ── Helpers ─────────────────────────────────────────────────────────────

def _parse_ref(ref: str) -> tuple[str, str]:
    """Parse 'chunk:abc' / 'segment:abc' / 'resource:abc' / bare 'abc'."""
    if ":" in ref:
        kind, ident = ref.split(":", 1)
        kind = kind.strip().lower()
        ident = ident.strip()
        if kind in ("chunk", "segment", "resource"):
            return kind, ident
    return "chunk", ref.strip()


def build_filters(
    *,
    user_id: str,
    scope: Scope,
    collection_id: str | None = None,
    resource_id: str | None = None,
    modality: list[Modality] | None = None,
):
    """Build filter args for the store. Validates scope requirements."""
    if scope == "collection" and not collection_id:
        raise ValueError("scope=collection requires collection_id")
    if scope == "resource" and not resource_id:
        raise ValueError("scope=resource requires resource_id")
    return {
        "user_id": user_id,
        "collection_id": collection_id if scope in ("collection", "resource") else None,
        "resource_id": resource_id if scope == "resource" else None,
        "modality": modality,
    }
