"""Tutor system prompt — modular section assembler.

Prompt caching requires the static block to be identical across turns.
Section order:
  1. CORE sections (always loaded, every session)
  2. DOMAIN sections (mode-specific, frozen at session start)
  3. TOOLKIT + TAGS + VOICE (always, after domain)
  --- cache boundary ---
  4. DYNAMIC context (per-turn, never cached)
"""

from __future__ import annotations

from typing import Sequence

from .sections import (
    SECTION_IDENTITY,
    SECTION_STUDENT_CALIBRATION,
    SECTION_PEDAGOGY,
    SECTION_LEARNING_MODEL,
    SECTION_STUDENT_ADAPTATION,
    SECTION_CONCEPT_TEACHING,
    SECTION_EXECUTION,
    SECTION_DSA_MODE,
    SECTION_SYSTEM_DESIGN_MODE,
    SECTION_MOCK_INTERVIEW_MODE,
)

# Registry: section name → prompt text
# Core sections are in fixed order; domain sections are appended by the blueprint.
_SECTION_REGISTRY: dict[str, str] = {
    "IDENTITY": SECTION_IDENTITY,
    "STUDENT_CALIBRATION": SECTION_STUDENT_CALIBRATION,
    "PEDAGOGY": SECTION_PEDAGOGY,
    "LEARNING_MODEL": SECTION_LEARNING_MODEL,
    "STUDENT_ADAPTATION": SECTION_STUDENT_ADAPTATION,
    "CONCEPT_TEACHING": SECTION_CONCEPT_TEACHING,
    "EXECUTION": SECTION_EXECUTION,
    "DSA_MODE": SECTION_DSA_MODE,
    "SYSTEM_DESIGN_MODE": SECTION_SYSTEM_DESIGN_MODE,
    "MOCK_INTERVIEW_MODE": SECTION_MOCK_INTERVIEW_MODE,
}

# Lazy-load mock company prompts into registry on first use
_mock_loaded = False


def _ensure_mock_prompts():
    global _mock_loaded
    if _mock_loaded:
        return
    _mock_loaded = True
    try:
        from .sections.mock_interviews import get_mock_prompt
        for company in ("google", "meta", "amazon", "microsoft", "generic"):
            prompt = get_mock_prompt(company)
            if prompt:
                _SECTION_REGISTRY[f"MOCK_{company.upper()}"] = prompt
    except ImportError:
        pass


def get_section(name: str) -> str | None:
    """Look up a prompt section by name."""
    _ensure_mock_prompts()
    return _SECTION_REGISTRY.get(name)


def build_tutor_system_prompt(
    prompt_sections: Sequence[str] | None = None,
    subject_id: str | None = None,
    # Legacy params — still supported for backward compat
    session_mode: str = "general",
    mock_company: str | None = None,
) -> str:
    """Assemble the full tutor system prompt from sections.

    If `prompt_sections` is provided (from a SessionBlueprint), use that list
    directly. Otherwise fall back to the legacy mode-based logic.

    All sections here are STATIC (same for every student, every turn).
    Per-student teaching overrides are injected into the DYNAMIC context
    block by build_tutor_prompt() to maximize prompt caching.
    """
    _ensure_mock_prompts()

    if prompt_sections:
        # Blueprint-driven: load sections in the exact order specified
        parts = []
        for name in prompt_sections:
            section = _SECTION_REGISTRY.get(name)
            if section:
                parts.append(section)
            else:
                import logging
                logging.getLogger(__name__).warning("Unknown prompt section: %s", name)

        # Inject subject profile after IDENTITY if present
        if subject_id:
            from app.agents.prompts.subjects import get_subject_prompt_section
            subject_section = get_subject_prompt_section(subject_id)
            if subject_section:
                # Insert after IDENTITY (index 0) if it exists
                insert_at = 1 if parts else 0
                parts.insert(insert_at, subject_section)

        return "\n\n".join(parts)

    # ── Legacy mode-based logic (backward compat) ──
    parts = [SECTION_IDENTITY]

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

    if session_mode == "dsa":
        parts.append(SECTION_DSA_MODE)
    elif session_mode == "sd":
        parts.append(SECTION_SYSTEM_DESIGN_MODE)
    elif session_mode == "mock_interview":
        parts.append(SECTION_MOCK_INTERVIEW_MODE)
        company_prompt = _SECTION_REGISTRY.get(f"MOCK_{(mock_company or 'generic').upper()}")
        if company_prompt:
            parts.append(company_prompt)

    return "\n\n".join(parts)
