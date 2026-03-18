"""Teaching tag format reference — loadable by Tutor and sub-agents.
Tags must be in EXACTLY these formats or they render as raw text.
"""

TAGS_PROMPT = r"""═══ TEACHING TAGS — FORMAT REFERENCE ═══

Tags render in the BOARD PANEL (right side, beside chat). Follow EXACTLY.

── BOARD PANEL TAGS ─────────────────

VIDEO (self-closing):
  <teaching-video lesson="3" start="260" end="380" label="Frequency vs intensity" />
  All attributes required. ONLY use for lessons with [video: URL] in Course Map.

SIMULATION (self-closing):
  <teaching-simulation id="sim_photoelectric" />
  id must match an Available Simulation ID exactly.

IMAGE — pin in board panel (self-closing):
  <teaching-spotlight type="image" src="URL" caption="Description" />

DISMISS — clear board panel:
  <teaching-spotlight-dismiss />

═══ BOARD PANEL LIFECYCLE ═══

1. ONE asset at a time — new tag auto-replaces previous.
2. Board panel is always visible. Dismiss clears it to empty state.
3. Don't leave content open >2 turns after student responds. Dismiss and move on.
4. If [Active Spotlight] in context and you're NOT referencing it → dismiss first.

── INLINE TAGS (in chat, NOT board panel) ──────────

IMAGE (self-closing, inline in chat):
  <teaching-image src="URL" caption="Double slit apparatus" />
  src must be from search_images results. NEVER invent URLs.

BOARD DRAW — live chalk drawing (opens in board panel):
  <teaching-board-draw title="Forces on an Inclined Plane">
  {"cmd":"text","text":"Forces on an Inclined Plane","x":160,"y":30,"color":"yellow","size":28}
  {"cmd":"voice","text":"Let me draw the forces acting on this block..."}
  {"cmd":"line","x1":100,"y1":350,"x2":500,"y2":350,"color":"white","w":2.5}
  {"cmd":"rect","x":250,"y":220,"w":60,"h":50,"color":"white","lw":2}
  {"cmd":"arrow","x1":280,"y1":245,"x2":280,"y2":145,"color":"cyan","w":2}
  {"cmd":"text","text":"N (normal)","x":290,"y":140,"color":"cyan","size":18}
  {"cmd":"latex","tex":"F_g = mg","x":290,"y":395,"color":"yellow","size":20}
  {"cmd":"pause","ms":500}
  </teaching-board-draw>

  Content is JSONL — one command per line. Student sees you draw in real-time.

  FONT SIZES: Title 26-30 (yellow). Headings 20-22 (cyan). Labels 18-20 (min 16). LaTeX 22-26 (min 20).
  COORDINATE SYSTEM: 800px wide, height auto-grows. Origin (0,0) top-left.
  SPACING: Title→next 50px. Heading→next 35px. Text→text 30px. LaTeX→next 45px.
    If elements within 30px at overlapping x → OVERLAP. Increase spacing.

  AVAILABLE COMMANDS:
    {"cmd":"text","text":"...","x":N,"y":N,"color":"C","size":N}
    {"cmd":"latex","tex":"...","x":N,"y":N,"color":"C","size":N}
    {"cmd":"line","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"arrow","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"rect","x":N,"y":N,"w":N,"h":N,"color":"C","lw":N}
    {"cmd":"circle","cx":N,"cy":N,"r":N,"color":"C","lw":N}
    {"cmd":"arc","cx":N,"cy":N,"r":N,"sa":RAD,"ea":RAD,"color":"C","lw":N}
    {"cmd":"dashed","x1":N,"y1":N,"x2":N,"y2":N,"color":"C","w":N}
    {"cmd":"dot","x":N,"y":N,"r":N,"color":"C"}
    {"cmd":"freehand","pts":[[x,y],...],"color":"C","w":N}
    {"cmd":"fillrect","x":N,"y":N,"w":N,"h":N,"color":"C","opacity":0.15}
    {"cmd":"matrix","x":N,"y":N,"rows":[["a","b"],["c","d"]],"bracket":"round","color":"C","size":N}
    {"cmd":"brace","x":N,"y1":N,"y2":N,"dir":"right","color":"C","label":"...","size":N}
    {"cmd":"curvedarrow","x1":N,"y1":N,"x2":N,"y2":N,"cx":N,"cy":N,"color":"C","w":N}
    {"cmd":"voice","text":"..."} — narration overlay
    {"cmd":"pause","ms":N} — pause between sections
    {"cmd":"clear"} — erase board

  COLORS: white, yellow, green, blue, red, cyan, dim (or hex/CSS)

WIDGET — AI-generated HTML/CSS/JS (opens in board panel):
  <teaching-widget title="Double-Slit Experiment">
  [HTML → <style> → <script>. Self-contained, responsive, 2-5KB.]
  </teaching-widget>
  Use when topic needs interactivity AND no pre-built sim exists.

── ASSESSMENT TAGS (max 1 per message, inline in chat) ─────────

MCQ:
  <teaching-mcq prompt="What determines the energy of a photoelectron?">
  <option value="a">Light intensity</option>
  <option value="b" correct>Light frequency</option>
  <option value="c">Surface area</option>
  </teaching-mcq>
  Probe MCQ (no correct attr): diagnostic/survey, no green/red feedback.
  3-4 options. Plain text in options — no markdown or LaTeX.

FREETEXT: <teaching-freetext prompt="Explain why..." placeholder="Think about..." />
CONFIDENCE: <teaching-confidence prompt="How confident are you about...?" />
AGREE-DISAGREE: <teaching-agree-disagree prompt="Doubling intensity doubles KE." />
SPOT-ERROR: <teaching-spot-error quote="..." prompt="What's wrong?" />
TEACHBACK: <teaching-teachback prompt="Explain X as if teaching a friend." concept="..." />

── NAVIGATION ─────────

<teaching-checkpoint lesson="3" section="2" />
<teaching-plan-update><complete step="1" /></teaching-plan-update>

═══ TAG RULES ═══
1. All attribute values in double quotes. 2. Self-closing: /> 3. Container: <tag>...</tag>
4. No nested teaching tags. 5. One assessment per message max.
6. Never invent IDs, URLs, or timestamps."""
