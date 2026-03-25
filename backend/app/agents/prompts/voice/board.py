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
  The engine auto-offsets Y coordinates — just use Y starting from 15 each scene.

  USE THE FULL WIDTH. Don't cram things left.
  - Titles: x=100-300, y=15
  - Main equation: x=80-200, y=45-70
  - Labels beside equations: x=400-750 (same Y as equation)
  - Explanations: x=30, y below equation
  - Animations: x=20, w=350, h=160 (left), text at x=400+
    OR full width: x=20, w=750, h=180

  TIGHT SPACING — pack content close:
  - 15-20px vertical gap between elements (NOT 30+)
  - 30px left/right margins (x=30 to x=770)
  - Place labels BESIDE things, not below with big gaps
  - The board should look full and organized, not sparse

═══ EPHEMERAL ANNOTATIONS ═══

Like a teacher circling on the whiteboard — appears then fades:
  annotate="circle:id:eq-main"     — hand-drawn circle, fades after 2s
  annotate="underline:id:label-1"  — wavy underline below element
  annotate="box:id:eq-schrodinger" — rounded rectangle highlight
  annotate="glow:id:wave-anim"     — soft glow overlay

Optional: annotate-color="#fbbf24" annotate-duration="3000"
"""
