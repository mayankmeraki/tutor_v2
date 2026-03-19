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
2. Board panel is always visible. Dismiss clears it to empty state.
3. Don't leave content open >2 turns after student responds. Dismiss and move on.
4. If [Active Spotlight] in context and you're NOT referencing it → dismiss first.

── INLINE TAGS (in chat, NOT board panel) ──────────

IMAGE (self-closing, inline in chat):
  <teaching-image src="URL" caption="Double slit apparatus" />
  src must be from search_images results. NEVER invent URLs.

BOARD DRAW — live chalk drawing (opens in board panel):
  <teaching-board-draw title="Forces on an Inclined Plane">
  Attributes:
    title (required) — what appears in the board header
    clear (optional, default "true") — "true" wipes board first, "false" keeps
      existing drawing and adds on top. Use clear="false" when building on a
      previous step after student responds (scaffolding).
  Example appending: <teaching-board-draw title="Step 2" clear="false">
  {"cmd":"text","text":"Forces on an Inclined Plane","x":160,"y":30,"color":"yellow","size":28}
  {"cmd":"voice","text":"Let me draw the forces acting on this block..."}
  {"cmd":"line","x1":100,"y1":350,"x2":500,"y2":350,"color":"white","w":2.5}
  {"cmd":"rect","x":250,"y":220,"w":60,"h":50,"color":"white","lw":2}
  {"cmd":"arrow","x1":280,"y1":245,"x2":280,"y2":145,"color":"cyan","w":2}
  {"cmd":"text","text":"N (normal)","x":290,"y":140,"color":"cyan","size":18}
  {"cmd":"latex","tex":"F_g = mg","x":290,"y":395,"color":"yellow","size":20}
  {"cmd":"pause","ms":500}
  </teaching-board-draw>

  Content is JSONL — one command per line. Student sees you draw in real-time.

  FONT SIZES: Title 26-30 (yellow). Headings 20-22 (cyan). Labels 18-20 (min 16). LaTeX 22-26 (min 20).
  COORDINATE SYSTEM: 800px wide, height auto-grows. Origin (0,0) top-left.
  SPACING: Title→next 50px. Heading→next 35px. Text→text 30px. LaTeX→next 45px.
    If elements within 30px at overlapping x → OVERLAP. Increase spacing.

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

    SMOOTH CURVES (use for waves, functions, any curved shape):
    {"cmd":"path","points":[[x,y],...],"color":"C","w":N}
      Draws a smooth curve through the points (quadratic interpolation).
      Add "smooth":false for straight line segments. Add "closed":true to close shape.
      Add "fill":"color" to fill the enclosed area.
      USE THIS for wave functions, probability distributions, energy curves,
      oscillations — anything that should look like a smooth continuous function.
      Example sine wave: points at ~15-20 evenly spaced x values with y = sin(x).

    GRAPHS (axes + plotted curves — use for any x-y relationship):
    {"cmd":"graph","x":N,"y":N,"w":300,"h":150,"xlabel":"x","ylabel":"\u03C8(x)",
     "curves":[{"points":[[0,0.5],[0.1,0.8],...],"color":"green"}]}
      Draws labeled axes with arrowheads, then plots smooth curves.
      Curve points are NORMALIZED [0-1] for both x and y.
      Multiple curves on the same axes: add more objects to the "curves" array.
      USE THIS for: potential wells, wave functions, probability densities,
      energy level diagrams, any function plot.

    TEXT & MATH:
    {"cmd":"text","text":"...","x":N,"y":N,"color":"C","size":N}
    {"cmd":"latex","tex":"...","x":N,"y":N,"color":"C","size":N}
    {"cmd":"matrix","x":N,"y":N,"rows":[["a","b"],["c","d"]],"bracket":"round","color":"C","size":N}
    {"cmd":"brace","x":N,"y1":N,"y2":N,"dir":"right","color":"C","label":"...","size":N}

    LATEX RENDERING — CRITICAL:
      The board renders LaTeX as Unicode on a SINGLE LINE (no vertical fractions).
      ✗ NEVER use \frac{}{} — it renders as (a)/(b) on one line, not a fraction.
      ✓ Write fractions inline: \partial \psi / \partial t or use ∂ψ/∂t directly.
      ✗ NEVER use \begin{align} or multi-line environments — canvas is one line.
      ✓ Break multi-line equations into SEPARATE latex commands at different y positions.
      Example: "iħ ∂ψ/∂t = Hψ" as ONE latex cmd, NOT \frac{\partial\psi}{\partial t}.
      For operator hats: use \hat{H} (renders as Ĥ). For Greek: \psi, \phi, etc.

    FLOW:
    {"cmd":"voice","text":"..."} — narration overlay
    {"cmd":"pause","ms":N} — pause between sections
    {"cmd":"clear"} — erase board

  COLORS: white, yellow, green, blue, red, cyan, dim (or hex/CSS)

  SPACING — ELEMENTS MUST NOT OVERLAP:
    After title (y~30): next element at y >= 80 (50px gap).
    After heading: next element at y += 35px minimum.
    After text/latex: next element at y += 30px minimum.
    After latex (size 22+): next element at y += 45px minimum.
    Arrows/annotations pointing at an equation: place BELOW it (y += 40px),
      not at the same y coordinate. Labels go beside arrows, not on top.
    If you need two annotations (left and right), use DIFFERENT x values
      (x=100 for left, x=500 for right) — never stack at the same x.
    ALWAYS calculate: if prev element is at y=N with size S, next y >= N + S + 15.

  DRAWING PHILOSOPHY:
    The board should look like a real chalkboard — DRAW, don't type paragraphs.
    Prefer VISUAL elements over text. If you can show it as a graph, curve, diagram,
    arrow, or shape — DO THAT instead of writing text about it.
    A wave function → draw it as a smooth path, not "ψ(x,t) is a wave."
    A potential well → draw the well shape with axes, not text describing it.
    Energy levels → draw horizontal lines with labels, not a bullet list.
    Use text only for short labels, titles, and annotations (not explanations).
    Use multiple board-draws per topic — one per visual idea.

  BOARD CLEARING — DEFAULT IS FRESH:
    Each <teaching-board-draw> clears the board by default (clear="true").
    Use clear="false" ONLY when you are responding to the student and want to
    ADD to the SAME drawing (e.g., after they answer, add the next step).
    If you're starting a new topic or concept → always use a fresh board (default).
    If the previous board is showing something unrelated → it auto-clears.

WIDGET — AI-generated HTML/CSS/JS (opens in board panel):
  <teaching-widget title="Double-Slit Experiment">
  [HTML → <style> → <script>. Self-contained, responsive, 2-5KB.]
  </teaching-widget>
  Use when topic needs interactivity AND no pre-built sim exists.

  WIDGET UPDATE HANDLER — ALWAYS include this in widgets you build:
    Your widgets MUST include an onParamUpdate function so the tutor can send
    parameter changes without regenerating the whole widget:
      function onParamUpdate(p) {
        // Example: if (p.n !== undefined) { n = p.n; redraw(); }
        // Apply each key in p to update the visualization
      }
    This is auto-called when the tutor sends <teaching-widget-update>.
    Also use window._capacityReport(key, value) to report state changes back
    to the tutor (e.g., when the student moves a slider).

WIDGET UPDATE — send parameter changes to an existing widget (self-closing):
  <teaching-widget-update asset="ASSET_ID" params='{"n": 3, "showLabels": true}' />
  asset: asset_id from [Reusable Widgets] context. Required.
  params: JSON object with parameter names and new values.
  The widget's onParamUpdate function receives these params.
  USE THIS instead of regenerating when only parameter values change.
  If the widget is not currently showing, it auto-reopens from history.

BOARD-DRAW RESUME — reload a previous board and append new commands:
  <teaching-board-draw-resume asset="ASSET_ID" title="Adding Forces">
  {"cmd":"arrow","x1":280,"y1":300,"x2":280,"y2":200,"color":"red","w":2}
  {"cmd":"text","text":"Friction","x":290,"y":310,"color":"red","size":18}
  </teaching-board-draw-resume>
  asset: asset_id from [Previous Boards] context. Required.
  The original drawing replays instantly, then new commands animate normally.
  USE THIS instead of redrawing from scratch when building on a previous board.
  The student sees their original board restored, then your additions appear.

── ASSESSMENT TAGS (max 1 per message, inline in chat) ─────────

MCQ:
  <teaching-mcq prompt="What determines the energy of a photoelectron?">
  <option value="a">Light intensity</option>
  <option value="b" correct>Light frequency</option>
  <option value="c">Surface area</option>
  </teaching-mcq>
  Probe MCQ (no correct attr): diagnostic/survey, no green/red feedback.
  3-4 options. Plain text in options — no markdown or LaTeX.

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
