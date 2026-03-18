"""Flow map sequencer — generates teaching sequence for a collection."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from app.core.mongodb import get_mongo_db
from app.services.pipeline.adapters.base import LLMAdapter

log = logging.getLogger(__name__)


async def generate_flow_map(
    collection_id: str,
    llm: LLMAdapter,
    version_increment: bool = False,
) -> dict:
    """Generate the teaching sequence: chapters with ordered topics."""
    db = get_mongo_db()

    topics = await db.topic_index.find(
        {"collectionId": collection_id}
    ).sort("order", 1).to_list(None)

    concepts = await db.concept_graph.find(
        {"collectionId": collection_id}
    ).to_list(None)

    if not topics:
        log.warning("No topics for collection %s — skipping flow map", collection_id)
        return {}

    topic_summaries = [
        {
            "topicId": t["topicId"],
            "name": t.get("name", ""),
            "subject": t.get("subject", ""),
            "difficulty": t.get("difficulty", "intermediate"),
            "conceptNames": t.get("conceptNames", []),
            "prerequisites": t.get("prerequisites", []),
            "chunkCount": len(t.get("chunkIds", [])),
            "exerciseCount": t.get("exerciseCount", 0),
        }
        for t in topics
    ]

    prompt = f"""Create a teaching sequence (chapters with ordered topics) for a learning platform. Students will follow this sequence to learn the material.

TOPICS:
{json.dumps(topic_summaries, indent=2)[:6000]}

CHAPTER SIZING:
- Each chapter should contain 2-5 topics (a coherent study session of 1-4 hours).
- If there are fewer than 4 topics total, use a single chapter.
- If there are more than 15 topics, aim for 4-6 chapters.

ORDERING RULES:
- Prerequisites MUST come before topics that depend on them. Check the prerequisites list.
- Within a chapter, order from foundational → applied: definitions first, then laws/principles, then problem-solving, then exercises.
- Topics with exercises should come AFTER the teaching topics they test (not before or mixed in).
- If two topics have no dependency relationship, order by difficulty (easier first).

estimatedMinutes GUIDANCE:
- Estimate based on chunkCount and exerciseCount: ~8 min per content chunk, ~5 min per exercise.
- Minimum: 10 min. Maximum: 90 min per topic.

EXAMPLE:
For topics [Vectors, Forces, F=ma, Friction, Newton's Laws Exercises]:
→ Chapter "Foundations": Vectors (15 min) → Forces (20 min) → F=ma (25 min)
→ Chapter "Applications": Friction (20 min) → Newton's Laws Exercises (30 min)

Respond as JSON only:
{{
  "chapters": [
    {{
      "title": "Foundations of Motion",
      "subject": "mechanics",
      "topics": [
        {{"topicId": "...", "order": 0, "estimatedMinutes": 15, "rationale": "Starting point — no prerequisites"}}
      ]
    }}
  ]
}}"""

    response = await llm.complete(prompt, model="sonnet", max_tokens=2000)

    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        flow = json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        log.warning("Failed to parse flow map, creating default sequence")
        flow = {
            "chapters": [{
                "title": "Course Content",
                "subject": topics[0].get("subject", "general") if topics else "general",
                "topics": [
                    {"topicId": t["topicId"], "order": i, "estimatedMinutes": 10}
                    for i, t in enumerate(topics)
                ],
            }],
        }

    # Build topic position lookup
    topic_positions = {}
    for ch_idx, chapter in enumerate(flow.get("chapters", [])):
        for t_idx, topic_ref in enumerate(chapter.get("topics", [])):
            topic_positions[topic_ref.get("topicId", "")] = {
                "chapter": ch_idx,
                "position": t_idx,
            }

    # Get existing version
    existing = await db.flow_map.find_one({"collectionId": collection_id})
    version = (existing.get("version", 0) + 1) if existing and version_increment else 1

    flow_doc = {
        "collectionId": collection_id,
        "generatedAt": datetime.utcnow(),
        "version": version,
        "chapters": flow.get("chapters", []),
        "topicPositions": topic_positions,
    }

    await db.flow_map.replace_one(
        {"collectionId": collection_id},
        flow_doc,
        upsert=True,
    )

    log.info(
        "Flow map generated for %s: %d chapters, %d topics, version %d",
        collection_id, len(flow.get("chapters", [])),
        sum(len(ch.get("topics", [])) for ch in flow.get("chapters", [])),
        version,
    )

    return flow_doc
