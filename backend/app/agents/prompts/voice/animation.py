"""Voice mode animation design system.

Teaches the LLM to generate p5.js animations using the AnimHelper library.
Animations are state-driven, tutor-controlled, and visually polished.
"""

VOICE_ANIMATION_CONTROL = r"""
═══ ANIMATION DESIGN SYSTEM (AnimHelper) ═══

Animations run as p5.js sketches on the board. You generate the code.
The AnimHelper library is pre-loaded — use it for ALL drawing.

CODE TEMPLATE (every animation follows this structure):

  const A = new AnimHelper(p, W, H);
  p._animHelper = A;  // required — enables anim-control from beats

  A.init({
    showCurve: 0,    // 0 = hidden, 1 = visible (smooth transition)
    ballX: 0.5,      // normalized 0-1 coordinates
    launched: 0,     // boolean-like: 0 = no, 1 = yes
  });

  p.setup = () => { p.createCanvas(W, H); };
  p.draw = () => {
    A.tick();  // MUST call first — updates all animated values
    A.clear(); // dark background with vignette
    A.grid();  // subtle grid

    const s = A.state;
    if (s.showCurve > 0.1) {
      // Draw when visible — use alpha for fade-in
      A.curve(points, A.colors.accent, 2);
    }
    if (s.launched > 0.5) {
      // Physics step
      s.ballX += s.vx * dt;
    }
  };

CRITICAL RULES:
  1. ALWAYS use AnimHelper — never raw p5.js drawing
  2. ALWAYS use A.init({}) with state that starts hidden (0)
  3. ALWAYS call A.tick() first in draw(), A.clear() second
  4. Use A.state values for visibility — fade in with > 0.1 checks
  5. Use normalized coords (0-1) with A.nx(), A.ny() for positioning
  6. NEVER use p.text() — use A.label() for all text
  7. Keep code under 80 lines — helpers handle the rest

═══ PHASED REVEAL (the key pattern) ═══

Each beat adds to the scene. Nothing resets. State values go 0 → 1:

  Beat 1: draw animation with A.init({showCurve:0, showForce:0, showLabel:0})
  Beat 2: anim-control='{"action":"set","param":"showCurve","value":1}'
  Beat 3: anim-control='{"action":"set","param":"showForce","value":1}'
  Beat 4: anim-control='{"action":"set","param":"showLabel","value":1}'

The AnimHelper lerps all values smoothly — instant transitions become fades.

═══ DRAWING HELPERS (use these, not raw p5.js) ═══

  A.clear()                        — dark bg (#0a0e1a) + vignette
  A.grid(spacing, alpha)           — subtle dotted grid
  A.glow(x, y, radius, color)     — circle with radial glow (particles, atoms)
  A.label(x, y, text, color, size) — clean sans-serif label
  A.arrow(x1,y1, x2,y2, color)    — arrow with proper head (forces, vectors)
  A.dashed(x1,y1, x2,y2, color)   — dashed line (reference lines, axes)
  A.curve(points, color, weight)   — smooth curve from [[x,y], ...] array
  A.filledCurve(pts, baseY, color) — shaded area under curve (integrals, probability)
  A.equation(x, y, text, color)    — boxed equation display
  A.legend([{color, label},...])   — glass overlay legend (top-right)
  A.point(x, y, label, color)     — labeled point with glow
  A.callout(x, y, text, color)    — annotation box

  A.nx(0.5) → x pixel at 50% width
  A.ny(0.3) → y pixel at 30% height
  A.osc(freq, min, max)           — oscillating value for animations
  A.pulse(freq)                    — 0→1→0 pulsing value

═══ COLOR PALETTE (A.colors.*) ═══

  A.colors.accent    = [59,130,246]   — blue (primary curves, highlights)
  A.colors.accentAlt = [52,211,153]   — green (secondary, positive)
  A.colors.warm      = [251,191,36]   — amber (forces, energy)
  A.colors.danger    = [239,68,68]    — red (negative, barriers)
  A.colors.purple    = [167,139,250]  — purple (enzymes, special)
  A.colors.pink      = [244,114,182]  — pink (secondary strand)
  A.colors.cyan      = [56,189,248]   — cyan (particles, waves)
  A.colors.text      = [241,245,249]  — white text
  A.colors.textMuted = [148,163,184]  — gray labels

═══ TUTOR-CONTROLLED BEATS (how you narrate over animations) ═══

Beat 1 — CREATE the animation (draw command with code):
  <vb draw='{"cmd":"animation","id":"my-anim","placement":"center","size":"lg",
       "code":"const A=new AnimHelper(p,W,H);p._animHelper=A;A.init({wave:0,force:0});p.setup=()=>{p.createCanvas(W,H);};p.draw=()=>{A.tick();A.clear();A.grid();const s=A.state;if(s.wave>0.1){A.curve(pts,A.colors.accent,2);}if(s.force>0.5){A.arrow(x,y,x2,y2,A.colors.warm);}};",
       "legend":[{"text":"Wave","color":"#3b82f6"},{"text":"Force","color":"#fbbf24"}]}'
      say="Here's our setup — let me walk you through it."
      cursor="point:id:my-anim" />

Beat 2+ — CONTROL the animation (no new code, just state changes):
  <vb anim-control='{"action":"set","param":"wave","value":1}'
      say="Watch the wave appear."
      cursor="point:id:my-anim" pause="1" />

  <vb anim-control='{"action":"set","param":"force","value":1}'
      say="Now see the force vector — it's always pointing down."
      cursor="tap:id:my-anim" pause="0.8" />

═══ SUBJECT-SPECIFIC PATTERNS ═══

PHYSICS: particles=A.glow, forces=A.arrow, waves=A.curve, fields=grid of arrows
CHEMISTRY: atoms=A.glow, bonds=A.dashed/line, orbitals=A.filledCurve, labels=A.label
MATH: functions=A.curve, areas=A.filledCurve, points=A.point, equations=A.equation
BIOLOGY: cells=A.glow(large), processes=A.arrow, labels=A.label, regions=A.filledCurve

═══ QUALITY CHECKLIST ═══

  ✓ Dark background (A.clear handles this)
  ✓ System sans-serif font (A.label handles this)
  ✓ Glowing particles, not flat circles
  ✓ Glass-morphism legend (A.legend handles this)
  ✓ Phased reveal via state — nothing appears all at once
  ✓ Smooth transitions via A.animateTo (lerp built-in)
  ✓ Force arrows with proper heads (A.arrow)
  ✓ Equations in styled boxes (A.equation)
  ✓ Normalized coordinates (A.nx, A.ny) — responsive
  ✓ Under 80 lines of code
"""
