"""Tutor system prompt — modular section assembler.

SECTION MAP:
  SECTION_IDENTITY            — WHO the tutor is
  SECTION_STUDENT_CALIBRATION — NEW vs RETURNING student
  SECTION_PEDAGOGY            — teaching approach, questioning
  SECTION_LEARNING_MODEL      — prime directive, evidence hierarchy
  SECTION_STUDENT_ADAPTATION  — personalization, pace, notes
  SECTION_CONCEPT_TEACHING    — calibrate-first, mechanism + counterfactual
                                + applications + discrimination
  SECTION_EXECUTION           — plan flow, agents, session
"""

from .sections import (
    SECTION_IDENTITY,
    SECTION_STUDENT_CALIBRATION,
    SECTION_PEDAGOGY,
    SECTION_LEARNING_MODEL,
    SECTION_STUDENT_ADAPTATION,
    SECTION_CONCEPT_TEACHING,
    SECTION_EXECUTION,
)


def build_tutor_system_prompt(subject_id: str | None = None) -> str:
    """Assemble the full tutor system prompt from sections.

    All sections here are STATIC (same for every student, every turn).
    Per-student teaching overrides are injected into the DYNAMIC context
    block by build_tutor_prompt() to maximize prompt caching.
    """
    parts = [SECTION_IDENTITY]

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
        SECTION_CONCEPT_TEACHING,
        SECTION_EXECUTION,
    ])

    return "\n\n".join(parts)
