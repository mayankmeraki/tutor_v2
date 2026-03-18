"""Exercise extraction from enriched chunks."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.core.mongodb import get_mongo_db
from app.services.pipeline.adapters.base import LLMAdapter
from app.services.pipeline.extractors.frame_classifier import ClassifiedFrame
from app.services.pipeline.processors.enricher import EnrichedChunk

log = logging.getLogger(__name__)


@dataclass
class Exercise:
    exercise_id: str = ""
    material_id: str = ""
    chunk_id: str = ""
    collection_id: str = ""
    statement: str = ""
    type: str = "conceptual"  # numerical, conceptual, derivation, multiple_choice
    difficulty: str = "intermediate"
    concepts: list[str] = field(default_factory=list)
    has_diagram: bool = False
    diagram_description: str = ""
    diagram_frame_id: str = ""
    diagram_url: str = ""
    solution: dict = field(default_factory=dict)
    topic_id: str = ""  # filled during index building


async def extract_exercises(
    chunks: list[EnrichedChunk],
    frames: list[ClassifiedFrame],
    material_id: str,
    collection_id: str,
    llm: LLMAdapter,
) -> list[Exercise]:
    """Extract exercises from chunks that contain problems."""

    exercises: list[Exercise] = []

    for chunk in chunks:
        if not chunk.is_exercise and not chunk.content.get("hasExercise"):
            continue

        # Find diagram frames for this chunk
        diagram_frames = [
            f for f in frames
            if f.classification in ("diagram", "equation")
            and chunk.anchor.get("start", 0) <= f.timestamp <= chunk.anchor.get("end", 0)
        ]

        diagram_context = ""
        if diagram_frames:
            descs = [
                f"- {f.content_description}"
                + (f" OCR: {f.ocr.text[:200]}" if f.ocr and f.ocr.text else "")
                for f in diagram_frames
            ]
            diagram_context = f"\n\nDIAGRAM DESCRIPTIONS:\n" + "\n".join(descs)

        prompt = f"""Extract practice exercises from this educational content. These will be presented to students as practice problems.

CONTENT:
{chunk.content.get('transcript', chunk.title)[:3000]}
{diagram_context}

CRITICAL DISTINCTION — Worked Examples vs Exercises:
- A WORKED EXAMPLE is where the instructor/textbook solves a problem step-by-step to TEACH a method. The solution is fully shown. Do NOT extract these as exercises.
- An EXERCISE is a problem the student is expected to SOLVE themselves. It may say "find", "calculate", "show that", "determine", or appear in a problem set.
- If unsure: does the content show the full solution immediately after the problem? → worked example (skip). Does it leave the answer for the student? → exercise (extract).

TYPE DEFINITIONS:
- "numerical": Requires calculation with specific numbers (e.g. "Find the acceleration of a 5kg block...")
- "conceptual": Requires explanation/reasoning, no calculation (e.g. "Explain why astronauts feel weightless...")
- "derivation": Requires mathematical proof or derivation (e.g. "Show that v^2 = v_0^2 + 2ax")
- "multiple_choice": Has explicit answer options listed (A, B, C, D)

SOLUTION COMPLETENESS:
- If the full solution is shown: solution.available = true, include all steps and final answer
- If only the final answer is given (no steps): solution.available = true, steps = [], answer = "the answer"
- If no solution provided: solution.available = false

Respond as JSON only:
{{
  "exercises": [
    {{
      "statement": "full problem text including ALL given values, conditions, and what to find/show",
      "type": "numerical" | "conceptual" | "derivation" | "multiple_choice",
      "difficulty": "beginner" | "intermediate" | "advanced",
      "concepts": ["friction", "inclined_plane"],
      "has_diagram": false,
      "diagram_description": "",
      "solution": {{
        "available": false,
        "steps": [],
        "answer": ""
      }}
    }}
  ]
}}

If no exercises found (only worked examples or no problems), return {{"exercises": []}}."""

        response = await llm.complete(prompt, model="haiku", max_tokens=1000)

        try:
            start = response.index("{")
            end = response.rindex("}") + 1
            data = json.loads(response[start:end])
        except (ValueError, json.JSONDecodeError):
            log.warning("Failed to parse exercises from chunk %s", chunk.title[:40])
            continue

        for ex_data in data.get("exercises", []):
            ex = Exercise(
                exercise_id=str(uuid.uuid4()),
                material_id=material_id,
                chunk_id=chunk.chunk_id,
                collection_id=collection_id,
                statement=ex_data.get("statement", ""),
                type=ex_data.get("type", "conceptual"),
                difficulty=ex_data.get("difficulty", "intermediate"),
                concepts=ex_data.get("concepts", []),
                has_diagram=ex_data.get("has_diagram", False),
                diagram_description=ex_data.get("diagram_description", ""),
                solution=ex_data.get("solution", {}),
            )

            if diagram_frames and ex.has_diagram:
                ex.diagram_frame_id = diagram_frames[0].frame_id
                ex.diagram_url = diagram_frames[0].gcs_url

            exercises.append(ex)

    return exercises


async def store_exercises(exercises: list[Exercise]) -> None:
    """Store exercises in MongoDB exercise_index."""
    if not exercises:
        return

    db = get_mongo_db()
    docs = []
    for ex in exercises:
        docs.append({
            "exerciseId": ex.exercise_id,
            "materialId": ex.material_id,
            "chunkId": ex.chunk_id,
            "collectionId": ex.collection_id,
            "statement": ex.statement,
            "type": ex.type,
            "difficulty": ex.difficulty,
            "concepts": ex.concepts,
            "hasDiagram": ex.has_diagram,
            "diagramDescription": ex.diagram_description,
            "diagramFrameId": ex.diagram_frame_id,
            "diagramUrl": ex.diagram_url,
            "solution": ex.solution,
            "topicId": ex.topic_id,
            "createdAt": datetime.utcnow(),
        })

    if docs:
        await db.exercise_index.insert_many(docs)
        log.info("Stored %d exercises for collection %s", len(docs), exercises[0].collection_id)
