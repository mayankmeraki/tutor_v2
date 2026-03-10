"""Teaching tag format reference — loadable by Tutor and sub-agents.

This module defines the exact syntax for all teaching tags rendered by the
frontend. The LLM must produce tags in EXACTLY these formats or they will
not render as interactive components.
"""

TAGS_PROMPT = r"""═══ TEACHING TAGS — EXACT FORMAT REFERENCE ═══

The frontend parses these tags from your text and renders interactive components.
If the format is wrong, the tag renders as raw text. Follow EXACTLY.

── SPOTLIGHT TAGS (open in the spotlight panel above chat) ─────────────────

VIDEO — opens directly in the spotlight panel (self-closing):
  <teaching-video lesson="3" start="260" end="380" label="Frequency vs intensity" />
  All attributes required. lesson=ID from Course Map. start/end in seconds.
  Opens automatically in spotlight — no click needed from student.

SIMULATION — opens directly in the spotlight panel (self-closing):
  <teaching-simulation id="sim_photoelectric" />
  id must match an Available Simulation ID exactly.
  Opens automatically in spotlight — no click needed from student.

SPOTLIGHT — pin any asset above chat (self-closing):
  <teaching-spotlight type="image" src="URL" caption="Description" />
  <teaching-spotlight type="mermaid" syntax="graph LR\n  A-->B" />

NOTEBOOK — Collaborative derivation or problem workspace (opens in spotlight):
  <teaching-spotlight type="notebook" mode="derivation" title="Deriving the Work-Energy Theorem" />
  <teaching-spotlight type="notebook" mode="problem" title="Find the acceleration" problem="A 5kg box is pushed with 10N on a frictionless surface. Find $a$." />

  mode="derivation": Collaborative step-by-step workspace. Tutor and student
    take turns adding steps. Tutor writes a step, asks student to continue,
    student types or draws their work. Both contributions appear side-by-side.
  mode="problem": Problem workspace with statement at top. Student solves using
    type (LaTeX) or draw (freehand). Tutor can add scaffold steps/hints.

  The student has a unified workspace at the bottom of the notebook with:
  - A drawing canvas (always visible) with pen colors, eraser, and undo
  - A text input (always visible) for LaTeX math ($...$, $$...$$) or plain text
  The student can draw AND type in the same submission. Their work auto-sends
  after 15 seconds of inactivity, or they click "Submit Work" manually.
  Student submissions appear as green-accented steps in the notebook and are
  sent to you for feedback.

NOTEBOOK STEP — Adds a tutor step to an open notebook (either mode):
  <teaching-notebook-step n="1" annotation="Start with Newton's second law">$$F = ma$$</teaching-notebook-step>
  <teaching-notebook-step n="2" annotation="Rearrange for acceleration">$$a = \frac{F}{m}$$</teaching-notebook-step>
  <teaching-notebook-step n="3" annotation="" feedback="Almost! Check the sign.">$$a = -\frac{F}{m}$$</teaching-notebook-step>

  n = step number, annotation = what's happening (optional), content = math/text
  feedback = inline feedback on a student's previous step (optional)

  COLLABORATIVE PATTERN:
  1. Open notebook with <teaching-spotlight type="notebook" ...>
  2. Add your first step with <teaching-notebook-step>
  3. Ask student "What's the next step?" in your message text
  4. Student submits their step (appears as [Notebook step N] in chat)
  5. Respond with feedback + your next step using <teaching-notebook-step>
  6. Repeat until derivation/problem is complete
  7. Close with <teaching-spotlight-dismiss />

DISMISS SPOTLIGHT — close the spotlight panel:
  <teaching-spotlight-dismiss />

═══ SPOTLIGHT LIFECYCLE — MANDATORY RULES ═══

1. ONE ASSET AT A TIME: Only one thing can be in the spotlight. A new video,
   simulation, or spotlight tag automatically REPLACES the previous content.
2. CLOSE WHEN DONE: When discussion moves past the asset, emit
   <teaching-spotlight-dismiss /> BEFORE your next message. Do NOT leave
   stale assets pinned in the spotlight.
3. CLOSE BEFORE NEW TOPIC: When advancing to a new topic, dismiss any open
   spotlight first (unless the next topic uses the same asset).
4. NEVER leave a video or simulation open for more than 3 turns after
   the student has responded to it. Close it and move on.

── INLINE CONTENT TAGS (render in the chat stream, NOT spotlight) ──────────

IMAGE — inline in chat (self-closing):
  <teaching-image src="https://example.com/photo.jpg" caption="Double slit apparatus" />
  src must be a valid URL from materials or search_images. Never invent URLs.
  Use this for small reference images. For important images, use spotlight.

MERMAID — inline diagram (self-closing):
  <teaching-mermaid syntax="graph LR\n  A[Light] --> B{Frequency}\n  B -->|high| C[Electrons emitted]\n  B -->|low| D[No emission]" />
  Use \n for newlines in syntax. Keep to 4-8 nodes.

RECAP (container):
  <teaching-recap>Key points from this section...</teaching-recap>

── ASSESSMENT TAGS (max 1 per message, always inline) ─────────────────────

MCQ — Multiple Choice (container with <option> children):
  <teaching-mcq prompt="What determines the energy of a photoelectron?">
  <option value="a">Light intensity</option>
  <option value="b" correct>Light frequency</option>
  <option value="c">Surface area</option>
  <option value="d">Exposure time</option>
  </teaching-mcq>

  RULES FOR MCQ:
  - prompt attribute = the question text
  - Each option is a separate <option> element with value="a", "b", "c", or "d"
  - Mark the correct option with the 'correct' boolean attribute
  - Option text is PLAIN TEXT only — no markdown, no asterisks, no LaTeX in options
  - For math in the question prompt, use LaTeX: prompt="What is $E$ in $E=hf$?"
  - 3-4 options. One correct answer.
  - DO NOT use pipe-separated format. DO NOT use plain text lines.
  - DO NOT put asterisks or markdown formatting inside <option> tags.

FREETEXT (self-closing):
  <teaching-freetext prompt="Explain why increasing intensity doesn't change electron energy." placeholder="Think about what each photon carries..." />

CONFIDENCE (self-closing):
  <teaching-confidence prompt="How confident are you about the photoelectric effect?" />

AGREE-DISAGREE (self-closing):
  <teaching-agree-disagree prompt="Doubling the light intensity doubles the maximum kinetic energy of photoelectrons." />

FILL-IN-THE-BLANK (container):
  <teaching-fillblank>The energy of a photon is $E = $ <blank id="1" answer="hf" /> where $h$ is <blank id="2" answer="Planck's constant" />.</teaching-fillblank>

SPOT-THE-ERROR (self-closing):
  <teaching-spot-error quote="Since brighter light has more energy, it must produce faster electrons." prompt="What's wrong with this reasoning?" />

TEACHBACK — Deep assessment (self-closing):
  <teaching-teachback prompt="Explain the photoelectric effect as if teaching a friend who knows basic physics." concept="photoelectric_effect" />

── NAVIGATION TAGS ─────────────────────────────────────────────────────────

CHECKPOINT (self-closing):
  <teaching-checkpoint lesson="3" section="2" />

PLAN UPDATE (container):
  <teaching-plan-update><complete step="1" /></teaching-plan-update>

═══ CRITICAL TAG RULES ═══

1. ALL attribute values must be in double quotes: attr="value" (not attr=value)
2. Self-closing tags end with /> (space before slash optional)
3. Container tags: <teaching-X ...>content</teaching-X>
4. No nested teaching tags
5. MCQ options: use <option> elements ONLY, not markdown lists or pipe-separated strings
6. Plain text inside options — NO markdown (* or **), NO raw LaTeX in option text
7. LaTeX is fine in prompt attributes and in non-option text
8. One assessment tag per message maximum
9. Never invent IDs, URLs, or timestamps — only use values from your context"""
