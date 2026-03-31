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
  - Use dark background: p.background(15, 20, 16) or similar
  - NEVER use p.text() — all labels go OUTSIDE as text commands with legends
  - Code must be plain JavaScript — use Math.PI not π, use * not ×
  - Keep code SHORT — under 40 lines. Simple code that works > complex code that breaks.

═══ 2D ANIMATIONS (default — use for graphs, waves, distributions) ═══

  let t = 0;
  p.setup = () => { p.createCanvas(W, H); };
  p.draw = () => {
    p.background(15, 20, 16);
    t += 0.02;
    p.noFill(); p.stroke(52, 211, 153); p.strokeWeight(2);
    p.beginShape();
    for (let x = 0; x < W; x += 2) {
      let y = H/2 + Math.sin(x * 0.05 + t) * H * 0.3;
      p.vertex(x, y);
    }
    p.endShape();
  };

═══ 3D ANIMATIONS (WEBGL — use for spheres, orbitals, 3D shapes) ═══

  let t = 0;
  p.setup = () => { p.createCanvas(W, H, p.WEBGL); };
  p.draw = () => {
    p.background(15, 20, 16);
    t += 0.01;
    p.ambientLight(60);
    p.pointLight(200, 200, 200, W*0.3, -H*0.3, W*0.5);
    p.rotateY(t * 0.3); p.rotateX(-0.3);
    p.noFill(); p.stroke(52, 211, 153); p.strokeWeight(1);
    p.sphere(W * 0.15);
  };

NEVER use p.text() in WEBGL — it requires loadFont() and crashes.

USE WEBGL ONLY FOR: Bloch spheres, orbitals, crystal lattices, 3D surfaces.
Everything else should be 2D (graphs, energy levels, wave functions, etc.)

═══ COLOR PALETTE (use these exact colors — legend must match) ═══

  Green:  p.stroke(52, 211, 153)   — #34d399
  Gold:   p.stroke(251, 191, 36)   — #fbbf24
  Cyan:   p.stroke(83, 216, 251)   — #53d8fb
  Rose:   p.stroke(251, 113, 133)  — #fb7185
  Axes:   p.stroke(80, 80, 80)     — dim gray

═══ ANIMATION FIGURE (self-contained: title + canvas + legend) ═══

Every animation is a self-contained FIGURE with title and legend — like matplotlib.
Include "title" and "legend" properties. NO separate text commands for legend:

  <vb draw='{"cmd":"animation","id":"wave","title":"Wave Function ψ(x,t)","code":"...","legend":[{"text":"ψ(x)","color":"#34d399"},{"text":"|ψ|²","color":"#fbbf24"}]}' say="Watch how the wave function evolves." />

This renders as: [Title bar] → [Animation canvas] → [Legend bar with colored dots]

═══ DIAGRAM QUALITY — MAKE IT LOOK PROFESSIONAL ═══

Every diagram/animation must look like a textbook figure, not a rough sketch:

  AXES & LABELS:
  - Always draw axes with arrows: use p.line + p.triangle for arrowheads
  - Label axes INSIDE the canvas: draw text near the axis ends
  - Use proportional coordinates (W*0.1, H*0.9 for origin, W*0.9 for x-axis end)
  - Leave 10% margin on all sides — never draw to the canvas edge

  GRID:
  - For quantitative plots: draw faint grid lines (p.stroke(30,35,32); p.strokeWeight(0.5))
  - Add tick marks on axes with values

  LEGEND (always use the "legend" property, not separate text):
  - Keep legend text SHORT: "ψ(x)" not "Green line = wave function ψ(x)"
  - Max 4 legend items
  - Colors must match what's drawn

  SIZING:
  - Use the full canvas — don't leave half the space empty
  - Curves should use 60-80% of the canvas height range
  - Minimum stroke weight: 2*S for main curves, 1*S for helper lines

  COMMON PATTERNS:
  - Graph: axes + curve + labels + legend
  - Phase space: two axes + trajectory + starting point dot
  - Energy levels: horizontal lines at different heights + labels
  - Probability cloud: random dots weighted by distribution
  - Vector field: arrows at grid points

  BAD diagram: tiny curves in the corner, no axes, no labels, no legend
  GOOD diagram: full-width axes, labeled, curves filling the space, clean legend

═══ ANIMATION CONTROL (runtime parameter changes) ═══

Control active animation parameters and highlight individual elements:
  anim-control='{"_highlight":"curve1"}' — glow/pulse a named element
  anim-control='{"_unhighlight":true}'   — remove all highlights

Animation code reads _controlParams for runtime changes:
  if (_controlParams._highlight === "psi") {
    p.strokeWeight(3); p.drawingContext.shadowColor = '#34d399';
    p.drawingContext.shadowBlur = 15;
  }

Example beat flow:
  <vb draw='{"cmd":"animation","id":"wave","code":"..."}' say="Two curves." />
  <vb anim-control='{"_highlight":"psi"}' say="This green one is psi. {ref:wave}" pause="1.5" />
  <vb anim-control='{"_unhighlight":true}' say="See how they relate?" />
"""
