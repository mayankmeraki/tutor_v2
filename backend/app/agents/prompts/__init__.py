from .tutor import TUTOR_SYSTEM_PROMPT, build_tutor_system_prompt
from .planning import PLANNING_PROMPT
from .toolkit import TOOLKIT_PROMPT, MQL_TOOLKIT_PROMPT
from .tags import TAGS_PROMPT
from .assessment import ASSESSMENT_SYSTEM_PROMPT
from .teaching_delegate import build_delegation_prompt
from .scenarios.course_follow import SKILL_COURSE
from .scenarios.exam import SKILL_EXAM_FULL
from .scenarios.exam_topic import SKILL_EXAM_TOPIC
from .scenarios.conceptual import SKILL_CONCEPTUAL
from .scenarios.curiosity import SKILL_FREE

SKILL_MAP: dict[str, str | None] = {
    "course": SKILL_COURSE,
    "exam_full": SKILL_EXAM_FULL,
    "exam_topic": SKILL_EXAM_TOPIC,
    "problem": None,
    "conceptual": SKILL_CONCEPTUAL,
    "free": SKILL_FREE,
}


def _inject_last_assessment(parts: list[str], summary: dict):
    """Inject persistent assessment summary so tutor always knows recent performance."""
    score = summary.get("score", {})
    pct = score.get("pct", 0)
    section = summary.get("section", "")
    weak = summary.get("weakConcepts", [])
    strong = summary.get("strongConcepts", [])
    rec = summary.get("recommendation", "")

    lines = [f"[Most Recent Assessment — {section}]"]
    lines.append(f"Score: {score.get('correct', 0)}/{score.get('total', 0)} ({pct}%)")
    lines.append(f"Mastery: {summary.get('overallMastery', '?')}")
    if weak:
        lines.append(f"WEAK (need re-teaching): {', '.join(weak)}")
    if strong:
        lines.append(f"Strong: {', '.join(strong)}")
    if rec:
        lines.append(f"Recommendation: {rec}")

    if pct < 60:
        lines.append(
            "\n⚠️  This student scored below 60%. They need continued teaching on "
            "the weak concepts above. Do NOT skip ahead or end the session. "
            "Use a different modality or approach than what was used before. "
            "Propose a plan to the student — give them agency but guide them."
        )
    parts.append("\n".join(lines) + "\n")


def _inject_experience_level(parts: list[str], context_data: dict):
    """Parse session metrics and inject NEW_STUDENT or RETURNING_STUDENT tag."""
    import json as _json

    session_count = 0
    completed_sections = 0

    metrics_raw = context_data.get("sessionMetrics", "")
    if metrics_raw:
        try:
            metrics = _json.loads(metrics_raw) if isinstance(metrics_raw, str) else metrics_raw
            session_count = metrics.get("sessionCount", metrics.get("sessionNumber", 0))
        except (ValueError, TypeError, AttributeError):
            pass

    profile_raw = context_data.get("studentProfile", "")
    if profile_raw:
        try:
            profile = _json.loads(profile_raw) if isinstance(profile_raw, str) else profile_raw
            if isinstance(profile, dict):
                completed_sections = len(profile.get("completedCourseSections", []))
                if not session_count:
                    session_count = profile.get("sessionCount", 0)
        except (ValueError, TypeError, AttributeError):
            pass

    is_new = session_count <= 2 and completed_sections < 3

    level = "NEW_STUDENT" if is_new else "RETURNING_STUDENT"
    parts.append(f"[Student Experience Level: {level}]")
    if is_new:
        parts.append(
            "This student is new to the course. Do NOT reference past lectures "
            "or say \"remember when the professor showed...\". Frame the course "
            "as something they are discovering. All questions must be self-contained.\n"
        )


def _compile_teaching_overrides(context_data: dict) -> str | None:
    """Compile per-student teaching style overrides from _profile notes.

    Parses the student model for _profile notes and extracts structured
    teaching preferences. Also considers topic type from the current plan
    to add topic-specific overrides.

    Returns an override block string, or None if no overrides are found.
    """
    import json as _json

    student_model = context_data.get("studentModel", "")
    if not student_model:
        return None

    # Parse student model JSON
    try:
        model = _json.loads(student_model) if isinstance(student_model, str) else student_model
    except (ValueError, TypeError):
        return None

    # Find _profile notes
    profile_text = ""
    notes = model.get("notes", [])
    if isinstance(notes, list):
        for note in notes:
            concepts = note.get("concepts", [])
            if "_profile" in concepts:
                profile_text += note.get("note", "") + "\n"
    elif isinstance(notes, dict):
        # Handle dict-style notes
        for key, note in notes.items():
            if "_profile" in key:
                if isinstance(note, str):
                    profile_text += note + "\n"
                elif isinstance(note, dict):
                    profile_text += note.get("note", "") + "\n"

    if not profile_text.strip():
        return None

    # Extract current topic type from teaching plan for topic-level overrides
    topic_type = None
    current_topic = context_data.get("currentTopic", "")
    if current_topic:
        try:
            topic = _json.loads(current_topic) if isinstance(current_topic, str) else current_topic
            if isinstance(topic, dict):
                # Look for delivery_pattern or topic type hints
                steps = topic.get("steps", [])
                if steps and isinstance(steps, list):
                    delivery = steps[0].get("delivery_pattern", "")
                    guidelines = steps[0].get("tutor_guidelines", "")
                    if delivery:
                        topic_type = delivery
        except (ValueError, TypeError, IndexError, KeyError):
            pass

    # Build the override block
    overrides = []
    overrides.append("═══ TEACHING STYLE OVERRIDES — THIS STUDENT ═══")
    overrides.append("")
    overrides.append("The following overrides are compiled from observed teaching")
    overrides.append("preferences for THIS student. They SUPERSEDE the default")
    overrides.append("pedagogy rules below. When an override conflicts with a")
    overrides.append("default, FOLLOW THE OVERRIDE.")
    overrides.append("")
    overrides.append("FROM STUDENT _PROFILE:")
    overrides.append(profile_text.strip())
    overrides.append("")
    overrides.append("HOW TO APPLY THESE OVERRIDES:")
    overrides.append("  - If _profile says 'prefers explain-first': lead with explanation,")
    overrides.append("    NOT Socratic questions. Ask ONE check question after explaining.")
    overrides.append("  - If _profile says 'fast mover': skip scaffolding, move quickly,")
    overrides.append("    one question per concept.")
    overrides.append("  - If _profile says 'board-draw anchor': use board-draw as the")
    overrides.append("    primary teaching tool, not video.")
    overrides.append("  - If _profile mentions specific modality preferences: honor them")
    overrides.append("    as default, but still vary (3+ same modality gets stale).")
    overrides.append("  - If _profile says 'avoids Socratic' or 'disengages with questions':")
    overrides.append("    use explain-then-discuss pattern, minimize cold-call questions.")
    overrides.append("  - TOPIC-SPECIFIC overrides in _profile take priority over general")
    overrides.append("    preferences (e.g., 'Socratic works for conceptual but not math').")
    overrides.append("")
    overrides.append("These overrides are NOT permanent. Keep testing what works.")
    overrides.append("If the student engages well with a different approach on a new topic,")
    overrides.append("note the updated preference via update_student_model.")

    # Add topic-type specific guidance if available
    if topic_type:
        overrides.append("")
        overrides.append(f"CURRENT TOPIC DELIVERY: {topic_type}")
        overrides.append("  Adapt the overrides above to this delivery pattern.")
        overrides.append("  If the student's preference conflicts with the delivery pattern,")
        overrides.append("  PRIORITIZE THE STUDENT'S PREFERENCE — the delivery pattern is")
        overrides.append("  a suggestion, the student's learning style is observed data.")

    return "\n".join(overrides)


def build_tutor_prompt(context_data: dict) -> str | tuple[str, str]:
    """Build tutor system prompt.

    Returns a tuple (static_prompt, dynamic_context) for prompt caching.
    The static part is cacheable (instructions + tags). The dynamic part
    changes every turn (student profile, board state, plan, etc.).
    """
    # Compile per-student teaching overrides from _profile notes
    teaching_overrides = _compile_teaching_overrides(context_data)

    # STATIC: tutor instructions + toolkit + tags (cacheable — identical for all students)
    tutor_prompt = build_tutor_system_prompt()
    static_parts = [tutor_prompt, TOOLKIT_PROMPT, TAGS_PROMPT]

    scenario_skill = context_data.get("scenarioSkill")
    if scenario_skill:
        static_parts.append(scenario_skill)

    static_prompt = "\n".join(static_parts)

    # DYNAMIC: context that changes per turn (not cacheable)
    parts = []

    # ─── SECTION 0: TEACHING OVERRIDES (per-student) ───────────
    # Injected into dynamic context so static prompt stays cacheable.
    if teaching_overrides:
        parts.append(teaching_overrides)
        parts.append("")

    # ─── SECTION 1: COURSE CONTEXT ──────────────────────────────
    # What this course contains — static per course, not per student.
    parts.append("\n═══════════════════════════════════════════════════")
    parts.append(" COURSE CONTEXT — the course content (your source of truth)")
    parts.append("═══════════════════════════════════════════════════\n")

    course_fields = [
        ("courseMap", "Course Map"),
        ("concepts", "Course Concepts"),
        ("simulations", "Available Simulations"),
    ]
    for key, label in course_fields:
        val = context_data.get(key)
        if val:
            parts.append(f"[{label}]\n{val}\n")

    # ─── SECTION 2: STUDENT CONTEXT ─────────────────────────────
    # Who this student is and what they know — persists across sessions.
    parts.append("\n═══════════════════════════════════════════════════")
    parts.append(" STUDENT CONTEXT — who this student is")
    parts.append("═══════════════════════════════════════════════════\n")

    student_profile = context_data.get("studentProfile")
    if student_profile:
        parts.append(f"[Student Profile]\n{student_profile}\n")

    _inject_experience_level(parts, context_data)

    knowledge_summary = context_data.get("knowledgeSummary")
    if knowledge_summary:
        parts.append(f"[Student Knowledge State]\n{knowledge_summary}\n")

    student_model = context_data.get("studentModel")
    if student_model:
        parts.append(f"[Student Model — Your Evolving Understanding of This Student]\n{student_model}\n")

    # Last assessment summary — persists across turns until next assessment
    last_assessment = context_data.get("lastAssessmentSummary")
    if last_assessment and not context_data.get("assessmentResult"):
        _inject_last_assessment(parts, last_assessment)

    # ─── SECTION 3: SESSION & TEACHING CONTEXT ──────────────────
    # Current session state — plan, topic, progress, scope.
    parts.append("\n═══════════════════════════════════════════════════")
    parts.append(" SESSION CONTEXT — current teaching state")
    parts.append("═══════════════════════════════════════════════════\n")

    # Inject current time for natural greetings and time-aware responses
    from datetime import datetime, timezone
    _now = datetime.now(timezone.utc)
    parts.append(f"[Current Time] {_now.strftime('%A, %B %d %Y, %H:%M UTC')}\n")

    session_metrics = context_data.get("sessionMetrics")
    if session_metrics:
        parts.append(f"[Session Metrics]\n{session_metrics}\n")

    active_sim = context_data.get("activeSimulation")
    if active_sim:
        parts.append(f"[Active Simulation State]\n{active_sim}\n")

    active_board = context_data.get("activeBoard")
    if active_board:
        parts.append(f"[ACTIVE BOARD — what the student sees on the board right now]\n{active_board}\n")

    previous_boards = context_data.get("previousBoards")
    if previous_boards:
        parts.append(f"[PREVIOUS BOARDS — completed board-draws this session]\n{previous_boards}\n")

    teaching_plan = context_data.get("teachingPlan")
    if teaching_plan:
        parts.append("[TEACHING PLAN — Full outline of all sections and topics]\n")
        parts.append(teaching_plan)

    current_topic = context_data.get("currentTopic")
    if current_topic:
        parts.append("\n[CURRENT TOPIC — Execute these steps now]\n")
        parts.append(current_topic)

    completed_topics = context_data.get("completedTopics")
    if completed_topics:
        parts.append(f"\n[COMPLETED TOPICS]\n{completed_topics}\n")

    session_scope = context_data.get("sessionScope")
    if session_scope:
        parts.append(f"\n[SESSION SCOPE]\n{session_scope}\n")

    # Voice mode instructions — completely different output format
    teaching_mode = context_data.get("teachingMode", "text")
    if teaching_mode == "voice":
        parts.append(r"""
[VOICE MODE — ACTIVE]
The student is in VOICE MODE. There is NO chat pane — only a full-screen board with subtitles.
Your spoken words are delivered via TTS. The board is the only visual.

═══ OUTPUT FORMAT: <teaching-voice-scene> ═══

Instead of text + <teaching-board-draw>, output a <teaching-voice-scene> tag.
Inside it: a sequence of <vb /> (voice beat) tags executed sequentially.

EXAMPLE:
<teaching-voice-scene title="The Schrödinger Equation">
<vb say="Let me show you the most important equation in quantum mechanics." cursor="rest" pause="0.3" />
<vb draw='{"cmd":"text","text":"iℏ ∂ψ/∂t = Ĥψ","x":150,"y":100,"color":"#fbbf24","size":40}' say="Here it is. The Schrödinger equation." cursor="write" pause="0.5" />
<vb say="The left side tells you how psi changes in time." cursor="tap:200,100" pause="0.8" />
<vb say="The right side — the Hamiltonian — encodes all the physics." cursor="tap:450,100" pause="1.0" />
<vb draw='{"cmd":"circle","cx":300,"cy":110,"r":60,"color":"#34d399"}' say="This single equation drives everything." cursor="tap:300,110" pause="1.5" />
<vb say="What does the left side represent physically?" cursor="rest" question="true" />
</teaching-voice-scene>

═══ <vb> ATTRIBUTES ═══

say="..."       — Text to speak (TTS). Short sentences (under 20 words). Empty = silent beat.
draw='...'      — Board draw JSON command (same format as board-draw JSONL). Single command per beat.
                  Use single quotes around the JSON: draw='{"cmd":"text",...}'
cursor="..."    — Hand cursor: "write" (follows draw), "tap:x,y" (point+pulse), "point:x,y" (hover), "rest" (hidden)
pause="N"       — Seconds to wait after voice+draw complete. Use for breathing room.
question="true" — Final beat. Shows input bar after speaking. Scene stops here.

═══ ASSET BEATS ═══

Widgets:    <vb widget-title="..." widget-code="<div>...</div>" say="Try this interactive." cursor="rest" />
Simulations: <vb simulation="sim-id" say="Let me open a simulation." cursor="rest" />
Videos:     <vb video-lesson="6" video-start="245" video-end="280" say="Watch this clip." cursor="rest" />
Images:     <vb image-src="url" image-caption="..." say="Look at this." cursor="rest" />

═══ VOICE vs DRAWING — CRITICAL ═══

The say text is SPOKEN ALOUD. It is NOT a reading of what you draw.
You draw the math. You SAY the meaning. Like a real teacher:

  WRONG: <vb draw='{"cmd":"text","text":"iℏ ∂ψ/∂t = Ĥψ",...}' say="i h-bar d psi d t equals H hat psi" />
  RIGHT: <vb draw='{"cmd":"text","text":"iℏ ∂ψ/∂t = Ĥψ",...}' say="Here's the Schrödinger equation." />

  WRONG: <vb draw='{"cmd":"circle",...}' say="Drawing a circle around this." />
  RIGHT: <vb draw='{"cmd":"circle",...}' say="This is the key part." />

  WRONG: <vb say="F equals m a" />
  RIGHT: <vb say="Force equals mass times acceleration." />

Never read equations symbol-by-symbol. Say what they MEAN in plain English.
Never narrate your drawing actions. Say what the drawing REPRESENTS.

═══ ORCHESTRATION RULES ═══

1. ALWAYS draw before talking about it. Never say "as you can see" without a prior draw beat.
2. Short say text — under 20 words per beat. TTS sounds robotic with long sentences.
3. Alternate draw and say beats for natural rhythm: draw → say → draw → say.
4. After writing something important, add a tap + pause beat to let it land.
5. Use pause="0.5" to "1.5" generously. Pauses are where learning happens.
6. End with question="true" when you want the student to respond.
7. The cursor is the student's focus point. Always move it to what you're discussing.
8. Multiple draw commands? Use separate <vb> tags for each — one draw per beat.
9. Do NOT write any text outside the <teaching-voice-scene> tag. Everything goes inside beats.
10. You can still call tools (spawn_agent, advance_topic, etc.) BEFORE the scene tag.
11. Keep the cursor visible throughout. Move it to each new element. Only "rest" during pauses.
12. Use board space efficiently — start from top-left, keep text sizes reasonable (24-36 for content, 20-28 for labels).

═══ BOARD LAYOUT ═══

- Assign IDs to key elements: draw='{"cmd":"text",...,"id":"eq-schrodinger"}'
- Reference later: cursor="tap:id:eq-schrodinger" — scrolls to element and taps it
- Clear board between major concepts: <vb clear-before="true" draw='...' />
  (saves snapshot before clearing so student can scroll back in frame strip)
- Go back: <vb scroll-to="id:eq-newton" say="Remember this?" cursor="tap:id:eq-newton" />

Layout (virtual coords 0-800 width — gets SCALED to screen, so use SMALL sizes):
  Titles: x=40, size=20-22, color=#5eead4 (cyan)
  Equations: x=60-120, size=18-24, color=#fbbf24 (yellow)
  Labels/explanations: size=14-18, color=#e8d5b7 (white) or #9a9a9a (dim)
  Animations: side-by-side with text (x=40, w=350, h=150) or below (x=40, w=700, h=200)
  Keep 30px margins on sides, 25px vertical gaps between elements
  Leave bottom 50px clear for subtitle overlap
  CRITICAL: On a wide screen, size=24 in virtual coords renders as ~42px. Use size 14-20 for most text!

═══ CURSOR RULES ═══

All cursor positioning uses element IDs. NEVER guess raw coordinates.

  cursor="write"              — auto-follows the draw in this beat (pen at bottom of text)
  cursor="write:id:eq-main"   — pen pose at bottom of element eq-main
  cursor="tap:id:eq-main"     — tap center of element (pulse + scroll)
  cursor="point:id:eq-main"   — hover at center (no pulse)
  cursor="rest"               — hide cursor (use during pauses, questions)

Every drawn element MUST have an id. Use descriptive IDs:
  "title-main", "eq-schrodinger", "label-lhs", "anim-wave", "arrow-1"

═══ EPHEMERAL ANNOTATIONS ═══

Like a teacher circling on the whiteboard — appears then fades:

  annotate="circle:id:eq-main"       — hand-drawn circle, fades after 2s
  annotate="underline:id:label-1"    — wavy underline below element
  annotate="box:id:eq-schrodinger"   — rounded rectangle highlight
  annotate="glow:id:wave-anim"       — soft glow overlay (great for animations)

Optional: annotate-color="#fbbf24" annotate-duration="3000"

Example:
  <vb draw='{"cmd":"text","text":"F = ma","x":100,"y":100,"id":"eq-f"}' cursor="write" />
  <vb say="This is the key equation." cursor="tap:id:eq-f" annotate="circle:id:eq-f" pause="1.5" />
  <vb say="Force is on the left." annotate="underline:id:eq-f" annotate-color="#fbbf24" pause="1.0" />

Use annotations to direct attention. They fade automatically — like gesturing.

═══ ANIMATION CONTROL ═══

- Control active animation: anim-control='{"param":"value"}'
- Animation code reads _controlParams: if (_controlParams.bumpX) x = _controlParams.bumpX;
- Glow parts: annotate="glow:id:anim-wave"
- Example:
  <vb draw='{"cmd":"animation","id":"wave-anim","w":400,"h":200,"x":40,"y":200,"code":"..."}' say="Watch this." />
  <vb anim-control='{"speed":2}' say="Speeding it up." cursor="point:id:wave-anim" />
  <vb anim-control='{"bumpX":0.7}' say="See the bump shift?" cursor="tap:id:wave-anim" annotate="glow:id:wave-anim" />

═══ BOARD CONTEXT ═══

- Keep the board clean. Max ~15 elements per board.
- Clear before new concept section: <vb clear-before="true" ... />
- Previous board saved as snapshot in frame strip.
""")

    # Plan accountability — injected every turn so the tutor knows exactly where it is
    plan_acct = context_data.get("planAccountability")
    if plan_acct:
        acct_lines = ["[PLAN ACCOUNTABILITY — internal, never reveal to student]"]
        if plan_acct.get("section_title"):
            acct_lines.append(f"Section: \"{plan_acct['section_title']}\" ({plan_acct.get('section_n', '?')} of {plan_acct.get('section_total', '?')})")
        if plan_acct.get("topic_title"):
            acct_lines.append(f"Topic: \"{plan_acct['topic_title']}\" ({plan_acct.get('topic_n', '?')} of {plan_acct.get('topic_total', '?')} in section)")
        if plan_acct.get("detour_active"):
            acct_lines.append(f"Detour: ACTIVE — {plan_acct.get('detour_reason', 'prerequisite gap')}")
            acct_lines.append(f"Return to: \"{plan_acct.get('return_topic', '?')}\" when detour completes")
        done = plan_acct.get("done_count", 0)
        total = plan_acct.get("total_count", 0)
        pct = round(done / total * 100) if total else 0
        acct_lines.append(f"Progress: {done}/{total} topics ({pct}%)")
        acct_lines.append(
            "RULES: Finish current topic before advancing. "
            "For prereq gaps, call modify_plan(action='insert_prereq'). "
            "To skip a topic the student knows, call modify_plan(action='skip')."
        )
        parts.append("\n".join(acct_lines) + "\n")

    # ─── SECTION 4: EVENT CONTEXT ───────────────────────────────
    # One-shot events from this turn — agent results, assessments, delegation.
    has_events = any(context_data.get(k) for k in [
        "agentResults", "delegationResult", "assessmentResult"
    ])

    if has_events:
        parts.append("\n═══════════════════════════════════════════════════")
        parts.append(" EVENT CONTEXT — results from background processes")
        parts.append("═══════════════════════════════════════════════════\n")

    agent_results = context_data.get("agentResults")
    if agent_results:
        parts.append("[AGENT RESULTS — Background agents completed]\n")
        parts.append(agent_results)

    delegation_result = context_data.get("delegationResult")
    if delegation_result:
        parts.append("\n[DELEGATION RESULT — Sub-agent just finished]\n")
        parts.append(delegation_result)

    # Assessment result from a just-ended assessment checkpoint
    assessment_result = context_data.get("assessmentResult")
    if assessment_result:
        parts.append("\n═══════════════════════════════════════════════════")
        parts.append(" ASSESSMENT RESULTS — Checkpoint just completed")
        parts.append("═══════════════════════════════════════════════════\n")
        parts.append(assessment_result)
        parts.append(
            "\nThe student just finished an assessment checkpoint. "
            "Follow the AFTER ASSESSMENT RETURNS instructions in your prompt: "
            "invite the student to discuss the results, go through wrong answers "
            "ONE AT A TIME asking why they thought that, identify the specific mistake, "
            "provide the correct explanation grounded in course content. "
            "Use OPEN-ENDED questions (let them explain in words) not more MCQs. "
            "If a student gets the same concept wrong twice, STOP quizzing — "
            "explain it clearly and move on to teaching it differently. "
            "Do NOT pester with repeated MCQs. "
            "If the student got everything right, briefly acknowledge and move on. "
            "If the student declines review, respect that and continue teaching. "
            "Start with the most revealing wrong answer, not a data dump.\n\n"
            "CRITICAL — WEAK SCORE (<60%): Do NOT end the session. Do NOT just "
            "explain and say goodbye. A weak score means the student needs MORE "
            "help, not less. After brief review, PROPOSE continuing with a "
            "different teaching approach. Give the student a choice: "
            "'Want to try this from a different angle?' or 'I think a simulation "
            "might make this click — want to try?' Be the tutor who stays and "
            "helps, not the one who gives up. NEVER close a session immediately "
            "after a weak assessment."
        )

    # Post-assessment marker — persists through the review discussion turns
    # Reminds tutor it's in post-assessment phase until it advances topic
    pre_assessment_note = context_data.get("preAssessmentNote")
    if pre_assessment_note and not assessment_result:
        parts.append("\n[POST-ASSESSMENT PHASE]")
        parts.append(
            "You are reviewing checkpoint results with the student. "
            "Your conversation history has your full teaching context — "
            "refer to it to know where you left off. The assessment agent's "
            "notes (in the student model) have detailed observations about "
            "what the student got right/wrong and why. "
            "IMPORTANT: Do NOT keep quizzing the student with MCQs. "
            "Use open-ended questions. If they struggle twice on a concept, "
            "explain it clearly, then re-teach using a different modality. "
            "If the assessment was weak (<60%), do NOT end the session — "
            "propose continuing with a different approach. Give the student "
            "agency: offer to try a simulation, board-draw, or new angle. "
            "When discussion is complete and the student is ready, call "
            "advance_topic to resume teaching.\n"
        )
        parts.append(pre_assessment_note)


    dynamic_context = "\n".join(parts)
    return (static_prompt, dynamic_context)


def build_byo_tutor_prompt(context_data: dict) -> str:
    """Build tutor prompt for BYO (student-uploaded) collections.

    Uses MQL toolkit instead of curated course toolkit. The lean context
    snapshot replaces the full course map dump.
    """
    parts = [TUTOR_SYSTEM_PROMPT, MQL_TOOLKIT_PROMPT, TAGS_PROMPT]

    # Lean context snapshot (replaces full course map, concepts, simulations)
    lean_context = context_data.get("leanContext")
    if lean_context:
        parts.append("\n═══════════════════════════════════════════════════")
        parts.append(" COLLECTION CONTEXT (lean snapshot — use MQL tools for details)")
        parts.append("═══════════════════════════════════════════════════\n")
        parts.append(lean_context)

    # Student profile (if available)
    student_profile = context_data.get("studentProfile")
    if student_profile:
        parts.append(f"\n[Student Profile]\n{student_profile}\n")

    # Session metrics
    session_metrics = context_data.get("sessionMetrics")
    if session_metrics:
        parts.append(f"[Session Metrics]\n{session_metrics}\n")

    # Student model
    student_model = context_data.get("studentModel")
    if student_model:
        parts.append(f"[Student Model]\n{student_model}\n")

    # Agent results, delegation results, assessment results — same as curated
    agent_results = context_data.get("agentResults")
    if agent_results:
        parts.append("\n═══════════════════════════════════════════════════")
        parts.append(" AGENT RESULTS")
        parts.append("═══════════════════════════════════════════════════\n")
        parts.append(agent_results)

    assessment_result = context_data.get("assessmentResult")
    if assessment_result:
        parts.append("\n═══════════════════════════════════════════════════")
        parts.append(" ASSESSMENT RESULTS")
        parts.append("═══════════════════════════════════════════════════\n")
        parts.append(assessment_result)

    return "\n".join(parts)


def build_planning_prompt(context_data: dict) -> str:
    """Build planning agent system prompt with course context."""
    parts = [PLANNING_PROMPT]

    parts.append("\n═══════════════════════════════════════════════════")
    parts.append(" COURSE CONTEXT")
    parts.append("═══════════════════════════════════════════════════\n")

    field_labels = [
        ("studentProfile", "Student Profile"),
        ("courseMap", "Course Map"),
        ("concepts", "Course Concepts"),
        ("simulations", "Available Simulations"),
        ("knowledgeState", "Student Knowledge State"),
    ]
    for key, label in field_labels:
        val = context_data.get(key)
        if val:
            parts.append(f"[{label}]\n{val}\n")

    # Student model — tutor's evolving notes on this student
    student_model = context_data.get("studentModel")
    if student_model:
        parts.append(f"[Student Model — Tutor's Notes on This Student]\n{student_model}\n")

    # Tutor's recent notes — observations from teaching
    tutor_notes = context_data.get("tutorNotes")
    if tutor_notes:
        parts.append(f"[Recent Tutor Observations]\n{tutor_notes}\n")

    completed = context_data.get("completedTopics")
    if completed:
        parts.append(f"\n[Completed Topics So Far]\n{completed}\n")

    session_scope = context_data.get("sessionScope")
    if session_scope:
        parts.append(f"\n[Session Scope]\n{session_scope}\n")

    # Last assessment results — critical for adapting the plan
    last_assessment = context_data.get("lastAssessmentSummary")
    if last_assessment:
        import json as _json
        score = last_assessment.get("score", {})
        pct = score.get("pct", 0)
        weak = last_assessment.get("weakConcepts", [])
        strong = last_assessment.get("strongConcepts", [])

        parts.append("\n═══════════════════════════════════════════════════")
        parts.append(" MOST RECENT ASSESSMENT RESULTS — Use this to adapt the plan")
        parts.append("═══════════════════════════════════════════════════\n")
        parts.append(f"Section: {last_assessment.get('section', '?')}")
        parts.append(f"Score: {score.get('correct', 0)}/{score.get('total', 0)} ({pct}%)")
        parts.append(f"Mastery: {last_assessment.get('overallMastery', '?')}")
        if weak:
            parts.append(f"WEAK concepts: {', '.join(weak)}")
        if strong:
            parts.append(f"Strong concepts: {', '.join(strong)}")
        rec = last_assessment.get("recommendation", "")
        if rec:
            parts.append(f"Recommendation: {rec}")

        if pct < 60:
            parts.append(
                "\nThe student scored below 60%. Your plan MUST:"
                "\n- Prioritize re-teaching the weak concepts with a DIFFERENT approach"
                "\n- Use different modalities (if text failed, use simulation/video/board-draw)"
                "\n- Include scaffolding steps that build up to the weak concepts"
                "\n- Add targeted checkpoint moments for the weak areas"
                "\n- Adjust language/pace based on student model observations"
            )
        elif pct < 80:
            parts.append(
                "\nStudent is developing. Your plan should:"
                "\n- Reinforce weak areas with additional practice"
                "\n- Use the student's strongest modality for difficult concepts"
                "\n- Build bridges from strong concepts to weak ones"
            )
        parts.append("")

    return "\n".join(parts)


def build_assessment_prompt(context_data: dict) -> str:
    """Build assessment agent system prompt with brief and course context.

    The assessment brief comes from the tutor's <teaching-assessment-handoff>
    tag, forwarded by the frontend as context_data["assessmentBrief"].
    """
    import json

    # Build the assessment brief block from the handoff data
    brief_parts: list[str] = []

    brief = context_data.get("assessmentBrief")
    if brief:
        # Parse if it's a JSON string
        if isinstance(brief, str):
            try:
                brief = json.loads(brief)
            except (json.JSONDecodeError, TypeError):
                brief_parts.append(brief)
                brief = None

        if isinstance(brief, dict):
            section = brief.get("section", {})
            brief_parts.append(f"Section: [{section.get('index', '?')}] {section.get('title', 'Unknown')}")
            brief_parts.append(f"Concepts to Test: {', '.join(brief.get('conceptsTested', []))}")

            profile = brief.get("studentProfile", {})
            if profile:
                brief_parts.append(f"\nStudent Profile (from tutor):")
                if profile.get("weaknesses"):
                    brief_parts.append(f"  Weaknesses: {', '.join(profile['weaknesses']) if isinstance(profile['weaknesses'], list) else profile['weaknesses']}")
                if profile.get("strengths"):
                    brief_parts.append(f"  Strengths: {', '.join(profile['strengths']) if isinstance(profile['strengths'], list) else profile['strengths']}")
                if profile.get("engagementStyle"):
                    brief_parts.append(f"  Engagement Style: {profile['engagementStyle']}")

            plan = brief.get("plan", {})
            if plan:
                qc = plan.get("questionCount", {})
                brief_parts.append(f"\nQuestion Plan:")
                brief_parts.append(f"  Questions: {qc.get('min', 3)}-{qc.get('max', 5)}")
                brief_parts.append(f"  Start Difficulty: {plan.get('startDifficulty', 'medium')}")
                if plan.get("types"):
                    brief_parts.append(f"  Preferred Types: {', '.join(plan['types'])}")
                if plan.get("focusAreas"):
                    brief_parts.append(f"  Focus Areas: {', '.join(plan['focusAreas']) if isinstance(plan['focusAreas'], list) else plan['focusAreas']}")
                if plan.get("avoid"):
                    brief_parts.append(f"  Skip/Minimize: {', '.join(plan['avoid']) if isinstance(plan['avoid'], list) else plan['avoid']}")

            concept_notes = brief.get("conceptNotes", {})
            if concept_notes:
                brief_parts.append(f"\nConcept Notes (from tutor's observations):")
                for cname, note in concept_notes.items():
                    brief_parts.append(f"  {cname}: {note}")

            grounding = brief.get("contentGrounding", {})
            if grounding:
                brief_parts.append(f"\nContent Grounding:")
                brief_parts.append(f"  Lesson ID: {grounding.get('lessonId', '?')}")
                brief_parts.append(f"  Section Indices: {grounding.get('sectionIndices', [])}")
                if grounding.get("keyExamples"):
                    brief_parts.append(f"  Key Examples: {', '.join(grounding['keyExamples'])}")
                if grounding.get("professorPhrasing"):
                    brief_parts.append(f"  Professor's Phrasing: {grounding['professorPhrasing']}")

    # Assessment progress (for mid-assessment turns)
    progress = context_data.get("assessmentProgress")
    if progress:
        if isinstance(progress, str):
            try:
                progress = json.loads(progress)
            except (json.JSONDecodeError, TypeError):
                pass
        if isinstance(progress, dict):
            brief_parts.append(f"\nAssessment Progress So Far:")
            brief_parts.append(f"  Questions Asked: {progress.get('questionsAsked', 0)}/{progress.get('maxQuestions', 5)}")
            brief_parts.append(f"  Current Difficulty: {progress.get('currentDifficulty', 'medium')}")
            results = progress.get("results", [])
            if results:
                correct = sum(1 for r in results if r.get("correct"))
                brief_parts.append(f"  Score: {correct}/{len(results)}")
                for r in results:
                    status = "correct" if r.get("correct") else "incorrect"
                    brief_parts.append(f"    - {r.get('concept', '?')} ({r.get('questionType', '?')}, {r.get('difficulty', '?')}): {status}")

    brief_text = "\n".join(brief_parts) if brief_parts else "No assessment brief provided."

    # Assemble the prompt: assessment system prompt + assessment-specific toolkit + tags + context
    parts = [
        ASSESSMENT_SYSTEM_PROMPT.replace("{assessment_brief}", brief_text),
        _ASSESSMENT_TOOLKIT,
        TAGS_PROMPT,
    ]

    # Course context (lighter than tutor — no simulations, no plan, no agents)
    parts.append("\n═══════════════════════════════════════════════════")
    parts.append(" COURSE CONTEXT")
    parts.append("═══════════════════════════════════════════════════\n")

    for key, label in [
        ("studentProfile", "Student Profile"),
        ("courseMap", "Course Map"),
        ("concepts", "Course Concepts"),
        ("sessionMetrics", "Session Metrics"),
    ]:
        val = context_data.get(key)
        if val:
            parts.append(f"[{label}]\n{val}\n")

    knowledge_summary = context_data.get("knowledgeSummary")
    if knowledge_summary:
        parts.append(f"[Student Knowledge State]\n{knowledge_summary}\n")

    student_model = context_data.get("studentModel")
    if student_model:
        parts.append(f"[Student Notes]\n{student_model}\n")

    return "\n".join(parts)


# Assessment-specific toolkit (lighter than tutor — no agent orchestration)
_ASSESSMENT_TOOLKIT = """═══ YOUR TOOLS (Assessment Mode) ═══

You have a focused subset of tools for assessment:

get_section_content(lesson_id, section_index)
  Fetch the professor's transcript, key points, and formulas for a section.
  Use to ground your questions in exact course content.

query_knowledge(query)
  Look up what you know about this student's understanding of a concept.
  Use before questioning to calibrate difficulty.

update_student_model(notes)
  Record your assessment observations. Call ONCE at the end with all results.
  Each note: { concepts: ["concept_name"], note: "Assessment: ..." }

search_images(query, limit)
  Find images if you need a visual for a question scenario.

web_search(query, limit)
  Supplementary info for question grounding (rare — prefer course content).

TOOLS YOU DO NOT HAVE (assessment is focused):
  spawn_agent, check_agents, delegate_teaching, advance_topic, reset_plan,
  control_simulation, request_board_image

Keep it simple: read content → ask question → evaluate → log."""
