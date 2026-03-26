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

═══ 2D ANIMATIONS (default) ═══

For waves, graphs, energy levels, probability distributions:
  p.setup = () => { p.createCanvas(W, H); };
  p.draw = () => {
    p.background(15, 20, 16);
    // Draw using W, H for coordinates
    p.stroke(52, 211, 153); // green
    for (let x = 0; x < W; x += 2) {
      let y = H/2 + Math.sin(x * 0.05 + t) * H * 0.3;
      p.vertex(x, y);
    }
  };

═══ 3D ANIMATIONS (WEBGL mode) ═══

For Bloch spheres, orbital shapes, 3D potentials, crystal structures:
  p.setup = () => { p.createCanvas(W, H, p.WEBGL); };
  p.draw = () => {
    p.background(15, 20, 16);
    p.rotateY(t * 0.5);
    p.rotateX(0.3);
    p.noFill(); p.stroke(52, 211, 153);
    p.sphere(W * 0.2);  // size relative to W
  };

USE WEBGL WHEN:
  - Showing a Bloch sphere (qubit state visualization)
  - Showing atomic/molecular orbitals (3D shapes)
  - Showing crystal lattices or unit cells
  - Showing 3D potential surfaces
  - Any concept that's inherently spatial/3D

WEBGL gives you: p.sphere(), p.box(), p.cylinder(), p.cone(),
  p.rotateX/Y/Z(), p.translate(), lighting (p.ambientLight, p.pointLight),
  p.normalMaterial(), proper depth buffering.

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
  <vb anim-control='{"_highlight":"psi"}' say="This cyan one is the input." pause="1.5" />
  <vb anim-control='{"_highlight":"result"}' say="This yellow one is the output." pause="1.5" />
  <vb anim-control='{"_unhighlight":true}' say="See how they differ?" />

═══ ANIMATION LABELS — OUTSIDE, NOT INSIDE ═══

DO NOT put text labels inside the animation code (they get cut off).
Instead, use placement tags to put labels beside/below the animation:

  <vb draw='{"cmd":"animation","placement":"row-start","id":"anim","code":"..."}' />
  <vb draw='{"cmd":"text","text":"Green = ψ(x)","placement":"row-next","size":"small","color":"#34d399","id":"l1"}' />
  <vb draw='{"cmd":"text","text":"Gold = |ψ|²","placement":"below:l1","size":"small","color":"#fbbf24"}' />
"""
