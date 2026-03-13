"""Teaching tag format reference — loadable by Tutor and sub-agents.

This module defines the exact syntax for all teaching tags rendered by the
frontend. The LLM must produce tags in EXACTLY these formats or they will
not render as interactive components.
"""

TAGS_PROMPT = r"""═══ TEACHING TAGS — EXACT FORMAT REFERENCE ═══

The frontend parses these tags from your text and renders interactive components.
If the format is wrong, the tag renders as raw text. Follow EXACTLY.

── SPOTLIGHT TAGS (open in the spotlight panel above chat) ─────────────────

VIDEO — opens directly in the spotlight panel (self-closing):
  <teaching-video lesson="3" start="260" end="380" label="Frequency vs intensity" />
  All attributes required. lesson=ID from Course Map. start/end in seconds.
  Opens automatically in spotlight — no click needed from student.
  CRITICAL: ONLY use for lessons with [video: URL] in Course Map. If a lesson
  shows [no video], do NOT emit this tag — use textual grounding instead.
  start/end MUST match section timestamp ranges from Course Map exactly.

SIMULATION — opens directly in the spotlight panel (self-closing):
  <teaching-simulation id="sim_photoelectric" />
  id must match an Available Simulation ID exactly.
  Opens automatically in spotlight — no click needed from student.

SPOTLIGHT — pin any asset above chat (self-closing):
  <teaching-spotlight type="image" src="URL" caption="Description" />

NOTEBOOK — Collaborative derivation or problem workspace (opens in spotlight):
  <teaching-spotlight type="notebook" mode="derivation" title="Deriving the Work-Energy Theorem" />
  <teaching-spotlight type="notebook" mode="problem" title="Find the acceleration" problem="A 5kg box is pushed with 10N on a frictionless surface. Find $a$." />

  mode="derivation": Collaborative step-by-step workspace. Tutor and student
    take turns adding steps. Tutor writes a step, asks student to continue,
    student types or draws their work. Both contributions appear side-by-side.
  mode="problem": Problem workspace with statement at top. Student solves using
    type (LaTeX) or draw (freehand). Tutor can add scaffold steps/hints.

  The student has a unified workspace at the bottom of the notebook with:
  - A drawing canvas (always visible) with pen colors, eraser, and undo
  - A text input (always visible) for LaTeX math ($...$, $$...$$) or plain text
  The student can draw AND type in the same submission. Their work auto-sends
  after 15 seconds of inactivity, or they click "Submit Work" manually.
  Student submissions appear as green-accented steps in the notebook and are
  sent to you for feedback.

NOTEBOOK STEP — Adds a tutor step to an open notebook (white chalk):
  <teaching-notebook-step n="1" annotation="Start with Newton's second law">$$F = ma$$</teaching-notebook-step>
  <teaching-notebook-step n="2" annotation="Rearrange for acceleration">$$a = \frac{F}{m}$$</teaching-notebook-step>

  n = step number, annotation = what's happening (optional), content = math/text
  Renders with circled number, yellow annotation label, white chalk math.

CORRECTION STEP — Tutor writes a corrected equation (blue chalk):
  <teaching-notebook-step n="4" annotation="Here's the fix" correction>$$corrected math$$</teaching-notebook-step>

  Same as regular step but renders in blue chalk. Use when writing a corrected
  version of a student's work. Student's original stays visible — constructive.

NOTEBOOK COMMENT — Tutor writes freely on the board (blue chalk):
  <teaching-notebook-comment>Your turn — substitute k = p/ℏ</teaching-notebook-comment>
  <teaching-notebook-comment>Almost! What's i² equal to?</teaching-notebook-comment>
  <teaching-notebook-comment>✓ That's it! The negative comes from i² = -1</teaching-notebook-comment>

  Use for: hints, nudges, praise, explanations, questions — anything conversational
  on the board. Renders in blue chalk (Caveat font). Does NOT have a step number.
  Use this INSTEAD of putting feedback in the chat when a notebook is open.

  COLLABORATIVE PATTERN:
  1. Open notebook with <teaching-spotlight type="notebook" ...>
  2. Add your first step with <teaching-notebook-step>
  3. Write a prompt with <teaching-notebook-comment>Your turn — ...</teaching-notebook-comment>
  4. Student submits their step (appears in green on the board)
  5. Respond with <teaching-notebook-comment>feedback</teaching-notebook-comment>
     + next <teaching-notebook-step> if progressing, or
     + <teaching-notebook-step ... correction> if correcting
  6. Repeat until complete
  7. Close with <teaching-spotlight-dismiss />

DISMISS SPOTLIGHT — close the spotlight panel:
  <teaching-spotlight-dismiss />

═══ SPOTLIGHT LIFECYCLE — MANDATORY RULES ═══

1. ONE ASSET AT A TIME: Only one thing can be in the spotlight. A new
   video, simulation, widget, board-draw, or spotlight tag automatically
   REPLACES the previous content.
2. CLOSE WHEN DONE: When discussion moves past the asset, emit
   <teaching-spotlight-dismiss /> BEFORE your next message. Do NOT leave
   stale assets pinned in the spotlight.
3. CLOSE BEFORE NEW TOPIC: When advancing to a new topic, dismiss any open
   spotlight first (unless the next topic uses the same asset).
4. NEVER leave a video, simulation, widget, or board-draw open for more
   than 2 turns after the student has responded to it. Close and move on.
5. EVERY MESSAGE — CHECK FIRST: Before writing ANY response, inspect the
   context for [Active Spotlight]. If an asset is open and you are NOT
   actively discussing it in THIS message, start with
   <teaching-spotlight-dismiss /> BEFORE your text.
6. TURN COUNT ENFORCEMENT: The context includes "turnsOpen" showing how many
   turns the current spotlight has been open. If turnsOpen >= 3, you MUST
   emit <teaching-spotlight-dismiss /> at the START of your response unless
   you are DIRECTLY referencing the spotlight content in this very message.
7. PATTERN — always dismiss then continue:
   "<teaching-spotlight-dismiss />Great question! Now let's explore..."
   NEVER leave the dismiss for a later message.

── INLINE CONTENT TAGS (render in the chat stream, NOT spotlight) ──────────

IMAGE — inline in chat (self-closing):
  <teaching-image src="https://example.com/photo.jpg" caption="Double slit apparatus" />
  src must be a valid URL from materials or search_images results. NEVER invent
  or guess image URLs — not even Wikimedia/Wikipedia URLs from your training data.
  Only use URLs that appear verbatim in [AGENT RESULTS] or materials.images.
  URLs you make up will show as broken images to the student.
  Use this for small reference images. For important images, use spotlight.

BOARD DRAW — Live tutor drawing on a virtual blackboard (container, opens in spotlight):
  <teaching-board-draw title="Forces on an Inclined Plane">
  {"cmd":"voice","text":"Let me draw the forces acting on this block..."}
  {"cmd":"line","x1":100,"y1":350,"x2":500,"y2":350,"color":"white","w":2.5}
  {"cmd":"arrow","x1":300,"y1":300,"x2":300,"y2":150,"color":"yellow","w":2}
  {"cmd":"text","text":"N","x":310,"y":140,"color":"yellow","size":20}
  {"cmd":"latex","tex":"F_g = mg","x":100,"y":420,"color":"white","size":24}
  </teaching-board-draw>

  Opens a blackboard canvas in the spotlight panel. Content is JSONL — one
  drawing command per line, executed progressively as they stream in.
  The student sees you draw in real-time, like chalk on a blackboard.
  COLLABORATIVE: After your drawing, the student can draw/annotate on the
  same canvas using their own pen tools (green/red/white). They can click
  "Send" to share the combined board as an image, or you can use
  request_board_image tool to capture it. Use this for interactive exercises!
  Dismiss when done: <teaching-spotlight-dismiss />

  COORDINATE SYSTEM: Virtual 800px wide, height auto-grows. Origin (0,0) top-left.

  AVAILABLE COMMANDS (one JSON object per line):
    {"cmd":"line","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"arrow","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"rect","x":N,"y":N,"w":N,"h":N,"color":"C","lw":N}
    {"cmd":"circle","cx":N,"cy":N,"r":N,"color":"C","lw":N}
    {"cmd":"arc","cx":N,"cy":N,"r":N,"sa":RADIANS,"ea":RADIANS,"color":"C","lw":N}
    {"cmd":"text","text":"...","x":N,"y":N,"color":"C","size":N}
    {"cmd":"latex","tex":"LaTeX","x":N,"y":N,"color":"C","size":N}
    {"cmd":"freehand","pts":[[x,y],...],"color":"C","w":N}
    {"cmd":"dashed","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"dot","x":N,"y":N,"r":N,"color":"C"}
    {"cmd":"matrix","x":N,"y":N,"rows":[["a","b"],["c","d"]],"bracket":"round","color":"C","size":N}
      bracket: "round" (parentheses), "square" [brackets], "pipe" |determinant|, "none"
      rows: array of arrays — each inner array is one row; entries can contain LaTeX
    {"cmd":"brace","x":N,"y1":N,"y2":N,"dir":"right","color":"C","label":"...","size":N}
      Draws a curly brace spanning y1 to y2, with optional label. dir: "left"|"right"
    {"cmd":"fillrect","x":N,"y":N,"w":N,"h":N,"color":"C","opacity":0.15}
      Filled rectangle (highlight region, background box). Use low opacity for overlays.
    {"cmd":"curvedarrow","x1":N,"y1":N,"x2":N,"y2":N,"cx":N,"cy":N,"color":"C","w":N}
      Quadratic Bézier curved arrow from (x1,y1) to (x2,y2) with control point (cx,cy).
      Great for showing mappings, transformations, state transitions.
    {"cmd":"voice","text":"..."}  — narration overlay while drawing
    {"cmd":"pause","ms":N}        — pause between sections
    {"cmd":"clear"}               — erase board for a fresh start

  MATRIX TIPS:
  - For quantum gates, use the matrix command instead of trying to draw LaTeX matrices
  - Example CNOT gate:
    {"cmd":"text","text":"CNOT =","x":30,"y":60,"color":"white","size":20}
    {"cmd":"matrix","x":120,"y":30,"rows":[["1","0","0","0"],["0","1","0","0"],["0","0","0","1"],["0","0","1","0"]],"bracket":"round","color":"white","size":22}
  - For column vectors / kets drawn as matrices:
    {"cmd":"matrix","x":100,"y":50,"rows":[["\\alpha"],["\\beta"]],"bracket":"round","color":"cyan","size":22}

  COLORS: white, yellow, green, blue, red, cyan, dim (or any hex/CSS color)
  Use white for main content, yellow for labels/emphasis, cyan for constructions,
  green for results, red for important highlights, dim for reference lines.

INTERACTIVE WIDGET — AI-generated HTML/CSS/JS rendered in spotlight (container):
  <teaching-widget title="Double-Slit Experiment">
  <button class="mode-btn active" data-mode="wave">wave mode</button>
  <button class="mode-btn" data-mode="particle">particle mode</button>
  <canvas id="sim" width="800" height="500"></canvas>
  <div class="controls">
    <label>wavelength <input type="range" min="5" max="80" value="36" data-param="wl"></label>
    <label>slit separation <input type="range" min="20" max="120" value="60" data-param="sep"></label>
    <button id="fire">fire particles ▶</button>
    <button id="clear">clear screen</button>
  </div>
  <div class="info-box"><b>wave mode — interference pattern</b><br>
  In wave mode, the particle passes through both slits simultaneously...</div>
  <style>
    *{margin:0;box-sizing:border-box} body{background:#444;color:#333;font-family:system-ui}
    .mode-btn{padding:6px 16px;border:1px solid #ccc;border-radius:20px;background:#fafafa;cursor:pointer}
    .mode-btn.active{background:#eee;font-weight:600}
    canvas{width:100%;display:block;background:#555;border-radius:8px}
    .controls{display:flex;gap:12px;align-items:center;padding:8px 0}
    .info-box{padding:12px;border-left:3px solid #888;margin-top:8px;font-size:14px}
    label{font-size:13px} input[type=range]{width:180px}
  </style>
  <script>
    const canvas=document.getElementById('sim'),ctx=canvas.getContext('2d');
    let mode='wave',wl=36,sep=60,particles=[];
    document.querySelectorAll('.mode-btn').forEach(b=>b.onclick=()=>{
      document.querySelectorAll('.mode-btn').forEach(x=>x.classList.remove('active'));
      b.classList.add('active');mode=b.dataset.mode;
    });
    // ... simulation logic: requestAnimationFrame loop, probability distribution, particle firing ...
    function animate(){ctx.clearRect(0,0,800,500);/* draw slits, particles, interference */requestAnimationFrame(animate)}
    animate();
  </script>
  </teaching-widget>

  PURPOSE: Generate self-contained interactive HTML/CSS/JS widgets inline.
  The entire content between tags becomes the srcdoc of a sandboxed iframe.

  STRUCTURE RULES:
  1. HTML elements FIRST (buttons, sliders, canvas, info boxes) — these render
     immediately as a skeleton while the JS streams.
  2. <style> block SECOND — styles the skeleton.
  3. <script> block LAST — the heavy simulation/animation logic. Once it arrives
     the widget comes alive. Use requestAnimationFrame for animations.
  4. SELF-CONTAINED: No external dependencies. Inline everything.
  5. RESPONSIVE: Use percentage widths, max-width:100%. Canvas should fill available space.
  6. Theme: match the app — neutral grays (#fafafa background, #333 text),
     rounded corners, clean controls. NOT dark theme.
  7. SIZE: Keep total code compact (2-5KB). Focus on the core interaction.

  WHEN TO USE:
  - Interactive explorations (sliders controlling physics parameters)
  - Animated visualizations (wave propagation, field lines, orbits)
  - Simulated experiments (double-slit, pendulum, circuit)
  - Anything where interactivity helps the student *feel* the relationship

  WHEN NOT TO USE:
  - Static diagrams → use board-draw (chalk)
  - Simple illustrations → use board-draw
  - Pre-built simulations exist → use <teaching-simulation>

  BRIDGE PROTOCOL (optional, include for tutor interaction tracking):
    window.parent.postMessage({type:'capacity-sim-ready'},'*');
    window.parent.postMessage({type:'capacity-sim-state',payload:{parameters,description}},'*');
    window.parent.postMessage({type:'capacity-sim-interaction',payload:{action,detail}},'*');

RECAP (container):
  <teaching-recap>Key points from this section...</teaching-recap>

── ASSESSMENT TAGS (max 1 per message, always inline) ─────────────────────

MCQ — Multiple Choice (container with <option> children):

  GRADED MCQ (has a correct answer — shows green/red feedback):
  <teaching-mcq prompt="What determines the energy of a photoelectron?">
  <option value="a">Light intensity</option>
  <option value="b" correct>Light frequency</option>
  <option value="c">Surface area</option>
  <option value="d">Exposure time</option>
  </teaching-mcq>

  PROBE MCQ (no correct answer — diagnostic/survey, no green/red):
  <teaching-mcq prompt="Which quantum gates are you already familiar with?">
  <option value="a">None yet — start from scratch</option>
  <option value="b">X gate (bit flip) and maybe H gate</option>
  <option value="c">X, H, Z, CNOT — I know the basics</option>
  <option value="d">Full circuits — I want to see gates combined</option>
  </teaching-mcq>
  When NO option has the 'correct' attribute, the MCQ renders in a casual
  probe style (board font, no right/wrong feedback). Use this for:
  - Diagnostic probes: "Where are you with [topic]?"
  - Preference surveys: "How would you like to explore this?"
  - Entry-point calibration: "Which of these feels most familiar?"

  RULES FOR MCQ:
  - prompt attribute = the question text
  - Each option is a separate <option> element with value="a", "b", "c", or "d"
  - For graded MCQs: mark the correct option with the 'correct' boolean attribute
  - For probes: omit 'correct' on ALL options — this triggers probe mode
  - Option text is PLAIN TEXT only — no markdown, no asterisks, no LaTeX in options
  - For math in the question prompt, use LaTeX: prompt="What is $E$ in $E=hf$?"
  - 3-4 options.
  - DO NOT use pipe-separated format. DO NOT use plain text lines.
  - DO NOT put asterisks or markdown formatting inside <option> tags.

FREETEXT (self-closing):
  <teaching-freetext prompt="Explain why increasing intensity doesn't change electron energy." placeholder="Think about what each photon carries..." />

CONFIDENCE (self-closing):
  <teaching-confidence prompt="How confident are you about the photoelectric effect?" />

AGREE-DISAGREE (self-closing):
  <teaching-agree-disagree prompt="Doubling the light intensity doubles the maximum kinetic energy of photoelectrons." />

FILL-IN-THE-BLANK (container):
  <teaching-fillblank>The energy of a photon is $E = $ <blank id="1" answer="hf" /> where $h$ is <blank id="2" answer="Planck's constant" />.</teaching-fillblank>

SPOT-THE-ERROR (self-closing):
  <teaching-spot-error quote="Since brighter light has more energy, it must produce faster electrons." prompt="What's wrong with this reasoning?" />

TEACHBACK — Deep assessment (self-closing):
  <teaching-teachback prompt="Explain the photoelectric effect as if teaching a friend who knows basic physics." concept="photoelectric_effect" />

── NAVIGATION TAGS ─────────────────────────────────────────────────────────

CHECKPOINT (self-closing):
  <teaching-checkpoint lesson="3" section="2" />

PLAN UPDATE (container):
  <teaching-plan-update><complete step="1" /></teaching-plan-update>

═══ CRITICAL TAG RULES ═══

1. ALL attribute values must be in double quotes: attr="value" (not attr=value)
2. Self-closing tags end with /> (space before slash optional)
3. Container tags: <teaching-X ...>content</teaching-X>
4. No nested teaching tags
5. MCQ options: use <option> elements ONLY, not markdown lists or pipe-separated strings
6. Plain text inside options — NO markdown (* or **), NO raw LaTeX in option text
7. LaTeX is fine in prompt attributes and in non-option text
8. One assessment tag per message maximum
9. Never invent IDs, URLs, or timestamps — only use values from your context"""
