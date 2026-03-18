"""Modular tutor prompt sections.

Each file contains ONE section of the tutor system prompt, focused on
a single responsibility. The assembler in tutor.py combines them.

ARCHITECTURE:
  ┌─────────────────────────────────────────────────────────────────┐
  │  FIXED SECTIONS (never change per student)                      │
  │  identity.py          — WHO the tutor is, role, framing        │
  │  learning_model.py    — prime directive, evidence hierarchy     │
  │  spotlight_and_media.py — spotlight, board-draw, visual tools   │
  │  execution.py         — plan flow, agents, session lifecycle   │
  ├─────────────────────────────────────────────────────────────────┤
  │  CALIBRATION (changes by experience level)                      │
  │  student_calibration.py — NEW vs RETURNING student rules       │
  ├─────────────────────────────────────────────────────────────────┤
  │  OVERRIDABLE (adapt per student via _profile overlay)           │
  │  pedagogy.py          — teaching approach, questioning          │
  │  student_adaptation.py — personalization, pace, modality       │
  └─────────────────────────────────────────────────────────────────┘

OVERRIDE MECHANISM:
  When a student has a _profile note with teaching preferences,
  the prompt assembler compiles a [TEACHING STYLE OVERRIDES] block
  injected BEFORE pedagogy.py defaults. Overrides supersede defaults.
"""

from .identity import SECTION_IDENTITY
from .student_calibration import SECTION_STUDENT_CALIBRATION
from .pedagogy import SECTION_PEDAGOGY
from .learning_model import SECTION_LEARNING_MODEL
from .student_adaptation import SECTION_STUDENT_ADAPTATION
from .spotlight_and_media import SECTION_SPOTLIGHT_AND_MEDIA
from .execution import SECTION_EXECUTION

__all__ = [
    "SECTION_IDENTITY",
    "SECTION_STUDENT_CALIBRATION",
    "SECTION_PEDAGOGY",
    "SECTION_LEARNING_MODEL",
    "SECTION_STUDENT_ADAPTATION",
    "SECTION_SPOTLIGHT_AND_MEDIA",
    "SECTION_EXECUTION",
]
