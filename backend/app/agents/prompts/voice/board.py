"""Voice mode board layout, cursor rules, and annotations.

Controls how content is positioned on the full-screen board,
how the hand cursor follows elements, and ephemeral annotations.
"""

VOICE_BOARD_RULES = r"""
═══ BOARD LAYOUT ═══

Every drawn element MUST have an id for cursor references.
Use descriptive IDs: "title-main", "eq-schrodinger", "label-lhs", "anim-wave"

Cursor positioning uses element IDs. NEVER guess raw coordinates:
  cursor="write"              — auto-follows the draw in this beat
  cursor="write:id:eq-main"   — pen pose at bottom of element
  cursor="tap:id:eq-main"     — tap center (pulse + scroll)
  cursor="point:id:eq-main"   — hover at center
  cursor="rest"               — hide cursor

FONT SIZES — semantic names (engine auto-scales to screen):
  "h1" — titles   "h2" — subtitles   "text" — equations/content
  "small" — annotations   "label" — axis labels/captions

LAYOUT RULES (virtual coords 0-800 width):
  The board is ONE continuous scrollable surface growing downward.
  The engine auto-offsets Y coordinates — just use Y starting from 20 each scene.

  KEY: Use the FULL 800-wide space. Don't cram things left.
  - Titles: x=150-300 (centered), y=20
  - Main equation: x=100-200 (centered), y=60-100
  - Labels LEFT of equation: x=30-200
  - Labels RIGHT of equation: x=450-750
  - Annotations/explanations: x=30, y below equation
  - Animations: x=30, w=350, h=180 (left side), text at x=400+
    OR full width: x=20, w=750, h=200

  SPACING:
  - 30px vertical gap between elements
  - 40px left/right margins (x=30 to x=770)
  - Don't stack more than 3 elements side by side
  - Leave room — whitespace is good for readability

═══ EPHEMERAL ANNOTATIONS ═══

Like a teacher circling on the whiteboard — appears then fades:
  annotate="circle:id:eq-main"     — hand-drawn circle, fades after 2s
  annotate="underline:id:label-1"  — wavy underline below element
  annotate="box:id:eq-schrodinger" — rounded rectangle highlight
  annotate="glow:id:wave-anim"     — soft glow overlay

Optional: annotate-color="#fbbf24" annotate-duration="3000"
"""
