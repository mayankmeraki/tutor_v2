"""Per-chunk enrichment — extract concepts, formulas, key points."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.services.pipeline.adapters.base import LLMAdapter
from app.services.pipeline.extractors.frame_classifier import ClassifiedFrame
from app.services.pipeline.processors.chunker import RawChunk

log = logging.getLogger(__name__)


@dataclass
class ConceptDetail:
    name: str
    definition: str = ""
    role: str = "introduced"  # introduced, prerequisite, applied


@dataclass
class EnrichedChunk:
    chunk_id: str = ""
    material_id: str = ""
    collection_id: str = ""
    index: int = 0
    title: str = ""
    anchor: dict = field(default_factory=dict)
    content: dict = field(default_factory=dict)
    concept_details: list[ConceptDetail] = field(default_factory=list)
    linked_frame_ids: list[str] = field(default_factory=list)
    media: dict = field(default_factory=dict)
    segments: list[dict] = field(default_factory=list)
    is_exercise: bool = False


async def enrich_chunk(
    chunk: RawChunk,
    source_type: str,
    frames: list[ClassifiedFrame],
    llm: LLMAdapter,
) -> EnrichedChunk:
    """Extract structured knowledge from a chunk."""

    # Find keyframes within this chunk's time range
    relevant_frames = [
        f for f in frames
        if chunk.anchor.start <= f.timestamp <= chunk.anchor.end
        and f.classification in ("board", "equation", "diagram", "slide")
    ]

    frame_context = ""
    if relevant_frames:
        descs = [
            f"[{f.display_time}] ({f.classification}) {f.content_description}"
            + (f"\n  OCR: {f.ocr.text[:200]}" if f.ocr and f.ocr.text else "")
            for f in relevant_frames
        ]
        frame_context = f"\n\nVISUAL CONTENT visible during this section:\n" + "\n".join(descs)

    prompt = f"""You are a teaching assistant extracting structured knowledge from one section of educational content. Your output will be used by a learning platform to help students navigate and study.

SECTION TITLE: {chunk.title}
SECTION TEXT:
{chunk.text[:3000]}
{frame_context}

EXTRACTION RULES:

Summary: Write 2-3 sentences AS IF explaining to a student what they'll learn in this section. Start with the main concept, then mention key applications or examples covered.

Key Points: List 3-6 specific, actionable takeaways. Each should be a complete thought a student could review.
  Good: "Newton's Third Law states that forces always occur in equal and opposite pairs"
  Bad: "Third Law" or "Forces" (too vague)

Concepts (max 8): Extract the most important physics/math concepts. For each:
  - "name": Use standard textbook terminology (e.g. "kinetic friction" not "friction when moving")
  - "definition": One clear sentence a student could use as a flashcard
  - "role": "introduced" = this section teaches/derives it; "prerequisite" = assumed known, not explained here; "applied" = used here but formally taught elsewhere

Formulas: Use standard notation. Write fractions as a/b, vectors with arrow notation, subscripts with underscore: F_net = ma, v = v_0 + at, KE = (1/2)mv^2. Do NOT use LaTeX.

EXAMPLE OUTPUT:
{{
  "summary": "This section introduces Newton's Second Law (F=ma) and shows how to apply it to calculate acceleration when given force and mass. Two worked examples demonstrate the method.",
  "keyPoints": ["Net force equals mass times acceleration (F_net = ma)", "To find acceleration, divide net force by mass", "Multiple forces must be summed as vectors before applying F=ma"],
  "concepts": [{{"name": "Newton's Second Law", "definition": "The net force on an object equals its mass times its acceleration", "role": "introduced"}}, {{"name": "net force", "definition": "The vector sum of all forces acting on an object", "role": "prerequisite"}}],
  "formulas": ["F_net = ma", "a = F_net / m"],
  "difficulty": "beginner",
  "hasExercise": false
}}

Respond as JSON only:
{{
  "summary": "...",
  "keyPoints": ["..."],
  "concepts": [{{"name": "...", "definition": "...", "role": "introduced|prerequisite|applied"}}],
  "formulas": ["..."],
  "difficulty": "beginner" | "intermediate" | "advanced",
  "hasExercise": false
}}"""

    response = await llm.complete(prompt, model="haiku", max_tokens=1000)

    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        data = json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        log.warning("Failed to parse enrichment for chunk %s", chunk.title[:40])
        data = {
            "summary": chunk.topic_summary or chunk.text[:200],
            "keyPoints": [],
            "concepts": [],
            "formulas": [],
            "difficulty": "intermediate",
            "hasExercise": chunk.is_exercise,
        }

    concept_details = [
        ConceptDetail(
            name=c.get("name", ""),
            definition=c.get("definition", ""),
            role=c.get("role", "introduced"),
        )
        for c in data.get("concepts", [])
    ]

    return EnrichedChunk(
        index=chunk.index,
        title=chunk.title,
        anchor={
            "start": chunk.anchor.start,
            "end": chunk.anchor.end,
            "displayStart": chunk.anchor.display_start,
            "displayEnd": chunk.anchor.display_end,
        },
        content={
            "transcript": chunk.text,
            "summary": data.get("summary", ""),
            "keyPoints": data.get("keyPoints", []),
            "formulas": data.get("formulas", []),
            "concepts": [c.name for c in concept_details],
            "difficulty": data.get("difficulty", "intermediate"),
            "confidence": "high" if data.get("concepts") else "low",
        },
        concept_details=concept_details,
        linked_frame_ids=[f.frame_id for f in relevant_frames if f.frame_id],
        media={"hasVideo": source_type == "youtube_video"},
        segments=[{"text": s.text, "start": s.start, "end": s.end} for s in chunk.segments],
        is_exercise=chunk.is_exercise or data.get("hasExercise", False),
    )


async def enrich_all_chunks(
    chunks: list[RawChunk],
    source_type: str,
    frames: list[ClassifiedFrame],
    llm: LLMAdapter,
) -> list[EnrichedChunk]:
    """Enrich all chunks (can be parallelized)."""
    import asyncio

    tasks = [
        enrich_chunk(chunk, source_type, frames, llm)
        for chunk in chunks
    ]
    return await asyncio.gather(*tasks)
