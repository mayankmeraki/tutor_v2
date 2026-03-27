"""Teaching tag format reference — loadable by Tutor and sub-agents.
Tags must be in EXACTLY these formats or they render as raw text.
"""

TAGS_PROMPT = r"""═══ TEACHING TAGS — FORMAT REFERENCE ═══

Tags render in the BOARD PANEL (right side, beside chat). Follow EXACTLY.

── BOARD PANEL TAGS ─────────────────

VIDEO (self-closing):
  <teaching-video lesson="3" start="260" end="380" label="Frequency vs intensity" />
  All attributes required. ONLY use for lessons with [video: URL] in Course Map.

SIMULATION (self-closing):
  <teaching-simulation id="sim_photoelectric" />
  id must match an Available Simulation ID exactly.

IMAGE — pin in board panel (self-closing):
  <teaching-spotlight type="image" src="URL" caption="Description" />

DISMISS — clear board panel:
  <teaching-spotlight-dismiss />

═══ BOARD PANEL LIFECYCLE ═══

1. ONE asset at a time — new tag auto-replaces previous.
2. Board panel always visible. Dismiss clears to empty.
3. Dismiss content >2 turns after student responds.
4. If [Active Spotlight] in context and NOT referencing it -> dismiss first.

── INLINE TAGS (in chat, NOT board panel) ──────────

IMAGE (self-closing, inline in chat):
  <teaching-image src="URL" caption="Double slit apparatus" />
  src must be from search_images results. NEVER invent URLs.

BOARD DRAW — live chalk drawing (opens in board panel):
  <teaching-board-draw title="Forces on an Inclined Plane">
  Attributes:
    title (required) — board header text
    clear (optional, default "true") — "false" keeps existing drawing and adds on top

  Content is JSONL — one command per line. Student sees real-time drawing.

  ═══ TWO COMMAND SYSTEMS ═══

  Use CONTENT COMMANDS for text, equations, explanations — they auto-layout safely.
  Use DRAWING COMMANDS (x,y positioned) for diagrams, shapes, arrows, annotations.
  NEVER use drawing commands (x,y) for body text — that causes overlap.
  A typical board mixes both: content commands for explanations, drawings for diagrams.

  ── CONTENT COMMANDS (auto-layout, safe, no overlap risk) ──

  These flow automatically. Use "placement" to control layout:
    "below" (default) — new line
    "center" — centered text
    "right" — right-aligned
    "indent" — indented
    "row-start" — start a side-by-side row
    "row-next" — add next item to the current row
    "beside:ID" — place beside element with that id

  TEXT:
    {"cmd":"text","text":"The Schrödinger Equation","color":"yellow","size":"h1","placement":"center"}
    {"cmd":"text","text":"Energy tells ψ how to change","color":"cyan","size":"h2"}
    Sizes: "h1" (largest), "h2", "h3", "text" (default), "small", "label" (smallest)

  EQUATION (equation + optional annotation):
    {"cmd":"equation","text":"iℏ ∂ψ/∂t = Ĥψ","note":"THE equation","color":"cyan","size":"h2"}

  COMPARE (two-column side-by-side — great for contrasts):
    {"cmd":"compare","left":{"title":"CLASSICAL","color":"cyan","items":["F = ma","Force drives motion"]},
                      "right":{"title":"QUANTUM","color":"yellow","items":["iℏ ∂ψ/∂t = Ĥψ","Energy drives ψ"]}}

  CALLOUT (highlighted box — for key insights):
    {"cmd":"callout","text":"Energy landscape → dictates time evolution","color":"gold"}

  STEP (numbered step):
    {"cmd":"step","n":1,"text":"Write down the Hamiltonian","color":"cyan"}

  LIST:
    {"cmd":"list","items":["First point","Second point","Third point"],"color":"white","style":"bullet"}

  RESULT (highlighted conclusion):
    {"cmd":"result","text":"ψ(x,t) = Ae^{i(kx-ωt)}","label":"Key Result","color":"gold"}

  CHECK/CROSS:
    {"cmd":"check","text":"Momentum is conserved"}
    {"cmd":"cross","text":"Energy is NOT conserved here"}

  DIVIDER: {"cmd":"divider"}

  EDITING (modify previous elements by id):
    {"cmd":"strikeout","target":"old-eq"} — strike through
    {"cmd":"update","target":"eq1","text":"new text","color":"green"} — replace content
    {"cmd":"delete","target":"wrong-step"} — fade out

  ── HOW TO USE THE BOARD LIKE A PROFESSOR ──

  Think of the board as a 2D space, NOT a document. A professor fills the
  board in ZONES — related content clusters together, with logical sections
  beside each other. The board is read spatially, not just top-to-bottom.

  PRINCIPLE 1: CONTENT CLUSTERS TOGETHER
    Related things go in the same zone. When you write an equation, the
    explanation of what each part means goes BESIDE it, not below in a
    separate section. When you show an animation, the labels describing
    what's happening go RIGHT NEXT to it.

    ✓ Equation on left, breakdown of its parts on right (same row)
    ✓ Animation on left, "what to watch for" list on right (same row)
    ✓ Diagram in center, annotations pointing to its parts nearby
    ✗ Equation alone, then 3 lines of text below, then animation alone

  PRINCIPLE 2: FILL THE BOARD IN LOGICAL ZONES
    A professor fills left-to-right, then moves down. One logical section
    occupies a zone, the next section goes beside it or below.

    Zone pattern for a typical explanation:
    ┌─────────────────────┬─────────────────────┐
    │ Main equation       │ What each symbol     │  ← row-start + row-next
    │ iℏ ∂ψ/∂t = Ĥψ     │ means (annotation)   │
    ├─────────────────────┴─────────────────────┤
    │ Key insight callout (full width)           │  ← callout
    ├─────────────────────┬─────────────────────┤
    │ Animation showing   │ What to watch:       │  ← row-start + row-next
    │ the concept         │ • green = real part  │
    │                     │ • spreading = disp.  │
    └─────────────────────┴─────────────────────┘

  PRINCIPLE 3: NEVER LEAVE EMPTY SPACE
    If you place a visual (animation, diagram, graph) and there's empty
    space beside it, FILL IT with related text, labels, or annotations.
    Every row should use its full width.

  BOARD FILLING SEQUENCE (follow this pattern):

  1. TITLE — centered, sets the topic
     {"cmd":"text","text":"The Big Question","color":"yellow","size":"h1","placement":"center"}

  2. CORE CONTENT — equation + explanation side by side
     {"cmd":"equation","text":"iℏ ∂ψ/∂t = Ĥψ","note":"THE equation","id":"eq1","placement":"row-start"}
     {"cmd":"text","text":"Left side: how ψ changes in time\nRight side: total energy acting on ψ\n\nThis is the ENTIRE equation.","color":"white","placement":"row-next"}

  3. KEY INSIGHT — full-width callout
     {"cmd":"callout","text":"Energy tells ψ how to change — that's the whole story","color":"gold"}

  4. VISUAL + COMMENTARY — animation with description beside it
     {"cmd":"animation","title":"ψ Evolving","code":"...","id":"anim1","placement":"row-start"}
     {"cmd":"text","text":"Watch the wave packet:\n\n• Cyan curve = ψ(x,t)\n• It oscillates with frequency ∝ energy\n• Higher energy → faster wiggles","color":"white","placement":"row-next"}

  5. CONTRAST or DEEPENING — compare, columns, or another row
     {"cmd":"compare","left":{"title":"HIGH ENERGY","color":"cyan","items":["Wiggles fast","Short wavelength","Many nodes"]},"right":{"title":"LOW ENERGY","color":"yellow","items":["Wiggles slow","Long wavelength","Few nodes"]}}

  6. CONCLUSION — result box
     {"cmd":"result","text":"Energy = clock speed of ψ","label":"Takeaway","color":"gold"}

  USE THIS PATTERN. Vary it, but always: pair things side-by-side,
  fill the width, cluster related content together.

  ── DRAWING COMMANDS (x,y positioned — for diagrams only) ──

  Use these ONLY for visual diagrams, force diagrams, geometric constructions,
  arrows connecting things, and spatial illustrations. NOT for body text.

  SHAPES & LINES:
    {"cmd":"line","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"arrow","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"dashed","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"rect","x":N,"y":N,"w":N,"h":N,"color":"C","lw":N}
    {"cmd":"fillrect","x":N,"y":N,"w":N,"h":N,"color":"C","opacity":0.15}
    {"cmd":"circle","cx":N,"cy":N,"r":N,"color":"C","lw":N}
    {"cmd":"dot","x":N,"y":N,"r":N,"color":"C"}
    {"cmd":"curvedarrow","x1":N,"y1":N,"x2":N,"y2":N,"cx":N,"cy":N,"color":"C","w":N}

  POSITIONED TEXT (ONLY for diagram labels — NOT for explanations):
    {"cmd":"text","text":"label","x":N,"y":N,"color":"C","size":N}
    {"cmd":"latex","tex":"F_g","x":N,"y":N,"color":"C","size":N}

  ANIMATION (p5.js — use placement for auto-layout OR x,y for diagrams):
    {"cmd":"animation","title":"Wave Packet","code":"...p5...","placement":"below"}
    {"cmd":"animation","x":N,"y":N,"w":W,"h":H,"code":"...","duration":MS}
    code: function(p, W, H) { p.setup=()=>{p.createCanvas(W,H);}; p.draw=()=>{...}; }
    Colors: bg=rgb(26,29,46) cyan=#53d8fb green=#7ed99a yellow=#f5d97a red=#ff6b6b

  ANNOTATE (label relative to an existing element — safe, no overlap):
    {"cmd":"annotate","target":"eq-id","text":"→ this drives everything","color":"dim","pos":"right"}
    pos: "right" (inline beside), "below", "below-right"
    Use for small annotations like "← THE equation" or "→ forces drive position"

  COLUMNS (multi-column grid — content flows into columns automatically):
    {"cmd":"columns","cols":2}
    [... content commands flow into the grid left-to-right ...]
    {"cmd":"columns-end"}

  LATEX — renders as Unicode, SINGLE LINE only:
    NEVER \frac{}{} → write a/b. NEVER \begin{align}. For hats: \hat{H}.

  ── CONTROL ──
    {"cmd":"voice","text":"..."} — narration overlay
    {"cmd":"pause","ms":N} — pause between sections
    {"cmd":"clear"} — erase board

  COLORS: white, yellow, green, blue, red, cyan, dim (or hex/CSS)

WIDGET — AI-generated HTML/CSS/JS (opens in board panel):
  <teaching-widget title="Double-Slit Experiment">
  [HTML + <style> + <script>. Self-contained, responsive, 2-5KB.]
  </teaching-widget>
  Use when topic needs interactivity AND no pre-built sim exists.

  ALWAYS include onParamUpdate(p) handler for tutor-driven updates.
  Use window._capacityReport(key, value) to report state changes back.

WIDGET UPDATE (self-closing):
  <teaching-widget-update asset="ASSET_ID" params='{"n": 3, "showLabels": true}' />
  Sends params to existing widget's onParamUpdate. Use instead of regenerating.
  If widget not showing, auto-reopens from history.

BOARD-DRAW RESUME — reload previous board + append:
  <teaching-board-draw-resume asset="ASSET_ID" title="Adding Forces">
  {"cmd":"arrow","x1":280,"y1":300,"x2":280,"y2":200,"color":"red","w":2}
  {"cmd":"text","text":"Friction","x":290,"y":310,"color":"red","size":18}
  </teaching-board-draw-resume>
  asset from [Previous Boards]. Original replays instantly, new commands animate.

── ASSESSMENT TAGS (max 1 per message, inline in chat) ─────────

MCQ:
  <teaching-mcq prompt="What determines the energy of a photoelectron?">
  <option value="a">Light intensity</option>
  <option value="b" correct>Light frequency</option>
  <option value="c">Surface area</option>
  </teaching-mcq>
  Probe MCQ (no correct attr): diagnostic, no green/red feedback. 3-4 options, plain text.

FREETEXT: <teaching-freetext prompt="Explain why..." placeholder="Think about..." />
CONFIDENCE: <teaching-confidence prompt="How confident are you about...?" />
AGREE-DISAGREE: <teaching-agree-disagree prompt="Doubling intensity doubles KE." />
SPOT-ERROR: <teaching-spot-error quote="..." prompt="What's wrong?" />
TEACHBACK: <teaching-teachback prompt="Explain X as if teaching a friend." concept="..." />

── NAVIGATION ─────────

<teaching-checkpoint lesson="3" section="2" />
<teaching-plan-update><complete step="1" /></teaching-plan-update>

═══ TAG RULES ═══
1. All attribute values in double quotes. 2. Self-closing: /> 3. Container: <tag>...</tag>
4. No nested teaching tags. 5. One assessment per message max.
6. Never invent IDs, URLs, or timestamps."""
