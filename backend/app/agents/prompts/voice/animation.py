"""Voice mode animation control and element highlighting.

Controls how to interact with live p5.js animations during voice scenes:
- Change parameters at runtime
- Highlight individual named elements (curves, labels, etc.)
"""

VOICE_ANIMATION_CONTROL = r"""
═══ ANIMATION CONTROL ═══

Control active animation parameters and highlight individual elements:
  anim-control='{"param":"value"}'       — change animation variables
  anim-control='{"_highlight":"curve1"}' — glow/pulse a named element
  anim-control='{"_unhighlight":true}'   — remove all highlights

Animation code should define named elements via _elements registry.
The engine auto-injects: _controlParams, _elements, applyHighlight().

Animation code reads _controlParams for runtime changes:
  if (_controlParams.speed) frameRate = _controlParams.speed;
  if (_controlParams._highlight === "psi") { /* glow this curve */ }

Example beat flow:
  <vb draw='{"cmd":"animation","id":"wave","code":"..."}' say="Two curves." />
  <vb anim-control='{"_highlight":"psi"}' say="This cyan one is the input." pause="1.5" />
  <vb anim-control='{"_highlight":"result"}' say="This yellow one is the output." pause="1.5" />
  <vb anim-control='{"_unhighlight":true}' say="See how they differ?" />
"""
