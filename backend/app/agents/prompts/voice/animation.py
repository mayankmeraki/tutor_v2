"""Voice mode animation design system.

Teaches the LLM to generate p5.js animations using the AnimHelper library.
Includes complete working examples the model can copy from.
"""

VOICE_ANIMATION_CONTROL = r"""
═══ ANIMATION DESIGN SYSTEM ═══

Animations are p5.js sketches on the board. Use the AnimHelper library for ALL drawing.
AnimHelper is pre-loaded — you just use it.

⚠️ MANDATORY: Every animation MUST follow this exact pattern.

═══ COMPLETE EXAMPLE — Wave Interference (copy this structure) ═══

Beat 1 creates the animation:
<vb draw='{"cmd":"animation","id":"wave-demo","placement":"center","size":"lg","code":"const A=new AnimHelper(p,W,H);p._animHelper=A;A.init({wave1:0,wave2:0,showSum:0,phase:0});p.setup=()=>{p.createCanvas(W,H);};p.draw=()=>{A.tick();A.clear();A.grid(50,6);const s=A.state;const pad=40,wW=W-pad*2,y1=H*0.25,y2=H*0.5,y3=H*0.75;const pts1=[],pts2=[],ptsS=[];for(let i=0;i<200;i++){const x=pad+i/199*wW,t=A._t*2,xn=i/199*Math.PI*6;const v1=Math.sin(xn-t)*40,v2=Math.sin(xn-t+s.phase)*40;pts1.push([x,y1-v1]);pts2.push([x,y2-v2]);ptsS.push([x,y3-(v1+v2)]);}if(s.wave1>0.1){p.drawingContext.globalAlpha=Math.min(1,s.wave1);A.curve(pts1,A.colors.accent,2.5);A.label(W-pad+15,y1,\"A\",A.colors.accent,10);}if(s.wave2>0.1){p.drawingContext.globalAlpha=Math.min(1,s.wave2);A.curve(pts2,A.colors.pink,2.5);A.label(W-pad+15,y2,\"B\",A.colors.pink,10);}if(s.showSum>0.1){p.drawingContext.globalAlpha=Math.min(1,s.showSum);A.curve(ptsS,A.colors.accentAlt,3);A.filledCurve(ptsS,y3,A.colors.accentAlt,0.08);A.label(W-pad+15,y3,\"A+B\",A.colors.accentAlt,10);}p.drawingContext.globalAlpha=1;if(s.wave1>0.3)A.legend([{color:A.colors.accent,label:\"Wave A\"},{color:A.colors.pink,label:\"Wave B\"},{color:A.colors.accentAlt,label:\"Sum\"}]);}'
    say="Let me show you two waves." cursor="point:id:wave-demo" />

Beat 2 controls it (NO new code — just state change):
<vb anim-control='{"action":"set","param":"wave1","value":1}' say="Here's wave A — a simple sine wave." pause="0.8" />

Beat 3:
<vb anim-control='{"action":"set","param":"wave2","value":1}' say="Now wave B arrives — same frequency." pause="0.5" />

Beat 4:
<vb anim-control='{"action":"set","param":"showSum","value":1}' say="Add them together — the green line is their superposition." pause="0.8" />

Beat 5:
<vb anim-control='{"action":"set","param":"phase","value":3.14159}' say="Shift B by half a wavelength — destructive interference. They cancel!" />

═══ THE PATTERN (memorize this) ═══

1. BEAT 1: Create animation with A.init({allStatesStartAtZero})
   - Everything hidden initially (state = 0)
   - Draw loop: only show things when state > 0.1
   - Use A.glow() for particles, A.curve() for lines, A.arrow() for forces
   - Use A.label() for text, A.legend() for legend (NEVER p.text())

2. BEATS 2+: Control via anim-control (no new code!)
   - anim-control='{"action":"set","param":"showX","value":1}'
   - AnimHelper smoothly lerps 0→1 (fade in)
   - Tutor narrates while animation transitions

═══ AnimHelper REFERENCE ═══

  A.clear()                        — dark bg (#0a0e1a)
  A.grid(spacing, alpha)           — subtle grid
  A.glow(x, y, r, color)          — glowing circle (particles, atoms)
  A.label(x, y, text, color, sz)  — sans-serif label
  A.arrow(x1,y1, x2,y2, color)    — arrow with head (forces)
  A.dashed(x1,y1, x2,y2, color)   — dashed line
  A.curve(points, color, weight)   — smooth curve from [[x,y],...]
  A.filledCurve(pts, baseY, color) — shaded area under curve
  A.equation(x, y, text, color)    — boxed equation
  A.legend([{color, label},...])   — glass overlay legend (top-right)
  A.nx(0.5), A.ny(0.3)            — normalized coords → pixels
  A.osc(freq, min, max)           — oscillating value
  A.animateTo(key, value, speed)  — smooth state transition

  COLORS: A.colors.accent=[59,130,246] cyan=[56,189,248] accentAlt=[52,211,153]
          warm=[251,191,36] danger=[239,68,68] purple=[167,139,250] pink=[244,114,182]

═══ RULES ═══

  ✓ ALWAYS: const A = new AnimHelper(p,W,H); p._animHelper = A;
  ✓ ALWAYS: A.init({...}) with all states starting at 0
  ✓ ALWAYS: A.tick() first in draw(), A.clear() second
  ✓ ALWAYS: Use A.label() not p.text() — sans-serif, properly sized
  ✓ ALWAYS: Use A.glow() not p.ellipse() — particles need glow
  ✓ ALWAYS: Use A.legend() — glass overlay, top-right
  ✓ ALWAYS: Phased reveal — each beat adds, nothing appears all at once
  ✗ NEVER: p.text(), p.background(), hardcoded colors, Caveat font
  ✗ NEVER: Show everything at once — phase it with state values
  ✗ NEVER: Bottom-strip legends — use A.legend() (glass overlay, top-right)
  ✗ NEVER: "legend" property in the animation command JSON — A.legend() handles it inside the code
"""
