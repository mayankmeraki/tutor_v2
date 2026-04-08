"""BYO (bring-your-own) content tool implementations."""

import logging

log = logging.getLogger(__name__)

async def _execute_byo_read(tool_input: dict) -> str:
    """Read content from a BYO collection."""
    from app.core.mongodb import get_mongo_db
    db = get_mongo_db()

    collection_id = tool_input.get("collection_id", "")
    query = tool_input.get("query", "")
    chunk_index = tool_input.get("chunk_index")

    if not collection_id:
        return "Error: collection_id is required"

    if chunk_index is not None:
        # Read specific chunk
        doc = await db.byo_chunks.find_one(
            {"collection_id": collection_id, "index": int(chunk_index)},
            {"_id": 0, "content": 1, "topics": 1, "labels": 1, "anchor": 1},
        )
        if not doc:
            return f"No chunk found at index {chunk_index} in collection {collection_id}"
        return f"[BYO Chunk {chunk_index}]\nTopics: {', '.join(doc.get('topics', []))}\n\n{doc.get('content', '')}"

    if query:
        # Search within collection
        import re
        words = [w for w in query.strip().split() if len(w) > 2]
        if not words:
            return "Search query too short"
        conditions = []
        for w in words[:5]:
            conditions.append({"content": {"$regex": re.escape(w), "$options": "i"}})
        cursor = db.byo_chunks.find(
            {"collection_id": collection_id, "$or": conditions},
            {"_id": 0, "index": 1, "content": 1, "topics": 1},
        ).limit(3)
        results = []
        async for doc in cursor:
            results.append(f"[Chunk {doc.get('index', '?')}] Topics: {', '.join(doc.get('topics', []))}\n{doc.get('content', '')[:500]}")
        if not results:
            return f"No matching content found for '{query}' in this collection."
        return "\n\n---\n\n".join(results)

    # No query — return first few chunks as overview
    cursor = db.byo_chunks.find(
        {"collection_id": collection_id},
        {"_id": 0, "index": 1, "content": 1, "topics": 1},
    ).sort("index", 1).limit(3)
    results = []
    async for doc in cursor:
        results.append(f"[Chunk {doc.get('index', '?')}] Topics: {', '.join(doc.get('topics', []))}\n{doc.get('content', '')[:400]}")
    if not results:
        # Check collection status for a better error message
        col = await db.collections.find_one(
            {"collection_id": collection_id},
            {"status": 1, "title": 1},
        )
        if col and col.get("status") == "processing":
            return f"Collection '{col.get('title', '?')}' is still being processed."
        elif col and col.get("status") == "error":
            return f"Collection '{col.get('title', '?')}' had a processing error — content could not be extracted."
        return "Collection has no text content. The original file may still be viewable but text extraction produced no results."
    return "\n\n---\n\n".join(results)


async def _execute_byo_list(tool_input: dict) -> str:
    """List chunks in a BYO collection."""
    from app.core.mongodb import get_mongo_db
    db = get_mongo_db()

    collection_id = tool_input.get("collection_id", "")
    if not collection_id:
        return "Error: collection_id is required"

    cursor = db.byo_chunks.find(
        {"collection_id": collection_id},
        {"_id": 0, "index": 1, "topics": 1, "labels": 1, "tokens": 1},
    ).sort("index", 1).limit(30)

    lines = [f"Chunks in collection {collection_id}:"]
    async for doc in cursor:
        topics = ", ".join(doc.get("topics", [])[:3])
        labels = ", ".join(doc.get("labels", [])[:2])
        lines.append(f"  [{doc.get('index', '?')}] {topics} ({labels}) — {doc.get('tokens', 0)} tokens")

    if len(lines) == 1:
        # Check if collection exists and its status
        col = await db.collections.find_one(
            {"collection_id": collection_id},
            {"status": 1, "title": 1},
        )
        if not col:
            return "Collection not found. Check the collection_id."
        status = col.get("status", "unknown")
        title = col.get("title", "?")
        if status == "processing":
            return f"Collection '{title}' is still being processed. Content will be available once processing completes."
        elif status == "error":
            return f"Collection '{title}' had a processing error — the content could not be extracted."
        return f"Collection '{title}' is ready but has no extractable text content. The original file may still be viewable."
    return "\n".join(lines)


async def _execute_byo_transcript(tool_input: dict) -> str:
    """Get transcript context around a timestamp in a BYO video."""
    from app.core.mongodb import get_mongo_db
    db = get_mongo_db()

    resource_id = tool_input.get("resource_id", "")
    timestamp = float(tool_input.get("timestamp", 0))
    if not resource_id:
        return "Error: resource_id is required"

    # Get resource info
    resource = await db.byo_resources.find_one(
        {"resource_id": resource_id},
        {"_id": 0, "original_name": 1, "source_url": 1, "collection_id": 1},
    )
    if not resource:
        return "Resource not found."

    # Find chunks around the timestamp (~60s window)
    t_start = max(0, timestamp - 30)
    t_end = timestamp + 30

    cursor = db.byo_chunks.find(
        {
            "resource_id": resource_id,
            "$or": [
                # Chunk starts or ends within our window
                {"anchor.start_time": {"$gte": t_start, "$lte": t_end}},
                {"anchor.end_time": {"$gte": t_start, "$lte": t_end}},
                # Chunk spans our entire window (mega-chunk)
                {"$and": [
                    {"anchor.start_time": {"$lte": t_start}},
                    {"anchor.end_time": {"$gte": t_end}},
                ]},
            ],
        },
        {"_id": 0, "content": 1, "anchor": 1, "topics": 1, "index": 1},
    ).sort("index", 1).limit(5)

    chunks = [doc async for doc in cursor]

    # Fallback: index-based
    if not chunks:
        est_index = max(0, int(timestamp / 30))
        cursor = db.byo_chunks.find(
            {"resource_id": resource_id, "index": {"$gte": max(0, est_index - 1), "$lte": est_index + 1}},
            {"_id": 0, "content": 1, "anchor": 1, "topics": 1, "index": 1},
        ).sort("index", 1).limit(3)
        chunks = [doc async for doc in cursor]

    if not chunks:
        return f"No transcript found around {int(timestamp)}s in this video."

    lines = [f"Transcript around {int(timestamp)}s in '{resource.get('original_name', '?')}':"]
    for c in chunks:
        content = c.get("content", "")
        anchor = c.get("anchor", {})
        chunk_start = anchor.get("start_time", 0) or 0
        chunk_end = anchor.get("end_time", 0) or 0

        # For mega-chunks (spanning entire video), extract just the relevant portion
        if chunk_end - chunk_start > 120 and content:
            import re
            # Parse timestamped lines: [M:SS] text or [MM:SS] text
            ts_lines = re.findall(r'\[(\d+:\d{2})\]\s*(.+?)(?=\n\[|\Z)', content, re.DOTALL)
            if ts_lines:
                relevant = []
                for ts_str, text in ts_lines:
                    parts = ts_str.split(':')
                    sec = int(parts[0]) * 60 + int(parts[1])
                    if t_start - 10 <= sec <= t_end + 10:
                        relevant.append(f"[{ts_str}] {text.strip()}")
                if relevant:
                    lines.append("\n".join(relevant))
                    continue
        # Short chunk or no timestamp parsing — use full content
        start = anchor.get("start_time")
        ts = f"[{int(start // 60)}:{int(start % 60):02d}] " if start is not None else ""
        lines.append(f"{ts}{content[:800]}")

    return "\n\n".join(lines)

