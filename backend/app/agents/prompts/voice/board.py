"""Voice mode board layout, cursor rules, and annotations.

Controls how content is positioned on the full-screen board,
how the hand cursor follows elements, and ephemeral annotations.
"""

VOICE_BOARD_RULES = r"""
═══ BOARD LAYOUT — PLACEMENT ENGINE ═══

Every drawn element MUST have an "id" for referencing and a "placement" for positioning.
DO NOT use raw x,y coordinates. The engine handles ALL positioning.

PLACEMENT TAGS — use these instead of x,y:
  "below"       — below last content, left-aligned (DEFAULT if omitted)
  "center"      — centered horizontally, below last content
  "right"       — right-aligned, below last content
  "indent"      — indented left, below last content
  "row-start"   — start a new side-by-side row
  "row-next"    — next item in the current row
  "beside:ID"   — to the right of element with that ID
  "below:ID"    — directly below element with that ID
  "full-width"  — span the entire board width

EXAMPLE:
  draw='{"cmd":"text","text":"Title","placement":"center","size":"h1","id":"title","color":"#fbbf24"}'
  draw='{"cmd":"text","text":"F = ma","placement":"center","size":"text","id":"eq-f"}'
  draw='{"cmd":"text","text":"← force","placement":"beside:eq-f","size":"small","id":"label-f"}'

SIDE-BY-SIDE LAYOUT:
  draw='{"cmd":"text","text":"Left item","placement":"row-start","id":"left"}'
  draw='{"cmd":"text","text":"Right item","placement":"row-next","id":"right"}'

The engine automatically:
  - Flows content downward (no gaps, no overlap)
  - Manages side-by-side rows
  - Centers elements when asked
  - Stacks labels beside their targets

FONT SIZES — semantic names (engine auto-scales to screen):
  "h1" — titles   "h2" — subtitles   "text" — equations/content
  "small" — annotations   "label" — axis labels/captions

ELEMENT IDs — ALWAYS provide descriptive IDs:
  Use: "title-main", "eq-schrodinger", "label-lhs", "anim-wave"
  IDs enable {ref:id} highlights and beside:/below: placements.

CURSOR — uses element IDs:
  cursor="write"              — auto-follows the draw in this beat
  cursor="tap:id:eq-main"     — tap center (pulse + scroll)
  cursor="point:id:eq-main"   — hover at center
  cursor="rest"               — hide cursor

═══ EPHEMERAL ANNOTATIONS ═══

Like a teacher circling on the whiteboard — appears then fades:
  annotate="circle:id:eq-main"     — hand-drawn circle
  annotate="underline:id:label-1"  — wavy underline
  annotate="box:id:eq-schrodinger" — rectangle highlight
  annotate="glow:id:wave-anim"     — soft glow

Optional: annotate-color="#fbbf24" annotate-duration="3000"
"""
