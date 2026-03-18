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


def build_tutor_system_prompt(teaching_overrides: str | None = None) -> str:
    """Assemble the full tutor system prompt from sections.

    Args:
        teaching_overrides: Optional per-student teaching style overrides
            compiled from _profile notes. Injected BEFORE the pedagogy
            section so they supersede defaults.

    Returns:
        Complete tutor system prompt string.
    """
    parts = [SECTION_IDENTITY, SECTION_STUDENT_CALIBRATION]

    # Inject teaching style overrides BEFORE pedagogy defaults
    if teaching_overrides:
        parts.append(teaching_overrides)

    parts.extend([
        SECTION_PEDAGOGY,
        SECTION_LEARNING_MODEL,
        SECTION_STUDENT_ADAPTATION,
        SECTION_SPOTLIGHT_AND_MEDIA,
        SECTION_EXECUTION,
    ])

    return "\n\n".join(parts)


# Backward compatibility — static prompt for imports that expect it
TUTOR_SYSTEM_PROMPT = build_tutor_system_prompt()
