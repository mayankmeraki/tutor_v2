"""Tool result formatters — call content_service directly (no HTTP)."""

import math

from app.services.content_service import get_learning_tool_by_id, get_section_full


async def get_section_content(lesson_id: int, section_index: int) -> str:
    data = await get_section_full(lesson_id, section_index)
    if not data:
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

    return "\n".join(lines)


async def get_simulation_details(simulation_id: str) -> str:
    data = await get_learning_tool_by_id(simulation_id)
    if not data:
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
