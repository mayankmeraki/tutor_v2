"""Knowledge state service — append-only freehand notes per student-course.

One MongoDB document per student-course. The tutor writes natural prose
observations that accumulate over time. No structured concepts, no enums,
no mastery scores — just notes with optional tags and substring search.

Collection: concept_states (in tutor_v2 database)

Document schema:
    _id:           ks_{courseId}_{safeEmail}
    courseId:       int
    userEmail:      str
    notes:         [{text, tags, sessionId, at}]   # append-only
    summary:       str | null                      # rolling summary
    lastUpdated:   ISO datetime
"""

import logging
from datetime import datetime, timezone

from app.core.mongodb import get_tutor_db

log = logging.getLogger(__name__)


# ─── Collection accessor ───────────────────────────────────────────

def _collection():
    return get_tutor_db()["concept_states"]


def _doc_id(course_id: int, user_email: str) -> str:
    safe_email = user_email.replace(".", "_dot_").replace("@", "_at_")
    return f"ks_{course_id}_{safe_email}"


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

    return {"logged": True, "note_length": len(text), "tags": tags or []}


def _normalize_tags(tags) -> list[str]:
    """Convert tags to a list of strings regardless of input format."""
    if isinstance(tags, str):
        return [t.strip() for t in tags.replace(",", " ").split() if t.strip()]
    if isinstance(tags, list):
        return [str(t).strip() for t in tags if t]
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

    Matching strategy: find any existing note that shares at least one
    concept tag with the new note. If found, REPLACE it entirely.
    If multiple match, replace the one with the most tag overlap.
    This keeps notes bounded — one note per concept cluster.
    """
    col = _collection()
    doc_id = _doc_id(course_id, user_email)
    now = datetime.now(timezone.utc).isoformat()
    primary = concepts[0] if concepts else "_uncategorized"

    new_note = {
        "text": note_text,
        "tags": concepts,
        "sessionId": session_id,
        "at": now,
    }
    if lesson:
        new_note["lesson"] = lesson

    new_set = set(concepts)

    doc = await col.find_one({"_id": doc_id})

    if doc:
        notes = doc.get("notes", [])

        # Find the best matching existing note (most tag overlap)
        best_idx = -1
        best_overlap = 0
        for i, existing in enumerate(notes):
            existing_tags = _normalize_tags(existing.get("tags", []))
            overlap = len(new_set & set(existing_tags))
            if overlap > best_overlap:
                best_overlap = overlap
                best_idx = i

        if best_idx >= 0:
            notes[best_idx] = new_note
            action = "replaced"
        else:
            notes.append(new_note)
            action = "created"

        await col.update_one(
            {"_id": doc_id},
            {"$set": {"notes": notes, "lastUpdated": now}},
        )
    else:
        await col.update_one(
            {"_id": doc_id},
            {
                "$set": {"notes": [new_note], "lastUpdated": now},
                "$setOnInsert": {
                    "courseId": course_id,
                    "userEmail": user_email,
                    "summary": None,
                },
            },
            upsert=True,
        )
        action = "created"

    log.info("Knowledge note %s: %s/%d [%s] (%d chars)",
             action, user_email, course_id, primary, len(note_text))

    return {"action": action, "primary_concept": primary}


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

    if doc.get("summary"):
        return doc["summary"]

    notes = doc.get("notes", [])
    if not notes:
        return None

    profile_text = None
    concept_entries = []

    for note in notes:
        tags = _normalize_tags(note.get("tags", []))
        text = note.get("text", "")
        primary = tags[0] if tags else ""

        if primary == "_profile":
            profile_text = text
        elif primary:
            snippet = text if len(text) <= 150 else text[:150] + "..."
            concept_entries.append(f"  {primary}: {snippet}")

    parts = []
    if profile_text:
        parts.append(f"[Student Profile] {profile_text}")
    if concept_entries:
        parts.append(f"[Student Notes — {len(concept_entries)} concepts]")
        parts.extend(concept_entries)

    return "\n".join(parts) if parts else None


# ─── Legacy compatibility ──────────────────────────────────────────

async def get_or_init_knowledge_state(course_id: int, student_name: str) -> dict:
    """Legacy wrapper — used by _load_knowledge_state in chat.py."""
    col = _collection()
    doc_id = _doc_id(course_id, student_name)
    doc = await col.find_one({"_id": doc_id})
    if doc:
        return doc
    # Return empty structure (don't create doc — append_note handles upsert)
    return {"notes": [], "summary": None}


def format_knowledge_state(knowledge_state: dict) -> str:
    """Format student notes grouped by concept for tutor context."""
    notes = knowledge_state.get("notes", [])
    if not notes:
        return "No student notes yet — this is a new student."

    profile_notes = []
    concept_notes = {}

    for note in notes:
        tags = _normalize_tags(note.get("tags", []))
        text = note.get("text", "")
        primary = tags[0] if tags else "_uncategorized"
        lesson = note.get("lesson", "")

        if primary == "_profile":
            profile_notes.append(text)
        else:
            concept_notes[primary] = {
                "text": text,
                "tags": tags,
                "lesson": lesson,
            }

    lines = []

    if profile_notes:
        lines.append("[Student Profile]")
        for p in profile_notes:
            lines.append(f"  {p}")
        lines.append("")

    if concept_notes:
        lines.append(f"[Student Notes — {len(concept_notes)} concepts]")
        for concept, data in concept_notes.items():
            text = data["text"]
            snippet = text if len(text) <= 200 else text[:200] + "..."
            other_tags = [t for t in data["tags"] if t != concept]
            related = f" (also: {', '.join(other_tags)})" if other_tags else ""
            lesson = f" [L:{data['lesson']}]" if data.get("lesson") else ""
            lines.append(f"  {concept}{related}{lesson}: {snippet}")
    elif not profile_notes:
        lines.append("No student notes yet — this is a new student.")

    return "\n".join(lines)
