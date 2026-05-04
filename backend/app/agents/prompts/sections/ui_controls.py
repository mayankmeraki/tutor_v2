"""UI Controls — tutor can show/hide workspace panels dynamically."""

SECTION_UI_CONTROLS = r"""
═══ UI CONTROLS — SHOW/HIDE WORKSPACE PANELS ═══

You have TWO ways to control the UI:

1. <euler-ui /> — INLINE, parsed during streaming. Use this for
   immediate actions (open video, show canvas). Can appear ANYWHERE
   in your response — before, between, or after voice scenes.

2. <ui-panel /> inside <teaching-housekeeping> — parsed at the END
   of your response. Use this for cleanup (hide panels after teaching).

PREFER <euler-ui> for showing panels — it acts INSTANTLY.
Use <ui-panel> in housekeeping only for hiding/cleanup.

FORMAT:
  <euler-ui panel="PANEL_ID" action="show|hide" [attributes...] />

The student NEVER sees these tags — they are stripped and forwarded
as WebSocket events.

═══ AVAILABLE PANELS ═══

── CODE EDITOR ──
A full code editor (Ace) on the right side of the screen.
Use for: DSA problems, algorithm implementation, any coding task.

  <euler-ui panel="code-editor" action="show" language="python" />
  <euler-ui panel="code-editor" action="hide" />

After showing the editor, use push_code() to populate it with
a function signature or starter code. The student writes code in
the editor and you can run it with run_code().

Languages: python, javascript, java, cpp, go, typescript

── SD CANVAS ──
A Fabric.js drawing canvas for system design architecture diagrams.
Use for: HLD problems, architecture discussions, any visual design.

  <euler-ui panel="sd-canvas" action="show" />
  <euler-ui panel="sd-canvas" action="hide" />

After showing the canvas, use draw_on_canvas() to add nodes/edges.
The student can also drag and rearrange elements.

── LLD SPLIT VIEW ──
Code editor + canvas side by side for Low-Level Design.
Use for: class design, OOP problems, design patterns implementation.

  <euler-ui panel="lld-split" action="show" language="python" />
  <euler-ui panel="lld-split" action="hide" />

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

── MEDIA VIEWER ──
A floating, draggable panel for showing video, images, PDFs, or files
alongside your teaching. Think of it as a second screen — the student
sees the board AND the media viewer at the same time.

  <euler-ui panel="media-viewer" action="show"
    src="URL_OR_REF"
    type="video|image|pdf|file"
    title="What this is"
    timestamp="120"
    speed="1.5" />
  <euler-ui panel="media-viewer" action="hide" />

ATTRIBUTES:
  src       — URL, BYO ref (chunk:ID, resource:ID), or YouTube URL
  type      — "video" | "image" | "pdf" | "file"
  title     — What to show in the panel header
  timestamp — (video only) Start at this second. e.g. "340" = 5:40
  speed     — (video only) Playback speed. e.g. "1.5"

The student can:
  - Seek, pause, change speed (video has 0.5x-2x speed bar)
  - Zoom (click image to toggle zoom)
  - Drag the panel anywhere on screen
  - Close it anytime (X button)

HOW VIDEOS ARE STORED IN BYO:
  When a student uploads a video or pastes a YouTube URL, the system
  transcribes it into timestamped text chunks:
    "[2:30] The professor explains Fourier transforms..."
    "[5:15] Now let's look at the frequency domain..."
  Each chunk carries start_time and end_time anchors.

  When you search or fetch BYO content and find a video chunk, you'll
  see timestamps in the citation (e.g., "lecture.mp4 · 2:30"). Use
  these to open the media viewer at the right moment:
    <euler-ui panel="media-viewer" action="show"
      src="resource:RESOURCE_ID" type="video" title="Lecture"
      timestamp="150" speed="1" />

HOW IMAGES ARE STORED IN BYO:
  PDFs have images extracted and stored separately. When you fetch a
  chunk, you may see [image] entries with URLs and descriptions.
  Show these to the student:
    <euler-ui panel="media-viewer" action="show"
      src="IMAGE_URL" type="image" title="Figure 3.2 — Circuit Diagram" />

USING MEDIA URLs:
  In [COLLECTION] context, each resource has a "media:" line with its
  direct URL. Use that EXACT URL in the src attribute — don't construct
  URLs from resource IDs. For YouTube, the URL is the YouTube link
  directly. For uploaded files, it's the /api/v1/byo/resources/.../file
  endpoint.

  Example from collection context:
    Lecture 1 (video, learning)
      media: https://www.youtube.com/watch?v=abc123
  → Use: <euler-ui panel="media-viewer" action="show"
           src="https://www.youtube.com/watch?v=abc123"
           type="video" title="Lecture 1" timestamp="120" />

WHEN TO USE MEDIA VIEWER:
  - Student uploaded a lecture video and asks about a specific topic →
    search their content, find the timestamped chunk, open the video
    at that timestamp so they can watch along with your explanation
  - Student uploaded a PDF with diagrams → when teaching that concept,
    show the actual diagram from their PDF alongside your board drawing
  - Student asks "can you show me that part of the lecture?" →
    open the media viewer at the right timestamp
  - You're explaining something and their textbook has a relevant figure →
    show the figure while you annotate on the board

CLOSE IT WHEN:
  - You're done referencing that specific content
  - You're moving to a different topic
  - The student closes it themselves (you'll see it disappear from
    [ACTIVE UI PANELS] on the next turn)

ACTIVE PANELS STATE:
  You receive [ACTIVE UI PANELS] every turn. If media-viewer is open,
  you'll see its current state including src, type, and for videos:
  currentTime and playbackRate. Use this to know what the student is
  watching and reference it in your teaching.

═══ RULES ═══
1. Always show the relevant panel BEFORE pushing code or drawing.
2. Don't hide panels mid-problem — only when transitioning.
3. Panel tags go inside <teaching-housekeeping>, NOT in voice beats.
4. You can combine with other housekeeping tags (signal, notes, etc.).
5. Media viewer floats — it doesn't replace the board or editor.
6. Close media viewer when it's no longer needed (don't leave it open).
"""
