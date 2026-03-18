"""Claude vision adapter for frame classification and OCR."""

from __future__ import annotations

import base64
import json
import logging

from .base import (
    FrameClassification,
    LLMAdapter,
    OCRAdapter,
    OcrElement,
    OcrResult,
    VisionClassifierAdapter,
)

log = logging.getLogger(__name__)

_CLASSIFY_PROMPT = """Classify each image from an educational video into ONE category. Your classification determines which frames get OCR processing and are shown to students.

CATEGORIES:
- "board": Blackboard/whiteboard with handwritten content (equations, diagrams, or text written by instructor)
- "equation": A mathematical equation, formula, or derivation is the PRIMARY content of the frame (printed or handwritten)
- "diagram": Technical diagram, physics figure, circuit, free body diagram, or scientific illustration
- "slide": Presentation slide with structured text content (bullet points, titles, formatted text)
- "table": Data table, comparison table, or structured numerical information
- "chart": Statistical chart, plot, graph with data points, or coordinate system with plotted functions
- "talking_head": Speaker/instructor is the dominant content — no significant board/slide/diagram visible
- "transition": Title card, chapter heading, blank screen, loading screen, or transition animation
- "other": None of the above (e.g. B-roll footage, real-world video clip)

DISAMBIGUATION RULES (critical for accuracy):
- Slide WITH an equation on it = "slide" (the slide is the container; the equation is part of it)
- Instructor visible BUT board/slide content is ALSO clearly visible and readable = classify by the CONTENT type (board/slide/equation), NOT as talking_head
- Board with BOTH text and equations = "board" (board is the medium)
- Diagram with labels/equations on it = "diagram" (the diagram is the primary content)
- If genuinely ambiguous between two content types, prefer the more specific one (equation > board, diagram > chart)

CONFIDENCE: Rate 0.0-1.0. If the frame is blurry, partially obscured, or genuinely ambiguous, rate below 0.7.

For each image (in order), respond with a JSON array:
[{"frame_index": 0, "classification": "...", "confidence": 0.9, "content_description": "brief description of what's shown",
  "has_text": true, "has_math": false, "has_diagram": false}, ...]"""


class ClaudeVisionClassifier(VisionClassifierAdapter):
    def __init__(self, llm: LLMAdapter):
        self._llm = llm

    async def classify_frames(self, frames: list[bytes]) -> list[FrameClassification]:
        result_text = await self._llm.complete_with_vision(
            _CLASSIFY_PROMPT, frames, model="haiku", max_tokens=1500,
        )
        try:
            # Extract JSON array from response
            start = result_text.index("[")
            end = result_text.rindex("]") + 1
            items = json.loads(result_text[start:end])
        except (ValueError, json.JSONDecodeError):
            log.warning("Failed to parse frame classifications: %s", result_text[:200])
            return [
                FrameClassification(frame_index=i, classification="other")
                for i in range(len(frames))
            ]

        return [
            FrameClassification(
                frame_index=item.get("frame_index", i),
                classification=item.get("classification", "other"),
                content_description=item.get("content_description", ""),
                has_text=item.get("has_text", False),
                has_math=item.get("has_math", False),
                has_diagram=item.get("has_diagram", False),
            )
            for i, item in enumerate(items)
        ]


class ClaudeVisionOCR(OCRAdapter):
    def __init__(self, llm: LLMAdapter):
        self._llm = llm

    async def extract_text(self, image_bytes: bytes) -> OcrResult:
        prompt = """Extract all visible text and mathematical content from this educational image. The extracted text will be used for search and concept linking.

READING ORDER: Read left-to-right, top-to-bottom. For multi-column layouts, read each column separately (left column first, then right).

ELEMENT TYPES:
- "equation": Mathematical formula, derivation step, or symbolic expression. Use standard notation: fractions as a/b, subscripts as x_0, superscripts as x^2, Greek letters spelled out (theta, omega, alpha). Example: "F_net = ma", "v = v_0 + at", "integral from 0 to t of F dt"
- "text": Regular written/printed text (explanations, labels, bullet points)
- "label": Short annotation on a diagram (axis labels, variable names, arrow labels)
- "diagram_desc": If there's a diagram/figure, describe its structure and key elements (e.g. "Free body diagram showing a block on an inclined plane with forces N, mg, and f_k labeled")

CONFIDENCE:
- 0.9+: Text is clearly legible, you're certain of the reading
- 0.7-0.9: Mostly legible but some characters are ambiguous (common with handwriting)
- <0.7: Significant portions are unclear — note uncertain parts with [?]

HANDWRITING: For handwritten content, do your best to transcribe. If a character is genuinely unreadable, use [?]. Prefer the most likely physics/math interpretation (e.g. a squiggle after "F =" is probably "ma" not random letters).

Return as JSON:
{"text": "all text concatenated in reading order", "elements": [
  {"type": "equation"|"text"|"label"|"diagram_desc", "text": "...", "confidence": 0.95}
]}"""
        result_text = await self._llm.complete_with_vision(
            prompt, [image_bytes], model="haiku", max_tokens=800,
        )
        try:
            start = result_text.index("{")
            end = result_text.rindex("}") + 1
            data = json.loads(result_text[start:end])
        except (ValueError, json.JSONDecodeError):
            return OcrResult(text=result_text.strip(), elements=[], confidence=0.5)

        elements = [
            OcrElement(
                type=e.get("type", "text"),
                text=e.get("text", ""),
                confidence=e.get("confidence", 0.8),
            )
            for e in data.get("elements", [])
        ]
        return OcrResult(
            text=data.get("text", ""),
            elements=elements,
            confidence=sum(e.confidence for e in elements) / max(len(elements), 1),
        )
