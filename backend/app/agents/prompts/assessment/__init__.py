"""Assessment agent system prompt — split across files for navigation.

Concatenated at import time into ASSESSMENT_SYSTEM_PROMPT (the public export).
"""

from .identity import PART as _identity
from .core_loop import PART as _core_loop
from .completion import PART as _completion
from .edge_cases import PART as _edge_cases

ASSESSMENT_SYSTEM_PROMPT = _identity + _core_loop + _completion + _edge_cases

__all__ = ["ASSESSMENT_SYSTEM_PROMPT"]
