"""Tool result formatters — call content_service directly (no HTTP)."""

import logging
import math

logger = logging.getLogger(__name__)

from app.services.content.content_service import (
    get_learning_tool_by_id,
    get_section_full,
    get_sections_for_lesson,
    get_enriched_section,
)


async def get_section_content(lesson_id: int, section_index: int) -> str:
    logger.debug("get_section_content lesson_id=%d section_index=%d", lesson_id, section_index)
    data = await get_section_full(lesson_id, section_index)
    if not data:
        logger.warning("section not found lesson_id=%d section_index=%d", lesson_id, section_index)
        return f"Section {lesson_id}:{section_index} not found."

    lines: list[str] = []
    lines.append(f"Section: {data.get('title') or f'Lesson {lesson_id}, Section {section_index}'}")

    start = data.get("start_seconds")
    end = data.get("end_seconds")
    if start is not None and end is not None:
        s_fmt = f"{math.floor(start / 60)}:{round(start % 60):02d}"
        e_fmt = f"{math.floor(end / 60)}:{round(end % 60):02d}"
        lines.append(f"Video timestamps: {s_fmt} - {e_fmt}")

    segments = data.get("segments")
    transcript_text = data.get("transcript")
    if segments and isinstance(segments, list):
        transcript = " ".join(s.get("text", s) if isinstance(s, dict) else str(s) for s in segments)
        if len(transcript) > 3000:
            transcript = transcript[:3000] + "..."
        lines.append(f"\nTranscript:\n{transcript}")
    elif transcript_text:
        t = transcript_text[:3000] + "..." if len(transcript_text) > 3000 else transcript_text
        lines.append(f"\nTranscript:\n{t}")

    if data.get("summary"):
        lines.append(f"\nSummary: {data['summary']}")
    if data.get("key_points") and isinstance(data["key_points"], list):
        lines.append("\nKey Points:\n" + "\n".join(f"  \u2022 {p}" for p in data["key_points"]))
    if data.get("concepts") and isinstance(data["concepts"], list):
        lines.append(f"\nConcepts: {', '.join(data['concepts'])}")
    if data.get("formulas") and isinstance(data["formulas"], list):
        lines.append(f"\nFormulas: {', '.join(data['formulas'])}")

    # Also include enriched teaching brief if available (avoids a second tool call)
    try:
        enriched = await get_enriched_section(lesson_id, section_index)
        if enriched:
            if enriched.get("teaching_summary"):
                lines.append(f"\nTeaching brief: {enriched['teaching_summary']}")
            if enriched.get("key_pedagogical_points"):
                lines.append("Teaching points: " + "; ".join(enriched["key_pedagogical_points"][:5]))
            if enriched.get("notable_examples"):
                lines.append("Professor's examples: " + "; ".join(enriched["notable_examples"][:3]))
            if enriched.get("professor_framing"):
                lines.append(f"How professor frames it: {enriched['professor_framing']}")
    except Exception:
        pass

    return "\n".join(lines)


def _fmt_time(seconds: float) -> str:
    m = math.floor(seconds / 60)
    s = round(seconds % 60)
    return f"{m}:{s:02d}"


async def get_transcript_context(lesson_id: int, timestamp: float) -> str:
    """Return transcript + key points + teaching brief around a timestamp.

    Single call gives everything the tutor needs — no chaining required.
    Includes: transcript window, section summary, key points, professor's framing,
    concepts, formulas, and notable examples.
    """
    logger.debug("get_transcript_context lesson_id=%d timestamp=%.1f", lesson_id, timestamp)
    sections = await get_sections_for_lesson(lesson_id)
    if not sections:
        return f"No sections found for lesson {lesson_id}."

    target = None
    for sec in sections:
        if sec.get("start_seconds", 0) <= timestamp <= sec.get("end_seconds", 0):
            target = sec
            break
    if not target:
        target = min(sections, key=lambda s: abs(s.get("start_seconds", 0) - timestamp))

    section_index = target.get("index", 0)
    full = await get_section_full(lesson_id, section_index)
    if not full:
        return f"Section data not available for lesson {lesson_id} at {timestamp}s."

    lines = [f"Section: {full.get('title', '')}", f"Timestamps: {_fmt_time(full.get('start_seconds', 0))} – {_fmt_time(full.get('end_seconds', 0))}", f"Student paused at: {_fmt_time(timestamp)}", ""]

    # Transcript window (60s before, 30s after)
    segments = full.get("segments")
    if segments and isinstance(segments, list):
        win_start, win_end = timestamp - 60, timestamp + 30
        windowed = []
        for seg in segments:
            seg_time = seg.get("timestamp", seg.get("start", full.get("start_seconds", 0))) if isinstance(seg, dict) else full.get("start_seconds", 0)
            seg_text = seg.get("text", "") if isinstance(seg, dict) else str(seg)
            if isinstance(seg_time, (int, float)) and win_start <= seg_time <= win_end:
                windowed.append(f"[{_fmt_time(seg_time)}] {seg_text}")
        transcript = "\n".join(windowed) if windowed else " ".join(s.get("text", s) if isinstance(s, dict) else str(s) for s in segments)
    else:
        transcript = full.get("transcript", "")

    if len(transcript) > 3200:
        transcript = transcript[:3200] + "..."
    lines.append(f"Transcript:\n{transcript}")

    # Key points + concepts + formulas from section data
    if full.get("summary"):
        lines.append(f"\nSummary: {full['summary']}")
    kp = full.get("key_points")
    if kp and isinstance(kp, list):
        lines.append("\nKey points:\n" + "\n".join(f"  • {p}" for p in kp[:8]))
    concepts = full.get("concepts")
    if concepts and isinstance(concepts, list):
        lines.append(f"Concepts: {', '.join(concepts)}")
    formulas = full.get("formulas")
    if formulas and isinstance(formulas, list):
        lines.append(f"Formulas: {', '.join(formulas)}")

    # Enriched teaching brief (professor's framing, examples)
    try:
        enriched = await get_enriched_section(lesson_id, section_index)
        if enriched:
            if enriched.get("teaching_summary"):
                lines.append(f"\nTeaching brief: {enriched['teaching_summary']}")
            if enriched.get("notable_examples"):
                lines.append("Professor's examples: " + "; ".join(enriched["notable_examples"][:3]))
            if enriched.get("professor_framing"):
                lines.append(f"How professor frames it: {enriched['professor_framing']}")
    except Exception:
        pass  # enriched data is optional

    return "\n".join(lines)


async def get_section_brief(lesson_id: int, section_index: int) -> str:
    """Return a compact teaching brief from enriched_sections."""
    logger.debug("get_section_brief lesson_id=%d section_index=%d", lesson_id, section_index)
    enriched = await get_enriched_section(lesson_id, section_index)
    if enriched:
        lines = [f"Section: {enriched.get('title', '')}", f"Timestamps: {_fmt_time(enriched.get('start_seconds', 0))} – {_fmt_time(enriched.get('end_seconds', 0))}"]
        if enriched.get("teaching_summary"): lines.append(f"\nSummary: {enriched['teaching_summary']}")
        if enriched.get("key_pedagogical_points"): lines.extend(["Key teaching points:"] + [f"  • {p}" for p in enriched["key_pedagogical_points"]])
        if enriched.get("notable_examples"): lines.extend(["Professor's examples:"] + [f"  – {ex}" for ex in enriched["notable_examples"]])
        if enriched.get("professor_framing"): lines.append(f"How professor frames it: {enriched['professor_framing']}")
        if enriched.get("concepts"): lines.append(f"Concepts: {', '.join(enriched['concepts'])}")
        return "\n".join(lines)

    data = await get_section_full(lesson_id, section_index)
    if not data:
        return f"Section {lesson_id}:{section_index} not found."
    lines = [f"Section: {data.get('title', '')}"]
    if data.get("summary"): lines.append(f"Summary: {data['summary']}")
    if data.get("key_points"): lines.extend(["Key points:"] + [f"  • {p}" for p in data["key_points"]])
    if data.get("concepts"): lines.append(f"Concepts: {', '.join(data['concepts'])}")
    return "\n".join(lines)


async def get_simulation_details(simulation_id: str) -> str:
    logger.debug("get_simulation_details simulation_id=%s", simulation_id)
    data = await get_learning_tool_by_id(simulation_id)
    if not data:
        logger.warning("simulation not found simulation_id=%s", simulation_id)
        return f"Simulation {simulation_id} not found."

    lines: list[str] = []
    lines.append(f"Simulation: {data.get('title', 'Unknown')}")
    lines.append(f"Type: {data.get('tool_type', 'N/A')}")
    lines.append(f"Description: {data.get('description', 'N/A')}")
    if data.get("at_timestamp"):
        lines.append(f"At timestamp: {data['at_timestamp']}")
    if data.get("thumbnail_url"):
        lines.append(f"Thumbnail: {data['thumbnail_url']}")

    ai = data.get("ai_context") or {}
    if ai.get("context"):
        lines.append(f"\nContext: {ai['context']}")
    if ai.get("visuals_and_animations"):
        lines.append(f"Visuals: {ai['visuals_and_animations']}")
    if ai.get("controls") and isinstance(ai["controls"], dict):
        ctrl = "\n".join(f"  {k}: {v}" for k, v in ai["controls"].items())
        lines.append(f"Controls:\n{ctrl}")
    if ai.get("guided_exercises") and isinstance(ai["guided_exercises"], list):
        lines.append(f"\nGuided Exercises ({len(ai['guided_exercises'])}):")
        for i, ex in enumerate(ai["guided_exercises"]):
            title = ex.get("title") or f"Exercise {i + 1}"
            instr = (ex.get("instruction") or "")[:200]
            lines.append(f"  {i + 1}. {title}: {instr}")

    entry_url = (data.get("content") or {}).get("entry_url") or data.get("entry_url")
    if entry_url:
        lines.append(f"Entry URL: {entry_url} (student can open this in the embedded viewer)")

    sim_id = data.get("_id") or data.get("id", simulation_id)
    safe_desc = (data.get("description") or "").replace('"', "'")
    lines.append(f'\nRender tag: <teaching-simulation id="{sim_id}" title="{data.get("title", "")}" description="{safe_desc}" />')

    return "\n".join(lines)
