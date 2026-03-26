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

PLACEMENT TAGS (no raw x,y — engine positions everything):
  "below"       — next line, left-aligned (DEFAULT — omit for normal flow)
  "center"      — centered (ONLY for scene title — max 1 per scene)
  "indent"      — indented — for sub-steps, therefore...
  "row-start"   — start side-by-side row (equation left + meaning right)
  "row-next"    — next item in the same row

That's it — just 4 placements. Content flows top-to-bottom by default.
Use row-start/row-next to spread content across BOTH halves of the board.

EVERY element MUST have an "id" for {ref:} references.

═══ COMPOUND COMMANDS — USE THESE INSTEAD OF RAW TEXT ═══

Compound commands produce richer visuals with fewer tokens. They handle
layout, annotation, and hierarchy internally. PREFER THESE over cmd:"text".

1. EQUATION — auto-annotated equation (replaces text+beside pattern):
   {"cmd":"equation","text":"Ĥψ = Eψ","note":"eigenvalue equation","placement":"below","color":"cyan","size":"text","id":"eq1"}
   → draws equation LEFT, scribbles "← eigenvalue equation" to its right.
   EVERY equation should use this. The note is mandatory for teaching.

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

⚠️ MANDATORY: At least 50% of your content beats MUST use row-start/row-next
or beside:/below: placement. If you find yourself writing 4+ consecutive "below"
placements, STOP — you're making a waterfall. Restructure.

PATTERN 1 — Equation left + meaning right (THE WORKHORSE):
  Like a professor writing the equation, then scribbling what it means beside it.
  <vb draw='{"cmd":"equation","text":"iℏ ∂ψ/∂t = Ĥψ","note":"energy drives time change","placement":"row-start","color":"#53d8fb","id":"se"}' say="The Schrödinger equation." />
  <vb draw='{"cmd":"text","text":"LHS = how ψ changes in time","placement":"row-next","size":"small","color":"#94a3b8","id":"se-meaning"}' say="Left side tells us about change." />

PATTERN 2 — Scatter-write across the top (TOPIC OVERVIEW):
  Like a professor writing three related keywords across the full board width
  before diving into any of them:
  <vb draw='{"cmd":"text","text":"1) Linearity","placement":"row-start","size":"h2","color":"#fbbf24","id":"lin"}' say="First: linearity." />
  <vb draw='{"cmd":"text","text":"EOM","placement":"row-next","size":"h2","color":"#fbbf24","id":"eom"}' say="Second: equations of motion." />
  <vb draw='{"cmd":"text","text":"dynamical variables","placement":"row-next","size":"h2","color":"#fbbf24","id":"dyn"}' say="Third: dynamical variables." />

PATTERN 3 — Animation with built-in legend (SELF-CONTAINED):
  The animation command includes a "legend" array — renders animation + legend side-by-side automatically:
  <vb draw='{"cmd":"animation","id":"diagram","code":"...","legend":[{"text":"Green = Re(z)","color":"#34d399"},{"text":"Gold = Im(z)","color":"#fbbf24"}]}' say="Here's the complex plane." />

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

PATTERN 8 — Animation + legend (AUTOMATIC — use legend property):
  <vb draw='{"cmd":"animation","id":"wave","code":"...","legend":[{"text":"Green = ψ(x)","color":"#34d399"},{"text":"Gold = |ψ|²","color":"#fbbf24"}]}' say="Green is the wave, gold is probability." />

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
