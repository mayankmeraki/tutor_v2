"""Student concept mastery — freehand notes per student.

One MongoDB document per student. Contains:
- Global profile (course-independent): learning style, pace, preferences
- Concept notes (tagged with courseId metadata): mastery observations

Collection: student_concept_mastery (in tutor_v2 database)
Vector index: student_concept_mastery_vectors (flat, for Atlas Vector Search)

Document schema:
    _id:           mastery_{safeEmail}
    userEmail:      str
    profile:       {text, updatedAt}              # global, cross-course
    notes:         [{text, tags, courseId, sessionId, lesson, at}]
    lastUpdated:   ISO datetime
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.core.mongodb import get_tutor_db

log = logging.getLogger(__name__)


# ─── Collection accessors ──────────────────────────────────────────

def _collection():
    """Source of truth: one doc per student with notes array + profile."""
    return get_tutor_db()["student_concept_mastery"]

def _index_collection():
    """Flat materialized index for vector search — one doc per concept."""
    return get_tutor_db()["student_concept_mastery_vectors"]


def _doc_id(course_id: int, user_email: str) -> str:
    """Document ID — per student (not per course). courseId is metadata on notes."""
    safe_email = user_email.lower().replace(".", "_dot_").replace("@", "_at_")
    return f"mastery_{safe_email}"


# ─── Core Operations ───────────────────────────────────────────────

async def append_note(
    course_id: int,
    user_email: str,
    session_id: str,
    text: str,
    tags: list[str] | None = None,
) -> dict:
    """Append a freehand observation to the student's knowledge journal.

    Single $push + $set lastUpdated. Creates the document if it doesn't exist.
    """
    col = _collection()
    doc_id = _doc_id(course_id, user_email)
    now = datetime.now(timezone.utc).isoformat()

    note = {
        "text": text,
        "tags": tags or [],
        "sessionId": session_id,
        "at": now,
    }

    await col.update_one(
        {"_id": doc_id},
        {
            "$push": {"notes": note},
            "$set": {"lastUpdated": now},
            "$setOnInsert": {
                "courseId": course_id,
                "userEmail": user_email,
                "summary": None,
            },
        },
        upsert=True,
    )

    log.info("Knowledge note appended: %s/%d (%d chars, %d tags)",
             user_email, course_id, len(text), len(tags or []))

    # Sync to vector index in background (non-blocking)
    asyncio.create_task(_sync_note_to_vector_index(
        course_id, user_email, text, tags or [], session_id
    ))

    return {"logged": True, "note_length": len(text), "tags": tags or []}


def _normalize_tag(tag: str) -> str:
    """Normalize a single tag: lowercase, spaces→underscores, strip special chars."""
    import re
    t = str(tag).strip().lower()
    t = re.sub(r'[^a-z0-9_\-]', '_', t)  # replace non-alphanumeric with underscore
    t = re.sub(r'_+', '_', t)  # collapse multiple underscores
    return t.strip('_') or '_uncategorized'


def _normalize_tags(tags) -> list[str]:
    """Convert tags to a normalized list of strings."""
    if isinstance(tags, str):
        return [_normalize_tag(t) for t in tags.replace(",", " ").split() if t.strip()]
    if isinstance(tags, list):
        return [_normalize_tag(str(t)) for t in tags if t]
    return []


async def upsert_concept_note(
    course_id: int,
    user_email: str,
    session_id: str,
    concepts: list[str],
    note_text: str,
    lesson: str | None = None,
) -> dict:
    """Upsert a freehand note by concept overlap.

    - _profile notes update the global profile (course-independent)
    - Concept notes are tagged with courseId metadata
    - Matching: find existing note sharing ≥1 tag, replace it
    - One note per concept cluster — bounded growth
    """
    col = _collection()
    doc_id = _doc_id(course_id, user_email)
    now = datetime.now(timezone.utc).isoformat()

    # Normalize tags
    concepts = [_normalize_tag(c) for c in concepts if c]
    if not concepts:
        concepts = ["_uncategorized"]
    primary = concepts[0]

    # Handle global profile separately
    if primary == "_profile":
        await col.update_one(
            {"_id": doc_id},
            {
                "$set": {
                    "profile": {"text": note_text, "updatedAt": now},
                    "lastUpdated": now,
                },
                "$setOnInsert": {"userEmail": user_email.lower()},
            },
            upsert=True,
        )
        log.info("Profile updated: %s (%d chars)", user_email, len(note_text))
        return {"action": "profile_updated", "primary_concept": "_profile"}

    # Build concept note with courseId metadata
    new_note = {
        "text": note_text,
        "tags": concepts,
        "courseId": course_id,
        "sessionId": session_id,
        "at": now,
    }
    if lesson:
        new_note["lesson"] = lesson

    new_set = set(concepts)
    doc = await col.find_one({"_id": doc_id})

    if doc:
        notes = doc.get("notes", [])

        # Find best matching existing note (most tag overlap)
        best_idx = -1
        best_overlap = 0
        for i, existing in enumerate(notes):
            existing_tags = _normalize_tags(existing.get("tags", []))
            overlap = len(new_set & set(existing_tags))
            if overlap > best_overlap:
                best_overlap = overlap
                best_idx = i

        old_primary = None
        if best_idx >= 0:
            old_tags = _normalize_tags(notes[best_idx].get("tags", []))
            old_primary = old_tags[0] if old_tags else "_uncategorized"
            notes[best_idx] = new_note
            action = "replaced"
        else:
            notes.append(new_note)
            action = "created"

        await col.update_one(
            {"_id": doc_id},
            {"$set": {"notes": notes, "lastUpdated": now}},
        )

        if old_primary and old_primary != primary:
            asyncio.create_task(_delete_vector_index_entry(
                course_id, user_email, old_primary
            ))
    else:
        await col.update_one(
            {"_id": doc_id},
            {
                "$set": {"notes": [new_note], "lastUpdated": now},
                "$setOnInsert": {"userEmail": user_email.lower()},
            },
            upsert=True,
        )
        action = "created"

    log.info("Mastery note %s: %s/%d [%s] (%d chars)",
             action, user_email, course_id, primary, len(note_text))

    # Sync to vector index in background
    asyncio.create_task(_sync_note_to_vector_index(
        course_id, user_email, note_text, concepts, session_id
    ))

    return {"action": action, "primary_concept": primary}


# ─── Vector Index Sync ─────────────────────────────────────────────

async def _delete_vector_index_entry(
    course_id: int, user_email: str, primary_tag: str
) -> None:
    """Delete an orphaned vector index entry (background task)."""
    try:
        doc_id = f"{user_email}:{course_id}:{primary_tag}"
        await _index_collection().delete_one({"_id": doc_id})
        log.debug("Deleted orphaned vector entry: %s", doc_id)
    except Exception as e:
        log.warning("Failed to delete orphaned vector entry: %s", e)

async def _sync_note_to_vector_index(
    course_id: int,
    user_email: str,
    note_text: str,
    tags: list[str],
    session_id: str,
) -> None:
    """Sync a note to the flat vector index (student_note_index).

    Generates embedding via OpenRouter, then upserts into the flat collection.
    Runs as background task — non-blocking.
    """
    try:
        from app.services.embedding_service import generate_embedding, get_embedding_metadata

        # Retry embedding up to 2 times
        embedding = None
        for attempt in range(2):
            embedding = await generate_embedding(note_text)
            if embedding:
                break
            if attempt == 0:
                await asyncio.sleep(1)  # brief wait before retry
        if not embedding:
            log.warning("Vector sync skipped — embedding failed after retries: %s", tags[:2])
            return

        now = datetime.now(timezone.utc).isoformat()
        meta = get_embedding_metadata()

        # Upsert by (studentEmail, courseId, primary tag) — one vector per concept cluster
        primary_tag = tags[0] if tags else "_uncategorized"
        doc_id = f"{user_email}:{course_id}:{primary_tag}"

        await _index_collection().update_one(
            {"_id": doc_id},
            {"$set": {
                "studentEmail": user_email,
                "courseId": course_id,
                "noteText": note_text[:2000],  # truncate for storage
                "tags": tags,
                "embedding": embedding,
                "embeddingModel": meta["model"],
                "embeddingProvider": meta["provider"],
                "sessionId": session_id,
                "updatedAt": now,
            }},
            upsert=True,
        )
        log.debug("Vector index synced: %s/%d/%s", user_email, course_id, primary_tag)

    except Exception as e:
        log.warning("Vector index sync failed: %s", e)


async def vector_search_notes(
    course_id: int,
    user_email: str,
    query: str,
    limit: int = 5,
    threshold: float = 0.72,
) -> list[dict]:
    """Search student notes using MongoDB Atlas Vector Search.

    Returns notes semantically similar to the query, filtered by student+course.
    Uses cosine similarity with a threshold to reject noise.

    Args:
        course_id: Course to search within
        user_email: Student's email
        query: Natural language search query
        limit: Max results to return
        threshold: Minimum similarity score (0-1). Higher = stricter.

    Returns:
        List of {noteText, tags, score, updatedAt} dicts, sorted by relevance.
    """
    try:
        from app.services.embedding_service import generate_embedding

        query_embedding = await generate_embedding(query)
        if not query_embedding:
            return []

        # MongoDB Atlas Vector Search aggregation
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "mastery_vector_index",
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": limit * 4,  # over-fetch then filter
                    "limit": limit * 2,
                    "filter": {
                        "studentEmail": user_email,
                        "courseId": course_id,
                    },
                }
            },
            {
                "$addFields": {
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
            {
                "$match": {
                    "score": {"$gte": threshold},
                }
            },
            {
                "$limit": limit,
            },
            {
                "$project": {
                    "_id": 0,
                    "noteText": 1,
                    "tags": 1,
                    "score": 1,
                    "updatedAt": 1,
                }
            },
        ]

        cursor = _index_collection().aggregate(pipeline)
        results = await cursor.to_list(limit)

        log.info("Vector search: %s/%d query='%s' → %d results (threshold=%.2f)",
                 user_email, course_id, query[:50], len(results), threshold)

        return results

    except Exception as e:
        log.warning("Vector search failed: %s", e)
        return []


async def hybrid_search_notes(
    course_id: int,
    user_email: str,
    query: str,
    limit: int = 5,
) -> str:
    """Hybrid search: vector search + text search, deduplicated and merged.

    Returns formatted string for tutor context injection.
    Falls back to text-only search if vector search fails.
    """
    # Try vector search first
    vector_results = await vector_search_notes(course_id, user_email, query, limit)

    # Also do text search (existing method)
    text_results = await search_notes(course_id, user_email, query)

    # If vector search returned results, format them
    if vector_results:
        lines = [f"Found {len(vector_results)} relevant notes:"]
        seen_tags = set()
        for r in vector_results:
            tags = r.get("tags", [])
            tag_key = tuple(tags) if tags else ("_none",)
            if tag_key in seen_tags:
                continue
            seen_tags.add(tag_key)

            text = r.get("noteText", "")
            score = r.get("score", 0)
            tags_str = f" [{', '.join(tags)}]" if tags else ""
            display = text if len(text) <= 250 else text[:250] + "..."
            lines.append(f"  [{score:.0%}] {display}{tags_str}")

        return "\n".join(lines)

    # Fallback to text search
    return text_results


async def search_notes(
    course_id: int,
    user_email: str,
    query: str,
) -> str:
    """Search student knowledge notes by substring matching.

    Case-insensitive search across note text and tags.
    Returns matching notes formatted for the tutor, most relevant first.
    """
    col = _collection()
    doc_id = _doc_id(course_id, user_email)
    doc = await col.find_one({"_id": doc_id})

    if not doc:
        return "No knowledge notes recorded yet for this student."

    notes = doc.get("notes", [])
    if not notes:
        return "No knowledge notes recorded yet for this student."

    query_lower = query.lower().strip()
    query_terms = query_lower.split()
    matches = []

    for i, note in enumerate(notes):
        text = note.get("text", "")
        tags = _normalize_tags(note.get("tags", []))
        text_lower = text.lower()
        tags_lower = [t.lower() for t in tags]

        score = 0

        # Score: query terms found in text
        for term in query_terms:
            if term in text_lower:
                score += 2

        # Score: tag matches (bonus)
        for term in query_terms:
            for tag in tags_lower:
                if term in tag:
                    score += 3

        if score > 0:
            matches.append((score, i, note))

    if not matches:
        return f"No notes matching '{query}' found."

    # Sort by relevance descending, then by recency (index) descending
    matches.sort(key=lambda x: (-x[0], -x[1]))

    lines = [f"Found {len(matches)} note{'s' if len(matches) != 1 else ''} matching '{query}':"]
    for _, idx, note in matches[:10]:
        text = note.get("text", "")
        tags = note.get("tags", [])
        at = note.get("at", "")

        # Truncate long notes for display
        display_text = text if len(text) <= 200 else text[:200] + "..."
        tags_str = f" [{', '.join(tags)}]" if tags else ""

        # Format timestamp
        time_str = ""
        if at:
            try:
                dt = datetime.fromisoformat(at)
                days_ago = (datetime.now(timezone.utc) - dt).days
                if days_ago == 0:
                    time_str = " (today)"
                elif days_ago == 1:
                    time_str = " (yesterday)"
                else:
                    time_str = f" ({days_ago}d ago)"
            except (ValueError, TypeError):
                pass

        lines.append(f"\n  - {display_text}{tags_str}{time_str}")

    return "\n".join(lines)


async def get_knowledge_summary(course_id: int, user_email: str) -> str | None:
    """Return a structured student briefing for system prompt injection.

    Groups notes by profile vs concept, presenting an actionable overview.
    Returns None if no notes exist.
    """
    col = _collection()
    doc_id = _doc_id(course_id, user_email)
    doc = await col.find_one({"_id": doc_id})

    if not doc:
        return None

    # NOTE: doc.summary cache removed — was never populated, always stale.
    # Always format fresh from notes.

    # Global profile (course-independent)
    profile = doc.get("profile")
    profile_text = profile.get("text") if isinstance(profile, dict) else None

    # Concept notes — filter by courseId if provided, show all otherwise
    notes = doc.get("notes", [])
    concept_entries = []
    for note in notes:
        tags = _normalize_tags(note.get("tags", []))
        text = note.get("text", "")
        primary = tags[0] if tags else ""
        note_course = note.get("courseId")

        if not primary or primary.startswith("_"):
            continue
        # Show notes from this course + notes with no course (universal)
        if course_id and note_course and note_course != course_id:
            continue
        snippet = text if len(text) <= 150 else text[:150] + "..."
        course_tag = f" [course:{note_course}]" if note_course and note_course != course_id else ""
        concept_entries.append(f"  {primary}: {snippet}{course_tag}")

    if not profile_text and not concept_entries:
        return None

    parts = []
    if profile_text:
        parts.append(f"[Student Profile — Global] {profile_text}")
    if concept_entries:
        parts.append(f"[Student Concept Mastery — {len(concept_entries)} concepts]")
        parts.extend(concept_entries)

    return "\n".join(parts) if parts else None


# ─── Legacy compatibility ──────────────────────────────────────────

async def get_or_init_knowledge_state(course_id: int, student_name: str) -> dict:
    """Load student mastery state. Returns empty structure if none exists."""
    col = _collection()
    doc_id = _doc_id(course_id, student_name)
    doc = await col.find_one({"_id": doc_id})
    if doc:
        return doc
    return {"notes": [], "profile": None}


def format_knowledge_state(knowledge_state: dict) -> str:
    """Format student mastery state for tutor context."""
    profile = knowledge_state.get("profile")
    notes = knowledge_state.get("notes", [])

    if not notes and not profile:
        return "No student notes yet — this is a new student."

    lines = []

    if profile and isinstance(profile, dict) and profile.get("text"):
        lines.append("[Student Profile — Global]")
        lines.append(f"  {profile['text']}")
        lines.append("")

    if notes:
        concept_notes = {}
        for note in notes:
            tags = _normalize_tags(note.get("tags", []))
            text = note.get("text", "")
            primary = tags[0] if tags else "_uncategorized"
            if primary.startswith("_"):
                continue
            concept_notes[primary] = {
                "text": text,
                "tags": tags,
                "lesson": note.get("lesson", ""),
                "courseId": note.get("courseId"),
            }

        if concept_notes:
            lines.append(f"[Student Concept Mastery — {len(concept_notes)} concepts]")
            for concept, data in concept_notes.items():
                text = data["text"]
                snippet = text if len(text) <= 200 else text[:200] + "..."
                other_tags = [t for t in data["tags"] if t != concept]
                related = f" (also: {', '.join(other_tags)})" if other_tags else ""
                lesson = f" [L:{data['lesson']}]" if data.get("lesson") else ""
                lines.append(f"  {concept}{related}{lesson}: {snippet}")

    if not lines:
        lines.append("No student notes yet — this is a new student.")

    return "\n".join(lines)


# ─── Backfill / Reindex ──────────────────────────────────────────

async def backfill_vector_index(dry_run: bool = False) -> dict:
    """Scan all concept_states docs, generate embeddings for notes missing from vector index.

    - Skips notes that already have a matching vector doc (by doc_id)
    - Removes orphaned vector docs that no longer match any source note
    - Returns stats: {total_notes, synced, skipped, orphans_removed, errors}
    """
    from app.services.embedding_service import generate_embedding, get_embedding_metadata

    col = _collection()
    idx = _index_collection()
    stats = {"total_notes": 0, "synced": 0, "skipped": 0, "orphans_removed": 0, "errors": 0}

    # Collect all valid vector doc_ids from source
    valid_vector_ids = set()

    cursor = col.find({})
    async for doc in cursor:
        course_id = doc.get("courseId")
        user_email = doc.get("userEmail")
        if not course_id or not user_email:
            continue

        notes = doc.get("notes", [])
        for note in notes:
            tags = _normalize_tags(note.get("tags", []))
            text = note.get("text", "")
            primary = tags[0] if tags else "_uncategorized"
            if not text or primary == "_profile":
                continue

            stats["total_notes"] += 1
            vector_id = f"{user_email}:{course_id}:{primary}"
            valid_vector_ids.add(vector_id)

            # Check if vector doc already exists
            existing = await idx.find_one({"_id": vector_id}, {"_id": 1})
            if existing:
                stats["skipped"] += 1
                continue

            if dry_run:
                stats["synced"] += 1
                continue

            # Generate embedding and upsert
            try:
                embedding = await generate_embedding(text)
                if not embedding:
                    stats["errors"] += 1
                    continue

                now = datetime.now(timezone.utc).isoformat()
                meta = get_embedding_metadata()

                await idx.update_one(
                    {"_id": vector_id},
                    {"$set": {
                        "studentEmail": user_email,
                        "courseId": course_id,
                        "noteText": text[:2000],
                        "tags": tags,
                        "embedding": embedding,
                        "embeddingModel": meta["model"],
                        "embeddingProvider": meta["provider"],
                        "sessionId": note.get("sessionId", "backfill"),
                        "updatedAt": now,
                    }},
                    upsert=True,
                )
                stats["synced"] += 1
                log.info("Backfilled vector: %s/%d/%s", user_email, course_id, primary)

            except Exception as e:
                stats["errors"] += 1
                log.warning("Backfill failed for %s: %s", vector_id, e)

    # Clean orphaned vector docs
    if not dry_run:
        orphan_cursor = idx.find({}, {"_id": 1})
        async for vdoc in orphan_cursor:
            if vdoc["_id"] not in valid_vector_ids:
                await idx.delete_one({"_id": vdoc["_id"]})
                stats["orphans_removed"] += 1
                log.info("Removed orphan vector doc: %s", vdoc["_id"])

    log.info("Backfill complete: %s", stats)
    return stats
