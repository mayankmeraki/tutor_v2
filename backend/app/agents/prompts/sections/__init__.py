"""Modular tutor prompt sections — one responsibility per file."""

from .identity import SECTION_IDENTITY
from .student_calibration import SECTION_STUDENT_CALIBRATION
from .pedagogy import SECTION_PEDAGOGY
from .learning_model import SECTION_LEARNING_MODEL
from .student_adaptation import SECTION_STUDENT_ADAPTATION
from .concept_teaching import SECTION_CONCEPT_TEACHING
from .execution import SECTION_EXECUTION
from .dsa_mode import SECTION_DSA_MODE
from .system_design_mode import SECTION_SYSTEM_DESIGN_MODE
from .mock_interview_mode import SECTION_MOCK_INTERVIEW_MODE

__all__ = [
    "SECTION_IDENTITY",
    "SECTION_STUDENT_CALIBRATION",
    "SECTION_PEDAGOGY",
    "SECTION_LEARNING_MODEL",
    "SECTION_STUDENT_ADAPTATION",
    "SECTION_CONCEPT_TEACHING",
    "SECTION_EXECUTION",
    "SECTION_DSA_MODE",
    "SECTION_SYSTEM_DESIGN_MODE",
    "SECTION_MOCK_INTERVIEW_MODE",
]
