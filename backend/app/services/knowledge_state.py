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
        tags = note.get("tags", [])
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
    """Return a brief summary for system prompt injection.

    Returns doc.summary if set. Otherwise builds a simple summary
    from the last few notes. Returns None if no notes exist.
    """
    col = _collection()
    doc_id = _doc_id(course_id, user_email)
    doc = await col.find_one({"_id": doc_id})

    if not doc:
        return None

    # If there's a pre-built summary, use it
    if doc.get("summary"):
        return doc["summary"]

    notes = doc.get("notes", [])
    if not notes:
        return None

    # Build a simple summary from the last N notes
    recent = notes[-5:]  # Last 5 notes
    total = len(notes)

    parts = [f"{total} observation{'s' if total != 1 else ''} recorded."]

    # Collect all tags for a quick overview
    all_tags = set()
    for note in notes:
        all_tags.update(note.get("tags", []))
    if all_tags:
        parts.append(f"Topics: {', '.join(sorted(all_tags)[:10])}.")

    # Show most recent notes (truncated)
    parts.append("Recent:")
    for note in recent:
        text = note.get("text", "")
        snippet = text if len(text) <= 100 else text[:100] + "..."
        parts.append(f"  - {snippet}")

    return "\n".join(parts)


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
    """Legacy format — used by _load_knowledge_state in chat.py."""
    notes = knowledge_state.get("notes", [])
    if not notes:
        return "No knowledge notes yet."

    # Show last 5 notes
    recent = notes[-5:]
    lines = [f"{len(notes)} note{'s' if len(notes) != 1 else ''} recorded. Recent:"]
    for note in recent:
        text = note.get("text", "")
        snippet = text if len(text) <= 120 else text[:120] + "..."
        tags = note.get("tags", [])
        tags_str = f" [{', '.join(tags)}]" if tags else ""
        lines.append(f"  - {snippet}{tags_str}")

    return "\n".join(lines)
