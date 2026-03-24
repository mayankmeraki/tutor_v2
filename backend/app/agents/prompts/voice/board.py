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

Layout patterns (virtual coords 0-800 width):
  Pattern A — Animation LEFT, text RIGHT: anim x=30,w=350 / text x=400+
  Pattern B — Text TOP, animation BELOW: title y=20, eq y=55, anim y=100
  Pattern C — Side by side: left x=20, right x=420

Keep 30px margins, 20-25px vertical gaps. Bottom 50px clear for subtitles.
Max ~15 elements per board. Use clear-before="true" between concepts.

═══ EPHEMERAL ANNOTATIONS ═══

Like a teacher circling on the whiteboard — appears then fades:
  annotate="circle:id:eq-main"     — hand-drawn circle, fades after 2s
  annotate="underline:id:label-1"  — wavy underline below element
  annotate="box:id:eq-schrodinger" — rounded rectangle highlight
  annotate="glow:id:wave-anim"     — soft glow overlay

Optional: annotate-color="#fbbf24" annotate-duration="3000"
"""
