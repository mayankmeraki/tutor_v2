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

2. COMPARE — side-by-side two-column contrast:
   {"cmd":"compare","left":{"title":"Classical","items":["Deterministic","Continuous","F = ma"],"color":"green"},"right":{"title":"Quantum","items":["Probabilistic","Discrete","Ĥψ = Eψ"],"color":"red"},"placement":"below","id":"cmp1"}
   → two columns with headers, separator line, bullet items. Use for ANY contrast.

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

6. RESULT — boxed key result with optional note:
   {"cmd":"result","text":"Eₙ = n²π²ℏ²/2mL²","note":"grows as n²","label":"Key Result","placement":"below","color":"gold","id":"r1"}
   → bordered box with optional badge label + annotation. Use for final answers.
   Use this to BOX important equations — like a professor drawing a rectangle
   around the key formula. Every derivation should end with a boxed result.

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

PATTERN 4 — Derivation chain → boxed result (THE BUILD-UP):
  Like a professor building from axiom to theorem, then boxing the final result.
  Each step adds to the derivation, ending with a boxed/highlighted conclusion:
  <vb draw='{"cmd":"equation","text":"L(αu₁ + βu₂)","note":"apply the operator","placement":"below","color":"#53d8fb","id":"d1"}' say="Apply L to a linear combination." />
  <vb draw='{"cmd":"equation","text":"= L(αu₁) + L(βu₂) = αLu₁ + βLu₂","note":"linearity!","placement":"below","color":"#53d8fb","id":"d2"}' say="Linearity lets us split it." />
  <vb draw='{"cmd":"result","text":"L is linear: L(αu + βv) = αLu + βLv","label":"Definition","placement":"below","color":"gold","id":"result-lin"}' say="This is THE definition of a linear operator. {ref:result-lin}" />

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

PATTERN 9 — Side-by-side comparison (CONTRAST):
  <vb draw='{"cmd":"compare","left":{"title":"Evolution","items":["Deterministic","Reversible","Info preserved"],"color":"green"},"right":{"title":"Measurement","items":["Probabilistic","Irreversible","Info lost"],"color":"red"},"placement":"below","id":"cmp"}' say="Evolution versus measurement — completely different." />

═══ BOARD RULES ═══

1. CENTER sparingly. ONLY the h1 title. Everything else uses below or
   row-start/row-next. If you center more than 1 element, you're wrong.

2. EVERY equation uses cmd:"equation" with a "note". Never orphan an equation.
   Raw cmd:"text" for equations is WRONG — use cmd:"equation" so annotations
   are automatic.

3. Use FULL WIDTH. Count your row-start/row-next uses. If you have fewer than 2
   row pairs per scene, you're wasting space. Spread equations left, meaning right.

4. VARY commands. A good scene mixes: text → equation → step → callout → compare.
   Monotone scenes (all "text" commands) are bad. Use at least 3 different
   command types per scene.

5. VISUAL RICHNESS per scene. A good scene has:
   - 1 title (h1, centered)
   - 2-3 equations (with notes)
   - 1 callout or result (boxed conclusion)
   - Steps OR compare OR check/cross list
   - 1 animation when the concept involves motion/change/3D

6. BOX your conclusions. Every derivation should END with a cmd:"result" that
   boxes the key formula. Like a professor drawing a rectangle around the
   final answer. Don't let the key result blend in with the rest.

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
