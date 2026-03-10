"""Knowledge state service — per-student, per-course concept mastery (async MongoDB).

Mirrors capacity's student_state.py pattern but uses Motor (async) and
a simplified mastery calculation (no lessons_completed or prereq_avg_mastery).

Collection: concept_states (in tutor_v2 database, same as sessions)

Document schema:
    _id:              state_{courseId}_{studentName}
    courseId:          int
    studentName:      str
    concepts:
      {concept_name}:
        mastery:              float 0-1
        tested:               bool
        test_passed:          bool | None
        able_to_explain:      bool
        evidence_level:       int (1-7, from evidence hierarchy)
        last_seen:            str (ISO datetime)
        first_seen:           str (ISO datetime)
        verification_count:   int
        notes:                [{at: str, text: str}]
    last_updated:     str (ISO datetime)
"""

import logging
from datetime import datetime, timezone

from app.core.mongodb import get_tutor_db

log = logging.getLogger(__name__)


# ─── Collection accessor ───────────────────────────────────────────

def _collection():
    return get_tutor_db()["concept_states"]


# ─── Mastery Calculation ───────────────────────────────────────────

def calculate_mastery(concept_state: dict) -> float:
    """Deterministic mastery from signals. Mirrors capacity's calculate_mastery.

    Score breakdown:
        +0.35  able_to_explain (L5+ evidence)
        +0.25  tested and passed
        +0.10  engaged (has notes)
        +0.05  recency bonus (seen in last 3 days)
        -0.15  tested but failed
    Clamped to [0.0, 1.0]
    """
    score = 0.0

    if concept_state.get("able_to_explain"):
        score += 0.35

    if concept_state.get("tested"):
        if concept_state.get("test_passed"):
            score += 0.25
        else:
            score -= 0.15

    if concept_state.get("notes"):
        score += 0.10

    last_seen = concept_state.get("last_seen")
    if last_seen:
        try:
            last_dt = datetime.fromisoformat(last_seen)
            days_ago = (datetime.now(timezone.utc) - last_dt).days
            if days_ago <= 3:
                score += 0.05
        except (ValueError, TypeError):
            pass

    return max(0.0, min(1.0, round(score, 2)))


# ─── Init & CRUD ──────────────────────────────────────────────────

async def get_or_init_knowledge_state(course_id: int, student_name: str) -> dict:
    """Load or create concept state. Mirrors capacity's get_or_init_student_state."""
    col = _collection()
    doc_id = f"state_{course_id}_{student_name}"

    doc = await col.find_one({"_id": doc_id})
    if doc:
        return doc

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "_id": doc_id,
        "courseId": course_id,
        "studentName": student_name,
        "concepts": {},
        "last_updated": now,
    }
    await col.insert_one(doc)
    log.info("Initialized knowledge state: course %d, student %s", course_id, student_name)
    return doc


async def get_knowledge_state(course_id: int, student_name: str) -> dict | None:
    """Get a student's concept state for a course."""
    doc_id = f"state_{course_id}_{student_name}"
    return await _collection().find_one({"_id": doc_id})


# ─── Updates ──────────────────────────────────────────────────────

async def log_interaction(
    course_id: int,
    student_name: str,
    concept_name: str,
    note: str = "",
    tested: bool | None = None,
    test_passed: bool | None = None,
    able_to_explain: bool | None = None,
    evidence_level: int | None = None,
) -> dict:
    """Log an interaction and recalculate mastery. Mirrors capacity's log_interaction."""
    col = _collection()
    now = datetime.now(timezone.utc).isoformat()

    state = await get_or_init_knowledge_state(course_id, student_name)
    doc_id = state["_id"]

    # Ensure concept exists in state
    if concept_name not in state.get("concepts", {}):
        await col.update_one(
            {"_id": doc_id},
            {"$set": {f"concepts.{concept_name}": {
                "mastery": 0.0,
                "tested": False,
                "test_passed": None,
                "able_to_explain": False,
                "evidence_level": 0,
                "last_seen": now,
                "first_seen": now,
                "verification_count": 0,
                "notes": [],
            }}}
        )

    # Build $set update
    update_ops: dict = {
        f"concepts.{concept_name}.last_seen": now,
        "last_updated": now,
    }

    if tested is not None:
        update_ops[f"concepts.{concept_name}.tested"] = tested
    if test_passed is not None:
        update_ops[f"concepts.{concept_name}.test_passed"] = test_passed
    if able_to_explain is not None:
        update_ops[f"concepts.{concept_name}.able_to_explain"] = able_to_explain
    if evidence_level is not None:
        update_ops[f"concepts.{concept_name}.evidence_level"] = evidence_level

    push_ops = {}
    if note:
        push_ops[f"concepts.{concept_name}.notes"] = {"at": now, "text": note}

    update_cmd: dict = {"$set": update_ops}
    if push_ops:
        update_cmd["$push"] = push_ops

    await col.update_one({"_id": doc_id}, update_cmd)

    # Recalculate mastery
    updated = await col.find_one({"_id": doc_id})
    concept_state = updated.get("concepts", {}).get(concept_name, {})
    mastery = calculate_mastery(concept_state)
    await col.update_one(
        {"_id": doc_id},
        {"$set": {f"concepts.{concept_name}.mastery": mastery}}
    )

    log.info(
        "Logged interaction: %s/%s concept=%s mastery=%.2f",
        student_name, course_id, concept_name, mastery,
    )
    return {**concept_state, "mastery": mastery}


async def batch_update_concepts(
    course_id: int,
    student_name: str,
    concept_status: dict,
    tutor_notes: str = "",
) -> None:
    """Bulk-update concepts from Tutor's concept_status observations.

    Maps statuses to mastery signals:
      verified → tested=True, test_passed=True, able_to_explain=True, evidence_level=5
      checked  → tested=True, test_passed=True, evidence_level=4
      gapped   → tested=True, test_passed=False, evidence_level=2
    """
    status_map = {
        "verified": {
            "tested": True,
            "test_passed": True,
            "able_to_explain": True,
            "evidence_level": 5,
        },
        "checked": {
            "tested": True,
            "test_passed": True,
            "able_to_explain": False,
            "evidence_level": 4,
        },
        "gapped": {
            "tested": True,
            "test_passed": False,
            "able_to_explain": False,
            "evidence_level": 2,
        },
        "persisting": {
            "tested": True,
            "test_passed": False,
            "able_to_explain": False,
            "evidence_level": 1,
        },
    }

    for concept_name, status in concept_status.items():
        signals = status_map.get(status)
        if not signals:
            # touched, explored, deepened — just log interaction without test signals
            await log_interaction(
                course_id, student_name, concept_name,
                note=tutor_notes if tutor_notes else f"Status: {status}",
            )
            continue

        # For verified, increment verification_count
        if status == "verified":
            col = _collection()
            state = await get_or_init_knowledge_state(course_id, student_name)
            await col.update_one(
                {"_id": state["_id"]},
                {"$inc": {f"concepts.{concept_name}.verification_count": 1}}
            )

        await log_interaction(
            course_id, student_name, concept_name,
            note=tutor_notes if tutor_notes else f"Status: {status}",
            **signals,
        )

    log.info(
        "Batch update concepts: %s/%d — %d concepts",
        student_name, course_id, len(concept_status),
    )


# ─── Formatting for Tutor Context ─────────────────────────────────

def format_knowledge_state(knowledge_state: dict) -> str:
    """Format concept state for the Tutor prompt context.

    Groups by status, highlights stale concepts (>7 days).
    """
    concepts = knowledge_state.get("concepts", {})
    if not concepts:
        return "No concept history yet."

    now = datetime.now(timezone.utc)

    verified = []
    checked = []
    gapped = []
    other = []

    for name, state in concepts.items():
        mastery = state.get("mastery", 0.0)
        evidence = state.get("evidence_level", 0)
        last_seen = state.get("last_seen")
        verification_count = state.get("verification_count", 0)

        # Calculate staleness
        days_ago = None
        stale = False
        if last_seen:
            try:
                last_dt = datetime.fromisoformat(last_seen)
                days_ago = (now - last_dt).days
                stale = days_ago > 7
            except (ValueError, TypeError):
                pass

        days_str = f"{days_ago}d ago" if days_ago is not None else "unknown"
        stale_marker = " ← STALE" if stale else ""
        line = f"  - {name}: mastery={mastery:.2f}, L{evidence}, last seen {days_str}{stale_marker}"

        if state.get("able_to_explain") and state.get("test_passed"):
            verified.append(line)
        elif state.get("tested") and state.get("test_passed"):
            checked.append(line)
        elif state.get("tested") and not state.get("test_passed"):
            gapped.append(line)
        else:
            other.append(line)

    parts = []
    if verified:
        parts.append("VERIFIED (may need review):")
        parts.extend(verified)
    if checked:
        parts.append("CHECKED (needs verification):")
        parts.extend(checked)
    if gapped:
        parts.append("GAPPED:")
        parts.extend(gapped)
    if other:
        parts.append("ENGAGED (no assessment yet):")
        parts.extend(other)

    return "\n".join(parts)
