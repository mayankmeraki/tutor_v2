"""Voice mode board layout, cursor rules, and annotations.

Controls how content is positioned on the full-screen board,
how the hand cursor follows elements, and ephemeral annotations.
"""

VOICE_BOARD_RULES = r"""
═══ BOARD — WRITE LIKE A REAL TEACHER ═══

Study how MIT professors use a chalkboard:
- Content SCATTERED across the full width, not in a single column
- Equations on the LEFT, plain-English meaning on the RIGHT
- Diagrams and animations BESIDE related equations, not above/below them
- Key results BOXED, with derivation leading up to them
- The board BUILDS incrementally — each beat adds to the picture

The board is a chalkboard, not a slide deck. Think LANDSCAPE, not PORTRAIT.
The right half of the board should NEVER be empty.

POSITIONING:

Add "x" and "y" to draw commands to place them spatially (0-100 = % of board):
  "x":5, "y":20   → left side, 20% down
  "x":55, "y":20  → right side, same height

Or use flow placements:
  "below"       — next line (DEFAULT — omit for normal flow)
  "center"      — centered (titles only)
  "row-start"   — start side-by-side pair
  "row-next"    — second item in pair

SPATIAL GRID — THE BOARD IS 100x100. RESPECT THESE ZONES:

  The board is divided into a logical grid. Use these reference points:

  LEFT COLUMN:   x: 3-45    (equations, steps, main content)
  RIGHT COLUMN:  x: 52-95   (meaning, notes, secondary content)
  TOP BAND:      y: 2-15    (title + subtitle only)
  MAIN AREA:     y: 18-75   (all teaching content)
  BOTTOM BAND:   y: 78-95   (results, conclusions, key takeaways)

  MINIMUM SPACING between elements:
  - Vertically: at least 10 units apart (e.g. y:20 then y:30, never y:20 then y:23)
  - Horizontally: left column (x:3-45) and right column (x:52-95) never overlap
  - Elements at the SAME y-level should differ by at most 3 in y (treat as same row)

  SAFE COORDINATE PAIRS (use these as defaults):
  Row 1: y:18  (left: x:3,  right: x:55)
  Row 2: y:30  (left: x:3,  right: x:55)
  Row 3: y:42  (left: x:3,  right: x:55)
  Row 4: y:54  (left: x:3,  right: x:55)
  Row 5: y:66  (left: x:3,  right: x:55)
  Result: y:80  (centered: x:20)

CRITICAL RULES:
  - NEVER split one equation into multiple positioned pieces. Use cmd:"equation"
    which automatically places equation LEFT + note RIGHT in one element.
  - Use x,y to position DIFFERENT concepts relative to each other — NOT to
    arrange parts of the same expression.
  - GOOD: equation at x:3,y:18 and a separate callout at x:3,y:30
  - BAD:  "iℏ∂ψ/∂t" at x:5, "=" at x:40, "Ĥψ" at x:55 (split equation!)
  - Elements are placed EXACTLY where you put them — there is NO automatic
    repositioning. If you place two elements at the same x,y they WILL overlap.
    YOU are responsible for spacing.

CONNECTION ARROWS (draw relationships):
  {"cmd":"connect","from":"eq1","to":"eq2","label":"implies","color":"gold"}
  Draws an arrow between elements. Use to show derivation flow.

EVERY element MUST have an "id" for {ref:} and connections.

═══ COMPOUND COMMANDS — USE THESE INSTEAD OF RAW TEXT ═══

Compound commands produce richer visuals with fewer tokens. They handle
layout, annotation, and hierarchy internally. PREFER THESE over cmd:"text".

1. EQUATION — auto-annotated equation (replaces text+beside pattern):
   {"cmd":"equation","text":"\\hat{H}\\psi = E\\psi","note":"eigenvalue equation","placement":"below","color":"cyan","size":"text","id":"eq1"}
   → renders equation with KaTeX LEFT, scribbles "← eigenvalue equation" to its right.
   EVERY equation should use this. The note is mandatory for teaching.
   IMPORTANT: Use LaTeX notation for equations, NOT Unicode symbols.
   GOOD: "\\frac{\\partial^2 \\psi}{\\partial x^2}" — renders as proper math
   BAD: "∂²ψ/∂x²" — renders as flat text, hard to read
   Use \\frac{}{} for fractions, ^{} for superscripts, _{} for subscripts,
   \\partial, \\psi, \\hbar, \\nabla, \\int, \\sum, etc.

3. STEP — numbered step in a sequence:
   {"cmd":"step","n":1,"text":"Write the unperturbed equation","placement":"below","id":"s1"}
   → circled number + text. Use for derivations, procedures, algorithms.

4. CHECK / CROSS — right/wrong, true/false, property list:
   {"cmd":"check","text":"Unitary: preserves norm","placement":"below","id":"c1"}
   {"cmd":"cross","text":"NOT reversible after measurement","placement":"below","id":"c2"}
   → green ✓ or red ✗ prefix. Use for property lists, misconception correction.

5. CALLOUT — bordered emphasis block:
   {"cmd":"callout","text":"Key insight: energy is quantized","placement":"below","color":"gold","id":"key1"}
   → left accent border + emphasized text. Use for takeaways, warnings, key points.

7. LIST — bulleted, numbered, or check-marked list:
   {"cmd":"list","items":["Linear","Hermitian","Unitary"],"style":"bullet","placement":"below","color":"white","id":"props"}
   → styles: "bullet" (•), "number" (1. 2. 3.), "check" (✓)

8. DIVIDER — section separator:
   {"cmd":"divider","placement":"below"}
   → subtle line across the board. Use between topic sections.

9. MERMAID — diagrams using Mermaid syntax (flowcharts, state diagrams, sequences):
   {"cmd":"mermaid","id":"flow","title":"Perturbation Flow","code":"graph LR\n  A[Ĥ₀ψ = Eψ] -->|add λV| B[Full Ĥ]\n  B -->|expand| C[First Order]\n  C -->|calculate| D[Energy Shift]"}
   → Auto-rendered diagram with dark theme and Caveat font.
   USE FOR: derivation flows, concept maps, decision trees, state transitions.
   The LLM knows Mermaid syntax — use graph, flowchart, stateDiagram, sequenceDiagram.

10. CONNECT — draw an arrow between ANY two elements:
    {"cmd":"connect","from":"eq1","to":"eq2","label":"implies","color":"gold"}
    → SVG arrow with optional label. Shows relationships on the board.

═══ WHEN TO USE ANIMATION vs POSITIONED TEXT ═══

USE cmd:"animation" (p5.js sketch) FOR:
  - Physics diagrams: ray diagrams, force diagrams, circuits, wave patterns
  - Geometric figures: triangles, circles, coordinate systems, graphs
  - Anything that needs LINES AT ANGLES, RAYS, or GEOMETRIC SHAPES
  - Diagrams where spatial relationships ARE the content (reflection, refraction,
    projectile motion, electric fields, molecular structures)

  These CANNOT be built from positioned text elements. Text + arrows cannot
  represent angled lines, curves, or geometric relationships. Use a p5.js
  animation that draws the actual geometry with proper coordinates, angles,
  and labels built into the sketch.

  Example — Total Internal Reflection (CORRECT):
  <vb draw='{"cmd":"animation","id":"tir","title":"Total Internal Reflection","code":"function setup(){createCanvas(700,400);noLoop()}function draw(){background(30,35,50);fill(100,180,255,40);noStroke();rect(0,0,700,200);fill(30,35,50,40);rect(0,200,700,200);stroke(255,255,255,60);strokeWeight(1);setLineDash([6,4]);line(350,30,350,370);setLineDash([]);stroke(255);strokeWeight(2);line(0,200,700,200);stroke(52,211,153);strokeWeight(2);line(200,50,350,200);stroke(251,191,36);line(350,200,500,50);push();noStroke();fill(52,211,153);textSize(14);textFont(\"Caveat\");text(\"incident\",220,100);fill(251,191,36);text(\"reflected\",420,100);fill(150,180,255);textSize(16);text(\"GLASS (n₁ = 1.5)\",50,120);fill(200);text(\"AIR (n₂ = 1.0)\",50,280);fill(255,107,107);text(\"✗ No refracted ray\",50,340);pop()}","legend":[{"text":"incident","color":"#34d399"},{"text":"reflected","color":"#fbbf24"}]}' />

  WRONG approach: placing "GLASS", "AIR", arrows, lines as separate positioned
  text elements with x,y — they scatter and cannot form coherent geometric shapes.

USE POSITIONED TEXT (x,y) FOR:
  - Equation layouts: equation left, meaning right
  - Concept maps: ideas scattered across board with connect arrows
  - Derivation flows: step-by-step with arrows between equations
  - Comparison layouts: two columns of related concepts

═══ ANTI-PATTERNS (NEVER DO THESE) ═══

❌ ANTI-PATTERN 1: THE CENTERED COLUMN
  Everything centered, single column, no annotations. This is PowerPoint, not a board:
  <vb draw='{"cmd":"text","text":"Title","placement":"center","size":"h1",...}' />
  <vb draw='{"cmd":"text","text":"equation 1","placement":"center",...}' />
  <vb draw='{"cmd":"text","text":"explanation","placement":"center",...}' />
  <vb draw='{"cmd":"text","text":"equation 2","placement":"center",...}' />

❌ ANTI-PATTERN 2: THE WATERFALL
  Everything stacked vertically with "below", right half completely empty:
  <vb draw='...' placement="below" />
  <vb draw='...' placement="below" />
  <vb draw='...' placement="below" />
  <vb draw='...' placement="below" />
  <vb draw='...' placement="below" />
  This wastes half the board. SPREAD content across both halves with row-start/row-next.

═══ LAYOUT PATTERNS — HOW REAL TEACHERS USE BOARDS ═══

⚠️ THE #1 RULE: USE x,y TO SCATTER CONTENT LIKE A REAL BOARD
Don't stack everything vertically. Place equation LEFT (x:5), meaning RIGHT (x:55),
diagram CENTER (x:25), result BOTTOM (y:80). Connect with arrows.

PATTERN 1 — Equation left + meaning right (SPATIAL):
  <vb draw='{"cmd":"equation","text":"iℏ ∂ψ/∂t = Ĥψ","note":"energy → time","x":3,"y":15,"color":"#53d8fb","id":"se"}' say="The Schrödinger equation." />
  <vb draw='{"cmd":"text","text":"Energy tells ψ how to evolve","x":55,"y":17,"size":"text","color":"#e2e8f0","id":"meaning"}' say="Energy drives evolution." />
  <vb draw='{"cmd":"connect","from":"se","to":"meaning","label":"means"}' />

PATTERN 2 — Derivation flow with arrows:
  <vb draw='{"cmd":"equation","text":"Ĥ₀ψ = Eψ","note":"known","x":3,"y":15,"color":"#53d8fb","id":"start"}' />
  <vb draw='{"cmd":"text","text":"Add perturbation λV","x":55,"y":15,"color":"#fbbf24","id":"step2"}' />
  <vb draw='{"cmd":"connect","from":"start","to":"step2","label":"then","color":"gold"}' />
  <vb draw='{"cmd":"result","text":"Eₙ ≈ Eₙ⁰ + λ⟨n|V|n⟩","label":"Result","x":20,"y":50,"color":"gold","id":"result"}' />
  <vb draw='{"cmd":"connect","from":"step2","to":"result","label":"gives"}' />

PATTERN 2 — Scatter-write across the top (TOPIC OVERVIEW):
  Like a professor writing three related keywords across the full board width
  before diving into any of them:
  <vb draw='{"cmd":"text","text":"1) Linearity","placement":"row-start","size":"h2","color":"#fbbf24","id":"lin"}' say="First: linearity." />
  <vb draw='{"cmd":"text","text":"EOM","placement":"row-next","size":"h2","color":"#fbbf24","id":"eom"}' say="Second: equations of motion." />
  <vb draw='{"cmd":"text","text":"dynamical variables","placement":"row-next","size":"h2","color":"#fbbf24","id":"dyn"}' say="Third: dynamical variables." />

PATTERN 3 — Animation figure (SELF-CONTAINED with title + legend):
  ONE command creates a complete figure — title, canvas, and color legend:
  <vb draw='{"cmd":"animation","id":"diagram","title":"Complex Plane","code":"...","legend":[{"text":"Re(z)","color":"#34d399"},{"text":"Im(z)","color":"#fbbf24"}]}' say="Here's the complex plane." />

PATTERN 3b — Animation + beat-synced narration (BEST for explained animations):
  When an animation needs explanation, use cmd:"figure" instead of
  cmd:"animation". It creates a wide row: animation on the LEFT (~58%),
  a narration column on the RIGHT (~42%). The narration column fills up
  ONE KEY POINT AT A TIME, in sync with the beats of the animation, as
  if you were breaking the figure down piece by piece.

  ─── THE STRUCTURE: KEY POINTS, BEAT BY BEAT ───

  Don't dump a single paragraph. Don't write a list of property labels
  either. Instead: as the animation unfolds across multiple beats, each
  beat writes ONE short key point into the column capturing the MEANING
  of what the animation is showing right now.

  Think of it like a teacher explaining a diagram with chalk in one hand
  and pointing at the figure with the other. Each pointing gesture
  comes with one key insight, written down beside the figure.

  The pattern:
    Beat 1: figure command — animation appears, you say what we're looking at
    Beat 2: narration → key point about FIRST element of the figure
    Beat 3: narration → key point about SECOND element / interaction
    Beat 4: narration → key point about WHY this matters / mechanism
    Beat 5: narration → key point about the consequence / takeaway
    (3 to 6 narration beats — one per concept the figure illustrates)

  ─── WHAT EACH KEY POINT SHOULD BE ───

  Each narration line is ONE short sentence (≤ ~80 chars) capturing the
  MEANING of one moment in the figure — not a label of what's drawn.

  GOOD — beat-by-beat key points (each one is a takeaway):
    Beat 1 (point particle appears in animation):
      "A point has zero extent — all the energy lives at one location."
    Beat 2 (energy rings expand around the point):
      "Quantum field theory then makes self-energy calculations diverge."
    Beat 3 (string appears beside it):
      "Replace the point with a tiny string — now there\u2019s actual length."
    Beat 4 (energy spreads along the string):
      "The same energy is smeared along the loop. No single hot point."
    Beat 5 (callout — the takeaway):
      "That extension is why string theory stays finite."

  BAD — property labels mirroring what's drawn:
    "Point particle = zero size"
    "Zoom in → energy blows up to ∞"
    "String = tiny loop with actual SIZE"
    "Energy smeared out → stays finite"
  These are facts the student already SEES in the animation. Repeating
  them as labels adds nothing. Key points should add the WHY/MECHANISM,
  not re-describe the visual.

  Difference in one line:
    LABEL describes what the student is looking at.
    KEY POINT explains what the student should understand from it.

  ─── HOW TO WRITE INTO THE NARRATION COLUMN ───

  Use ONLY cmd:"text" with placement="figure:<figure-id>". Each text
  becomes ONE bullet point in the column. The renderer auto-applies a
  uniform 15px font and a bullet marker — every line looks the same.

  DO NOT use:
    ✗ cmd:"callout"   — visually dominates the column, breaks uniformity
    ✗ size:"h3" / "h2" — overridden anyway; no headings inside the column
    ✗ size:"small"    — overridden; everything is the same size
    ✗ Mixed commands  — keep it pure cmd:"text" for the bulleted feel

  The ONLY thing you change between key points is `color`:
    • white  (#e2e8f0) — neutral / setup / mechanism
    • red    (#ff6b6b) — what goes wrong
    • green  (#34d399) — the fix / conclusion
    • gold   (#fbbf24) — the takeaway (ONE per figure, at the end)

  ─── RULES ───
    - cmd:"figure" REQUIRES an "id"
    - Use placement="figure:<id>" on cmd:"text" (cmd:"narrate" is an alias)
    - 3 to 6 bullets total — one per animation beat / one per concept
    - Each bullet ≤ ~80 chars — one short sentence capturing the MEANING
    - DO NOT mirror animation labels — those are already on screen
    - DO NOT use callouts, headings, or lists inside the narration column
    - Color the LAST bullet gold to mark the takeaway
    - The full spoken sentence goes in `say`; the bullet gets the
      tightened key-point version of the same thing

  ─── EXAMPLE — Why strings fix infinities ───
  <vb draw='{"cmd":"figure","id":"strings","title":"Point vs String","code":"function setup(){createCanvas(560,400);noLoop()}function draw(){background(0,0);noStroke();fill(251,191,36);ellipse(170,200,12);fill(251,191,36,180);textSize(13);textAlign(CENTER);text(\"Point Particle\",170,235);noFill();stroke(255,107,107,140);strokeWeight(1);for(let r=20;r<140;r+=22){ellipse(170,200,r*2)}fill(255,107,107);noStroke();text(\"Energy → ∞\",170,55);stroke(52,211,153,200);strokeWeight(2.5);noFill();beginShape();vertex(380,180);bezierVertex(360,160,340,200,360,225);bezierVertex(380,250,420,235,420,205);bezierVertex(420,180,400,160,380,180);endShape();fill(52,211,153);noStroke();text(\"Closed String\",390,260);text(\"Energy spread out\",390,140)}","legend":[{"text":"Point → diverges","color":"#fbbf24"},{"text":"String → finite","color":"#34d399"}]}'
      say="Look at this. A point particle on the left, a tiny closed string on the right." />
  <vb draw='{"cmd":"text","text":"A point has zero extent — all its energy lives at one location.","placement":"figure:strings","color":"#e2e8f0"}'
      say="The point has zero size, so all the energy is packed into one location." />
  <vb draw='{"cmd":"text","text":"Self-energy then diverges — the math blows up to infinity.","placement":"figure:strings","color":"#ff6b6b"}'
      say="Calculate the self-energy and the math diverges. You get infinity." />
  <vb draw='{"cmd":"text","text":"Replace the point with a string and you give it actual length.","placement":"figure:strings","color":"#e2e8f0"}'
      say="Now replace the point with a string — a tiny loop with real length." />
  <vb draw='{"cmd":"text","text":"Energy spreads along the loop. No single point to concentrate at.","placement":"figure:strings","color":"#34d399"}'
      say="The same energy is smeared along the loop. There\u2019s no single point for it to concentrate at." />
  <vb draw='{"cmd":"text","text":"That extension is why string theory stays finite.","placement":"figure:strings","color":"#fbbf24"}'
      say="And that extension — that little bit of length — is the reason string theory is finite where particle physics blows up." />

  Notice how the column reads top-to-bottom as a natural breakdown:
  what the figure shows → what goes wrong → what the fix is →
  why the fix works → the takeaway. Five short key points instead of
  five property labels. The student can re-read it later and understand
  the figure WITHOUT having to replay the animation.

  ─── WHEN TO USE figure vs animation ───
    - One-shot diagram, no explanation needed → cmd:"animation"
    - Animation you'll break down across 3+ beats → cmd:"figure" + key points
    - Animation where the explanation IS the lesson → cmd:"figure"

PATTERN 4 — Derivation chain → callout takeaway (THE BUILD-UP):
  Like a professor building from axiom to theorem, then putting the conclusion
  in a callout. Each step adds to the derivation, ending with the takeaway:
  <vb draw='{"cmd":"equation","text":"L(αu₁ + βu₂)","note":"apply the operator","placement":"below","color":"#53d8fb","id":"d1"}' say="Apply L to a linear combination." />
  <vb draw='{"cmd":"equation","text":"= L(αu₁) + L(βu₂) = αLu₁ + βLu₂","note":"linearity!","placement":"below","color":"#53d8fb","id":"d2"}' say="Linearity lets us split it." />
  <vb draw='{"cmd":"callout","text":"L is linear: L(αu + βv) = αLu + βLv","placement":"below","color":"gold","id":"def-lin"}' say="This is THE definition of a linear operator. {ref:def-lin}" />

PATTERN 5 — Concrete example left + abstract equation right:
  Like showing a specific numerical example on the left and the general formula
  on the right, so the student sees both the trees and the forest:
  <vb draw='{"cmd":"text","text":"Example: n=3","placement":"row-start","size":"h3","color":"#34d399","id":"ex-title"}' say="Let's try n equals three." />
  <vb draw='{"cmd":"text","text":"General formula","placement":"row-next","size":"h3","color":"#fbbf24","id":"gen-title"}' say="And the general case." />
  <vb draw='{"cmd":"equation","text":"E₃ = 9π²ℏ²/2mL²","note":"≈ 3.4 eV","placement":"row-start","color":"#34d399","id":"ex-val"}' say="E three is nine times the ground state." />
  <vb draw='{"cmd":"equation","text":"Eₙ = n²π²ℏ²/2mL²","note":"grows as n²","placement":"row-next","color":"#fbbf24","id":"gen-eq"}' say="In general, energy goes as n squared. {ref:gen-eq}" />

PATTERN 6 — Steps left + results right (PROCEDURE):
  <vb draw='{"cmd":"step","n":1,"text":"Write the equation","placement":"row-start","id":"s1"}' say="Step one." />
  <vb draw='{"cmd":"equation","text":"Ĥ₀|n⟩ = Eₙ|n⟩","note":"known","placement":"row-next","color":"#53d8fb","id":"s1r"}' say="Start with the unperturbed system." />
  <vb draw='{"cmd":"step","n":2,"text":"Add perturbation","placement":"row-start","id":"s2"}' say="Step two." />
  <vb draw='{"cmd":"equation","text":"Ĥ = Ĥ₀ + λV","note":"λ ≪ 1","placement":"row-next","color":"#34d399","id":"s2r"}' say="Add a small perturbation." />

PATTERN 7 — Properties in two columns:
  <vb draw='{"cmd":"check","text":"Hermitian","placement":"row-start","id":"p1"}' say="It's Hermitian." />
  <vb draw='{"cmd":"text","text":"→ real eigenvalues (measurable)","placement":"row-next","size":"small","color":"#94a3b8"}' say="So eigenvalues are real." />
  <vb draw='{"cmd":"check","text":"Linear","placement":"row-start","id":"p2"}' say="It's linear." />
  <vb draw='{"cmd":"text","text":"→ superposition works","placement":"row-next","size":"small","color":"#94a3b8"}' say="So superposition applies." />

PATTERN 8 — Animation beside equation (VISUAL + MATH):
  Animation in row-start, equation explanation in row-next — side-by-side:
  <vb draw='{"cmd":"animation","placement":"row-start","id":"anim","title":"Energy Levels","code":"...","legend":[{"text":"n=1","color":"#34d399"},{"text":"n=2","color":"#fbbf24"}]}' say="Watch the energy levels." />
  <vb draw='{"cmd":"equation","text":"Eₙ = n²π²ℏ²/2mL²","note":"grows as n²","placement":"row-next","color":"#fbbf24","id":"eq"}' say="Energy goes as n squared." />

═══ BOARD RULES ═══

1. CENTER sparingly. ONLY the h1 title. Everything else uses below or
   row-start/row-next. If you center more than 1 element, you're wrong.

2. EVERY equation uses cmd:"equation" with a "note". Never orphan an equation.
   Raw cmd:"text" for equations is WRONG — use cmd:"equation" so annotations
   are automatic.

3. Use FULL WIDTH. Count your row-start/row-next uses. If you have fewer than 2
   row pairs per scene, you're wasting space. Spread equations left, meaning right.

4. VARY commands. A good scene mixes: text → equation → step → callout → check/cross.
   Monotone scenes (all "text" commands) are bad. Use at least 3 different
   command types per scene.

5. VISUAL RICHNESS per scene. A good scene has:
   - 1 title (h1, centered)
   - 2-3 equations (with notes)
   - 1 callout (the takeaway / key conclusion)
   - Steps OR check/cross list
   - 1 animation when the concept involves motion/change/3D

6. END with a takeaway. Every derivation should finish with a cmd:"callout"
   stating the key conclusion in plain language. Don't let the final
   equation blend in — give it a callout so the student knows it's THE point.

7. BUILD incrementally. Don't dump 5 equations at once. Write one, explain it,
   then build the next from it. Each beat adds ONE thing to the board.

8. Color carries meaning:
   Gold (#fbbf24) — titles, key results, callouts
   Green (#34d399) — correct, results, checks, specific examples
   Cyan (#53d8fb) — equations, secondary content
   Red (#ff6b6b) — wrong, warnings, crosses
   Dim (#94a3b8) — annotations, notes (auto-applied by equation's note)
   White (#e2e8f0) — explanatory text

FONT SIZES:
  "h1" — title (ONE per scene, centered)
  "h2" — subtopic heading (left-aligned)
  "text" — equations, content (bulk of writing)
  "small" — annotations, labels
  "label" — tiny captions

CURSOR — uses element IDs:
  cursor="write" — follows current draw
  cursor="tap:id:X" — taps element (pulse)
  cursor="rest" — hidden

ANNOTATIONS — teacher circling on the board:
  annotate="circle:id:eq1" — circles it
  annotate="underline:id:eq1" — underlines it
"""
