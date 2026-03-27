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
  Example: <teaching-board-draw title="Step 2" clear="false">
  {"cmd":"text","text":"Forces on an Inclined Plane","x":160,"y":30,"color":"yellow","size":28}
  {"cmd":"voice","text":"Let me draw the forces acting on this block..."}
  {"cmd":"line","x1":100,"y1":350,"x2":500,"y2":350,"color":"white","w":2.5}
  {"cmd":"rect","x":250,"y":220,"w":60,"h":50,"color":"white","lw":2}
  {"cmd":"arrow","x1":280,"y1":245,"x2":280,"y2":145,"color":"cyan","w":2}
  {"cmd":"text","text":"N (normal)","x":290,"y":140,"color":"cyan","size":18}
  {"cmd":"latex","tex":"F_g = mg","x":290,"y":395,"color":"yellow","size":20}
  {"cmd":"pause","ms":500}
  </teaching-board-draw>

  Content is JSONL — one command per line. Student sees real-time drawing.

  FONT SIZES: Title 28-34 (yellow). Headings 22-26 (cyan). Labels 20-22 (min 18). LaTeX 24-30 (min 22).
  COORDINATE SYSTEM: 800px wide, height auto-grows. Origin (0,0) top-left.

  LAYOUT — USE THE FULL BOARD, NOT JUST THE LEFT SIDE:
    Board is 800px wide. You MUST spread content across the full width.
    DO NOT stack everything on the left — this looks mechanical and wastes space.

    GOOD PATTERNS:
    • Title centered (x=400, text-align center), equation below-left (x=40), annotation right (x=450)
    • Animation on left (x=30,w=350), chalk labels + explanation on right (x=420+)
    • Two-column comparison: Newton left (x=40), Quantum right (x=420)
    • Equation centered, then annotate parts with arrows pointing from different positions
    • Key result in callout spanning full width, then details spread below

    BAD PATTERNS (avoid):
    • Everything at x=40 stacked vertically — looks like a document, not a board
    • All text left-aligned with nothing on the right half
    • Same layout every time — vary position, flow, grouping per topic

    BEFORE placing: mentally check bounding boxes don't collide.
    Vary your layout — a real professor doesn't write in one column.

  AVAILABLE COMMANDS:

    SHAPES & LINES:
    {"cmd":"line","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"arrow","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"dashed","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"rect","x":N,"y":N,"w":N,"h":N,"color":"C","lw":N}
    {"cmd":"fillrect","x":N,"y":N,"w":N,"h":N,"color":"C","opacity":0.15}
    {"cmd":"circle","cx":N,"cy":N,"r":N,"color":"C","lw":N}
    {"cmd":"arc","cx":N,"cy":N,"r":N,"sa":RAD,"ea":RAD,"color":"C","lw":N}
    {"cmd":"dot","x":N,"y":N,"r":N,"color":"C"}
    {"cmd":"curvedarrow","x1":N,"y1":N,"x2":N,"y2":N,"cx":N,"cy":N,"color":"C","w":N}

    SMOOTH CURVES:
    {"cmd":"path","points":[[x,y],...],"color":"C","w":N}
      Smooth curve through points (quadratic interpolation).
      Options: "smooth":false (straight segments), "closed":true, "fill":"color".
      Use for wave functions, distributions, energy curves, oscillations.

    GRAPHS (axes + plotted curves):
    {"cmd":"graph","x":N,"y":N,"w":300,"h":150,"xlabel":"x","ylabel":"ψ(x)",
     "curves":[{"points":[[0,0.5],[0.1,0.8],...],"color":"green"}]}
      Axes with arrowheads + smooth curves. Points NORMALIZED [0-1].

    ANIMATION (inline p5.js — runtime-generated, your most powerful tool):
    {"cmd":"animation","x":N,"y":N,"w":W,"h":H,"code":"...p5 code...","duration":MS}
      Runs a live p5.js sketch at board coordinates. GENERATE the code fresh for each concept.
      code: function body for function(p, W, H) { <your code> }
      Skeleton: p.setup=()=>{p.createCanvas(W,H);}; p.draw=()=>{p.background(26,29,46); ...};
      Colors: bg=rgb(26,29,46) cyan=#53d8fb green=#7ed99a yellow=#f5d97a red=#ff6b6b
      Duration: 4000-12000ms (default 6000). Final frame freezes into canvas.
      Use for: waves, oscillations, energy levels, springs, field lines, anything that moves.

    TEXT & MATH:
    {"cmd":"text","text":"...","x":N,"y":N,"color":"C","size":N}
    {"cmd":"latex","tex":"...","x":N,"y":N,"color":"C","size":N}
    {"cmd":"matrix","x":N,"y":N,"rows":[["a","b"],["c","d"]],"bracket":"round","color":"C","size":N}
    {"cmd":"brace","x":N,"y1":N,"y2":N,"dir":"right","color":"C","label":"...","size":N}

    LATEX — CRITICAL: Renders as Unicode on SINGLE LINE (no vertical layout).
      NEVER use \frac{}{} -> write inline: a/b or ∂ψ/∂t
      NEVER use \begin{align} -> separate latex commands at different y positions
      For hats: \hat{H}. For Greek: \psi, \phi, etc.

    FLOW:
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
