"""Qdrant-backed BYO content store.

Single Qdrant collection `byo_content` stores one point per segment with:
  - vector: 1536-dim embedding (for search)
  - payload: segment content + parent content + all metadata

Parent content is DENORMALIZED onto every segment so search hits carry
the full teaching context without a second lookup ("small-to-big" baked
into storage). This trades ~4x storage for zero-latency expansion.

No Mongo dependency for content reads — all retrieval goes through Qdrant.
Mongo is only used for operational data (jobs, resources, collections).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from byo.shared.store import BYOContentStore, ContentHit

log = logging.getLogger(__name__)

COLLECTION = "byo_content"
VECTOR_DIM = 1536


def _get_client():
    from byo.shared.qdrant import get_qdrant_client
    return get_qdrant_client()


def _ensure_collection(client):
    from qdrant_client.models import Distance, VectorParams
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        log.info("Qdrant collection '%s' created", COLLECTION)

    # Always ensure indexes exist (idempotent — Qdrant ignores if already present)
    info = client.get_collection(COLLECTION)
    existing_indexes = set(info.payload_schema.keys()) if info.payload_schema else set()
    required = {"user_id": "keyword", "collection_id": "keyword", "resource_id": "keyword",
                "modality": "keyword", "chunk_id": "keyword", "segment_id": "keyword"}
    for field, schema in required.items():
        if field not in existing_indexes:
            try:
                client.create_payload_index(COLLECTION, field, schema)
                log.info("Qdrant index created: %s (%s)", field, schema)
            except Exception:
                pass
    if "index" not in existing_indexes:
        try:
            client.create_payload_index(COLLECTION, "index", "integer")
            log.info("Qdrant index created: index (integer)")
        except Exception:
            pass


def _to_uuid(s: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, s))


def _hit_from_payload(payload: dict, score: float = 0.0) -> ContentHit:
    return ContentHit(
        chunk_id=payload.get("chunk_id", ""),
        segment_id=payload.get("segment_id", ""),
        resource_id=payload.get("resource_id", ""),
        resource_name=payload.get("resource_name", ""),
        collection_id=payload.get("collection_id", ""),
        user_id=payload.get("user_id", ""),
        content=payload.get("parent_content", "") or payload.get("content", "") or payload.get("text", ""),
        segment_content=payload.get("segment_content", "") or payload.get("content", "") or payload.get("text", ""),
        anchor_page=payload.get("anchor_page"),
        anchor_section=payload.get("anchor_section", ""),
        score=score,
        modality=payload.get("modality", ""),
        retrieval_mode=payload.get("retrieval_mode", ""),
        topics=payload.get("topics") or [],
        labels=payload.get("labels") or [],
        index=payload.get("index", 0),
        title=payload.get("title", ""),
        image_refs=payload.get("image_refs") or [],
    )


class QdrantContentStore:
    """All BYO content in Qdrant. Zero Mongo reads for retrieval."""

    async def upsert(
        self,
        *,
        resource_id: str,
        collection_id: str,
        user_id: str,
        resource_name: str,
        parents: list[dict],
        segments: list[dict],
    ) -> tuple[int, int]:
        from qdrant_client.models import PointStruct

        client = _get_client()
        if client is None:
            log.warning("Qdrant unavailable — content not stored")
            return 0, 0

        _ensure_collection(client)

        # Delete existing content for this resource (idempotent)
        await self.delete_resource(resource_id)

        # Build parent lookup for denormalization
        parent_map: dict[str, dict] = {}
        for p in parents:
            parent_map[p["chunk_id"]] = p

        # Build points — one per segment, carrying parent content
        points = []
        for s in segments:
            emb = s.get("embedding")
            if not emb:
                continue

            parent = parent_map.get(s.get("parent_chunk_id", ""), {})

            payload = {
                "segment_id": s["segment_id"],
                "chunk_id": s.get("parent_chunk_id", ""),
                "collection_id": collection_id,
                "resource_id": resource_id,
                "resource_name": resource_name,
                "user_id": user_id,

                # Both contents — small-to-big baked in
                "segment_content": s.get("content", ""),
                "parent_content": parent.get("content", s.get("content", "")),

                # Metadata for filtering + citation
                "anchor_page": (s.get("anchor") or {}).get("page")
                    or (parent.get("anchor") or {}).get("page"),
                "anchor_page_end": (parent.get("anchor") or {}).get("page_end"),
                "anchor_section": (s.get("anchor") or {}).get("section", "")
                    or (parent.get("anchor") or {}).get("section", ""),
                "modality": s.get("modality", ""),
                "retrieval_mode": s.get("retrieval_mode", ""),
                "topics": s.get("topics") or parent.get("topics") or [],
                "labels": parent.get("labels") or [],
                "questions": s.get("questions") or [],
                "index": parent.get("index", s.get("index", 0)),
                "tokens": parent.get("tokens", 0),
                "title": parent.get("title", ""),
                "image_refs": parent.get("image_refs") or [],
            }

            point_id = _to_uuid(s["segment_id"])
            points.append(PointStruct(id=point_id, vector=emb, payload=payload))

        if not points:
            return len(parents), 0

        # Batch upsert
        BATCH = 100
        total = 0
        for i in range(0, len(points), BATCH):
            batch = points[i:i + BATCH]
            client.upsert(collection_name=COLLECTION, points=batch)
            total += len(batch)

        log.info(
            "[STORE] upserted resource=%s name=%s parents=%d segments=%d points=%d",
            resource_id[:8], resource_name[:30], len(parents), len(segments), total,
        )
        return len(parents), total

    async def delete_resource(self, resource_id: str) -> int:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        client = _get_client()
        if client is None:
            return 0
        _ensure_collection(client)
        client.delete(
            collection_name=COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="resource_id", match=MatchValue(value=resource_id))]
            ),
        )
        return 0  # Qdrant doesn't return count

    async def search(
        self,
        query_vector: list[float],
        *,
        user_id: str,
        collection_id: str | None = None,
        resource_id: str | None = None,
        modality: list[str] | None = None,
        topics: list[str] | None = None,
        k: int = 5,
        min_score: float = 0.35,
    ) -> list[ContentHit]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

        client = _get_client()
        if client is None:
            return []

        must = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        if collection_id:
            must.append(FieldCondition(key="collection_id", match=MatchValue(value=collection_id)))
        if resource_id:
            must.append(FieldCondition(key="resource_id", match=MatchValue(value=resource_id)))
        if modality:
            must.append(FieldCondition(key="modality", match=MatchAny(any=modality)))
        if topics:
            must.append(FieldCondition(key="topics", match=MatchAny(any=topics)))

        hits = client.query_points(
            collection_name=COLLECTION,
            query=query_vector,
            query_filter=Filter(must=must),
            limit=k,
            score_threshold=min_score,
            with_payload=True,
        ).points

        # Dedupe by chunk_id (multiple segments from same parent → keep best)
        seen_chunks: set[str] = set()
        results: list[ContentHit] = []
        for h in hits:
            cid = h.payload.get("chunk_id", "")
            if cid in seen_chunks:
                continue
            seen_chunks.add(cid)
            results.append(_hit_from_payload(h.payload, h.score))

        return results

    async def fetch(
        self,
        chunk_id: str,
        *,
        user_id: str,
    ) -> ContentHit | None:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = _get_client()
        if client is None:
            return None

        # Find any segment belonging to this parent chunk
        hits = client.query_points(
            collection_name=COLLECTION,
            query=None,  # no vector query — payload filter only
            query_filter=Filter(must=[
                FieldCondition(key="chunk_id", match=MatchValue(value=chunk_id)),
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            ]),
            limit=1,
            with_payload=True,
        ).points

        if not hits:
            return None
        return _hit_from_payload(hits[0].payload)

    async def nearby(
        self,
        chunk_id: str,
        *,
        user_id: str,
        window: int = 1,
    ) -> list[ContentHit]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

        client = _get_client()
        if client is None:
            return []

        # First find the target chunk to get its resource_id + index
        target = await self.fetch(chunk_id, user_id=user_id)
        if not target:
            return []

        # Fetch chunks in [index-window, index+window] from the same resource
        idx_lo = max(0, target.index - window)
        idx_hi = target.index + window

        hits = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(must=[
                FieldCondition(key="resource_id", match=MatchValue(value=target.resource_id)),
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                FieldCondition(key="index", range=Range(gte=idx_lo, lte=idx_hi)),
            ]),
            limit=50,
            with_payload=True,
            with_vectors=False,
        )[0]

        # Dedupe by chunk_id + sort by index
        seen: set[str] = set()
        results: list[ContentHit] = []
        for h in hits:
            cid = h.payload.get("chunk_id", "")
            if cid in seen:
                continue
            seen.add(cid)
            results.append(_hit_from_payload(h.payload))
        results.sort(key=lambda r: r.index)
        return results

    async def list_chunks(
        self,
        *,
        user_id: str,
        collection_id: str | None = None,
        resource_id: str | None = None,
        limit: int = 50,
    ) -> list[ContentHit]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = _get_client()
        if client is None:
            return []

        must = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        if collection_id:
            must.append(FieldCondition(key="collection_id", match=MatchValue(value=collection_id)))
        if resource_id:
            must.append(FieldCondition(key="resource_id", match=MatchValue(value=resource_id)))

        hits = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(must=must),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )[0]

        # Dedupe by chunk_id + sort by index
        seen: set[str] = set()
        results: list[ContentHit] = []
        for h in hits:
            cid = h.payload.get("chunk_id", "")
            if cid in seen:
                continue
            seen.add(cid)
            results.append(_hit_from_payload(h.payload))
        results.sort(key=lambda r: (r.resource_name, r.index))
        return results

    async def read_resource(
        self,
        resource_id: str,
        *,
        user_id: str,
        page_start: int | None = None,
        page_end: int | None = None,
    ) -> list[ContentHit]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

        client = _get_client()
        if client is None:
            return []

        must = [
            FieldCondition(key="resource_id", match=MatchValue(value=resource_id)),
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        ]
        if page_start is not None or page_end is not None:
            must.append(FieldCondition(
                key="anchor_page",
                range=Range(
                    gte=page_start if page_start is not None else 1,
                    lte=page_end if page_end is not None else 99999,
                ),
            ))

        hits = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(must=must),
            limit=200,
            with_payload=True,
            with_vectors=False,
        )[0]

        seen: set[str] = set()
        results: list[ContentHit] = []
        for h in hits:
            cid = h.payload.get("chunk_id", "")
            if cid in seen:
                continue
            seen.add(cid)
            results.append(_hit_from_payload(h.payload))
        results.sort(key=lambda r: r.index)
        return results
