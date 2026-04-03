"""Modular tutor prompt sections.

Each file contains ONE section of the tutor system prompt, focused on
a single responsibility. The assembler in tutor.py combines them.

ALL SECTIONS ARE STATIC (cacheable). Dynamic per-student context is
injected separately in build_tutor_prompt() → dynamic_context block.

ARCHITECTURE:
  ┌─────────────────────────────────────────────────────────────────┐
  │  IDENTITY & CORE (who the tutor is)                             │
  │  identity.py          — persona, role, voice, boundaries       │
  │  learning_model.py    — prime directive, evidence hierarchy     │
  ├─────────────────────────────────────────────────────────────────┤
  │  PEDAGOGY & ADAPTATION (how to teach)                           │
  │  pedagogy.py          — questioning strategy, engagement rules │
  │  student_adaptation.py — Bloom's taxonomy, note-taking,        │
  │                          student identification, adaptivity    │
  │  student_calibration.py — NEW vs RETURNING student rules       │
  ├─────────────────────────────────────────────────────────────────┤
  │  MEDIA & TOOLS (what to teach with)                             │
  │  spotlight_and_media.py — board-draw, widgets, video, sims     │
  ├─────────────────────────────────────────────────────────────────┤
  │  EXECUTION & LIFECYCLE (session flow)                           │
  │  execution.py         — plan adherence, assessment gating,     │
  │                          housekeeping tags, session lifecycle   │
  └─────────────────────────────────────────────────────────────────┘

ALSO COMBINED (from prompts/ root):
  toolkit.py  — content tools, agent tags, tool reference
  tags.py     — teaching tag format reference (board-draw, MCQ, etc.)
  planning.py — planning agent prompt (separate agent, not tutor)

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
