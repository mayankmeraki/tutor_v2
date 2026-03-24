"""Voice mode prompts — full-screen board with TTS narration.

Organized into:
- scene.py: <teaching-voice-scene> format, <vb> beat attributes
- board.py: board layout, cursor rules, ephemeral annotations
- animation.py: animation control, element highlighting
"""

from .scene import VOICE_SCENE_FORMAT
from .board import VOICE_BOARD_RULES
from .animation import VOICE_ANIMATION_CONTROL


VOICE_MODE_HEADER = r"""
[VOICE MODE — ACTIVE]
The student is in VOICE MODE. There is NO chat pane — only a full-screen board with subtitles.
Your spoken words are delivered via TTS. The board is the only visual.

═══ RULES ═══

1. Draw before referencing. 2. Short sentences (under 20 words per beat).
3. Alternate draw/say beats for natural rhythm.
4. Use pause="0.5"-"1.5" generously — pauses are where learning happens.
5. End with question="true" for student response.
6. Every drawn element MUST have an id for cursor references.
7. Use semantic font sizes: "h1", "h2", "text", "small", "label".
8. No text outside <teaching-voice-scene>. Tools go BEFORE the scene tag.
9. Board is continuous — keep drawing below previous content. Use increasing Y values.
"""


def build_voice_mode_prompt() -> str:
    """Build the complete voice mode prompt (static, cacheable)."""
    return "\n".join([
        VOICE_MODE_HEADER,
        VOICE_SCENE_FORMAT,
        VOICE_BOARD_RULES,
        VOICE_ANIMATION_CONTROL,
    ])
