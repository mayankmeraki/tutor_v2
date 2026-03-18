"""Material classifier — type detection and subject analysis."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.services.pipeline.adapters.base import LLMAdapter

log = logging.getLogger(__name__)


@dataclass
class Classification:
    type: str  # lecture, assignment, exercise_set, reference, notes, mixed
    subjects: list[str] = field(default_factory=list)
    difficulty: str = "intermediate"
    is_structured: bool = False
    has_exercises: bool = False
    language: str = "en"
    confidence: float = 0.8
    title_suggestion: str = ""
    educational_quality: str = "medium"  # high, medium, low, non_educational


async def classify_material(text_sample: str, llm: LLMAdapter) -> Classification:
    """Classify material type and detect subjects using Haiku."""

    prompt = f"""You are classifying educational material for a learning platform. Analyze the text sample below and produce a structured classification.

TEXT SAMPLE (first 3000 chars):
{text_sample[:3000]}

CLASSIFICATION RULES:
- "type": Choose the DOMINANT type. If >30% of content is exercises but the rest is lecture, use "mixed" (not "lecture").
- "subjects": List 1-4 specific subject areas (e.g. ["classical mechanics", "kinematics"] not just ["physics"]).
- "difficulty": beginner = no prerequisites assumed; intermediate = builds on intro concepts; advanced = requires significant prior knowledge.
- "isStructured": true if the text has clear headings, numbered sections, or slide-like formatting.
- "hasExercises": true if the text contains practice problems, homework, or "find/calculate/derive" prompts.
- "educational_quality": Rate the teaching value:
  - "high" = clearly educational, well-structured, covers concepts with explanations
  - "medium" = educational but informal, incomplete, or surface-level
  - "low" = marginally educational (e.g. tangential discussion, mostly off-topic)
  - "non_educational" = no educational content (e.g. cooking recipe, news article, social media)
- "confidence": 0.0-1.0 calibration: 0.9+ = text is clearly one type; 0.7-0.9 = mostly clear but some ambiguity; 0.5-0.7 = significant ambiguity; <0.5 = guessing.

EXAMPLES:
Input: "Chapter 3: Newton's Laws. 3.1 First Law (Inertia)..." → type: "lecture", subjects: ["classical mechanics"], educational_quality: "high", confidence: 0.95
Input: "Problem Set 4. 1) A 2kg block slides..." → type: "exercise_set", hasExercises: true, educational_quality: "high", confidence: 0.9
Input: "So today we're gonna talk about, like, force and stuff..." → type: "lecture", educational_quality: "medium", confidence: 0.7

ANTI-PATTERNS (do NOT do these):
- Do NOT set confidence above 0.8 if the sample is very short (<500 chars)
- Do NOT classify social media posts or news as "lecture"
- Do NOT list more than 4 subjects

Respond as JSON only:
{{
  "type": "lecture" | "assignment" | "exercise_set" | "reference" | "notes" | "mixed",
  "subjects": ["classical mechanics", "kinematics"],
  "difficulty": "beginner" | "intermediate" | "advanced",
  "isStructured": true,
  "hasExercises": false,
  "language": "en",
  "confidence": 0.9,
  "educational_quality": "high" | "medium" | "low" | "non_educational",
  "title_suggestion": "Newton's Laws of Motion"
}}"""

    response = await llm.complete(prompt, model="haiku", max_tokens=400)

    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        data = json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        log.warning("Failed to parse classification: %s", response[:200])
        return Classification(type="mixed", confidence=0.3)

    return Classification(
        type=data.get("type", "mixed"),
        subjects=data.get("subjects", []),
        difficulty=data.get("difficulty", "intermediate"),
        is_structured=data.get("isStructured", False),
        has_exercises=data.get("hasExercises", False),
        language=data.get("language", "en"),
        confidence=data.get("confidence", 0.8),
        title_suggestion=data.get("title_suggestion", ""),
        educational_quality=data.get("educational_quality", "medium"),
    )
