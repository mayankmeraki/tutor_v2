"""Lean context builder for BYO collections.

Produces a ~600-800 token snapshot that gives the agent just enough context
to know WHERE it is and HOW to discover more via MQL tools. The agent
queries content on-demand, never gets a giant dump upfront.

Context snapshot includes:
- Collection identity (title, subjects, stats)
- Student position (current topic, completed topics, mastery summary)
- Session state (objective, completed topics count)
- Available tool reference (brief — the full toolkit is in the system prompt)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from app.core.mongodb import get_mongo_db, get_tutor_db

log = logging.getLogger(__name__)


async def build_lean_context(
    collection_id: str,
    user_email: str,
    session_id: str | None = None,
) -> str:
    """Build a lean context snapshot for the tutor agent.

    Target: 600-800 tokens. Agent uses MQL tools to explore further.
    """
    db = get_mongo_db()
    tutor_db = get_tutor_db()

    parts: list[str] = []

    # ── 1. Collection Identity ───────────────────────────────────────
    collection = await db.content_collections.find_one(
        {"collectionId": collection_id},
        {"title": 1, "subjects": 1, "stats": 1, "status": 1},
    )
    if not collection:
        return f"[Error: Collection {collection_id} not found]"

    stats = collection.get("stats", {})
    parts.append(f"[Collection: {collection.get('title', '?')}]")
    parts.append(
        f"Subjects: {', '.join(collection.get('subjects', ['general']))}"
        f" | {stats.get('totalTopics', 0)} topics, {stats.get('totalChunks', 0)} chunks, "
        f"{stats.get('totalExercises', 0)} exercises"
    )
    parts.append(f"collectionId: {collection_id}")

    if collection.get("status") != "ready":
        parts.append(f"⚠ Collection status: {collection.get('status', '?')} — some content may still be processing")

    # ── 2. Flow Map Summary (brief) ──────────────────────────────────
    flow = await db.flow_map.find_one(
        {"collectionId": collection_id},
        {"chapters": 1},
    )
    if flow and flow.get("chapters"):
        chapters = flow["chapters"]
        chapter_summary = " → ".join(
            f"{ch.get('title', '?')} ({len(ch.get('topics', []))} topics)"
            for ch in chapters
        )
        parts.append(f"\nSequence: {chapter_summary}")
    else:
        parts.append("\nSequence: Not yet generated. Use browse_topics to see available content.")

    # ── 3. Student Position ──────────────────────────────────────────
    progress = await tutor_db.student_progress.find_one({
        "collectionId": collection_id,
        "userEmail": user_email,
    })

    if progress:
        completed = progress.get("completedTopics", [])
        pos = progress.get("currentPosition", {})
        sessions = progress.get("sessionCount", 0)

        parts.append(f"\n[Student Progress]")
        parts.append(f"Sessions: {sessions} | Completed topics: {len(completed)}")

        if pos.get("topicId"):
            # Get current topic name
            topic = await db.topic_index.find_one(
                {"topicId": pos["topicId"]},
                {"name": 1},
            )
            topic_name = topic.get("name", "?") if topic else "?"
            parts.append(f"Current topic: {topic_name} (topicId: {pos['topicId']})")

        if completed:
            parts.append(f"Completed: {', '.join(completed[:5])}" + ("..." if len(completed) > 5 else ""))

        # Mastery highlights (only weak/developing concepts)
        mastery = progress.get("conceptMastery", {})
        weak = [k for k, v in mastery.items() if v.get("level") in ("weak", "developing")]
        if weak:
            parts.append(f"Needs work: {', '.join(weak[:5])}")
    else:
        parts.append("\n[Student Progress]")
        parts.append("New student — no prior progress in this collection.")
        parts.append("Start with browse_topics or get_flow to plan the session.")

    # ── 4. Tool Quick Reference ──────────────────────────────────────
    parts.append("""
[MQL Tools — Content Discovery]
Use these tools to explore and teach from the collection:
  browse_topics()          — list all topics
  browse_topic(topicId)    — details for one topic
  get_flow()               — teaching sequence
  read_chunk(chunkId)      — full content for one chunk
  search_content(query)    — text search across all chunks
  find_concept(name)       — concept definition + locations
  get_exercises(topicId?)  — practice problems
  get_mastery()            — student progress
  get_assets(topicId?)     — diagrams, board captures, clips""")

    return "\n".join(parts)


async def get_collection_type(collection_id: str) -> str | None:
    """Check if a collection is 'byo' or 'curated_course'. Returns None if not found."""
    db = get_mongo_db()
    doc = await db.content_collections.find_one(
        {"collectionId": collection_id},
        {"type": 1},
    )
    return doc.get("type") if doc else None
