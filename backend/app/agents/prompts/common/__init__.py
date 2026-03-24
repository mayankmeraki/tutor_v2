"""Common prompts shared across text and voice teaching modes.

All content lives in sections/ — this module provides clean re-exports
and a build function for the common (mode-independent) prompt.
"""

from ..sections.identity import SECTION_IDENTITY
from ..sections.pedagogy import SECTION_PEDAGOGY
from ..sections.learning_model import SECTION_LEARNING_MODEL
from ..sections.student_calibration import SECTION_STUDENT_CALIBRATION
from ..sections.student_adaptation import SECTION_STUDENT_ADAPTATION
from ..sections.execution import SECTION_EXECUTION

# Ordered list of common prompt sections
COMMON_SECTIONS = [
    SECTION_IDENTITY,
    SECTION_STUDENT_CALIBRATION,
    SECTION_PEDAGOGY,
    SECTION_LEARNING_MODEL,
    SECTION_STUDENT_ADAPTATION,
    SECTION_EXECUTION,
]

def build_common_prompt() -> str:
    """Build the common tutor prompt (shared across modes)."""
    return "\n\n".join(COMMON_SECTIONS)
