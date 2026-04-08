"""Modular tutor prompt sections — one responsibility per file."""

from .identity import SECTION_IDENTITY
from .student_calibration import SECTION_STUDENT_CALIBRATION
from .pedagogy import SECTION_PEDAGOGY
from .learning_model import SECTION_LEARNING_MODEL
from .student_adaptation import SECTION_STUDENT_ADAPTATION
from .execution import SECTION_EXECUTION

__all__ = [
    "SECTION_IDENTITY",
    "SECTION_STUDENT_CALIBRATION",
    "SECTION_PEDAGOGY",
    "SECTION_LEARNING_MODEL",
    "SECTION_STUDENT_ADAPTATION",
    "SECTION_EXECUTION",
]
