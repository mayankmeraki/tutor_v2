"""Tutor system prompt — modular section assembler.

The tutor prompt is split into separate files under sections/, one per
responsibility. This module imports them and provides the assembler
that combines sections into the final system prompt.

Prompt content lives in sections/*.py — this file is CODE ONLY.

SECTION MAP (see sections/__init__.py for architecture diagram):
  SECTION_IDENTITY            — WHO the tutor is (fixed)
  SECTION_STUDENT_CALIBRATION — NEW vs RETURNING student (calibrated)
  SECTION_PEDAGOGY            — teaching approach, questioning (overridable)
  SECTION_LEARNING_MODEL      — prime directive, evidence hierarchy (fixed)
  SECTION_STUDENT_ADAPTATION  — personalization, pace, notes (overridable)
  SECTION_SPOTLIGHT_AND_MEDIA — spotlight, board-draw, tools (fixed mechanics)
  SECTION_EXECUTION           — plan flow, agents, session (fixed)
"""

from .sections import (
    SECTION_IDENTITY,
    SECTION_STUDENT_CALIBRATION,
    SECTION_PEDAGOGY,
    SECTION_LEARNING_MODEL,
    SECTION_STUDENT_ADAPTATION,
    SECTION_SPOTLIGHT_AND_MEDIA,
    SECTION_EXECUTION,
)


def build_tutor_system_prompt(voice_mode: bool = False, subject_id: str | None = None) -> str:
    """Assemble the full tutor system prompt from sections.

    All sections here are STATIC (same for every student, every turn).
    Per-student teaching overrides are injected into the DYNAMIC context
    block by build_tutor_prompt() to maximize prompt caching.

    Args:
        voice_mode: If True, excludes coordinate-based layout examples.
        subject_id: Optional subject profile ID (e.g. "physics", "mathematics").
            If provided, subject-specific teaching instructions are injected
            after identity. If None, tutor operates in general mode.

    Returns:
        Complete tutor system prompt string.
    """
    parts = [
        SECTION_IDENTITY,
    ]

    # Inject subject-specific teaching profile if available
    if subject_id:
        from app.agents.prompts.subjects import get_subject_prompt_section
        subject_section = get_subject_prompt_section(subject_id)
        if subject_section:
            parts.append(subject_section)

    parts.extend([
        SECTION_STUDENT_CALIBRATION,
        SECTION_PEDAGOGY,
        SECTION_LEARNING_MODEL,
        SECTION_STUDENT_ADAPTATION,
    ])

    if not voice_mode:
        parts.append(SECTION_SPOTLIGHT_AND_MEDIA)

    parts.append(SECTION_EXECUTION)

    return "\n\n".join(parts)


# Backward compatibility — static prompt for imports that expect it
TUTOR_SYSTEM_PROMPT = build_tutor_system_prompt()
