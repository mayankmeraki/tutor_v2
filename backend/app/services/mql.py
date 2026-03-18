"""Material Query Layer (MQL) — 12 tools for querying processed BYO content.

Agents query structured indexes, never raw storage. Each tool returns
concise, formatted text suitable for injection into agent context.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from app.core.mongodb import get_mongo_db, get_tutor_db

log = logging.getLogger(__name__)


# ── 1. browse_topics ─────────────────────────────────────────────────────────

async def browse_topics(collection_id: str) -> str:
    """List all topics in the collection with progress indicators.

    Like `ls` — shows what's available to teach.
    """
    db = get_mongo_db()
    topics = await db.topic_index.find(
        {"collectionId": collection_id}
    ).sort("order", 1).to_list(None)

    if not topics:
        return "No topics found in this collection."

    lines = [f"Topics ({len(topics)}):"]
    for t in topics:
        ex_count = t.get("exerciseCount", 0)
        exercise_tag = f" [{ex_count} exercises]" if ex_count else ""
        lines.append(
            f"  {t.get('order', 0) + 1}. {t.get('displayName') or t.get('name', '?')} "
            f"({t.get('difficulty', '?')}){exercise_tag} — {t.get('description', '')[:80]}"
        )
        lines.append(f"     topicId: {t.get('topicId', '')}")

    return "\n".join(lines)


# ── 2. browse_topic ──────────────────────────────────────────────────────────

async def browse_topic(collection_id: str, topic_id: str) -> str:
    """Open a specific topic — shows chunks, concepts, exercises, assets.

    Like opening a directory — detailed view of one topic.
    """
    db = get_mongo_db()
    topic = await db.topic_index.find_one({"collectionId": collection_id, "topicId": topic_id})

    if not topic:
        return f"Topic {topic_id} not found."

    lines = [
        f"Topic: {topic.get('displayName') or topic.get('name', '?')}",
        f"Subject: {topic.get('subject', '?')}",
        f"Difficulty: {topic.get('difficulty', '?')}",
        f"Description: {topic.get('description', '')}",
    ]

    # Prerequisites / successors
    prereqs = topic.get("prerequisites", [])
    if prereqs:
        lines.append(f"Prerequisites: {', '.join(prereqs)}")
    successors = topic.get("successors", [])
    if successors:
        lines.append(f"Leads to: {', '.join(successors)}")

    # Chunks
    chunk_ids = topic.get("chunkIds", [])
    if chunk_ids:
        chunks = await db.chunks.find(
            {"collectionId": collection_id, "chunkId": {"$in": chunk_ids}}
        ).to_list(None)
        lines.append(f"\nContent Chunks ({len(chunks)}):")
        for c in chunks:
            anchor = c.get("anchor", {})
            time_range = ""
            if anchor.get("displayStart"):
                time_range = f" [{anchor['displayStart']}-{anchor.get('displayEnd', '')}]"
            lines.append(
                f"  • {c.get('title', '?')}{time_range} — {c.get('content', {}).get('summary', '')[:100]}"
            )
            lines.append(f"    chunkId: {c.get('chunkId', '')}")

    # Exercises
    exercises = await db.exercise_index.find(
        {"collectionId": collection_id, "topicId": topic_id}
    ).to_list(None)
    if exercises:
        lines.append(f"\nExercises ({len(exercises)}):")
        for ex in exercises:
            lines.append(
                f"  • [{ex.get('type', '?')}/{ex.get('difficulty', '?')}] "
                f"{ex.get('statement', '')[:80]}..."
            )
            lines.append(f"    exerciseId: {ex.get('exerciseId', '')}")

    # Concepts
    concept_names = topic.get("conceptNames", [])
    if concept_names:
        lines.append(f"\nConcepts: {', '.join(concept_names)}")

    return "\n".join(lines)


# ── 3. get_flow ──────────────────────────────────────────────────────────────

async def get_flow(collection_id: str) -> str:
    """Read the flow map — chapter/topic teaching sequence.

    Like reading a README — the recommended learning path.
    """
    db = get_mongo_db()
    flow = await db.flow_map.find_one({"collectionId": collection_id})

    if not flow:
        return "No flow map generated yet."

    lines = [f"Teaching Sequence (v{flow.get('version', 1)}):"]

    for ch_idx, chapter in enumerate(flow.get("chapters", [])):
        lines.append(f"\nChapter {ch_idx + 1}: {chapter.get('title', '?')}")
        for topic_ref in chapter.get("topics", []):
            est = topic_ref.get("estimatedMinutes", "?")
            lines.append(
                f"  {topic_ref.get('order', 0) + 1}. [{est} min] "
                f"topicId={topic_ref.get('topicId', '?')}"
            )
            if topic_ref.get("rationale"):
                lines.append(f"     → {topic_ref['rationale']}")

    return "\n".join(lines)


# ── 4. read_chunk ────────────────────────────────────────────────────────────

async def read_chunk(collection_id: str, chunk_id: str) -> str:
    """Read a specific content chunk — full transcript, key points, formulas.

    Like `cat` — the actual content to teach from.
    """
    db = get_mongo_db()
    chunk = await db.chunks.find_one({"collectionId": collection_id, "chunkId": chunk_id})

    if not chunk:
        return f"Chunk {chunk_id} not found."

    content = chunk.get("content", {})
    anchor = chunk.get("anchor", {})

    lines = [f"Chunk: {chunk.get('title', '?')}"]

    if anchor.get("displayStart"):
        lines.append(f"Time: {anchor['displayStart']} - {anchor.get('displayEnd', '')}")

    lines.append(f"Difficulty: {content.get('difficulty', '?')}")

    if content.get("summary"):
        lines.append(f"\nSummary: {content['summary']}")

    if content.get("keyPoints"):
        lines.append("\nKey Points:")
        for kp in content["keyPoints"]:
            lines.append(f"  • {kp}")

    if content.get("formulas"):
        lines.append(f"\nFormulas: {', '.join(content['formulas'])}")

    if content.get("concepts"):
        lines.append(f"Concepts: {', '.join(content['concepts'])}")

    transcript = content.get("transcript", "")
    if transcript:
        # Truncate long transcripts
        if len(transcript) > 3000:
            transcript = transcript[:3000] + "... [truncated]"
        lines.append(f"\nTranscript:\n{transcript}")

    # Linked frames
    frame_ids = chunk.get("linkedFrameIds", [])
    if frame_ids:
        frames = await db.extracted_frames.find(
            {"frameId": {"$in": frame_ids}}
        ).to_list(None)
        if frames:
            lines.append("\nVisual Content:")
            for f in frames:
                lines.append(
                    f"  [{f.get('displayTime', '?')}] ({f.get('classification', '?')}) "
                    f"{f.get('contentDescription', '')}"
                )
                ocr_text = f.get("ocr", {}).get("fullText", "")
                if ocr_text:
                    lines.append(f"    OCR: {ocr_text[:200]}")

    return "\n".join(lines)


# ── 5. search_content ────────────────────────────────────────────────────────

async def search_content(collection_id: str, query: str) -> str:
    """Text search across all chunks in a collection.

    Like `grep` — find where a concept/topic is discussed.
    """
    db = get_mongo_db()

    # Search in chunk transcripts and summaries
    results = await db.chunks.find(
        {
            "collectionId": collection_id,
            "$or": [
                {"content.transcript": {"$regex": query, "$options": "i"}},
                {"content.summary": {"$regex": query, "$options": "i"}},
                {"title": {"$regex": query, "$options": "i"}},
                {"content.concepts": {"$regex": query, "$options": "i"}},
            ],
        },
        {"chunkId": 1, "title": 1, "content.summary": 1, "content.concepts": 1, "anchor": 1},
    ).limit(10).to_list(None)

    if not results:
        return f"No results for '{query}' in this collection."

    lines = [f"Search results for '{query}' ({len(results)} matches):"]
    for r in results:
        anchor = r.get("anchor", {})
        time_tag = f" [{anchor.get('displayStart', '')}-{anchor.get('displayEnd', '')}]" if anchor.get("displayStart") else ""
        lines.append(f"  • {r.get('title', '?')}{time_tag}")
        lines.append(f"    {r.get('content', {}).get('summary', '')[:100]}")
        lines.append(f"    chunkId: {r.get('chunkId', '')}")

    return "\n".join(lines)


# ── 6. grep_material ─────────────────────────────────────────────────────────

async def grep_material(collection_id: str, material_id: str, query: str) -> str:
    """Search within a specific material's chunks.

    Like `grep file` — search within one document.
    """
    db = get_mongo_db()

    results = await db.chunks.find(
        {
            "collectionId": collection_id,
            "materialId": material_id,
            "$or": [
                {"content.transcript": {"$regex": query, "$options": "i"}},
                {"content.summary": {"$regex": query, "$options": "i"}},
                {"title": {"$regex": query, "$options": "i"}},
            ],
        },
        {"chunkId": 1, "title": 1, "content.summary": 1, "anchor": 1},
    ).to_list(None)

    if not results:
        return f"No results for '{query}' in material {material_id}."

    lines = [f"Results for '{query}' ({len(results)} chunks):"]
    for r in results:
        anchor = r.get("anchor", {})
        time_tag = f" [{anchor.get('displayStart', '')}-{anchor.get('displayEnd', '')}]" if anchor.get("displayStart") else ""
        lines.append(f"  • {r.get('title', '?')}{time_tag} — chunkId: {r.get('chunkId', '')}")

    return "\n".join(lines)


# ── 7. find_concept ──────────────────────────────────────────────────────────

async def find_concept(collection_id: str, concept_name: str) -> str:
    """Find a concept by name or alias — definition, prerequisites, locations.

    Returns the concept's full graph entry including where it appears.
    """
    db = get_mongo_db()

    concept = await db.concept_graph.find_one({
        "collectionId": collection_id,
        "$or": [
            {"name": {"$regex": f"^{concept_name}$", "$options": "i"}},
            {"normalizedName": concept_name.lower().replace(" ", "_")},
            {"aliases": {"$regex": f"^{concept_name}$", "$options": "i"}},
        ],
    })

    if not concept:
        return f"Concept '{concept_name}' not found. Try search_concepts for fuzzy search."

    lines = [
        f"Concept: {concept.get('name', '?')}",
        f"Definition: {concept.get('definition', 'N/A')}",
        f"Category: {concept.get('category', '?')} / {concept.get('subject', '?')}",
        f"Difficulty: {concept.get('difficulty', '?')}",
    ]

    aliases = concept.get("aliases", [])
    if aliases:
        lines.append(f"Also known as: {', '.join(aliases)}")

    formulas = concept.get("formulas", [])
    if formulas:
        lines.append(f"Formulas: {', '.join(formulas)}")

    prereqs = concept.get("prerequisites", [])
    if prereqs:
        lines.append(f"Prerequisites: {', '.join(prereqs)}")

    related = concept.get("related", [])
    if related:
        lines.append(f"Related: {', '.join(related)}")

    locations = concept.get("locations", [])
    if locations:
        lines.append(f"\nAppears in {len(locations)} location(s):")
        for loc in locations[:5]:
            lines.append(f"  • topicId={loc.get('topicId', '?')}, role={loc.get('role', '?')}")

    return "\n".join(lines)


# ── 8. search_concepts ───────────────────────────────────────────────────────

async def search_concepts(collection_id: str, query: str) -> str:
    """Fuzzy search across all concepts in the collection."""
    db = get_mongo_db()

    results = await db.concept_graph.find(
        {
            "collectionId": collection_id,
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"aliases": {"$regex": query, "$options": "i"}},
                {"definition": {"$regex": query, "$options": "i"}},
                {"category": {"$regex": query, "$options": "i"}},
            ],
        },
        {"conceptId": 1, "name": 1, "definition": 1, "difficulty": 1},
    ).limit(10).to_list(None)

    if not results:
        return f"No concepts matching '{query}'."

    lines = [f"Concepts matching '{query}' ({len(results)}):"]
    for c in results:
        lines.append(
            f"  • {c.get('name', '?')} ({c.get('difficulty', '?')}) — "
            f"{c.get('definition', '')[:80]}"
        )

    return "\n".join(lines)


# ── 9. get_exercises ─────────────────────────────────────────────────────────

async def get_exercises(
    collection_id: str,
    topic_id: str | None = None,
    difficulty: str | None = None,
    limit: int = 5,
) -> str:
    """Get exercises, optionally filtered by topic or difficulty."""
    db = get_mongo_db()

    query: dict = {"collectionId": collection_id}
    if topic_id:
        query["topicId"] = topic_id
    if difficulty:
        query["difficulty"] = difficulty

    exercises = await db.exercise_index.find(query).limit(limit).to_list(None)

    if not exercises:
        filters = []
        if topic_id:
            filters.append(f"topic={topic_id}")
        if difficulty:
            filters.append(f"difficulty={difficulty}")
        filter_str = f" (filters: {', '.join(filters)})" if filters else ""
        return f"No exercises found{filter_str}."

    lines = [f"Exercises ({len(exercises)}):"]
    for ex in exercises:
        lines.append(
            f"\n  [{ex.get('type', '?')}/{ex.get('difficulty', '?')}] "
            f"exerciseId: {ex.get('exerciseId', '')}"
        )
        lines.append(f"  {ex.get('statement', '')[:200]}")
        if ex.get("concepts"):
            lines.append(f"  Concepts: {', '.join(ex['concepts'])}")
        sol = ex.get("solution", {})
        if sol.get("available"):
            lines.append(f"  Solution available: {sol.get('answer', '')[:100]}")

    return "\n".join(lines)


# ── 10. get_mastery ──────────────────────────────────────────────────────────

async def get_mastery(collection_id: str, user_email: str) -> str:
    """Get student's mastery state for a collection."""
    tutor_db = get_tutor_db()

    progress = await tutor_db.student_progress.find_one({
        "collectionId": collection_id,
        "userEmail": user_email,
    })

    if not progress:
        return "No progress recorded for this student in this collection."

    lines = ["Student Progress:"]

    completed_topics = progress.get("completedTopics", [])
    if completed_topics:
        lines.append(f"\nCompleted Topics ({len(completed_topics)}):")
        for t in completed_topics:
            lines.append(f"  ✓ {t}")

    mastery = progress.get("conceptMastery", {})
    if mastery:
        lines.append(f"\nConcept Mastery ({len(mastery)}):")
        for concept_id, data in mastery.items():
            level = data.get("level", "unknown")
            tested = "tested" if data.get("tested") else "not tested"
            lines.append(f"  • {concept_id}: {level} ({tested})")
            observations = data.get("observations", [])
            if observations:
                latest = observations[-1]
                lines.append(f"    Latest: {latest.get('text', '')[:80]}")

    pos = progress.get("currentPosition", {})
    if pos:
        lines.append(f"\nCurrent Position: topic={pos.get('topicId', '?')}, chunk={pos.get('chunkIndex', '?')}")

    lines.append(f"Sessions: {progress.get('sessionCount', 0)}")

    return "\n".join(lines)


# ── 11. log_observation ──────────────────────────────────────────────────────

async def log_observation(
    collection_id: str,
    user_email: str,
    concept_id: str,
    observation: str,
    session_id: str = "",
) -> str:
    """Log a mastery observation for a student on a specific concept."""
    tutor_db = get_tutor_db()

    obs = {
        "text": observation,
        "at": datetime.utcnow(),
        "sessionId": session_id,
    }

    await tutor_db.student_progress.update_one(
        {"collectionId": collection_id, "userEmail": user_email},
        {
            "$push": {f"conceptMastery.{concept_id}.observations": obs},
            "$set": {
                f"conceptMastery.{concept_id}.lastSeen": datetime.utcnow(),
                "lastSessionAt": datetime.utcnow(),
            },
            "$setOnInsert": {
                "collectionId": collection_id,
                "userEmail": user_email,
                "currentPosition": {},
                "completedChunks": [],
                "completedTopics": [],
                "sessionCount": 0,
            },
        },
        upsert=True,
    )

    return f"Observation logged for {concept_id}."


# ── 12. get_assets ───────────────────────────────────────────────────────────

async def get_assets(
    collection_id: str,
    topic_id: str | None = None,
    asset_type: str | None = None,
    limit: int = 10,
) -> str:
    """Get teaching assets (diagrams, board captures, clips) for a topic."""
    db = get_mongo_db()

    query: dict = {"collectionId": collection_id}
    if topic_id:
        query["topicId"] = topic_id
    if asset_type:
        query["type"] = asset_type

    assets = await db.asset_index.find(query).limit(limit).to_list(None)

    if not assets:
        return "No assets found."

    lines = [f"Assets ({len(assets)}):"]
    for a in assets:
        lines.append(
            f"  • [{a.get('type', '?')}] {a.get('description', '')[:100]}"
        )
        if a.get("gcsUrl"):
            lines.append(f"    URL: {a['gcsUrl']}")
        if a.get("ocrText"):
            lines.append(f"    OCR: {a['ocrText'][:100]}")

    return "\n".join(lines)
