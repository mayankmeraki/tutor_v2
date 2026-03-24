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
"""
