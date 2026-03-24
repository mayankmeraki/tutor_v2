"""Student calibration, adaptation, personalization, and note-taking.

Merged from sections/student_calibration.py + sections/student_adaptation.py.
Shared across text and voice modes.
"""

from ..sections.student_calibration import SECTION_STUDENT_CALIBRATION
from ..sections.student_adaptation import SECTION_STUDENT_ADAPTATION

STUDENT_PROMPT = SECTION_STUDENT_CALIBRATION + "\n" + SECTION_STUDENT_ADAPTATION
