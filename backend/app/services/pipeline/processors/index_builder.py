"""Index builder — cross-material organization.

Builds: topic_index, concept_graph, exercise linking, asset_index, difficulty_map.

Supports two modes:
  1. Full rebuild (build_indexes) — used by /reindex endpoint
  2. Incremental merge (merge_into_indexes) — used after each material finishes
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from app.core.mongodb import get_mongo_db
from app.services.pipeline.adapters.base import LLMAdapter
from app.services.pipeline.processors.sequencer import generate_flow_map

log = logging.getLogger(__name__)

# Lock timeout: if a lock is older than this, consider it stale and steal it
_LOCK_TIMEOUT_SECONDS = 300


# ── MongoDB-based locking ────────────────────────────────────────────────────

async def _acquire_index_lock(collection_id: str) -> bool:
    """Try to acquire an index merge lock. Returns True if acquired."""
    db = get_mongo_db()
    now = datetime.utcnow()

    # Try to insert a lock document (atomic — only one succeeds)
    try:
        await db.index_locks.insert_one({
            "collectionId": collection_id,
            "acquiredAt": now,
            "expiresAt": datetime(now.year, now.month, now.day, now.hour,
                                  now.minute + _LOCK_TIMEOUT_SECONDS // 60, now.second),
        })
        return True
    except Exception:
        # Lock already exists — check if stale
        existing = await db.index_locks.find_one({"collectionId": collection_id})
        if existing:
            age = (now - existing.get("acquiredAt", now)).total_seconds()
            if age > _LOCK_TIMEOUT_SECONDS:
                # Stale lock — steal it
                await db.index_locks.replace_one(
                    {"collectionId": collection_id},
                    {"collectionId": collection_id, "acquiredAt": now},
                )
                log.warning("Stole stale index lock for collection %s (age: %.0fs)", collection_id, age)
                return True
        return False


async def _release_index_lock(collection_id: str) -> None:
    """Release the index merge lock."""
    db = get_mongo_db()
    await db.index_locks.delete_one({"collectionId": collection_id})


async def _queue_merge(collection_id: str, material_id: str) -> None:
    """Queue a merge request for later processing."""
    db = get_mongo_db()
    await db.merge_queue.update_one(
        {"collectionId": collection_id, "materialId": material_id},
        {"$set": {"queuedAt": datetime.utcnow()}},
        upsert=True,
    )


async def _process_merge_queue(collection_id: str, llm: LLMAdapter) -> None:
    """Process any queued merges after the current merge completes."""
    db = get_mongo_db()
    queued = await db.merge_queue.find({"collectionId": collection_id}).to_list(None)
    if not queued:
        return

    for item in queued:
        await db.merge_queue.delete_one({"_id": item["_id"]})
        material_id = item["materialId"]
        log.info("Processing queued merge for material %s", material_id)
        await _do_incremental_merge(collection_id, material_id, llm)


# ── Incremental merge (called after each material) ──────────────────────────

async def merge_into_indexes(collection_id: str, material_id: str, llm: LLMAdapter) -> None:
    """Incrementally merge one material's data into collection indexes.

    Called after each material finishes enrichment (no waiting for all materials).
    Uses a MongoDB-based lock to prevent concurrent merges.
    """
    acquired = await _acquire_index_lock(collection_id)
    if not acquired:
        log.info("Index lock held for collection %s — queueing merge for material %s", collection_id, material_id)
        await _queue_merge(collection_id, material_id)
        return

    try:
        await _do_incremental_merge(collection_id, material_id, llm)
        # Process any queued merges
        await _process_merge_queue(collection_id, llm)
    finally:
        await _release_index_lock(collection_id)


async def _do_incremental_merge(collection_id: str, material_id: str, llm: LLMAdapter) -> None:
    """Perform the actual incremental merge for one material."""
    db = get_mongo_db()

    # Get this material's new chunks
    new_chunks = await db.chunks.find({
        "collectionId": collection_id,
        "materialId": material_id,
    }).to_list(None)

    if not new_chunks:
        log.warning("No chunks for material %s — skipping merge", material_id)
        return

    # Check if we have existing topics (i.e., is this the first material?)
    existing_topics = await db.topic_index.find({"collectionId": collection_id}).to_list(None)

    if not existing_topics:
        # First material: full build
        log.info("First material in collection %s — running full index build", collection_id)
        all_chunks = new_chunks
        topics = await _detect_topics(all_chunks, collection_id, llm)
        concepts = await _build_concept_graph(all_chunks, topics, collection_id, llm)
    else:
        # Incremental: merge new chunks into existing structure
        topics = await _merge_topics(new_chunks, existing_topics, collection_id, llm)
        existing_concepts = await db.concept_graph.find({"collectionId": collection_id}).to_list(None)
        concepts = await _merge_concepts(new_chunks, existing_concepts, topics, collection_id, llm)

    # Link exercises for this material
    new_exercises = await db.exercise_index.find({
        "collectionId": collection_id,
        "materialId": material_id,
    }).to_list(None)
    if new_exercises:
        await _link_exercises_to_topics(new_exercises, topics, concepts, collection_id)

    # Catalog new frames (incremental — only this material)
    new_frames = await db.extracted_frames.find({
        "collectionId": collection_id,
        "materialId": material_id,
    }).to_list(None)
    if new_frames:
        await _catalog_new_assets(new_frames, topics, collection_id)

    # Rebuild difficulty map with all topics
    all_topics = await db.topic_index.find({"collectionId": collection_id}).to_list(None)
    all_concepts = await db.concept_graph.find({"collectionId": collection_id}).to_list(None)
    await _build_difficulty_map(all_topics, all_concepts, collection_id)

    # Re-generate flow map with version increment
    await generate_flow_map(collection_id, llm, version_increment=True)

    # Update collection stats
    all_chunks = await db.chunks.find({"collectionId": collection_id}).to_list(None)
    all_exercises = await db.exercise_index.find({"collectionId": collection_id}).to_list(None)
    await db.content_collections.update_one(
        {"collectionId": collection_id},
        {"$set": {
            "stats": {
                "totalMaterials": await db.materials.count_documents({"collectionId": collection_id, "status": "ready"}),
                "totalChunks": len(all_chunks),
                "totalConcepts": len(all_concepts),
                "totalExercises": len(all_exercises),
                "totalTopics": len(all_topics),
            },
            "updatedAt": datetime.utcnow(),
        }},
    )

    log.info(
        "Incremental merge complete for material %s: %d topics, %d concepts",
        material_id, len(all_topics), len(all_concepts),
    )


# ── Incremental merge helpers ────────────────────────────────────────────────

async def _merge_topics(
    new_chunks: list[dict],
    existing_topics: list[dict],
    collection_id: str,
    llm: LLMAdapter,
) -> list[dict]:
    """Merge new chunks into existing topics or create new topics."""
    db = get_mongo_db()

    new_chunk_summaries = [
        {
            "chunkId": c.get("chunkId", ""),
            "materialId": c.get("materialId", ""),
            "title": c.get("title", ""),
            "summary": c.get("content", {}).get("summary", ""),
            "concepts": c.get("content", {}).get("concepts", []),
        }
        for c in new_chunks
    ]

    existing_topic_summaries = [
        {
            "topicId": t["topicId"],
            "name": t.get("name", ""),
            "description": t.get("description", ""),
            "conceptNames": t.get("conceptNames", []),
            "chunkCount": len(t.get("chunkIds", [])),
        }
        for t in existing_topics
    ]

    prompt = f"""You are merging NEW content chunks into an EXISTING topic structure for a learning platform.

EXISTING TOPICS:
{json.dumps(existing_topic_summaries, indent=2)[:4000]}

NEW CHUNKS to merge:
{json.dumps(new_chunk_summaries, indent=2)[:4000]}

For each new chunk, decide:
1. "add_to_existing" — it covers the same topic as an existing one. Provide the topicId.
2. "create_new" — it covers a genuinely new topic not yet represented. Provide full topic details.

Also rate "overlap_score" for each chunk: 0.0 = completely new content, 0.5 = partial overlap, 1.0 = near-duplicate of existing content.

Respond as JSON only:
{{
  "assignments": [
    {{
      "chunkId": "...",
      "action": "add_to_existing",
      "topicId": "existing-topic-id",
      "overlap_score": 0.7
    }},
    {{
      "chunkId": "...",
      "action": "create_new",
      "overlap_score": 0.1,
      "new_topic": {{
        "name": "Rotational Dynamics",
        "displayName": "Rotational Dynamics and Torque",
        "subject": "mechanics",
        "description": "Torque, moment of inertia, and rotational analogs of Newton's laws",
        "difficulty": "intermediate",
        "conceptNames": ["torque", "moment_of_inertia"],
        "prerequisites": ["newtons_second_law"],
        "successors": []
      }}
    }}
  ]
}}"""

    response = await llm.complete(prompt, model="sonnet", max_tokens=3000)

    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        data = json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        log.warning("Failed to parse topic merge — falling back to full rebuild")
        all_chunks = await db.chunks.find({"collectionId": collection_id}).to_list(None)
        return await _detect_topics(all_chunks, collection_id, llm)

    # Process assignments
    updated_topics = {t["topicId"]: t for t in existing_topics}

    for assignment in data.get("assignments", []):
        chunk_id = assignment.get("chunkId", "")
        action = assignment.get("action", "")

        if action == "add_to_existing":
            topic_id = assignment.get("topicId", "")
            if topic_id in updated_topics:
                # Append chunk to existing topic
                await db.topic_index.update_one(
                    {"topicId": topic_id},
                    {"$addToSet": {"chunkIds": chunk_id}},
                )
                updated_topics[topic_id].setdefault("chunkIds", []).append(chunk_id)

        elif action == "create_new":
            new_topic_data = assignment.get("new_topic", {})
            topic_doc = {
                "topicId": str(uuid.uuid4()),
                "collectionId": collection_id,
                "name": new_topic_data.get("name", f"New Topic"),
                "displayName": new_topic_data.get("displayName", new_topic_data.get("name", "")),
                "subject": new_topic_data.get("subject", "general"),
                "description": new_topic_data.get("description", ""),
                "difficulty": new_topic_data.get("difficulty", "intermediate"),
                "order": len(updated_topics),
                "chunkIds": [chunk_id],
                "conceptNames": new_topic_data.get("conceptNames", []),
                "prerequisites": new_topic_data.get("prerequisites", []),
                "successors": new_topic_data.get("successors", []),
                "exerciseCount": 0,
                "createdAt": datetime.utcnow(),
            }
            await db.topic_index.insert_one(topic_doc)
            updated_topics[topic_doc["topicId"]] = topic_doc

    return list(updated_topics.values())


async def _merge_concepts(
    new_chunks: list[dict],
    existing_concepts: list[dict],
    topics: list[dict],
    collection_id: str,
    llm: LLMAdapter,
) -> list[dict]:
    """Merge new concept mentions into existing concept graph."""
    db = get_mongo_db()

    # Collect new concept mentions
    new_raw_concepts = []
    for c in new_chunks:
        for concept_name in c.get("content", {}).get("concepts", []):
            new_raw_concepts.append({
                "name": concept_name,
                "chunkId": c.get("chunkId", ""),
                "materialId": c.get("materialId", ""),
            })

    if not new_raw_concepts:
        return existing_concepts

    existing_concept_summaries = [
        {
            "conceptId": c["conceptId"],
            "name": c.get("name", ""),
            "normalizedName": c.get("normalizedName", ""),
            "aliases": c.get("aliases", []),
        }
        for c in existing_concepts
    ]

    prompt = f"""You are merging NEW concept mentions into an EXISTING concept graph for a learning platform.

EXISTING CONCEPTS:
{json.dumps(existing_concept_summaries, indent=2)[:4000]}

NEW CONCEPT MENTIONS:
{json.dumps(new_raw_concepts[:60], indent=2)[:3000]}

For each new concept mention, decide:
1. "map_to_existing" — it's the same concept as an existing one (possibly different wording). Provide the conceptId.
2. "create_new" — it's a genuinely new concept. Provide full concept details.

Remember: "velocity" and "speed" are DIFFERENT concepts. "F=ma" and "Newton's Second Law" are the SAME concept.

Respond as JSON only:
{{
  "assignments": [
    {{
      "name": "acceleration",
      "chunkId": "...",
      "action": "map_to_existing",
      "conceptId": "existing-concept-id",
      "add_alias": null
    }},
    {{
      "name": "angular momentum",
      "chunkId": "...",
      "action": "create_new",
      "new_concept": {{
        "name": "Angular Momentum",
        "normalizedName": "angular_momentum",
        "aliases": ["L"],
        "definition": "The rotational analog of linear momentum, L = I * omega",
        "category": "rotational_dynamics",
        "subject": "mechanics",
        "difficulty": "advanced",
        "formulas": ["L = I * omega"],
        "prerequisites": ["moment_of_inertia", "angular_velocity"],
        "related": ["linear_momentum"]
      }}
    }}
  ]
}}"""

    response = await llm.complete(prompt, model="sonnet", max_tokens=3000)

    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        data = json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        log.warning("Failed to parse concept merge — skipping concept update for these chunks")
        return existing_concepts

    updated_concepts = {c["conceptId"]: c for c in existing_concepts}

    for assignment in data.get("assignments", []):
        action = assignment.get("action", "")
        chunk_id = assignment.get("chunkId", "")

        if action == "map_to_existing":
            concept_id = assignment.get("conceptId", "")
            if concept_id in updated_concepts:
                # Add location to existing concept
                location = {"chunkId": chunk_id, "role": "introduced"}
                # Find topic for this chunk
                for topic in topics:
                    if chunk_id in topic.get("chunkIds", []):
                        location["topicId"] = topic["topicId"]
                        break
                await db.concept_graph.update_one(
                    {"conceptId": concept_id},
                    {"$push": {"locations": location}},
                )
                # Add alias if provided
                add_alias = assignment.get("add_alias")
                if add_alias:
                    await db.concept_graph.update_one(
                        {"conceptId": concept_id},
                        {"$addToSet": {"aliases": add_alias}},
                    )

        elif action == "create_new":
            new_concept_data = assignment.get("new_concept", {})
            # Build locations
            locations = [{"chunkId": chunk_id, "role": "introduced"}]
            for topic in topics:
                if chunk_id in topic.get("chunkIds", []):
                    locations[0]["topicId"] = topic["topicId"]
                    break

            concept_doc = {
                "conceptId": str(uuid.uuid4()),
                "collectionId": collection_id,
                "name": new_concept_data.get("name", assignment.get("name", "")),
                "normalizedName": new_concept_data.get("normalizedName", ""),
                "aliases": new_concept_data.get("aliases", []),
                "definition": new_concept_data.get("definition", ""),
                "category": new_concept_data.get("category", ""),
                "subject": new_concept_data.get("subject", ""),
                "difficulty": new_concept_data.get("difficulty", "intermediate"),
                "formulas": new_concept_data.get("formulas", []),
                "prerequisites": new_concept_data.get("prerequisites", []),
                "related": new_concept_data.get("related", []),
                "locations": locations,
                "createdAt": datetime.utcnow(),
            }
            await db.concept_graph.insert_one(concept_doc)
            updated_concepts[concept_doc["conceptId"]] = concept_doc

    return list(updated_concepts.values())


async def _catalog_new_assets(
    new_frames: list[dict],
    topics: list[dict],
    collection_id: str,
) -> None:
    """Incremental asset cataloging — only processes new material's frames."""
    db = get_mongo_db()

    for frame in new_frames:
        if frame.get("classification") not in ("board", "equation", "diagram", "slide", "chart"):
            continue

        # Find topic by matching frame's materialId to chunks in topics
        topic_id = ""
        for topic in topics:
            for chunk_id in topic.get("chunkIds", []):
                topic_id = topic["topicId"]
                break
            if topic_id:
                break

        asset_doc = {
            "assetId": str(uuid.uuid4()),
            "collectionId": collection_id,
            "type": frame.get("classification", "diagram"),
            "description": frame.get("contentDescription", ""),
            "materialId": frame.get("materialId", ""),
            "frameId": frame.get("frameId", ""),
            "timestamp": frame.get("timestamp", 0),
            "gcsPath": frame.get("gcsPath", ""),
            "gcsUrl": frame.get("gcsUrl", ""),
            "topicId": topic_id,
            "ocrText": frame.get("ocr", {}).get("fullText", ""),
            "createdAt": datetime.utcnow(),
        }
        await db.asset_index.insert_one(asset_doc)


# ── Full rebuild (kept for /reindex endpoint) ────────────────────────────────

async def build_indexes(collection_id: str, llm: LLMAdapter) -> None:
    """Full rebuild of all structured indexes for a collection.

    Used by the /reindex endpoint for manual rebuilds.
    For incremental updates, use merge_into_indexes() instead.
    """
    db = get_mongo_db()

    chunks = await db.chunks.find({"collectionId": collection_id}).to_list(None)
    frames = await db.extracted_frames.find({"collectionId": collection_id}).to_list(None)
    exercises = await db.exercise_index.find({"collectionId": collection_id}).to_list(None)

    if not chunks:
        log.warning("No chunks found for collection %s — skipping index build", collection_id)
        return

    # 1. Topic detection
    topics = await _detect_topics(chunks, collection_id, llm)

    # 2. Concept deduplication
    concepts = await _build_concept_graph(chunks, topics, collection_id, llm)

    # 3. Exercise linking
    await _link_exercises_to_topics(exercises, topics, concepts, collection_id)

    # 4. Asset cataloging
    await _catalog_assets(frames, topics, collection_id)

    # 5. Difficulty mapping
    await _build_difficulty_map(topics, concepts, collection_id)

    # Update collection stats
    await db.content_collections.update_one(
        {"collectionId": collection_id},
        {"$set": {
            "stats": {
                "totalMaterials": await db.materials.count_documents({"collectionId": collection_id}),
                "totalChunks": len(chunks),
                "totalConcepts": len(concepts),
                "totalExercises": len(exercises),
                "totalTopics": len(topics),
            },
            "updatedAt": datetime.utcnow(),
        }},
    )

    log.info(
        "Indexes built for %s: %d topics, %d concepts, %d exercises",
        collection_id, len(topics), len(concepts), len(exercises),
    )


# ── Topic detection (full build) ────────────────────────────────────────────

async def _detect_topics(chunks: list[dict], collection_id: str, llm: LLMAdapter) -> list[dict]:
    """Group chunks into coherent teaching topics."""
    db = get_mongo_db()

    # Clear existing topics
    await db.topic_index.delete_many({"collectionId": collection_id})

    chunk_summaries = [
        {
            "chunkId": c.get("chunkId", ""),
            "materialId": c.get("materialId", ""),
            "title": c.get("title", ""),
            "summary": c.get("content", {}).get("summary", ""),
            "concepts": c.get("content", {}).get("concepts", []),
            "difficulty": c.get("content", {}).get("difficulty", "intermediate"),
        }
        for c in chunks
    ]

    prompt = f"""Group these content chunks into coherent TEACHING TOPICS for a learning platform. A topic is a unit of study a student works through in one sitting (typically 15-60 minutes of content).

CHUNKS:
{json.dumps(chunk_summaries, indent=2)[:8000]}

TOPIC GRANULARITY:
- Too granular: "Definition of Velocity" (too narrow — merge into a bigger topic)
- Just right: "Kinematics: Velocity and Acceleration" (15-60 min of content, teachable unit)
- Too broad: "Classical Mechanics" (too wide — split into sub-topics)

MERGE CRITERIA — combine chunks into ONE topic when:
- They cover the same concept from different angles (e.g. video lecture + textbook section on same topic)
- One chunk is a direct continuation of another (Part 1 / Part 2 of same derivation)
- They're from different materials but teach the same skill

SPLIT CRITERIA — separate into DIFFERENT topics when:
- The concepts require different prerequisites
- A student could study one without the other
- They belong to clearly different subject sub-areas

ANTI-PATTERNS:
- Do NOT create single-chunk topics unless the chunk covers a genuinely standalone concept
- Do NOT create a catch-all "Miscellaneous" or "Other Topics" topic
- Do NOT duplicate chunk IDs across topics — each chunk belongs to exactly one topic
- Do NOT list concept names that aren't actually covered in the assigned chunks

ORDER: List topics in natural teaching sequence. Prerequisites before dependents.

Respond as JSON only:
{{
  "topics": [
    {{
      "name": "Newton's Second Law",
      "displayName": "Newton's Second Law of Motion",
      "subject": "mechanics",
      "description": "Relationship between net force, mass, and acceleration (F=ma) with applications to single-object problems",
      "difficulty": "intermediate",
      "chunkIds": ["chk_1", "chk_2"],
      "conceptNames": ["force", "mass", "acceleration"],
      "prerequisites": ["vectors", "free_body_diagrams"],
      "successors": ["friction", "circular_motion"]
    }}
  ]
}}"""

    response = await llm.complete(prompt, model="sonnet", max_tokens=3000)

    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        data = json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        log.warning("Failed to parse topics, creating one topic per chunk")
        data = {"topics": [
            {
                "name": c.get("title", f"Topic {i}"),
                "subject": "general",
                "description": c.get("content", {}).get("summary", ""),
                "difficulty": c.get("content", {}).get("difficulty", "intermediate"),
                "chunkIds": [c.get("chunkId", "")],
                "conceptNames": c.get("content", {}).get("concepts", []),
            }
            for i, c in enumerate(chunks)
        ]}

    topics = []
    for i, t in enumerate(data.get("topics", [])):
        topic_doc = {
            "topicId": str(uuid.uuid4()),
            "collectionId": collection_id,
            "name": t.get("name", f"Topic {i + 1}"),
            "displayName": t.get("displayName", t.get("name", "")),
            "subject": t.get("subject", "general"),
            "description": t.get("description", ""),
            "difficulty": t.get("difficulty", "intermediate"),
            "order": i,
            "chunkIds": t.get("chunkIds", []),
            "conceptNames": t.get("conceptNames", []),
            "prerequisites": t.get("prerequisites", []),
            "successors": t.get("successors", []),
            "exerciseCount": 0,
            "createdAt": datetime.utcnow(),
        }
        await db.topic_index.insert_one(topic_doc)
        topics.append(topic_doc)

    return topics


# ── Concept graph (full build) ───────────────────────────────────────────────

async def _build_concept_graph(
    chunks: list[dict],
    topics: list[dict],
    collection_id: str,
    llm: LLMAdapter,
) -> list[dict]:
    """Build deduplicated concept graph across all materials."""
    db = get_mongo_db()

    # Clear existing concepts
    await db.concept_graph.delete_many({"collectionId": collection_id})

    # Collect raw concept mentions
    raw_concepts = []
    for c in chunks:
        for concept_name in c.get("content", {}).get("concepts", []):
            raw_concepts.append({
                "name": concept_name,
                "chunkId": c.get("chunkId", ""),
                "materialId": c.get("materialId", ""),
            })

    if not raw_concepts:
        return []

    prompt = f"""Deduplicate and organize these raw concept mentions into a clean concept graph for a learning platform.

RAW CONCEPTS (from {len(chunks)} chunks):
{json.dumps(raw_concepts[:100], indent=2)[:6000]}

MERGE CRITERIA — merge into ONE concept when:
- They are the exact same concept with different wording: "Newton's 2nd Law" + "Newton's Second Law" + "F=ma" → one concept
- They are abbreviation vs full name: "KE" + "kinetic energy" → one concept
- They are the same formula in different notation: "F=ma" + "F_net = ma" → one concept

DO NOT MERGE when:
- They are related but distinct concepts: "velocity" vs "speed" are DIFFERENT (velocity has direction)
- They are at different levels of specificity: "friction" vs "kinetic friction" — keep "kinetic friction" as its own concept with "friction" as a related/parent concept
- They are different laws/principles: "Newton's First Law" vs "Newton's Second Law" — these are distinct

CANONICAL NAMING:
- Use standard textbook names: "kinetic energy" not "energy of motion"
- Use lowercase_with_underscores for normalizedName: "kinetic_energy"
- Put informal names, abbreviations, and formula representations in aliases

PREREQUISITE FORMAT:
- Prerequisites are concepts a student must understand BEFORE learning this concept
- Use the normalizedName of the prerequisite concept
- Keep the prerequisite chain shallow (direct prerequisites only, not transitive)

Respond as JSON only:
{{
  "concepts": [
    {{
      "name": "Newton's Second Law",
      "normalizedName": "newtons_second_law",
      "aliases": ["F=ma", "Newton's 2nd Law", "second law of motion"],
      "definition": "The net force on an object equals its mass times its acceleration",
      "category": "dynamics",
      "subject": "mechanics",
      "difficulty": "intermediate",
      "formulas": ["F_net = ma"],
      "prerequisites": ["force", "mass", "acceleration", "free_body_diagram"],
      "related": ["newtons_first_law", "newtons_third_law"]
    }}
  ]
}}"""

    response = await llm.complete(prompt, model="sonnet", max_tokens=3000)

    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        data = json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        log.warning("Failed to parse concept graph")
        return []

    concepts = []
    for c in data.get("concepts", []):
        # Find which chunks mention this concept
        mentions = [
            rc for rc in raw_concepts
            if rc["name"].lower() == c.get("name", "").lower()
            or rc["name"].lower() in [a.lower() for a in c.get("aliases", [])]
        ]

        # Find topic assignment
        locations = []
        for mention in mentions:
            for topic in topics:
                if mention["chunkId"] in topic.get("chunkIds", []):
                    locations.append({
                        "topicId": topic["topicId"],
                        "chunkId": mention["chunkId"],
                        "role": "introduced",
                    })

        concept_doc = {
            "conceptId": str(uuid.uuid4()),
            "collectionId": collection_id,
            "name": c.get("name", ""),
            "normalizedName": c.get("normalizedName", c.get("name", "").lower().replace(" ", "_")),
            "aliases": c.get("aliases", []),
            "definition": c.get("definition", ""),
            "category": c.get("category", ""),
            "subject": c.get("subject", ""),
            "difficulty": c.get("difficulty", "intermediate"),
            "formulas": c.get("formulas", []),
            "prerequisites": c.get("prerequisites", []),
            "related": c.get("related", []),
            "locations": locations,
            "createdAt": datetime.utcnow(),
        }
        await db.concept_graph.insert_one(concept_doc)
        concepts.append(concept_doc)

    return concepts


# ── Shared helpers ───────────────────────────────────────────────────────────

async def _link_exercises_to_topics(
    exercises: list[dict],
    topics: list[dict],
    concepts: list[dict],
    collection_id: str,
) -> None:
    """Link exercises to topics via concept overlap."""
    db = get_mongo_db()

    for exercise in exercises:
        ex_concepts = set(c.lower() for c in exercise.get("concepts", []))
        best_topic = None
        best_overlap = 0

        for topic in topics:
            topic_concepts = set(c.lower() for c in topic.get("conceptNames", []))
            overlap = len(ex_concepts & topic_concepts)
            if overlap > best_overlap:
                best_overlap = overlap
                best_topic = topic

        if best_topic:
            await db.exercise_index.update_one(
                {"exerciseId": exercise.get("exerciseId")},
                {"$set": {"topicId": best_topic["topicId"]}},
            )
            # Update topic exercise count
            await db.topic_index.update_one(
                {"topicId": best_topic["topicId"]},
                {"$inc": {"exerciseCount": 1}},
            )


async def _catalog_assets(
    frames: list[dict],
    topics: list[dict],
    collection_id: str,
) -> None:
    """Create asset entries from extracted frames (full rebuild)."""
    db = get_mongo_db()

    # Clear existing assets
    await db.asset_index.delete_many({"collectionId": collection_id})

    for frame in frames:
        if frame.get("classification") not in ("board", "equation", "diagram", "slide", "chart"):
            continue

        # Find topic by timestamp overlap with chunks
        topic_id = ""
        for topic in topics:
            for chunk_id in topic.get("chunkIds", []):
                topic_id = topic["topicId"]
                break
            if topic_id:
                break

        asset_doc = {
            "assetId": str(uuid.uuid4()),
            "collectionId": collection_id,
            "type": frame.get("classification", "diagram"),
            "description": frame.get("contentDescription", ""),
            "materialId": frame.get("materialId", ""),
            "frameId": frame.get("frameId", ""),
            "timestamp": frame.get("timestamp", 0),
            "gcsPath": frame.get("gcsPath", ""),
            "gcsUrl": frame.get("gcsUrl", ""),
            "topicId": topic_id,
            "ocrText": frame.get("ocr", {}).get("fullText", ""),
            "createdAt": datetime.utcnow(),
        }
        await db.asset_index.insert_one(asset_doc)


async def _build_difficulty_map(
    topics: list[dict],
    concepts: list[dict],
    collection_id: str,
) -> None:
    """Build difficulty progression map."""
    db = get_mongo_db()

    levels = {"beginner": [], "intermediate": [], "advanced": []}
    for topic in topics:
        level = topic.get("difficulty", "intermediate")
        levels.setdefault(level, []).append({
            "topicId": topic["topicId"],
            "name": topic["name"],
            "conceptCount": len(topic.get("conceptNames", [])),
        })

    doc = {
        "collectionId": collection_id,
        "levels": levels,
        "topicCount": len(topics),
        "conceptCount": len(concepts),
        "updatedAt": datetime.utcnow(),
    }

    await db.difficulty_map.replace_one(
        {"collectionId": collection_id},
        doc,
        upsert=True,
    )
