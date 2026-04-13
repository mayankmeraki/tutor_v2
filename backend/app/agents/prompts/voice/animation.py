"""Voice mode animation design system.

Teaches the LLM to generate production-quality animations in both:
  - 2D (p5.js + AnimHelper) for flat diagrams, charts, algorithm vizzes
  - 3D (Three.js) for molecules, fields, surfaces, spatial concepts

The renderer auto-detects: if code uses THREE.* → Three.js engine.
Otherwise → p5.js engine. Both use cmd:"animation".
"""

VOICE_ANIMATION_CONTROL = r"""
═══ ANIMATION DESIGN SYSTEM ═══

You generate BOTH 2D and 3D animations with cmd:"animation". The renderer
auto-detects the engine from your code:
  - Code uses THREE.* API → Three.js engine
  - Code uses p5 API → p5.js engine (AnimHelper available)

⚠️ QUALITY IS NON-NEGOTIABLE. Every animation must be production-grade —
the level of Brilliant.org or 3Blue1Brown. NEVER output stub code,
wireframes, axis-only plots, or fewer than 60 lines.

⚠️ CODE LENGTH LIMIT: Keep animation code between 60–150 lines MAX.
The code goes inside a JSON string in a single <vb> beat. If the code
is too long (>150 lines / >4000 chars), the beat gets TRUNCATED by the
token limit and the student sees NOTHING — blank screen, stuck UI.
Prefer DENSE, efficient code over sprawling verbose code. Use loops
for repeated geometry. Reuse materials. Don't create separate labeled
sprites when a single legend suffices. COMPACT = WORKS. VERBOSE = BREAKS.

═══ 3D ANIMATIONS (Three.js) — PREFERRED for highest quality ═══

PREFER Three.js for ALL subjects except inherently flat 2D (arrays,
trees, circuits, flowcharts). Three.js produces dramatically better visuals.

Variables available in your Three.js code:
  THREE    — the Three.js library (r128)
  scene    — THREE.Scene (ambient + 2 directional lights already added)
  camera   — THREE.PerspectiveCamera (position 0,0,18 — adjust freely)
  renderer — THREE.WebGLRenderer (antialiased, sized to container)

Canvas: ~700×450px. Background: #060e11. OrbitControls + auto-rotation
are handled by the host. You ADD objects to the scene. Don't recreate
scene/camera/renderer. You CAN use requestAnimationFrame for animation
loops — the host intercepts it for Pause/Speed control.

── QUALITY TECHNIQUES (use these in every 3D animation) ──

POINT CLOUDS (orbitals, probability, fields):
  var geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(posArray, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(colArray, 3));
  scene.add(new THREE.Points(geo, new THREE.PointsMaterial({
    size: 0.05, vertexColors: true, transparent: true, opacity: 0.75,
    sizeAttenuation: true, blending: THREE.AdditiveBlending, depthWrite: false
  })));
  // AdditiveBlending makes high-density regions glow. 8k-15k points.

INSTANCED MESH (atoms, molecules, repeated objects):
  var geo = new THREE.SphereGeometry(0.35, 14, 14);
  var mat = new THREE.MeshPhongMaterial({ shininess: 110, specular: 0x446688 });
  var im = new THREE.InstancedMesh(geo, mat, N);
  // Per-instance transform + color via setMatrixAt / setColorAt
  // Far more efficient than N separate Mesh objects.

PARAMETRIC SURFACES (waves, fields, landscapes):
  var pg = new THREE.PlaneGeometry(14, 14, gridN-1, gridN-1);
  var pa = pg.attributes.position.array;
  // In animation loop: update pa[(i*N+j)*3+2] = heightValue;
  // pg.attributes.position.needsUpdate = true;
  // pg.computeVertexNormals();
  scene.add(new THREE.Mesh(pg, new THREE.MeshPhongMaterial({
    color: 0x2277cc, shininess: 60, side: THREE.DoubleSide
  })));

ORGANIC STRANDS (DNA, bonds, paths, field lines):
  var pts = []; // array of THREE.Vector3 from parametric equations
  var curve = new THREE.CatmullRomCurve3(pts);
  scene.add(new THREE.Mesh(
    new THREE.TubeGeometry(curve, 200, 0.14, 8, false),
    new THREE.MeshPhongMaterial({ color: 0x378ADD, shininess: 90 })
  ));

GLOW + ATMOSPHERE:
  scene.fog = new THREE.FogExp2(0x060e11, 0.012);
  // Emissive glow on materials:
  new THREE.MeshPhongMaterial({ emissive: 0x2244ff, emissiveIntensity: 0.3 })
  // Additive point lights for local glow:
  var pl = new THREE.PointLight(0x88ccff, 0.7, 30);

ANIMATION LOOP:
  (function tick() {
    requestAnimationFrame(tick);  // host intercepts for Pause/Speed
    group.rotation.y += 0.004;
    group.rotation.x = Math.sin(Date.now() * 0.0003) * 0.15;
  })();

── PHASE REVEAL FOR FIGURES (beat-by-beat build-up) ──

⚠️ When inside cmd:"figure", the animation MUST build up piece by piece
as narration beats arrive. The renderer auto-advances the next hidden
state/group with each narration beat. THIS IS THE CORE TEACHING EFFECT.

THREE.JS FIGURE REVEAL — use Groups with visible=false:
  var g1 = new THREE.Group(); g1.visible = false; scene.add(g1);
  // add DNA strand geometry to g1...
  var g2 = new THREE.Group(); g2.visible = false; scene.add(g2);
  // add polymerase geometry to g2...
  var g3 = new THREE.Group(); g3.visible = false; scene.add(g3);
  // add mRNA geometry to g3...

  Beat 2 narration → g1 scales up (DNA appears)
  Beat 3 narration → g2 scales up (polymerase appears)
  Beat 4 narration → g3 scales up (mRNA appears)

P5.JS FIGURE REVEAL — use AnimHelper with state guards:
  ⚠️ NEVER use noLoop() in figure animations — draw() must keep running
  so states can animate smoothly. The continuous loop is essential.

  const A = new AnimHelper(p, W, H);
  p._animHelper = A;
  A.init({ strand: 0, bases: 0, rna: 0, labels: 0 });
  p.draw = function() {
    A.tick(); A.clear(); A.grid(50, 6);
    var s = A.state;
    // Phase 1: DNA strand (revealed by first narration beat)
    if (s.strand > 0.1) {
      p.stroke(53, 216, 251, 180 * s.strand);
      p.line(60, 110, 640, 110);
      // ... draw strand details
    }
    // Phase 2: base pairs (revealed by second narration beat)
    if (s.bases > 0.1) {
      // ... draw base pair letters with alpha * s.bases
    }
    // Phase 3: mRNA (revealed by third narration beat)
    if (s.rna > 0.1) {
      // ... draw growing mRNA strand
    }
    // Phase 4: labels (revealed by fourth narration beat)
    if (s.labels > 0.1) {
      A.label(350, 385, "RNA Pol reads 3'→5', builds 5'→3'", A.colors.warm);
    }
  };

  Each narration beat auto-sets the next state to 1 (in A.init order).
  AnimHelper smoothly lerps 0→1 so content fades in naturally.

RULES:
  ✗ NEVER noLoop() in figures — phases won't animate
  ✗ NEVER draw everything unconditionally — use if(s.key > 0.1) guards
  ✓ ALWAYS A.init({...}) with one state per reveal phase
  ✓ ALWAYS A.tick() and A.clear() at the start of draw()
  ✓ Use opacity * stateValue for smooth fade-in

For standalone cmd:"animation" (NOT figure): draw everything from the
start — no phase reveal needed. noLoop() is OK for static diagrams.

── REFERENCE: what production quality looks like ──

Quantum orbital (point cloud):     12k MCMC-sampled points, additive blend,
  vertex colors by radius, FogExp2, subtle axis lines, nucleus glow sphere

Molecular dynamics (instanced):    36 atoms as InstancedMesh, per-instance
  color by kinetic energy, dynamic bond LineSegments, wireframe box, velocity
  Verlet integration, temperature-controlled phase transitions

Wave interference (parametric):    120×120 PlaneGeometry, FDTD wave equation,
  direct vertex manipulation per frame, MeshPhongMaterial with specular,
  wireframe overlay, PointLight for depth

DNA helix (tube geometry):         CatmullRomCurve3 from parametric helix
  equations → TubeGeometry backbones, SphereGeometry nucleotides,
  CylinderGeometry base pair rungs, 50 rungs, 3.5 turns, auto-rotation

Electromagnetic field:             ArrowHelper grid (8×8×4), color gradient
  by magnitude, animated charge with emissive glow + trail, field lines
  as TubeGeometry, animated dash offset for flow direction

Loss landscape (ML):               ParametricGeometry from f(x,y), vertex
  colors mapped to height, wireframe overlay, animated gradient descent
  sphere + trail BufferGeometry

MINIMUM EXPECTATIONS: 30+ distinct visual elements, 2+ material types,
requestAnimationFrame animation loop, proper camera framing. NEVER just
axes + a few spheres.

═══ 2D ANIMATIONS (p5.js + AnimHelper) — for flat abstractions ═══

For 2D: use AnimHelper for clean, consistent drawing.

Pattern:
  Beat 1: Create animation with A.init({allStatesStartAtZero})
  Beat 2+: Control via anim-control (state changes only, no new code)
  OR use cmd:"figure" — states auto-reveal as narration beats arrive.

AnimHelper setup (required at the start of your code):
  const A = new AnimHelper(p, W, H);
  p._animHelper = A;
  A.init({ wave1: 0, wave2: 0, showResult: 0 });

AnimHelper API:
  A.clear()                        — board bg fill
  A.grid(spacing, alpha)           — subtle grid
  A.glow(x, y, r, color)          — glowing circle
  A.label(x, y, text, color, sz)  — sans-serif label
  A.arrow(x1,y1, x2,y2, color)    — arrow with head
  A.dashed(x1,y1, x2,y2, color)   — dashed line
  A.curve(points, color, weight)   — smooth curve
  A.filledCurve(pts, baseY, color) — shaded area under curve
  A.equation(x, y, text, color)    — boxed equation
  A.legend([{color, label},...])   — glass overlay legend
  A.nx(0.5), A.ny(0.3)            — normalized coords → pixels
  A.osc(freq, min, max)           — oscillating value

  COLORS: A.colors.accent, .cyan, .accentAlt, .warm, .danger, .purple, .pink

2D QUALITY TECHNIQUES (from production examples):
  • createRadialGradient for glows (charges, particles, tips)
  • Trail arrays with gradient-faded HSL alpha (pendulum, particle paths)
  • setLineDash + lineDashOffset for animated flow direction (field lines)
  • RK4 / Verlet / FDTD — use real physics, not fake motion
  • 60+ frame trail histories for smooth paths

2D RULES:
  ✓ Use A.label() not p.text()
  ✓ Use A.glow() not p.ellipse() for particles
  ✓ States start at 0, fade in per beat
  ✓ Use A.legend() for color legend
  ✗ Never p.background() — use A.clear()
  ✗ Never hardcode colors — use A.colors.*

Controlling animations across beats (2D only):
  <vb anim-control='{"action":"set","param":"wave1","value":1}' say="Here's the first wave." />

═══ WHEN TO USE 3D vs 2D ═══

USE 3D (Three.js): molecules, orbitals, fields, waves, surfaces, vectors,
  protein structures, orbits, crystal lattices, neural networks, loss
  landscapes, planetary motion, fluid dynamics — anything spatial.

USE 2D (p5.js): arrays, trees, graphs, circuits, 2D geometry, function
  plots, flowcharts, timelines, sorting algorithms, state machines.

When in doubt, use 3D — it builds better spatial intuition and looks
dramatically more professional.
"""
