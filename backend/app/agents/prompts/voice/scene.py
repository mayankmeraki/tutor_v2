"""Voice scene format — <teaching-voice-scene> with <vb> beats.

Defines the output contract for voice mode teaching.
Each beat synchronizes: voice narration + board drawing + cursor + pause.
"""

VOICE_SCENE_FORMAT = r"""
═══ OUTPUT FORMAT: <teaching-voice-scene> ═══

Instead of text + <teaching-board-draw>, output a <teaching-voice-scene> tag.
Inside it: a sequence of <vb /> (voice beat) tags executed sequentially.

EXAMPLE (uses compound commands for rich layout):
<teaching-voice-scene title="The Schrödinger Equation">
<vb draw='{"cmd":"text","text":"The Schrödinger Equation","placement":"center","size":"h1","color":"#fbbf24","id":"title"}' say="Here's the most important equation." cursor="write" />
<vb draw='{"cmd":"equation","text":"iℏ ∂ψ/∂t = Ĥψ","note":"energy drives time change","placement":"below","color":"#fbbf24","id":"eq-main"}' say="Energy governs time evolution." cursor="write" pause="0.5" />
<vb draw='{"cmd":"callout","text":"Ĥ contains ALL physics of the system","placement":"below","color":"gold","id":"key1"}' say="Everything is encoded in the Hamiltonian. {ref:eq-main}" />
<vb say="What does the left side represent physically?" cursor="rest" question="true" />
</teaching-voice-scene>

NOTE: Use "placement" instead of x,y in all draw commands. See BOARD LAYOUT for placement tags.

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

═══ REFERENCING — CURRENT SCENE ONLY ═══

{ref:elementId} zooms and scrolls to that element. Use it to point.

RULES:
  - {ref:id} in say text. Stripped from TTS — student only hears words.
  - ONLY reference elements from the CURRENT scene. Never reference
    content from previous scenes — it's scrolled away and jarring.
    If you need to recall something, REWRITE it in the current scene.
  - Max 1 ref per beat. Too many refs cause jumpy scrolling.
  - Use FINE-GRAINED IDs. Give each key term its own id:
    GOOD: id="lhs" for left side, id="rhs" for right side of equation
    BAD: id="eq1" for the whole line (can't point to specific parts)

Example of fine-grained IDs:
  <vb draw='{"cmd":"text","text":"iℏ ∂ψ/∂t","placement":"row-start","id":"lhs","color":"#53d8fb"}' />
  <vb draw='{"cmd":"text","text":"= Ĥψ","placement":"row-next","id":"rhs","color":"#fbbf24"}' />
  <vb say="Look at the left side. {ref:lhs}" pause="1" />
  <vb say="Now the right side — that's where the physics is. {ref:rhs}" />

═══ BOARD EDITING — MODIFY EXISTING CONTENT ═══

You can modify what's already on the board:

STRIKEOUT — draw a line through an element (wrong answer, old value):
  {"cmd":"strikeout","target":"old-eq"}

UPDATE — replace text in an existing element (correction, new value):
  {"cmd":"update","target":"eq1","text":"corrected value","color":"green"}

DELETE — erase an element completely:
  {"cmd":"delete","target":"scratch-work"}

Use these to teach interactively — cross out wrong answers, update values
as you derive them, clean up scratch work.

═══ EPHEMERAL ANNOTATIONS ═══

For extra emphasis, use annotate to visually mark elements:
  annotate="circle:id:eq-main"     — freehand circle around element
  annotate="underline:id:label-1"  — wavy underline

Optional: annotate-color="#fbbf24" annotate-duration="3000"
"""
