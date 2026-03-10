"""Teaching tag format reference — loadable by Tutor and sub-agents.

This module defines the exact syntax for all teaching tags rendered by the
frontend. The LLM must produce tags in EXACTLY these formats or they will
not render as interactive components.
"""

TAGS_PROMPT = r"""═══ TEACHING TAGS — EXACT FORMAT REFERENCE ═══

The frontend parses these tags from your text and renders interactive components.
If the format is wrong, the tag renders as raw text. Follow EXACTLY.

── CONTENT TAGS (no student input needed) ──────────────────────────────────

VIDEO (self-closing):
  <teaching-video lesson="3" start="260" end="380" label="Frequency vs intensity" />
  All attributes required. lesson=ID from Course Map. start/end in seconds.

IMAGE (self-closing):
  <teaching-image src="https://example.com/photo.jpg" caption="Double slit apparatus" />
  src must be a valid URL from materials or search_images. Never invent URLs.

SIMULATION (self-closing):
  <teaching-simulation id="sim_photoelectric" title="Photoelectric Effect" description="Explore how light frequency affects electron emission" />
  id must match an Available Simulation ID exactly.

MERMAID (self-closing):
  <teaching-mermaid syntax="graph LR\n  A[Light] --> B{Frequency}\n  B -->|high| C[Electrons emitted]\n  B -->|low| D[No emission]" />
  Use \n for newlines in syntax. Keep to 4-8 nodes.

RECAP (container):
  <teaching-recap>Key points from this section...</teaching-recap>

── ASSESSMENT TAGS (max 1 per message) ─────────────────────────────────────

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

CANVAS — Drawing (self-closing):
  <teaching-canvas prompt="Draw the force diagram for a block on an inclined plane." grid="cartesian" />
  grid options: "cartesian", "polar", "blank"

TEACHBACK — Deep assessment (self-closing):
  <teaching-teachback prompt="Explain the photoelectric effect as if teaching a friend who knows basic physics." concept="photoelectric_effect" />

── NAVIGATION TAGS ─────────────────────────────────────────────────────────

CHECKPOINT (self-closing):
  <teaching-checkpoint lesson="3" section="2" />

PLAN UPDATE (container):
  <teaching-plan-update><complete step="1" /></teaching-plan-update>

── SPOTLIGHT TAGS (pins asset above chat) ──────────────────────────────────

  <teaching-spotlight type="simulation" id="sim_photoelectric" />
  <teaching-spotlight type="image" src="URL" caption="Description" />
  <teaching-spotlight type="video" lesson="3" start="260" end="380" label="Segment title" />
  <teaching-spotlight-dismiss />

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
