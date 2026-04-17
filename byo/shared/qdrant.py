"""Qdrant client singleton for BYO vector search.

Qdrant replaces Atlas $vectorSearch as the vector store. Mongo remains
the document store (chunks, segments, resources, collections).

Collection: `byo_segments`
  - vector: 1536 dim, cosine
  - payload: segment_id, parent_chunk_id, collection_id, resource_id,
             user_id, modality, retrieval_mode, topics, content (truncated)

Env:
  QDRANT_URL       — cluster URL (required)
  QDRANT_API_KEY   — API key (required for cloud)
"""

from __future__ import annotations

import logging
import os
import uuid

log = logging.getLogger(__name__)

QDRANT_COLLECTION = "byo_segments"
VECTOR_DIM = 1536

_client = None


def get_qdrant_client():
    """Lazy-init Qdrant client singleton."""
    global _client
    if _client is not None:
        return _client

    from qdrant_client import QdrantClient

    url = os.environ.get("QDRANT_URL", "")
    api_key = os.environ.get("QDRANT_API_KEY", "")

    if not url:
        log.warning("QDRANT_URL not set — Qdrant disabled")
        return None

    _client = QdrantClient(url=url, api_key=api_key or None, timeout=30)
    log.info("Qdrant client connected: %s", url[:60])
    return _client


def ensure_collection():
    """Create the byo_segments collection if it doesn't exist."""
    from qdrant_client.models import Distance, VectorParams

    client = get_qdrant_client()
    if client is None:
        return

    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION in existing:
        return

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )
    # Payload indexes for filtering
    for field in ("user_id", "collection_id", "resource_id", "modality"):
        client.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name=field,
            field_schema="keyword",
        )
    log.info("Qdrant collection '%s' created with payload indexes", QDRANT_COLLECTION)


def segment_id_to_uuid(segment_id: str) -> str:
    """Deterministic UUID from segment_id string (Qdrant needs UUIDs or ints)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, segment_id))


def upsert_segments(segments: list[dict]) -> int:
    """Upsert segment vectors + payload into Qdrant. Returns count upserted."""
    from qdrant_client.models import PointStruct

    client = get_qdrant_client()
    if client is None:
        return 0
    if not segments:
        return 0

    ensure_collection()

    points = []
    for s in segments:
        emb = s.get("embedding")
        if not emb:
            continue
        point_id = segment_id_to_uuid(s["segment_id"])
        payload = {
            "segment_id": s["segment_id"],
            "parent_chunk_id": s.get("parent_chunk_id", ""),
            "collection_id": s.get("collection_id", ""),
            "resource_id": s.get("resource_id", ""),
            "resource_name": s.get("resource_name", ""),
            "user_id": s.get("user_id", ""),
            "modality": s.get("modality", ""),
            "retrieval_mode": s.get("retrieval_mode", ""),
            "topics": s.get("topics") or [],
            "anchor_page": s.get("anchor", {}).get("page"),
            "anchor_section": s.get("anchor", {}).get("section", ""),
            "content_preview": (s.get("content") or "")[:300],
        }
        points.append(PointStruct(id=point_id, vector=emb, payload=payload))

    if not points:
        return 0

    # Batch 100 at a time
    BATCH = 100
    total = 0
    for i in range(0, len(points), BATCH):
        batch = points[i:i + BATCH]
        client.upsert(collection_name=QDRANT_COLLECTION, points=batch)
        total += len(batch)

    log.info("Qdrant upserted %d segments", total)
    return total


def delete_by_resource(resource_id: str) -> int:
    """Delete all vectors for a resource_id. Returns count deleted."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = get_qdrant_client()
    if client is None:
        return 0

    ensure_collection()
    result = client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="resource_id", match=MatchValue(value=resource_id))]
        ),
    )
    return getattr(result, "deleted", 0) if result else 0


def search_vectors(
    query_vector: list[float],
    *,
    user_id: str,
    collection_id: str | None = None,
    resource_id: str | None = None,
    modality: list[str] | None = None,
    limit: int = 20,
    score_threshold: float = 0.35,
) -> list[tuple[str, str, float]]:
    """Search Qdrant. Returns [(segment_id, parent_chunk_id, score)]."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

    client = get_qdrant_client()
    if client is None:
        return []

    must = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
    if collection_id:
        must.append(FieldCondition(key="collection_id", match=MatchValue(value=collection_id)))
    if resource_id:
        must.append(FieldCondition(key="resource_id", match=MatchValue(value=resource_id)))
    if modality:
        must.append(FieldCondition(key="modality", match=MatchAny(any=modality)))

    hits = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        query_filter=Filter(must=must),
        limit=limit,
        score_threshold=score_threshold,
    ).points

    return [
        (
            h.payload.get("segment_id", ""),
            h.payload.get("parent_chunk_id", ""),
            h.score,
        )
        for h in hits
        if h.payload.get("segment_id")
    ]
