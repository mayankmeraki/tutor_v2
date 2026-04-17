"""Filter helpers — thin conveniences around SearchFilters.

SearchFilters itself lives in byo.shared.results (it's used by processing
too). This module adds service-local helpers: ref parsing and
user-scoped Mongo lookups.
"""

from __future__ import annotations

from typing import Any

from byo.shared.results import SearchFilters


def parse_ref(ref: str) -> tuple[str, str]:
    """Parse a ref like `chunk:abc`, `segment:xy`, `resource:rr` → (kind, id).

    Bare IDs (no prefix) default to "chunk" for backward compat with the
    existing adapter callers.
    """
    if not ref:
        raise ValueError("ref is empty")
    if ":" in ref:
        kind, _, ident = ref.partition(":")
        kind = kind.strip().lower()
        ident = ident.strip()
        if kind not in ("chunk", "segment", "resource"):
            # unknown prefix — treat as bare id
            return "chunk", ref.strip()
        if not ident:
            raise ValueError(f"ref {ref!r} has empty id")
        return kind, ident
    return "chunk", ref.strip()


def require_user_filter(user_id: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a user-scoped Mongo filter. Raises if user_id missing."""
    if not user_id:
        raise ValueError("user_id is required (security boundary)")
    q: dict[str, Any] = {"user_id": user_id}
    if extra:
        q.update(extra)
    return q


async def segment_to_parent_chunk_id(segment_id: str, user_id: str) -> str | None:
    """Resolve a segment_id to its parent_chunk_id.

    Returns None if the segment doesn't exist or belongs to another user.
    """
    from app.core.mongodb import get_mongo_db

    if not user_id:
        raise ValueError("user_id is required (security boundary)")
    db = get_mongo_db()
    doc = await db.byo_segments.find_one(
        {"segment_id": segment_id, "user_id": user_id},
        {"_id": 0, "parent_chunk_id": 1},
    )
    if not doc:
        return None
    return doc.get("parent_chunk_id")


def scoped_filters(
    *,
    user_id: str,
    collection_id: str | None = None,
    resource_id: str | None = None,
) -> SearchFilters:
    """Build a minimal SearchFilters for fetch/peek/nearby paths."""
    if not user_id:
        raise ValueError("user_id is required (security boundary)")
    return SearchFilters(
        user_id=user_id,
        collection_id=collection_id,
        resource_id=resource_id,
    )
