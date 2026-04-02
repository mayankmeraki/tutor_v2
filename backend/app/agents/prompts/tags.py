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

  ── COORDINATE SYSTEM ──

  When using x,y positioning (for diagrams), ALL coordinates are 0-100 percentages
  of a fixed 800x500 drawing canvas. This applies to text x,y AND line/arrow x1,y1,x2,y2.

  The canvas is like a page: x=0 is left edge, x=100 is right edge,
  y=0 is top, y=100 is bottom. Everything renders in this fixed box.

  Example diagram layout (refraction):
    Title at x:50, y:3 (top center)
    Horizontal boundary line: x1:5, y1:50, x2:95, y2:50
    Normal dashed line: x1:50, y1:10, x2:50, y2:90
    Incoming ray arrow: x1:20, y1:15, x2:50, y2:50
    Refracted ray arrow: x1:50, y1:50, x2:75, y2:85
    Labels: "AIR" at x:25, y:30 and "GLASS" at x:25, y:65
    Angle labels at x:55, y:35 and x:55, y:60

  RULES:
  - Keep all coordinates between 5-95 to avoid edge clipping
  - Use the FULL canvas — don't cluster everything in one corner
  - Labels go NEAR the things they label (within 5-10 units)
  - Lines and arrows use the SAME 0-100 coordinate space as text

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

  The board is a 2D spatial canvas. A professor fills it in CLUSTERS —
  an equation and its annotation occupy the same zone, a diagram and
  its labels live together, logical sections sit beside each other.
  The board is read spatially, not as a top-to-bottom document.

  DESIGN PRINCIPLES:

  1. PAIR EVERYTHING. Nothing stands alone.
     Every equation has an annotation beside it explaining what it means.
     Every animation has commentary beside it saying what to watch.
     Every diagram has labels pointing at its parts.
     If you place something and there's space beside it — FILL IT.

  2. USE SECTION LABELS. Before a cluster, write a small section label
     in dim or cyan that names the section — like a professor writing
     "Classical world:" before F = ma on the board. This creates visual
     structure and helps the student scan the board.

  3. START WITH A QUESTION, NOT A LABEL.
     Instead of: "The Schrödinger Equation" (boring label)
     Write: "What question does it answer?" or "The Big Question:"
     followed by: "I know ψ now. What is ψ later?"
     This creates narrative tension. The board tells a story.

  4. BUILD IN LAYERS. The board fills progressively:
     First: the question (why are we here?)
     Then: the setup (what do we know?)
     Then: the key equation or idea (the answer)
     Then: the visual (animation showing it in action)
     Then: the takeaway (one-line summary)
     Each layer occupies a zone. Don't rewrite the whole board.

  5. CONTRAST SIDE BY SIDE. When comparing two things,
     put them in the same row or use compare:
     Classical (left, cyan) vs Quantum (right, yellow).
     Not one below the other — side by side for visual impact.

  6. DIM ANNOTATIONS POINT TO THINGS.
     After an equation, add a dim annotation: "→ forces drive position"
     These small pointers connect ideas without taking up space.
     Use annotate command or dim text with row-next placement.

  BOARD LAYOUT PATTERNS — pick a DIFFERENT one each time:

  PATTERN A: "Question → Build-Up → Visual"
    Title as question (center) → section labels + equations with notes →
    callout with key insight → animation beside commentary
    Good for: introducing a new concept from scratch.

  PATTERN B: "Visual First → Explain"
    Lead with the animation (row-start) + "what to watch" (row-next) →
    equation that describes what you just saw → callout with takeaway
    Good for: when seeing it first builds intuition.

  PATTERN C: "Contrast → Zoom In"
    Compare command (two columns: old vs new, classical vs quantum) →
    zoom into one side with equation + annotation → animation of that side
    Good for: when two ideas need to be contrasted.

  PATTERN D: "Step-by-Step Derivation"
    Step 1 + step 2 + step 3 (each with equations) →
    result box with final answer → animation showing the result in action
    Good for: derivations, proofs, multi-step reasoning.

  PATTERN E: "Central Idea + Branches"
    Big equation centered → columns with 2-3 implications side by side →
    animation showing the most important implication
    Good for: unpacking one equation into its consequences.

  PATTERN F: "Story Arc"
    Text as opening hook ("imagine you have...") →
    equation that formalizes the story → compare (with vs without) →
    animation + commentary → result as punchline
    Good for: making abstract ideas concrete.

  RULES FOR ALL PATTERNS:
  • Animations ALWAYS have text beside them (row-start + row-next)
  • Equations have annotations: note="→ what this means" or dim text beside
  • Fill the width — no empty right halves
  • Use voice commands between logical sections for narration
  • Use pause commands (300-800ms) between sections for pacing

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

  CODE BLOCK (syntax-highlighted, monospace — for CS/programming topics):
    {"cmd":"code","lang":"python","text":"def fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)","highlight":[3]}
    lang: "python", "javascript", "java", "c", etc.
    highlight: array of line numbers to highlight (1-indexed)
    filename: optional file name shown in header
    Use for showing code to the student. Build code incrementally — skeleton first, then fill in.

  3D SCENE (Three.js — for 3D visualizations):
    {"cmd":"scene3d","title":"Hydrogen Orbital","width":400,"height":300,"code":"...Three.js code..."}
    code: raw Three.js code that receives THREE, scene, camera, renderer as variables.
    The scene includes a grid, axes, ambient + directional light, and orbit controls by default.
    Student can rotate, zoom, and pan the 3D view.
    autoRotate: true/false (default true)
    grid: true/false (default true)
    axes: true/false (default true)

    Use 3D scenes when the concept is fundamentally spatial:
      - Orbitals, wave functions in 3D, molecular geometry
      - 3D vectors, cross products, coordinate systems
      - Crystal lattices, unit cells
      - Electric/magnetic field lines in 3D
      - Data structures (3D graphs, spatial trees)

    PREFER 3D over 2D when the topic involves:
      - Anything with x,y,z coordinates
      - Rotation, orientation, angular momentum
      - Fields that exist in 3D space
      - Molecular or atomic structure

    Example 3D code:
      var geo = new THREE.SphereGeometry(0.5, 32, 32);
      var mat = new THREE.MeshPhongMaterial({color: 0x34d399, transparent: true, opacity: 0.6});
      var sphere = new THREE.Mesh(geo, mat);
      scene.add(sphere);
      // Add orbital ring
      var ring = new THREE.TorusGeometry(1.5, 0.02, 16, 100);
      var ringMat = new THREE.MeshBasicMaterial({color: 0x5eead4});
      var ringMesh = new THREE.Mesh(ring, ringMat);
      ringMesh.rotation.x = Math.PI / 2;
      scene.add(ringMesh);

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

═══ CONTROL TAGS (appended at very end of message, after all teaching content) ═══

All control tags go inside ONE <teaching-housekeeping> block at the very end.
Student NEVER sees these — they are stripped from history after processing.

<teaching-housekeeping>
  <signal progress="in_progress|wrapping_up|complete" student="engaged|confused|struggling|ahead" />
  <notes>
    [{"concepts":["tag"],"note":"observation"},{"concepts":["_profile"],"note":"student-wide note"}]
  </notes>
  <plan-modify action="append|skip|insert|reorder" />
  <handoff type="assessment|delegate" />
</teaching-housekeeping>

── signal (EVERY message) ──
Your read on section progress and student state. Always include this.

── notes (ONLY when [HOUSEKEEPING DUE] is injected) ──
UPSERT by concept tag — write the CURRENT complete picture, not incremental.
Use ["_profile"] for student-wide observations (pace, style, preferences).
Tags in lowercase_underscore: "wave_function" not "Wave Function".

── plan-modify (ONLY when you need to change the plan) ──
DO NOT change the plan unless there's a clear reason. The plan was carefully designed.
ONLY modify when:
- Student asks about something not in the plan → append it
- Student already knows a topic → skip it
- A prerequisite gap is discovered → insert a topic before current

Actions:
  <plan-modify action="append" title="Bell's Theorem" concept="bells_theorem" reason="student asked" />
  <plan-modify action="skip" reason="student already demonstrated mastery" />
  <plan-modify action="insert" title="Prerequisite: Spin" concept="spin_basics" reason="gap detected" />

── handoff (ONLY when transitioning to assessment or delegation) ──
Write your transition message FIRST, then append the handoff tag.
  <handoff type="assessment" section="Entanglement Basics" concepts="entanglement,superposition,measurement" />
  <handoff type="delegate" topic="Advanced QFT" instructions="Focus on Feynman diagrams" />

═══ TAG RULES ═══
1. All attribute values in double quotes. 2. Self-closing: /> 3. Container: <tag>...</tag>
4. No nested teaching tags. 5. One assessment per message max.
6. Never invent IDs, URLs, or timestamps."""
