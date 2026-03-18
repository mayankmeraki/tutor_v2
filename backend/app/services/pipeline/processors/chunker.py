"""Semantic chunker — splits materials into coherent teaching sections."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.services.pipeline.adapters.base import LLMAdapter, Segment

log = logging.getLogger(__name__)


@dataclass
class Anchor:
    start: float  # seconds (video) or char offset (text)
    end: float
    display_start: str = ""
    display_end: str = ""


@dataclass
class RawChunk:
    index: int
    title: str
    anchor: Anchor
    text: str
    topic_summary: str = ""
    segments: list[Segment] = field(default_factory=list)
    is_exercise: bool = False


def _format_time(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


async def chunk_material(
    source_type: str,
    classification_type: str,
    is_structured: bool,
    full_text: str,
    transcript_segments: list[Segment] | None,
    llm: LLMAdapter,
) -> list[RawChunk]:
    """Split material into semantic chunks. Strategy depends on material type."""

    if source_type == "youtube_video" and transcript_segments:
        return await _chunk_video_transcript(transcript_segments, llm)
    elif classification_type in ("assignment", "exercise_set"):
        return await _chunk_assignment(full_text, llm)
    elif is_structured:
        return await _chunk_structured_text(full_text, llm)
    else:
        return await _chunk_unstructured_text(full_text, llm)


async def _chunk_video_transcript(segments: list[Segment], llm: LLMAdapter) -> list[RawChunk]:
    """Use LLM to detect topic boundaries in transcript."""

    transcript_text = "\n".join(
        f"[{_format_time(s.start)}] {s.text}" for s in segments
    )

    # Truncate if very long
    if len(transcript_text) > 15000:
        transcript_text = transcript_text[:15000] + "\n... [truncated]"

    prompt = f"""Split this lecture transcript into coherent topic sections for a learning platform.

TRANSCRIPT:
{transcript_text}

SECTION BOUNDARY RULES:
- Target 3-7 minutes per section (acceptable range: 1.5-10 min). Prefer longer sections over splitting mid-explanation.
- Split at TOPIC TRANSITIONS, not at pauses or filler words. A new section starts when the instructor moves to a genuinely different concept.
- NEVER split in the middle of a worked example or derivation — keep the full example in one section.
- If the instructor says "now let's look at..." or "moving on to..." that's usually a boundary.
- A brief recap at the start of a new topic belongs with the NEW section, not the old one.

TITLE RULES:
- Titles must be specific and descriptive: "Deriving the Kinematic Equations" not "Kinematics" or "Part 2"
- NEVER use generic titles like "Introduction", "Conclusion", "Overview", "Summary", "Continued"
- Include the key concept: "Free Body Diagrams for Inclined Planes" not "Diagram Drawing"

EXAMPLE:
Input transcript covering projectile motion then friction:
→ Section 1: "Horizontal and Vertical Components of Projectile Motion" (0:00-5:30)
→ Section 2: "Range Equation and Maximum Height" (5:30-11:00)
→ Section 3: "Static vs Kinetic Friction" (11:00-16:20)
NOT: "Introduction" (0:00-2:00), "Projectile Motion" (2:00-11:00), "Friction" (11:00-16:20)

Respond as JSON only:
{{
  "sections": [
    {{
      "title": "descriptive title",
      "start_time": 0.0,
      "end_time": 180.0,
      "topic_summary": "one sentence describing what this section covers"
    }}
  ]
}}"""

    response = await llm.complete(prompt, model="sonnet", max_tokens=2000)

    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        data = json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        log.warning("Failed to parse chunk sections, falling back to time-based chunking")
        return _fallback_time_chunks(segments)

    chunks = []
    for i, section in enumerate(data.get("sections", [])):
        start_time = section.get("start_time", 0)
        end_time = section.get("end_time", 0)

        chunk_segments = [s for s in segments if s.start >= start_time and s.start < end_time]
        chunk_text = " ".join(s.text for s in chunk_segments)

        chunks.append(RawChunk(
            index=i,
            title=section.get("title", f"Section {i + 1}"),
            anchor=Anchor(
                start=start_time,
                end=end_time,
                display_start=_format_time(start_time),
                display_end=_format_time(end_time),
            ),
            text=chunk_text,
            segments=chunk_segments,
            topic_summary=section.get("topic_summary", ""),
        ))

    return chunks or _fallback_time_chunks(segments)


async def _chunk_assignment(full_text: str, llm: LLMAdapter) -> list[RawChunk]:
    """Split assignment into individual problems."""

    prompt = f"""Split this assignment into individual problems/exercises for a learning platform.

CONTENT:
{full_text[:10000]}

SPLITTING RULES:
- Each problem is ONE self-contained exercise. Multi-part problems (a, b, c, d) stay together as ONE problem.
- If a preamble or shared context ("A 5kg block on a 30° incline...") applies to multiple sub-parts, include it in EACH problem's statement.
- Worked examples (solutions already shown) are NOT problems — skip them entirely.
- Include all given values, diagrams references, and "find/calculate/show" instructions in the statement.

EXAMPLE:
Input: "1. A car accelerates from rest... (a) Find the acceleration (b) Find the distance"
→ ONE problem titled "Problem 1: Car Acceleration" with full text including parts a and b.
NOT two problems splitting (a) and (b).

Input: "Example 3.1: A block slides down... Solution: Using F=ma..."
→ SKIP — this is a worked example, not a problem.

Respond as JSON only:
{{
  "problems": [
    {{
      "title": "Problem 1: Kinematics of Accelerating Car",
      "statement": "the full problem text including all parts and given values",
      "start_char": 0,
      "end_char": 500
    }}
  ]
}}"""

    response = await llm.complete(prompt, model="sonnet", max_tokens=2000)

    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        data = json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        log.warning("Failed to parse assignment chunks")
        return [RawChunk(
            index=0,
            title="Full Assignment",
            anchor=Anchor(start=0, end=len(full_text)),
            text=full_text,
            is_exercise=True,
        )]

    chunks = []
    for i, problem in enumerate(data.get("problems", [])):
        chunks.append(RawChunk(
            index=i,
            title=problem.get("title", f"Problem {i + 1}"),
            anchor=Anchor(
                start=problem.get("start_char", 0),
                end=problem.get("end_char", 0),
                display_start=f"Problem {i + 1}",
                display_end="",
            ),
            text=problem.get("statement", ""),
            is_exercise=True,
        ))

    return chunks


async def _chunk_structured_text(full_text: str, llm: LLMAdapter) -> list[RawChunk]:
    """Chunk text with clear structure (headings, sections)."""

    prompt = f"""Split this structured educational text into coherent teaching sections for a learning platform.

TEXT:
{full_text[:10000]}

HEADING HIERARCHY RULES:
- H1 / major headings (e.g. "Chapter 3: Forces") = ALWAYS a section boundary.
- H2 headings = usually a section boundary, UNLESS the H2 section is very short (<300 chars). In that case, merge it with the next H2.
- H3 and below = merge into the parent H2 section. Do NOT create a separate section for each H3.
- If no headings exist, split at paragraph clusters of ~1000-2000 chars, breaking at natural topic shifts.

MERGE / SPLIT THRESHOLDS:
- Minimum section size: ~300 chars. If smaller, merge with adjacent section.
- Maximum section size: ~3000 chars. If larger, split at the most natural sub-topic boundary.
- A single formula or definition alone is NOT a section — merge it with the surrounding explanation.

TITLE RULES:
- Use the actual heading text from the document when available.
- If no heading exists for a section, write a specific descriptive title (not "Section 3" or "Continued").

Respond as JSON only:
{{
  "sections": [
    {{
      "title": "section title from heading or descriptive",
      "start_char": 0,
      "end_char": 500,
      "topic_summary": "one sentence summary of what this section teaches"
    }}
  ]
}}"""

    response = await llm.complete(prompt, model="sonnet", max_tokens=1500)

    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        data = json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        return _fallback_char_chunks(full_text)

    chunks = []
    for i, section in enumerate(data.get("sections", [])):
        s = section.get("start_char", 0)
        e = section.get("end_char", len(full_text))
        chunks.append(RawChunk(
            index=i,
            title=section.get("title", f"Section {i + 1}"),
            anchor=Anchor(start=s, end=e),
            text=full_text[s:e],
            topic_summary=section.get("topic_summary", ""),
        ))

    return chunks or _fallback_char_chunks(full_text)


async def _chunk_unstructured_text(full_text: str, llm: LLMAdapter) -> list[RawChunk]:
    """Chunk plain text by paragraph groups (~1500 chars each)."""
    return _fallback_char_chunks(full_text)


def _fallback_time_chunks(segments: list[Segment], chunk_duration: float = 180) -> list[RawChunk]:
    """Fallback: chunk video by fixed time intervals."""
    if not segments:
        return []

    total_duration = segments[-1].end
    chunks = []
    i = 0

    for chunk_start in range(0, int(total_duration), int(chunk_duration)):
        chunk_end = min(chunk_start + chunk_duration, total_duration)
        chunk_segments = [s for s in segments if s.start >= chunk_start and s.start < chunk_end]
        chunk_text = " ".join(s.text for s in chunk_segments)

        chunks.append(RawChunk(
            index=i,
            title=f"Segment {_format_time(chunk_start)} - {_format_time(chunk_end)}",
            anchor=Anchor(
                start=chunk_start,
                end=chunk_end,
                display_start=_format_time(chunk_start),
                display_end=_format_time(chunk_end),
            ),
            text=chunk_text,
            segments=chunk_segments,
        ))
        i += 1

    return chunks


def _fallback_char_chunks(full_text: str, chunk_size: int = 1500) -> list[RawChunk]:
    """Fallback: chunk text by character count, splitting at paragraph boundaries."""
    paragraphs = full_text.split("\n\n")
    chunks = []
    current_text = ""
    current_start = 0
    i = 0

    for para in paragraphs:
        if len(current_text) + len(para) > chunk_size and current_text:
            chunks.append(RawChunk(
                index=i,
                title=f"Section {i + 1}",
                anchor=Anchor(start=current_start, end=current_start + len(current_text)),
                text=current_text.strip(),
            ))
            i += 1
            current_start += len(current_text)
            current_text = para + "\n\n"
        else:
            current_text += para + "\n\n"

    if current_text.strip():
        chunks.append(RawChunk(
            index=i,
            title=f"Section {i + 1}",
            anchor=Anchor(start=current_start, end=current_start + len(current_text)),
            text=current_text.strip(),
        ))

    return chunks
