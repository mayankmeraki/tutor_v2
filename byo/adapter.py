"""BYOCollectionAdapter — ContentProvider for student-uploaded materials.

Implements the same 4-method protocol as CapacityCourseAdapter, so the
tutor uses the same tools regardless of content source.

Thin wrappers over `byo.retrieval.service`:
  - content_search  → service.search (string-formatted)
  - content_read    → service.fetch
  - content_peek    → service.peek
  - content_map     → service.list_contents(group_by="resource")
  - content_nearby  → service.nearby
"""

from __future__ import annotations

import logging

from byo.retrieval import service as retrieval_service

log = logging.getLogger(__name__)


def _get_db():
    from app.core.mongodb import get_mongo_db
    return get_mongo_db()


def _format_anchor(anchor) -> str:
    if anchor is None:
        return ""
    parts: list[str] = []
    page = getattr(anchor, "page", None)
    section = getattr(anchor, "section", None)
    start = getattr(anchor, "start_time", None)
    if page is not None:
        parts.append(f"p. {page}")
    if section:
        parts.append(str(section))
    if start is not None:
        m = int(start // 60)
        s = int(start % 60)
        parts.append(f"{m}:{s:02d}")
    return " · ".join(parts)


class BYOCollectionAdapter:
    """ContentProvider for BYO student materials."""

    def __init__(self, collection_id: str, user_id: str):
        if not user_id:
            raise ValueError(
                "BYOCollectionAdapter requires user_id (security boundary)"
            )
        self.collection_id = collection_id
        self.user_id = user_id

    async def content_map(self) -> str:
        """Overview of what's in this collection."""
        db = _get_db()

        col = await db.collections.find_one(
            {"collection_id": self.collection_id, "user_id": self.user_id},
            {"_id": 0, "title": 1, "stats": 1, "intent": 1},
        )
        if not col:
            # Back-compat: some legacy collections may not have user_id denormalized yet
            col = await db.collections.find_one(
                {"collection_id": self.collection_id},
                {"_id": 0, "title": 1, "stats": 1, "intent": 1},
            )
        if not col:
            return "Collection not found."

        lines = [f"{col.get('title', 'Collection')}"]
        if col.get("intent"):
            lines.append(f"Intent: {col['intent']}")
        lines.append("")

        refs = await retrieval_service.list_contents(
            self.collection_id,
            user_id=self.user_id,
            group_by="resource",
            limit=50,
        )
        if refs:
            lines.append("Resources:")
            for r in refs:
                lines.append(f"  {r.title} — {r.snippet}")

        stats = col.get("stats") or {}
        topics = stats.get("topics") or []
        if topics:
            lines.append("")
            lines.append(f"Topics: {', '.join(topics[:20])}")

        return "\n".join(lines)

    async def content_read(self, ref: str) -> str:
        """Read a chunk/segment/resource by ref. Returns full content with citation."""
        # Preserve legacy plain-id input
        if ":" not in ref:
            ref = f"chunk:{ref}"
        hit = await retrieval_service.fetch(ref, user_id=self.user_id)
        if not hit:
            return f"{ref} not found."

        citation_parts: list[str] = []
        if hit.resource_name:
            citation_parts.append(hit.resource_name)
        anchor_str = _format_anchor(hit.anchor)
        if anchor_str:
            citation_parts.append(anchor_str)
        citation = " — ".join(citation_parts) if citation_parts else hit.chunk_id

        parts = [hit.content or ""]
        if hit.labels:
            parts.append(f"\nType: {', '.join(hit.labels)}")
        if hit.topics:
            parts.append(f"Topics: {', '.join(hit.topics)}")
        parts.append(f"Source: {citation}")
        return "\n".join(parts)

    async def content_search(self, query: str, limit: int = 5) -> str:
        """Hybrid search across this collection."""
        try:
            hits = await retrieval_service.search(
                query,
                user_id=self.user_id,
                scope="collection",
                collection_id=self.collection_id,
                k=limit,
            )
        except Exception as e:
            log.warning("BYO content_search failed: %s", e)
            hits = []

        if not hits:
            return "No results found."

        lines = [f'Search results for "{query}":']
        for h in hits:
            ref = f"chunk:{h.chunk_id}"
            preview = (h.content or "")[:100].replace("\n", " ")
            labels = ", ".join(h.labels) if h.labels else ""
            tag = f"[{labels}] " if labels else ""
            lines.append(f"  {ref}  {tag}{preview}...")
        return "\n".join(lines)

    async def content_peek(self, ref: str) -> str:
        """Brief summary of a chunk, segment, or resource."""
        if ":" not in ref:
            ref = f"chunk:{ref}"
        summary = await retrieval_service.peek(ref, user_id=self.user_id)
        if not summary:
            return f"{ref} not found."

        preview = summary.snippet
        title = summary.title
        lines = [f"[{title}] {preview}"] if title else [preview]
        anchor_str = _format_anchor(summary.anchor)
        if anchor_str:
            lines.append(f"At: {anchor_str}")
        return "\n".join(lines)

    async def content_nearby(self, ref: str, window: int = 1) -> str:
        """Deterministic anchor walk around a ref. Returns joined content."""
        if ":" not in ref:
            ref = f"chunk:{ref}"
        hits = await retrieval_service.nearby(
            ref, user_id=self.user_id, window=window,
        )
        if not hits:
            return f"No nearby content for {ref}."
        lines: list[str] = []
        for h in hits:
            anchor_str = _format_anchor(h.anchor)
            header = f"chunk:{h.chunk_id}"
            if anchor_str:
                header = f"{header} ({anchor_str})"
            lines.append(header)
            lines.append(h.content or "")
            lines.append("")
        return "\n".join(lines).rstrip()
