"""Voice scene format — <teaching-voice-scene> with <vb> beats.

Defines the output contract for voice mode teaching.
Each beat synchronizes: voice narration + board drawing + cursor + pause.
"""

VOICE_SCENE_FORMAT = r"""
═══ OUTPUT FORMAT: <teaching-voice-scene> ═══

Instead of text + <teaching-board-draw>, output a <teaching-voice-scene> tag.
Inside it: a sequence of <vb /> (voice beat) tags executed sequentially.

EXAMPLE:
<teaching-voice-scene title="The Schrödinger Equation">
<vb say="Let me show you the most important equation in quantum mechanics." cursor="rest" pause="0.3" />
<vb draw='{"cmd":"text","text":"iℏ ∂ψ/∂t = Ĥψ","x":150,"y":100,"color":"#fbbf24","size":"text","id":"eq-main"}' say="Here it is." cursor="write" pause="0.5" />
<vb say="The left side — how psi changes in time." cursor="tap:id:eq-main" pause="0.8" />
<vb say="What does the left side represent physically?" cursor="rest" question="true" />
</teaching-voice-scene>

═══ <vb> ATTRIBUTES ═══

say="..."       — Text to speak (TTS). Short sentences (under 20 words).
draw='...'      — Board draw JSON command. Use SINGLE QUOTES around JSON.
cursor="..."    — "write" | "tap:id:X" | "point:id:X" | "rest"
pause="N"       — Seconds to wait after beat completes.
question="true" — Final beat. Shows input bar. Scene stops.

═══ ASSET BEATS ═══

Widgets:     <vb widget-title="..." widget-code="..." say="Try this." cursor="rest" />
Simulations: <vb simulation="sim-id" say="Let me open this." cursor="rest" />
Videos:      <vb video-lesson="6" video-start="245" video-end="280" say="Watch this." cursor="rest" />

═══ VOICE vs DRAWING ═══

say text is SPOKEN ALOUD via TTS. It is NOT a reading of what you draw.
Draw the math. SAY the meaning. Like a real teacher:
  WRONG: say="i h-bar d psi d t equals H psi"
  RIGHT: say="Here's the Schrödinger equation."
  WRONG: say="Drawing a circle around this."
  RIGHT: say="This is the key part."
  WRONG: say="Let me write the formula on the board." (narrating the action)
  RIGHT: (just draw it) say="This tells us energy drives evolution."

═══ PACING — KEEP THE STUDENT'S EYES ON THE BOARD ═══

The student is LISTENING, not reading. They cannot re-read. Respect this:

RULE 1: MAX 6-8 BEATS per scene, then ask a question.
  Long monologues lose the student. Teach a chunk, check understanding, continue.

RULE 2: NEVER 2+ say-only beats in a row without drawing or referencing.
  If you have nothing new to draw, use {ref:id} to point at something existing.
  Every spoken sentence should have a VISUAL ANCHOR — something on the board
  the student can look at while listening.

RULE 3: ONE IDEA per beat. Max 15 words per say.
  Short spoken chunks. The board carries the detail, speech carries the meaning.

RULE 4: DRAW FIRST, then explain.
  Don't announce what you'll draw. Draw it, then say what it means.

═══ BOARD AS CLASS NOTES ═══

The board is the student's NOTEBOOK. After the session, they should be able
to scroll through it and understand the full lesson sequence. This means:

- Use clear HEADINGS (h1 for topic, h2 for subtopic)
- LABEL everything — equations, diagrams, animations all need text labels
- ORGANIZE spatially — related items grouped, whitespace between sections
- ANNOTATE animations — write what the animation shows next to it
- SEQUENCE matters — the board reads top to bottom like a story
- No orphaned elements — every equation has context, every diagram has labels

GOOD board: Title → equation → labeled diagram → annotation → question
BAD board: Random equations scattered with no labels or sequence

═══ REFERENCING — MANDATORY ═══

EVERY beat that mentions something on the board MUST include {ref:elementId}.
The UI temporarily enlarges that element (zoom-pop) and scrolls to it.
This is how you POINT — the student's eye follows the zoom.

RULES:
  - {ref:id} in say text. Stripped from TTS — student only hears words.
  - Use AGGRESSIVELY. Any mention of "this equation", "that term", "the wave"
    MUST have a {ref:id}. Don't make the student guess what you mean.
  - When comparing two things, reference one then the other in sequence.

Example:
  <vb draw='{"cmd":"text","text":"F = ma","x":50,"y":100,"id":"eq-f","size":"text"}' say="Newton's second law." cursor="write" />
  <vb say="Force drives acceleration. {ref:eq-f}" pause="0.8" />
  ... later ...
  <vb say="Remember this? {ref:eq-f} Same idea, quantum version." />

═══ EPHEMERAL ANNOTATIONS ═══

For extra emphasis, use annotate to visually mark elements:
  annotate="circle:id:eq-main"     — freehand circle around element
  annotate="underline:id:label-1"  — wavy underline
  annotate="box:id:eq-schrodinger" — hand-drawn rectangle
  annotate="glow:id:wave-anim"     — soft highlight

Optional: annotate-color="#fbbf24" annotate-duration="3000"
"""
