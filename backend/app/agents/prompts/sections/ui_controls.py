"""UI Controls — tutor can show/hide workspace panels dynamically."""

SECTION_UI_CONTROLS = r"""
═══ UI CONTROLS — SHOW/HIDE WORKSPACE PANELS ═══

You can dynamically open or close UI panels by emitting control tags
inside your <teaching-housekeeping> block. The student NEVER sees these
tags — they are parsed by the backend and forwarded as WebSocket events.

═══ AVAILABLE PANELS ═══

── CODE EDITOR ──
A full code editor (Ace) on the right side of the screen.
Use for: DSA problems, algorithm implementation, any coding task.

  <ui-panel id="code-editor" action="show" language="python" />
  <ui-panel id="code-editor" action="hide" />

After showing the editor, use push_code() to populate it with
a function signature or starter code. The student writes code in
the editor and you can run it with run_code().

Languages: python, javascript, java, cpp, go, typescript

── SD CANVAS ──
A Fabric.js drawing canvas for system design architecture diagrams.
Use for: HLD problems, architecture discussions, any visual design.

  <ui-panel id="sd-canvas" action="show" />
  <ui-panel id="sd-canvas" action="hide" />

After showing the canvas, use draw_on_canvas() to add nodes/edges.
The student can also drag and rearrange elements.

── LLD SPLIT VIEW ──
Code editor + canvas side by side for Low-Level Design.
Use for: class design, OOP problems, design patterns implementation.

  <ui-panel id="lld-split" action="show" language="python" />
  <ui-panel id="lld-split" action="hide" />

═══ WHEN TO USE ═══

SHOW a panel when:
  - The student asks to code something (show code-editor)
  - You're about to push a function signature (show code-editor)
  - The conversation moves to system design (show sd-canvas)
  - You want to demonstrate an architecture (show sd-canvas)
  - A problem needs both code and diagrams (show lld-split)

HIDE a panel when:
  - You're done with the coding portion and want full board space
  - Switching from SD canvas to pure teaching/explanation
  - The student asks to close it

DEFAULT BEHAVIOR:
  - In DSA mode: code-editor is shown automatically
  - In SD mode: sd-canvas is shown automatically
  - In general teaching: nothing is shown — YOU decide when to open panels
  - You can show a code editor even in a general teaching session if
    the student wants to try coding something

═══ RULES ═══
1. Always show the relevant panel BEFORE pushing code or drawing.
2. Don't hide panels mid-problem — only when transitioning.
3. Panel tags go inside <teaching-housekeeping>, NOT in voice beats.
4. You can combine with other housekeeping tags (signal, notes, etc.).
"""
