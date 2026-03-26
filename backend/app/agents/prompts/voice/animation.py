"""Voice mode animation control and element highlighting.

Controls how to interact with live p5.js animations during voice scenes:
- Change parameters at runtime
- Highlight individual named elements (curves, labels, etc.)
"""

VOICE_ANIMATION_CONTROL = r"""
═══ ANIMATION — p5.js INLINE ON BOARD ═══

Animations are p5.js sketches that run live on the board.
The code receives: p (p5 instance), W (width px), H (height px).
Use these for ALL sizing — never hardcode pixel values.

IMPORTANT RULES:
  - Always use p.createCanvas(W, H) or p.createCanvas(W, H, p.WEBGL) in setup
  - Use W and H for ALL coordinates and sizing (proportional drawing)
  - Use the injected S variable for text/stroke scaling
  - Keep text OUTSIDE the animation — use beside:/below: placement for labels
  - The animation container has an expand button — design for both compact and expanded view
  - Use dark background: p.background(15, 20, 16) or similar
  - NEVER call p.createCanvas more than once — it resets the canvas

═══ WHEN TO USE ANIMATIONS ═══

USE animation when:
  - Showing time-varying behavior (wave propagation, oscillation, decay)
  - Showing continuous relationships (how y changes as x varies)
  - Comparing dynamic processes (input vs output, before vs after)
  - Showing motion or trajectories (particles, orbits, pendulums)
  - Showing 3D shapes that benefit from rotation (orbitals, spheres)

DON'T use animation when:
  - A static diagram would suffice (energy level diagram → use text/equations)
  - Showing a single number or formula (→ use cmd:"equation")
  - Showing a table or list (→ use cmd:"compare" or cmd:"list")
  - The concept is fundamentally static (circuit diagram, periodic table)

═══ 2D ANIMATIONS (default) — WHEN AND HOW ═══

USE 2D FOR: waves, graphs, energy levels, probability distributions,
  phase space plots, transfer functions, circuit signals, time series,
  any concept that maps to a flat x-y graph.

STRUCTURE — every 2D animation should follow this skeleton:

  let t = 0;
  p.setup = () => { p.createCanvas(W, H); };
  p.draw = () => {
    p.background(15, 20, 16);
    t += 0.02; // time step — keep SLOW (0.01-0.03)

    // ── AXES (draw first, behind everything) ──
    p.stroke(80); p.strokeWeight(sStroke(1));
    p.line(W*0.1, H*0.85, W*0.9, H*0.85);  // x-axis
    p.line(W*0.1, H*0.15, W*0.1, H*0.85);  // y-axis

    // ── AXIS LABELS (use p.text — keep short, 1-2 chars) ──
    p.noStroke(); p.fill(120);
    p.textSize(sTextSize(10)); p.textAlign(p.CENTER);
    p.text('x', W*0.9, H*0.92);
    p.text('ψ', W*0.05, H*0.15);

    // ── DATA CURVES ──
    p.noFill(); p.stroke(52, 211, 153); p.strokeWeight(sStroke(2));
    p.beginShape();
    for (let x = W*0.1; x < W*0.9; x += 2) {
      let y = H*0.5 + Math.sin((x-W*0.1)*0.05 + t) * H*0.25;
      p.vertex(x, y);
    }
    p.endShape();
  };

KEY PRINCIPLES:
  1. AXES FIRST — draw axes behind data. Use 10% margin on all sides.
  2. AXIS LABELS — short (x, t, ψ, E). Use p.text inside the animation
     ONLY for axis labels (1-2 chars). All other text goes OUTSIDE.
  3. SMOOTH MOTION — keep time step small (0.01-0.03). Avoid jitter.
  4. PADDING — leave 10-15% margin from each edge. Never draw edge-to-edge.
  5. SCALE TO CONTAINER — use W*fraction, H*fraction for all positions.
  6. DISTINCT COLORS — each curve gets its own color from the palette below.

═══ 3D ANIMATIONS (WEBGL mode) — WHEN AND HOW ═══

USE 3D FOR: Bloch spheres, atomic/molecular orbitals, crystal lattices,
  3D potential surfaces, electromagnetic fields, wave fronts in 3D,
  any concept that is inherently spatial and benefits from rotation.

STRUCTURE — every 3D animation should follow this skeleton:

  let t = 0;
  p.setup = () => { p.createCanvas(W, H, p.WEBGL); };
  p.draw = () => {
    p.background(15, 20, 16);
    t += 0.01;

    // ── LIGHTING ──
    p.ambientLight(60);
    p.pointLight(200, 200, 200, W*0.3, -H*0.3, W*0.5);

    // ── CAMERA / ROTATION ──
    p.rotateX(-0.3);    // slight tilt toward viewer
    p.rotateY(t * 0.3); // slow continuous rotation

    // ── REFERENCE GEOMETRY (axes, wireframes) ──
    p.stroke(60); p.strokeWeight(1);
    p.line(-W*0.3, 0, 0, W*0.3, 0, 0); // x-axis
    p.line(0, -H*0.3, 0, 0, H*0.3, 0); // y-axis
    p.line(0, 0, -W*0.3, 0, 0, W*0.3); // z-axis

    // ── MAIN OBJECT ──
    p.noFill(); p.stroke(52, 211, 153); p.strokeWeight(sStroke(1.5));
    p.sphere(W * 0.15);
  };

KEY PRINCIPLES:
  1. LIGHTING — always add ambientLight + pointLight. Without it, shapes are black.
  2. SLOW ROTATION — rotateY(t * 0.2 to 0.5). Let student observe, not get dizzy.
  3. REFERENCE AXES — draw thin x,y,z axes so student has spatial orientation.
  4. SIZE — main object radius ~15-20% of W. Leave space for rotation.
  5. WIREFRAME PREFERRED — use p.noFill() + p.stroke() for most shapes.
     Solid fills obscure the structure. Use p.normalMaterial() for surfaces.

WEBGL PRIMITIVES: p.sphere(), p.box(), p.cylinder(), p.cone(), p.torus(),
  p.rotateX/Y/Z(), p.translate(), p.push()/p.pop() for transforms,
  p.ambientLight(), p.pointLight(), p.normalMaterial(), p.specularMaterial().

═══ COLOR PALETTE — CONSISTENT ACROSS ALL ANIMATIONS ═══

Use these EXACT colors for consistency. The legend beside the animation
should use the SAME hex values:

  Primary curve:    rgb(52, 211, 153)  — #34d399  — emerald green
  Secondary curve:  rgb(251, 191, 36)  — #fbbf24  — gold
  Third curve:      rgb(83, 216, 251)  — #53d8fb  — cyan
  Fourth curve:     rgb(251, 113, 133) — #fb7185  — rose
  Fifth curve:      rgb(167, 139, 250) — #a78bfa  — violet

  Axes/grid:        rgb(80, 80, 80)    — dim gray
  Axis labels:      rgb(120, 120, 120) — light gray
  Background:       rgb(15, 20, 16)    — near-black

Rule: if you draw 2 curves, use green + gold. 3 curves: green + gold + cyan.
The legend beside the animation MUST use the same colors as the animation.

═══ HIGHLIGHT SUPPORT — MAKE ELEMENTS ADDRESSABLE ═══

If the animation has multiple visual elements (curves, arrows, regions),
give each a name and respond to _controlParams._highlight:

  // In draw():
  const hlPsi = _controlParams._highlight === 'psi';
  const hlProb = _controlParams._highlight === 'prob';

  // Draw ψ curve
  applyHighlight(p, '#34d399', hlPsi);
  p.stroke(52, 211, 153);
  // ... draw curve ...

  // Draw |ψ|² curve
  applyHighlight(p, '#fbbf24', hlProb);
  p.stroke(251, 191, 36);
  // ... draw curve ...

  // Reset
  p.drawingContext.shadowBlur = 0;

═══ ANIMATION CONTROL (runtime parameter changes) ═══

Control active animation parameters and highlight individual elements:
  anim-control='{"param":"value"}'       — change animation variables
  anim-control='{"_highlight":"curve1"}' — glow/pulse a named element
  anim-control='{"_unhighlight":true}'   — remove all highlights

Animation code reads _controlParams for runtime changes:
  if (_controlParams.speed) frameRate = _controlParams.speed;
  if (_controlParams._highlight === "psi") { /* glow this curve */ }

Example beat flow:
  <vb draw='{"cmd":"animation","id":"wave","code":"..."}' say="Two curves." />
  <vb anim-control='{"_highlight":"psi"}' say="This green one is psi. {ref:wave}" pause="1.5" />
  <vb anim-control='{"_highlight":"prob"}' say="This gold one is the probability. {ref:wave}" pause="1.5" />
  <vb anim-control='{"_unhighlight":true}' say="See how they relate?" />

═══ ANIMATION LABELS — OUTSIDE, NOT INSIDE ═══

DO NOT put text labels inside the animation code (they get cut off and
can't be referenced with {ref:id}).
Exception: axis labels (1-2 chars like "x", "ψ") belong INSIDE.

Everything else goes OUTSIDE using placement tags:

PATTERN — Animation + Legend (the STANDARD layout):
  <vb draw='{"cmd":"animation","placement":"row-start","id":"anim","code":"..."}' say="Here's the wave function." />
  <vb draw='{"cmd":"text","text":"Legend:","placement":"row-next","size":"h3","color":"#fbbf24","id":"leg-title"}' />
  <vb draw='{"cmd":"text","text":"Green = ψ(x)","placement":"below:leg-title","size":"small","color":"#34d399","id":"l1"}' />
  <vb draw='{"cmd":"text","text":"Gold = |ψ|²","placement":"below:l1","size":"small","color":"#fbbf24","id":"l2"}' />
  <vb draw='{"cmd":"text","text":"Dashed = classical limit","placement":"below:l2","size":"small","color":"#94a3b8","id":"l3"}' />

RULES for legends:
  1. ALWAYS include a legend when there are 2+ visual elements.
  2. Use "row-start" for animation, "row-next" for the first legend item.
  3. Color text matches the curve color EXACTLY (same hex).
  4. Legend items use "size":"small" and stack with below:prev_id.
  5. For single-curve animations, one line of text beside is sufficient.

═══ COMMON MISTAKES TO AVOID ═══

1. HARDCODED PIXELS — never write p.line(100, 200, 300, 400).
   Always use W*fraction, H*fraction.

2. NO AXES — a graph without axes is meaningless. Always draw them.

3. TOO FAST — t += 0.1 is nauseating. Use 0.01-0.03.

4. MISSING LEGEND — animation without a legend beside it is an orphan.
   Student cannot tell what the curves represent.

5. TEXT INSIDE — long labels inside the animation get clipped when
   the container is compact. Keep them outside.

6. EDGE-TO-EDGE — drawing from (0,0) to (W,H) leaves no margin.
   Start from (W*0.1, H*0.1) to (W*0.9, H*0.9).

7. TOO COMPLEX — more than 3-4 visual elements overwhelms.
   Show one concept per animation. Use multiple animations for
   multiple concepts.

8. NO HIGHLIGHT NAMES — if you plan to reference parts of the
   animation in later beats, you MUST add highlight support.

9. STATIC ANIMATION — if nothing moves, don't use animation.
   Use a static diagram (text commands) instead.

10. REDEFINING W/H/S — the variables W, H, and S are injected.
    Never write `let W = ...` or `const H = ...`.
"""
