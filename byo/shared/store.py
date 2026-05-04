"""BYO content store — repository pattern hiding the underlying DB.

All BYO content operations (chunks, segments, search, navigation) go
through the `BYOContentStore` protocol. Concrete implementations can
back this with Qdrant, Pinecone, Postgres+pgvector, or a dict for tests.

The processing pipeline WRITES here. The retrieval service READS here.
Neither knows which database is underneath.

Usage:
    from byo.shared.store import get_content_store
    store = get_content_store()  # returns the configured implementation
    await store.upsert(resource_id, parents, segments)
    hits = await store.search(query_vec, user_id=..., k=5)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

log = logging.getLogger(__name__)


# ── Data types ──────────────────────────────────────────────────────────

@dataclass
class ContentHit:
    """A retrieved chunk with all context needed for citation.

    Carries BOTH the parent content (what the LLM reads) and the segment
    content (what matched the query). The score comes from the vector DB.
    """
    chunk_id: str
    segment_id: str
    resource_id: str
    resource_name: str
    collection_id: str
    user_id: str

    content: str           # parent content (~800 tok) — what the tutor reads
    segment_content: str   # child content (~200 tok) — what matched

    anchor_page: int | None = None
    anchor_section: str = ""
    anchor_start_time: float | None = None  # video timestamp (seconds)
    anchor_end_time: float | None = None
    score: float = 0.0

    modality: str = ""
    retrieval_mode: str = ""
    topics: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    index: int = 0         # position within resource (for sequential nav)
    title: str = ""        # short title for TOC display
    image_refs: list[dict] = field(default_factory=list)  # [{url, description, page}]


# ── Protocol (the contract) ─────────────────────────────────────────────

@runtime_checkable
class BYOContentStore(Protocol):
    """Interface for BYO content storage and retrieval.

    Implementations must be async. The store owns ALL content operations:
    upsert, delete, search, fetch, nearby, list. Callers never touch the
    underlying DB directly.
    """

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
        """Write parents + segments. Idempotent — deletes existing first.
        Returns (parents_written, segments_written).
        """
        ...

    async def delete_resource(self, resource_id: str) -> int:
        """Delete all content for a resource. Returns count deleted."""
        ...

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
        """Semantic search. Returns top-k hits sorted by score desc."""
        ...

    async def fetch(
        self,
        chunk_id: str,
        *,
        user_id: str,
    ) -> ContentHit | None:
        """Fetch a specific chunk by ID."""
        ...

    async def nearby(
        self,
        chunk_id: str,
        *,
        user_id: str,
        window: int = 1,
    ) -> list[ContentHit]:
        """Get adjacent chunks by index (sequential navigation)."""
        ...

    async def list_chunks(
        self,
        *,
        user_id: str,
        collection_id: str | None = None,
        resource_id: str | None = None,
        limit: int = 50,
    ) -> list[ContentHit]:
        """List chunks without a query (for browsing/overview)."""
        ...

    async def read_resource(
        self,
        resource_id: str,
        *,
        user_id: str,
        page_start: int | None = None,
        page_end: int | None = None,
    ) -> list[ContentHit]:
        """Read chunks from a resource, optionally filtered by page range.
        Returns all parent chunks in order — like reading the document.
        """
        ...


# ── Factory ─────────────────────────────────────────────────────────────

_store: BYOContentStore | None = None


def get_content_store() -> BYOContentStore:
    """Get the configured content store singleton.

    Default: QdrantContentStore. Override with BYO_CONTENT_STORE env var
    for testing (e.g., 'memory' for in-memory dict store).
    """
    global _store
    if _store is not None:
        return _store

    import os
    backend = os.environ.get("BYO_CONTENT_STORE", "qdrant")

    if backend == "qdrant":
        from byo.shared._qdrant_store import QdrantContentStore
        _store = QdrantContentStore()
    elif backend == "memory":
        from byo.shared._memory_store import MemoryContentStore
        _store = MemoryContentStore()
    else:
        raise ValueError(f"Unknown BYO_CONTENT_STORE: {backend}")

    log.info("BYO content store: %s", type(_store).__name__)
    return _store


def set_content_store(store: BYOContentStore) -> None:
    """Override the content store (for tests)."""
    global _store
    _store = store
