"""Subject-specific teaching profiles.

The core teaching system (board mechanics, pedagogy, execution flow,
assessment, planning) is SUBJECT-NEUTRAL. Profiles add domain flavor.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SubjectProfile:
    """A domain-specific teaching profile."""
    id: str
    name: str
    identity: str           # How the tutor frames itself for this subject
    teaching_guide: str     # Subject-specific pedagogy tips
    examples: str           # Example equations, board layouts, topics
    misconceptions: str     # Common mistakes to watch for


# ── Registry ──────────────────────────────────────────────────────────

_PROFILES: dict[str, SubjectProfile] = {}


def _register_profile(profile: SubjectProfile):
    _PROFILES[profile.id] = profile


def get_subject_prompt_section(subject_id: str | None) -> str:
    """Build the subject-specific prompt section for injection into the tutor.

    Returns empty string for unknown/None subjects (tutor operates in general mode).
    """
    if not subject_id:
        return ""
    profile = _PROFILES.get(subject_id)
    if not profile:
        return ""

    parts = [
        f"═══ SUBJECT: {profile.name.upper()} ═══\n",
        profile.identity,
        "\n── Teaching this subject ──\n",
        profile.teaching_guide,
        "\n── Example patterns ──\n",
        profile.examples,
        "\n── Common misconceptions ──\n",
        profile.misconceptions,
    ]
    return "\n".join(parts)


# ── Load all built-in profiles ────────────────────────────────────────

from app.agents.prompts.subjects.physics import PROFILE as _physics
from app.agents.prompts.subjects.mathematics import PROFILE as _math
from app.agents.prompts.subjects.chemistry import PROFILE as _chemistry
from app.agents.prompts.subjects.biology import PROFILE as _biology
from app.agents.prompts.subjects.business import PROFILE as _business
from app.agents.prompts.subjects.computer_science import PROFILE as _cs

for _p in [_physics, _math, _chemistry, _biology, _business, _cs]:
    _register_profile(_p)
