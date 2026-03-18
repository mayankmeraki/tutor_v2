"""Teaching tag format reference — loadable by Tutor and sub-agents.

This module defines the exact syntax for all teaching tags rendered by the
frontend. The LLM must produce tags in EXACTLY these formats or they will
not render as interactive components.
"""

TAGS_PROMPT = r"""═══ TEACHING TAGS — EXACT FORMAT REFERENCE ═══

The frontend parses these tags and renders interactive components.
Wrong format = raw text. Follow EXACTLY.

── SPOTLIGHT TAGS (open in spotlight panel above chat) ─────────────────

VIDEO (self-closing):
  <teaching-video lesson="3" start="260" end="380" label="Frequency vs intensity" />
  All attributes required. lesson=ID from Course Map. start/end in seconds.
  ONLY use for lessons with [video: URL] in Course Map.

SIMULATION (self-closing):
  <teaching-simulation id="sim_photoelectric" />
  id must match an Available Simulation ID exactly.

SPOTLIGHT — pin asset above chat (self-closing):
  <teaching-spotlight type="image" src="URL" caption="Description" />

NOTEBOOK — collaborative workspace (opens in spotlight):
  <teaching-spotlight type="notebook" mode="derivation" title="Deriving Work-Energy Theorem" />
  <teaching-spotlight type="notebook" mode="problem" title="Find acceleration" problem="A 5kg box pushed with 10N on frictionless surface. Find $a$." />
  mode="derivation": tutor and student take turns adding steps.
  mode="problem": problem at top, student solves with type/draw workspace.
  Student can draw AND type. Auto-sends after 15s or manual submit.

NOTEBOOK STEP — tutor step (white chalk):
  <teaching-notebook-step n="1" annotation="Start with Newton's second law">$$F = ma$$</teaching-notebook-step>
  n=step number, annotation=context (optional), content=math/text.

CORRECTION STEP — tutor correction (blue chalk):
  <teaching-notebook-step n="4" annotation="Here's the fix" correction>$$corrected math$$</teaching-notebook-step>
  Same as step but renders blue. Student's original stays visible.

NOTEBOOK COMMENT — tutor words on board (blue chalk):
  <teaching-notebook-comment>Your turn — substitute k = p/ℏ</teaching-notebook-comment>
  For hints, nudges, praise, feedback. Use INSTEAD of chat when notebook is open.

  COLLABORATIVE PATTERN:
  1. Open notebook → 2. Your step → 3. Comment prompt → 4. Student submits (green)
  → 5. Comment feedback + next step or correction → 6. Repeat → 7. <teaching-spotlight-dismiss />

DISMISS SPOTLIGHT:
  <teaching-spotlight-dismiss />

═══ SPOTLIGHT LIFECYCLE ═══

1. ONE asset at a time — new tag auto-replaces previous.
2. CLOSE WHEN DONE: <teaching-spotlight-dismiss /> before moving on.
3. Close BEFORE new topic (unless same asset continues).
4. Don't leave open >2 turns after student responds.
5. EVERY MESSAGE: check [Active Spotlight]. If open and not discussing → dismiss first.
6. turnsOpen >= 3 → MUST dismiss unless directly referencing content.
7. Always dismiss then continue — never delay dismiss to next message.

── INLINE CONTENT TAGS (in chat stream, NOT spotlight) ──────────

IMAGE (self-closing):
  <teaching-image src="https://example.com/photo.jpg" caption="Double slit apparatus" />
  src must be a valid URL from materials or search_images results. NEVER invent URLs.

BOARD DRAW — live tutor drawing on virtual blackboard (opens in spotlight):
  <teaching-board-draw title="Forces on an Inclined Plane">
  {"cmd":"text","text":"Forces on an Inclined Plane","x":160,"y":30,"color":"yellow","size":28}
  {"cmd":"voice","text":"Let me draw the forces acting on this block..."}
  {"cmd":"line","x1":100,"y1":350,"x2":500,"y2":350,"color":"white","w":2.5}
  ...JSONL commands...
  </teaching-board-draw>

  Content is JSONL — one command per line, drawn progressively.

  FONT SIZE MINIMUMS:
    Title: 26-30 (yellow). Section headings: 20-22 (cyan).
    Labels: 18-20 (min 16). LaTeX: 22-26 (min 20). Never < 16.

  COORDINATE SYSTEM: 800px wide, height auto-grows. Origin (0,0) top-left.

  SPACING RULES:
    Title → next: 50px. Heading → next: 35px. Text → text below: 30px.
    LaTeX → next below: 45px. Between sections: 60px.
    Labels offset 15px from lines. Side-by-side text: 30px gap.
    Legend column: x=560+. If two elements within 30px vertically at
    overlapping x, they WILL overlap — increase spacing.

  AVAILABLE COMMANDS:
    {"cmd":"line","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"arrow","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"rect","x":N,"y":N,"w":N,"h":N,"color":"C","lw":N}
    {"cmd":"circle","cx":N,"cy":N,"r":N,"color":"C","lw":N}
    {"cmd":"arc","cx":N,"cy":N,"r":N,"sa":RAD,"ea":RAD,"color":"C","lw":N}
    {"cmd":"text","text":"...","x":N,"y":N,"color":"C","size":N}
    {"cmd":"latex","tex":"LaTeX","x":N,"y":N,"color":"C","size":N}
    {"cmd":"freehand","pts":[[x,y],...],"color":"C","w":N}
    {"cmd":"dashed","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"dot","x":N,"y":N,"r":N,"color":"C"}
    {"cmd":"matrix","x":N,"y":N,"rows":[["a","b"],["c","d"]],"bracket":"round","color":"C","size":N}
      bracket: "round"|"square"|"pipe"|"none". rows: array of arrays, entries can be LaTeX.
    {"cmd":"brace","x":N,"y1":N,"y2":N,"dir":"right","color":"C","label":"...","size":N}
    {"cmd":"fillrect","x":N,"y":N,"w":N,"h":N,"color":"C","opacity":0.15}
    {"cmd":"curvedarrow","x1":N,"y1":N,"x2":N,"y2":N,"cx":N,"cy":N,"color":"C","w":N}
      Quadratic Bézier curved arrow. Great for mappings, transitions.
    {"cmd":"voice","text":"..."}  — narration overlay
    {"cmd":"pause","ms":N}        — pause between sections
    {"cmd":"clear"}               — erase board

  COLORS: white, yellow, green, blue, red, cyan, dim (or any hex/CSS color)
  white=main, yellow=labels, cyan=constructions, green=results, red=highlights, dim=reference.

WIDGET — AI-generated HTML/CSS/JS in spotlight (container):
  <teaching-widget title="Double-Slit Experiment">
  ...HTML elements... <style>...</style> <script>...</script>
  </teaching-widget>
  Structure: HTML first (skeleton) → <style> → <script> (logic last).
  Self-contained, no external deps, responsive, 2-5KB. Light theme (#fafafa bg).
  Optional bridge: window.parent.postMessage({type:'capacity-sim-ready'},'*');

RECAP (container):
  <teaching-recap>Key points from this section...</teaching-recap>

── ASSESSMENT TAGS (max 1 per message, inline) ─────────────────────

GRADED MCQ:
  <teaching-mcq prompt="What determines photoelectron energy?">
  <option value="a">Light intensity</option>
  <option value="b" correct>Light frequency</option>
  <option value="c">Surface area</option>
  </teaching-mcq>

PROBE MCQ (no correct attribute on any option — casual diagnostic):
  <teaching-mcq prompt="Which gates are you familiar with?">
  <option value="a">None yet</option>
  <option value="b">X and maybe H</option>
  <option value="c">X, H, Z, CNOT</option>
  </teaching-mcq>

MCQ RULES: prompt= is question. <option value="a|b|c|d">. Mark correct with
  'correct' attribute for graded. Plain text in options only (no markdown, no LaTeX).
  LaTeX OK in prompt. 3-4 options. No pipe-separated format.

FREETEXT (self-closing):
  <teaching-freetext prompt="Explain why intensity doesn't change electron energy." placeholder="Think about what each photon carries..." />

CONFIDENCE (self-closing):
  <teaching-confidence prompt="How confident are you about the photoelectric effect?" />

AGREE-DISAGREE (self-closing):
  <teaching-agree-disagree prompt="Doubling light intensity doubles max KE of photoelectrons." />

FILL-IN-THE-BLANK (container):
  <teaching-fillblank>The energy of a photon is $E = $ <blank id="1" answer="hf" /> where $h$ is <blank id="2" answer="Planck's constant" />.</teaching-fillblank>

SPOT-THE-ERROR (self-closing):
  <teaching-spot-error quote="Since brighter light has more energy, it must produce faster electrons." prompt="What's wrong with this reasoning?" />

TEACHBACK (self-closing):
  <teaching-teachback prompt="Explain the photoelectric effect as if teaching a friend." concept="photoelectric_effect" />

── NAVIGATION TAGS ─────────────────────────────────────────────────────

CHECKPOINT: <teaching-checkpoint lesson="3" section="2" />
PLAN UPDATE: <teaching-plan-update><complete step="1" /></teaching-plan-update>

═══ CRITICAL TAG RULES ═══

1. All attribute values in double quotes: attr="value"
2. Self-closing tags end with />
3. Container tags: <teaching-X ...>content</teaching-X>
4. No nested teaching tags
5. MCQ options: <option> elements ONLY
6. Plain text inside options — no markdown, no raw LaTeX
7. LaTeX OK in prompt attributes and non-option text
8. One assessment tag per message maximum
9. Never invent IDs, URLs, or timestamps — only from context"""
