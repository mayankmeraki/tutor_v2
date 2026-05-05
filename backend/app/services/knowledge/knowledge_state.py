"""Student concept mastery — freehand notes per student.

One MongoDB document per student. Contains:
- Global profile: learning style, pace, preferences
- Concept notes: mastery observations

Collection: student_concept_mastery (in tutor_v2 database)
Vector index: student_concept_mastery_vectors (flat, for Atlas Vector Search)

Document schema:
    _id:           mastery_{safeEmail}
    userEmail:     str
    profile:       {text, updatedAt}
    notes:         [{text, tags, sessionId, lesson, at}]
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


def _doc_id(user_email: str) -> str:
    """Document ID — per student."""
    safe_email = user_email.lower().replace(".", "_dot_").replace("@", "_at_")
    return f"mastery_{safe_email}"


# ─── Core Operations ───────────────────────────────────────────────


def _normalize_tag(tag: str) -> str:
    """Normalize a single tag: lowercase, spaces→underscores, strip special chars."""
    import re
    t = str(tag).strip().lower()
    t = re.sub(r'[^a-z0-9_\-]', '_', t)
    t = re.sub(r'_+', '_', t)
    return t.strip('_') or '_uncategorized'


def _normalize_tags(tags) -> list[str]:
    if isinstance(tags, str):
        return [_normalize_tag(t) for t in tags.replace(",", " ").split() if t.strip()]
    if isinstance(tags, list):
        return [_normalize_tag(str(t)) for t in tags if t]
    return []


async def upsert_concept_note(
    user_email: str,
    session_id: str,
    concepts: list[str],
    note_text: str,
    lesson: str | None = None,
    blooms: str | None = None,
    approach_tried: str | None = None,
    approach_worked: bool | None = None,
) -> dict:
    """Upsert a freehand note by concept overlap.

    - _profile notes update the global profile
    - Matching: find existing note sharing ≥1 tag, replace it
    - One note per concept cluster — bounded growth
    """
    col = _collection()
    doc_id = _doc_id(user_email)
    now = datetime.now(timezone.utc).isoformat()

    concepts = [_normalize_tag(c) for c in concepts if c]
    if not concepts:
        concepts = ["_uncategorized"]
    primary = concepts[0]

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

    new_note = {
        "text": note_text,
        "tags": concepts,
        "sessionId": session_id,
        "at": now,
    }
    if blooms:
        new_note["blooms"] = blooms.lower()
    if approach_tried:
        new_note["approach_tried"] = approach_tried
    if approach_worked is not None:
        new_note["approach_worked"] = approach_worked
    if lesson:
        new_note["lesson"] = lesson

    new_set = set(concepts)
    doc = await col.find_one({"_id": doc_id})

    if doc:
        notes = doc.get("notes", [])

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
            asyncio.create_task(_delete_vector_index_entry(user_email, old_primary))
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

    log.info("Mastery note %s: %s [%s] (%d chars)",
             action, user_email, primary, len(note_text))

    asyncio.create_task(_sync_note_to_vector_index(
        user_email, note_text, concepts, session_id
    ))

    return {"action": action, "primary_concept": primary}


# ─── Vector Index Sync ─────────────────────────────────────────────


async def _delete_vector_index_entry(user_email: str, primary_tag: str) -> None:
    try:
        doc_id = f"{user_email}:{primary_tag}"
        await _index_collection().delete_one({"_id": doc_id})
        log.debug("Deleted orphaned vector entry: %s", doc_id)
    except Exception as e:
        log.warning("Failed to delete orphaned vector entry: %s", e)


async def _sync_note_to_vector_index(
    user_email: str,
    note_text: str,
    tags: list[str],
    session_id: str,
) -> None:
    """Sync a note to the flat vector index. Background task — non-blocking."""
    try:
        from app.services.content.embedding_service import generate_embedding, get_embedding_metadata

        embedding = None
        for attempt in range(2):
            embedding = await generate_embedding(note_text)
            if embedding:
                break
            if attempt == 0:
                await asyncio.sleep(1)
        if not embedding:
            log.warning("Vector sync skipped — embedding failed after retries: %s", tags[:2])
            return

        now = datetime.now(timezone.utc).isoformat()
        meta = get_embedding_metadata()

        primary_tag = tags[0] if tags else "_uncategorized"
        doc_id = f"{user_email}:{primary_tag}"

        await _index_collection().update_one(
            {"_id": doc_id},
            {"$set": {
                "studentEmail": user_email,
                "noteText": note_text[:2000],
                "tags": tags,
                "embedding": embedding,
                "embeddingModel": meta["model"],
                "embeddingProvider": meta["provider"],
                "sessionId": session_id,
                "updatedAt": now,
            }},
            upsert=True,
        )
        log.debug("Vector index synced: %s/%s", user_email, primary_tag)

    except Exception as e:
        log.warning("Vector index sync failed: %s", e)


async def vector_search_notes(
    user_email: str,
    query: str,
    limit: int = 5,
    threshold: float = 0.72,
) -> list[dict]:
    """Search student notes using MongoDB Atlas Vector Search."""
    try:
        from app.services.content.embedding_service import generate_embedding

        query_embedding = await generate_embedding(query)
        if not query_embedding:
            return []

        pipeline = [
            {
                "$vectorSearch": {
                    "index": "mastery_vector_index",
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": limit * 4,
                    "limit": limit * 2,
                    "filter": {
                        "studentEmail": user_email,
                    },
                }
            },
            {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
            {"$match": {"score": {"$gte": threshold}}},
            {"$limit": limit},
            {"$project": {"_id": 0, "noteText": 1, "tags": 1, "score": 1, "updatedAt": 1}},
        ]

        cursor = _index_collection().aggregate(pipeline)
        results = await cursor.to_list(limit)

        log.info("Vector search: %s query='%s' → %d results (threshold=%.2f)",
                 user_email, query[:50], len(results), threshold)

        return results

    except Exception as e:
        log.warning("Vector search failed: %s", e)
        return []


async def hybrid_search_notes(
    user_email: str,
    query: str,
    limit: int = 5,
) -> str:
    """Hybrid search: vector + text, deduplicated.

    Returns formatted string for tutor context injection.
    Falls back to text-only search if vector search fails.
    """
    vector_results = await vector_search_notes(user_email, query, limit)
    text_results = await search_notes(user_email, query)

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

    return text_results


async def search_notes(user_email: str, query: str) -> str:
    """Search student knowledge notes by substring matching."""
    col = _collection()
    doc_id = _doc_id(user_email)
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
        for term in query_terms:
            if term in text_lower:
                score += 2
        for term in query_terms:
            for tag in tags_lower:
                if term in tag:
                    score += 3

        if score > 0:
            matches.append((score, i, note))

    if not matches:
        return f"No notes matching '{query}' found."

    matches.sort(key=lambda x: (-x[0], -x[1]))

    lines = [f"Found {len(matches)} note{'s' if len(matches) != 1 else ''} matching '{query}':"]
    for _, idx, note in matches[:10]:
        text = note.get("text", "")
        tags = note.get("tags", [])
        at = note.get("at", "")

        display_text = text if len(text) <= 200 else text[:200] + "..."
        tags_str = f" [{', '.join(tags)}]" if tags else ""

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


async def get_knowledge_summary(user_email: str) -> str | None:
    """Return a structured student briefing for system prompt injection."""
    col = _collection()
    doc_id = _doc_id(user_email)
    doc = await col.find_one({"_id": doc_id})

    if not doc:
        return None

    profile = doc.get("profile")
    profile_text = profile.get("text") if isinstance(profile, dict) else None

    notes = doc.get("notes", [])
    concept_entries = []
    for note in notes:
        tags = _normalize_tags(note.get("tags", []))
        text = note.get("text", "")
        primary = tags[0] if tags else ""

        if not primary or primary.startswith("_"):
            continue
        snippet = text if len(text) <= 150 else text[:150] + "..."
        concept_entries.append(f"  {primary}: {snippet}")

    if not profile_text and not concept_entries:
        return None

    parts = []
    if profile_text:
        parts.append(f"[Student Profile — Global] {profile_text}")
    if concept_entries:
        parts.append(f"[Student Concept Mastery — {len(concept_entries)} concepts]")
        parts.extend(concept_entries)

    return "\n".join(parts) if parts else None


async def get_or_init_knowledge_state(user_email: str) -> dict:
    """Load student mastery state. Returns empty structure if none exists."""
    col = _collection()
    doc_id = _doc_id(user_email)
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
        concept_groups = {}
        for note in notes:
            tags = _normalize_tags(note.get("tags", []))
            text = note.get("text", "")
            primary = tags[0] if tags else "_uncategorized"
            if primary.startswith("_"):
                continue
            at = note.get("at", "")
            existing = concept_groups.get(primary)
            if existing is None:
                concept_groups[primary] = {
                    "count": 1,
                    "latest_text": text,
                    "latest_at": at,
                    "tags": tags,
                    "lesson": note.get("lesson", ""),
                }
            else:
                existing["count"] += 1
                if at > existing["latest_at"]:
                    existing["latest_text"] = text
                    existing["latest_at"] = at
                    existing["tags"] = tags
                    existing["lesson"] = note.get("lesson", "")

        if concept_groups:
            lines.append(f"[Student Concept Mastery — {len(concept_groups)} concepts]")
            sorted_concepts = sorted(
                concept_groups.items(),
                key=lambda kv: (-kv[1]["count"], kv[0]),
            )
            for concept, data in sorted_concepts:
                text = data["latest_text"]
                snippet = text if len(text) <= 200 else text[:200] + "..."
                other_tags = [t for t in data["tags"] if t != concept]
                related = f" (also: {', '.join(other_tags)})" if other_tags else ""
                lesson = f" [L:{data['lesson']}]" if data.get("lesson") else ""
                count = data["count"]
                if count == 1:
                    counter = ""
                elif count == 2:
                    counter = " [seen 2x]"
                else:
                    counter = f" [seen {count}x — IF STILL STRUGGLING, USE A DIFFERENT APPROACH]"
                lines.append(f"  {concept}{related}{lesson}{counter}: {snippet}")

    if not lines:
        lines.append("No student notes yet — this is a new student.")

    return "\n".join(lines)


# ─── Backfill / Reindex ──────────────────────────────────────────


async def backfill_vector_index(dry_run: bool = False) -> dict:
    """Scan all mastery docs, generate embeddings for notes missing from vector index."""
    from app.services.content.embedding_service import generate_embedding, get_embedding_metadata

    col = _collection()
    idx = _index_collection()
    stats = {"total_notes": 0, "synced": 0, "skipped": 0, "orphans_removed": 0, "errors": 0}

    valid_vector_ids = set()

    cursor = col.find({})
    async for doc in cursor:
        user_email = doc.get("userEmail")
        if not user_email:
            continue

        notes = doc.get("notes", [])
        for note in notes:
            tags = _normalize_tags(note.get("tags", []))
            text = note.get("text", "")
            primary = tags[0] if tags else "_uncategorized"
            if not text or primary == "_profile":
                continue

            stats["total_notes"] += 1
            vector_id = f"{user_email}:{primary}"
            valid_vector_ids.add(vector_id)

            existing = await idx.find_one({"_id": vector_id}, {"_id": 1})
            if existing:
                stats["skipped"] += 1
                continue

            if dry_run:
                stats["synced"] += 1
                continue

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
                log.info("Backfilled vector: %s/%s", user_email, primary)

            except Exception as e:
                stats["errors"] += 1
                log.warning("Backfill failed for %s: %s", vector_id, e)

    if not dry_run:
        orphan_cursor = idx.find({}, {"_id": 1})
        async for vdoc in orphan_cursor:
            if vdoc["_id"] not in valid_vector_ids:
                await idx.delete_one({"_id": vdoc["_id"]})
                stats["orphans_removed"] += 1
                log.info("Removed orphan vector doc: %s", vdoc["_id"])

    log.info("Backfill complete: %s", stats)
    return stats
