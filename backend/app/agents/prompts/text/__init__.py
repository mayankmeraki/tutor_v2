"""Text mode prompts — chat-based teaching with board on the right.

Re-exports existing text mode components:
- Media: spotlight, board-draw conventions (from sections/spotlight_and_media.py)
- Toolkit: tool documentation for text mode
- Tags: teaching tags (<teaching-board-draw>, <teaching-widget>, etc.)
"""

from ..sections.spotlight_and_media import SECTION_SPOTLIGHT_AND_MEDIA
from ..toolkit import TOOLKIT_PROMPT
from ..tags import TAGS_PROMPT

TEXT_MODE_SECTIONS = [
    SECTION_SPOTLIGHT_AND_MEDIA,
]

def build_text_mode_prompt() -> str:
    """Build text-mode-specific prompt sections."""
    return "\n\n".join(TEXT_MODE_SECTIONS) + "\n\n" + TOOLKIT_PROMPT + "\n\n" + TAGS_PROMPT
