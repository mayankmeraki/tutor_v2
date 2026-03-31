"""BYOCollectionAdapter — ContentProvider for student-uploaded materials.

Implements the same 4-method protocol as CapacityCourseAdapter,
so the tutor uses the same tools regardless of content source.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def _get_db():
    from backend.app.core.mongodb import get_mongo_db
    return get_mongo_db()


class BYOCollectionAdapter:
    """ContentProvider for BYO student materials."""

    def __init__(self, collection_id: str, user_id: str):
        self.collection_id = collection_id
        self.user_id = user_id

    async def content_map(self) -> str:
        """Overview of what's in this collection."""
        db = _get_db()

        col = await db.collections.find_one(
            {"collection_id": self.collection_id},
            {"_id": 0, "title": 1, "stats": 1, "intent": 1},
        )
        if not col:
            return "Collection not found."

        lines = [
            f"{col.get('title', 'Collection')}",
            f"Intent: {col.get('intent', 'study')}" if col.get("intent") else "",
            "",
        ]

        # List resources
        resources = []
        async for res in db.byo_resources.find(
            {"collection_id": self.collection_id, "status": "ready"},
            {"_id": 0, "resource_id": 1, "original_name": 1, "mime_type": 1,
             "chunk_count": 1, "meta": 1},
        ):
            resources.append(res)

        if resources:
            lines.append("Resources:")
            for r in resources:
                name = r.get("original_name", "?")
                chunks = r.get("chunk_count", 0)
                mime = r.get("mime_type", "")
                type_str = "PDF" if "pdf" in mime else "Video" if "video" in mime or "youtube" in mime else "Text"
                lines.append(f"  {type_str}: {name} ({chunks} chunks)")

        # Topics
        stats = col.get("stats", {})
        topics = stats.get("topics", [])
        if topics:
            lines.append(f"\nTopics: {', '.join(topics[:20])}")

        return "\n".join(lines)

    async def content_read(self, ref: str) -> str:
        """Read a chunk by ID. Returns full content with citation."""
        db = _get_db()
        chunk_id = ref.replace("chunk:", "").strip()

        chunk = await db.byo_chunks.find_one(
            {"chunk_id": chunk_id, "collection_id": self.collection_id},
            {"_id": 0, "embedding": 0},
        )
        if not chunk:
            return f"Chunk {chunk_id} not found."

        # Build citation
        anchor = chunk.get("anchor", {})
        resource = await db.byo_resources.find_one(
            {"resource_id": chunk.get("resource_id")},
            {"_id": 0, "original_name": 1},
        )
        source_name = resource.get("original_name", "Unknown") if resource else "Unknown"

        citation_parts = [source_name]
        if anchor.get("page"):
            citation_parts.append(f"p. {anchor['page']}")
        if anchor.get("section"):
            citation_parts.append(anchor["section"])
        if anchor.get("start_time") is not None:
            m = int(anchor["start_time"] // 60)
            s = int(anchor["start_time"] % 60)
            citation_parts.append(f"{m}:{s:02d}")

        citation = " — ".join(citation_parts)

        content = chunk.get("content", "")
        labels = chunk.get("labels", [])
        topics = chunk.get("topics", [])

        result_parts = [content]
        if labels:
            result_parts.append(f"\nType: {', '.join(labels)}")
        if topics:
            result_parts.append(f"Topics: {', '.join(topics)}")
        result_parts.append(f"Source: {citation}")

        return "\n".join(result_parts)

    async def content_search(self, query: str, limit: int = 5) -> str:
        """Vector search across all chunks in this collection."""
        db = _get_db()

        try:
            from backend.app.services.embedding_service import generate_embedding
            embedding = await generate_embedding(query)

            if embedding:
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": "byo_chunks_vector",
                            "path": "embedding",
                            "queryVector": embedding,
                            "numCandidates": limit * 5,
                            "limit": limit,
                            "filter": {"collection_id": self.collection_id},
                        }
                    },
                    {
                        "$project": {
                            "_id": 0, "chunk_id": 1, "content": 1, "labels": 1,
                            "topics": 1, "anchor": 1, "resource_id": 1,
                            "score": {"$meta": "vectorSearchScore"},
                        }
                    },
                ]
                results = []
                async for doc in db.byo_chunks.aggregate(pipeline):
                    results.append(doc)

                if results:
                    lines = [f'Search results for "{query}":']
                    for r in results:
                        ref = f"chunk:{r.get('chunk_id', '?')}"
                        preview = r.get("content", "")[:100]
                        labels = ", ".join(r.get("labels", []))
                        lines.append(f"  {ref}  [{labels}] {preview}...")
                    return "\n".join(lines)

        except Exception as e:
            log.warning("Vector search failed: %s", e)

        # Fallback: text search
        cursor = db.byo_chunks.find(
            {
                "collection_id": self.collection_id,
                "$or": [
                    {"content": {"$regex": query, "$options": "i"}},
                    {"topics": {"$regex": query, "$options": "i"}},
                ],
            },
            {"_id": 0, "chunk_id": 1, "content": 1, "labels": 1, "topics": 1},
        ).limit(limit)

        results = [doc async for doc in cursor]
        if not results:
            return "No results found."

        lines = [f'Text search results for "{query}":']
        for r in results:
            ref = f"chunk:{r.get('chunk_id', '?')}"
            preview = r.get("content", "")[:100]
            lines.append(f"  {ref}  {preview}...")
        return "\n".join(lines)

    async def content_peek(self, ref: str) -> str:
        """Brief summary of a chunk or resource."""
        db = _get_db()

        # Check if it's a resource ref
        if ref.startswith("resource:"):
            resource_id = ref.replace("resource:", "").strip()
            res = await db.byo_resources.find_one(
                {"resource_id": resource_id, "collection_id": self.collection_id},
                {"_id": 0},
            )
            if not res:
                return f"Resource {resource_id} not found."

            name = res.get("original_name", "?")
            chunks = res.get("chunk_count", 0)
            meta = res.get("meta", {})
            lines = [f"{name} — {chunks} chunks"]
            if meta.get("pages"):
                lines.append(f"Pages: {meta['pages']}")
            if meta.get("duration"):
                lines.append(f"Duration: {int(meta['duration'] // 60)} min")
            return "\n".join(lines)

        # Chunk ref
        chunk_id = ref.replace("chunk:", "").strip()
        chunk = await db.byo_chunks.find_one(
            {"chunk_id": chunk_id, "collection_id": self.collection_id},
            {"_id": 0, "content": 1, "labels": 1, "topics": 1, "anchor": 1},
        )
        if not chunk:
            return f"Chunk {chunk_id} not found."

        content = chunk.get("content", "")
        preview = content[:150] + "..." if len(content) > 150 else content
        labels = ", ".join(chunk.get("labels", []))
        topics = ", ".join(chunk.get("topics", []))

        return f"[{labels}] {preview}\nTopics: {topics}"
