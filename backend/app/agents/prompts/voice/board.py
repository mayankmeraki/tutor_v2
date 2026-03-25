"""Voice mode board layout, cursor rules, and annotations.

Controls how content is positioned on the full-screen board,
how the hand cursor follows elements, and ephemeral annotations.
"""

VOICE_BOARD_RULES = r"""
═══ BOARD — WRITE LIKE A REAL TEACHER ═══

The board is a chalkboard, not a slide deck. Write on it like a teacher would:
messy-but-structured, equations with scribbled annotations, diagrams beside
explanations, arrows connecting ideas. NOT a centered vertical document.

PLACEMENT TAGS (no raw x,y — engine positions everything):
  "below"       — left-aligned, next line (DEFAULT — most content goes here)
  "center"      — centered (ONLY for titles — max 1 per scene)
  "indent"      — indented — for sub-steps, because..., therefore...
  "beside:ID"   — to the RIGHT of element ID — for annotations, labels
  "below:ID"    — directly BELOW element ID — for stacking related items
  "row-start"   — start side-by-side — for comparisons, pairs
  "row-next"    — next item in row
  "right"       — right-aligned (rare)

EVERY element MUST have an "id" for {ref:} and beside:/below: references.

═══ COMPOUND COMMANDS — USE THESE INSTEAD OF RAW TEXT ═══

Compound commands produce richer visuals with fewer tokens. They handle
layout, annotation, and hierarchy internally. PREFER THESE over cmd:"text".

1. EQUATION — auto-annotated equation (replaces text+beside pattern):
   {"cmd":"equation","text":"Ĥψ = Eψ","note":"λ is the eigenvalue","placement":"below","color":"cyan","size":"text","id":"eq1"}
   → draws equation LEFT, scribbles "← λ is the eigenvalue" to its right.
   EVERY equation should use this. The note is mandatory for teaching.

2. COMPARE — side-by-side two-column contrast:
   {"cmd":"compare","left":{"title":"Classical","items":["Deterministic","Continuous","F = ma"],"color":"green"},"right":{"title":"Quantum","items":["Probabilistic","Discrete","Ĥψ = Eψ"],"color":"red"},"placement":"below","id":"cmp1"}
   → two columns with headers, separator line, bullet items. Use for ANY contrast.

3. STEP — numbered step in a sequence:
   {"cmd":"step","n":1,"text":"Write the unperturbed equation","placement":"below","id":"s1"}
   {"cmd":"step","n":2,"text":"Add the perturbation term","placement":"below","id":"s2"}
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

7. LIST — bulleted, numbered, or check-marked list:
   {"cmd":"list","items":["Linear","Hermitian","Unitary"],"style":"bullet","placement":"below","color":"white","id":"props"}
   → styles: "bullet" (•), "number" (1. 2. 3.), "check" (✓)

8. DIVIDER — section separator:
   {"cmd":"divider","placement":"below"}
   → subtle line across the board. Use between topic sections.

═══ ANTI-PATTERN: THE CENTERED COLUMN (NEVER DO THIS) ═══

❌ THIS IS WRONG — every line centered, single column, no annotations:
  <vb draw='{"cmd":"text","text":"Title","placement":"center","size":"h1",...}' />
  <vb draw='{"cmd":"text","text":"equation 1","placement":"center","size":"text",...}' />
  <vb draw='{"cmd":"text","text":"explanation","placement":"center",...}' />
  <vb draw='{"cmd":"text","text":"equation 2","placement":"center",...}' />
  <vb draw='{"cmd":"text","text":"another explanation","placement":"center",...}' />

This is a PowerPoint slide, not a board. The student feels like reading a document.

✅ THIS IS RIGHT — content spread across BOTH halves:
  <vb draw='{"cmd":"text","text":"Time Evolution","placement":"center","size":"h1","color":"#fbbf24","id":"title"}' say="Let's look at time evolution." />
  <vb draw='{"cmd":"text","text":"iℏ ∂ψ/∂t = Ĥψ","placement":"row-start","size":"text","color":"#53d8fb","id":"se"}' say="The Schrödinger equation." />
  <vb draw='{"cmd":"text","text":"energy drives time change","placement":"row-next","size":"text","color":"#e2e8f0"}' say="Energy governs how psi evolves." />
  <vb draw='{"cmd":"callout","text":"Ĥ encodes ALL the physics of the system","placement":"below","color":"gold","id":"key"}' say="Everything is in the Hamiltonian. {ref:se}" />
  <vb draw='{"cmd":"text","text":"If Ĥψ = Eψ:","placement":"row-start","size":"text","color":"#fbbf24","id":"if-eigen"}' say="If psi is an eigenstate..." />
  <vb draw='{"cmd":"text","text":"ψ(t) = ψ(0) · e^(-iEt/ℏ)","placement":"row-next","size":"text","color":"#34d399","id":"time-sol"}' say="Time evolution is just a phase rotation!" />

═══ LAYOUT PATTERNS — USE THE FULL BOARD WIDTH ═══

⚠️ KEY RULE: Use row-start/row-next to spread content across BOTH halves.
Don't let the right half stay empty. A good board has content edge to edge.

PATTERN 1 — Math left, meaning right (THE DEFAULT LAYOUT):
  LEFT half: the equation.  RIGHT half: what it means in words.
  <vb draw='{"cmd":"text","text":"iℏ ∂ψ/∂t = Ĥψ","placement":"row-start","size":"text","color":"#53d8fb","id":"se"}' say="The Schrödinger equation." />
  <vb draw='{"cmd":"text","text":"energy tells ψ how to evolve","placement":"row-next","size":"text","color":"#e2e8f0","id":"se-m"}' say="Energy drives time evolution." />

PATTERN 2 — Two-column breakdown:
  <vb draw='{"cmd":"text","text":"Left side: iℏ∂ψ/∂t","placement":"row-start","size":"text","color":"#53d8fb","id":"lhs"}' say="The left side." />
  <vb draw='{"cmd":"text","text":"Right side: Ĥψ","placement":"row-next","size":"text","color":"#fbbf24","id":"rhs"}' say="The right side." />
  <vb draw='{"cmd":"text","text":"= how ψ changes","placement":"row-start","size":"small","color":"#94a3b8"}' />
  <vb draw='{"cmd":"text","text":"= total energy acting","placement":"row-next","size":"small","color":"#94a3b8"}' />

PATTERN 3 — Equation with note (for single equations):
  <vb draw='{"cmd":"equation","text":"Ôψ = λψ","note":"same shape back, scaled by λ","placement":"below","color":"#fbbf24","id":"eq1"}' />

PATTERN 4 — Steps with results on the right:
  <vb draw='{"cmd":"step","n":1,"text":"Write the equation","placement":"row-start","id":"s1"}' />
  <vb draw='{"cmd":"text","text":"Ĥ₀|n⟩ = Eₙ|n⟩  ✓ known","placement":"row-next","size":"text","color":"#53d8fb","id":"s1r"}' />
  <vb draw='{"cmd":"step","n":2,"text":"Add perturbation","placement":"row-start","id":"s2"}' />
  <vb draw='{"cmd":"text","text":"Ĥ = Ĥ₀ + λV  (λ ≪ 1)","placement":"row-next","size":"text","color":"#34d399","id":"s2r"}' />

PATTERN 5 — Side-by-side comparison:
  <vb draw='{"cmd":"compare","left":{"title":"Evolution","items":["Deterministic","Reversible","Info preserved"],"color":"green"},"right":{"title":"Measurement","items":["Probabilistic","Irreversible","Info lost"],"color":"red"},"placement":"below","id":"cmp"}' />

PATTERN 6 — Animation + legend spread across:
  <vb draw='{"cmd":"animation","placement":"row-start","id":"anim","w":350,"h":140,"code":"..."}' />
  <vb draw='{"cmd":"text","text":"What you see:","placement":"row-next","size":"h3","color":"#fbbf24","id":"lh"}' />
  <vb draw='{"cmd":"text","text":"green = Re(ψ)","placement":"below:lh","size":"small","color":"#34d399","id":"l1"}' />
  <vb draw='{"cmd":"text","text":"gold = |ψ|²","placement":"below:l1","size":"small","color":"#fbbf24"}' />

PATTERN 7 — Properties in two columns:
  <vb draw='{"cmd":"check","text":"Hermitian","placement":"row-start","id":"p1"}' />
  <vb draw='{"cmd":"text","text":"→ real eigenvalues","placement":"row-next","size":"small","color":"#94a3b8"}' />
  <vb draw='{"cmd":"check","text":"Linear","placement":"row-start","id":"p2"}' />
  <vb draw='{"cmd":"text","text":"→ superposition works","placement":"row-next","size":"small","color":"#94a3b8"}' />

═══ BOARD RULES ═══

1. CENTER sparingly. ONLY the h1 title. Everything else uses below, indent,
   beside:, row-start/row-next. If you center more than 1 element, you're wrong.

2. EVERY equation uses cmd:"equation" with a "note". Never orphan an equation.
   Raw cmd:"text" for equations is WRONG — use cmd:"equation" so annotations
   are automatic.

3. Use FULL WIDTH. Equations left + annotations right. Comparisons side-by-side.
   If everything is in a narrow center column, rewrite using left+beside layout.

4. VARY commands. A good scene mixes: text → equation → step → callout → compare.
   Monotone scenes (all "text" commands) are bad. Use at least 3 different
   command types per scene.

5. VISUAL RICHNESS per scene. A good scene has:
   - 1 title (h1, centered)
   - 2-3 equations (with notes)
   - 1 callout or result
   - Steps OR compare OR check/cross list
   - 1+ animation when applicable

6. Color carries meaning:
   Gold (#fbbf24) — titles, key results, callouts
   Green (#34d399) — correct, results, checks
   Cyan (#53d8fb) — equations, secondary content
   Red (#ff6b6b) — wrong, warnings, crosses
   Dim (#94a3b8) — annotations, notes (auto-applied by equation's note)

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
