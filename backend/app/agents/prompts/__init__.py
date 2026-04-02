from .tutor import TUTOR_SYSTEM_PROMPT, build_tutor_system_prompt
from .planning import PLANNING_PROMPT
from .toolkit import TOOLKIT_PROMPT
from .tags import TAGS_PROMPT
from .assessment import ASSESSMENT_SYSTEM_PROMPT
from .teaching_delegate import build_delegation_prompt
from .voice import build_voice_mode_prompt
from .scenarios.course_follow import SKILL_COURSE
from .scenarios.exam import SKILL_EXAM_FULL
from .scenarios.exam_topic import SKILL_EXAM_TOPIC
from .scenarios.conceptual import SKILL_CONCEPTUAL
from .scenarios.curiosity import SKILL_FREE
from .scenarios.video_follow import SKILL_VIDEO_FOLLOW

SKILL_MAP: dict[str, str | None] = {
    "course": SKILL_COURSE,
    "exam_full": SKILL_EXAM_FULL,
    "exam_topic": SKILL_EXAM_TOPIC,
    "problem": None,
    "conceptual": SKILL_CONCEPTUAL,
    "free": SKILL_FREE,
    "video_follow": SKILL_VIDEO_FOLLOW,
}


# ── Subject detection ──────────────────────────────────────────────────

# Map course tags/titles to subject profile IDs
_SUBJECT_KEYWORDS = {
    "physics": ["physics", "mechanics", "thermodynamics", "optics", "electromagnetism", "quantum"],
    "mathematics": ["math", "calculus", "algebra", "geometry", "statistics", "differential", "linear algebra"],
    "chemistry": ["chemistry", "organic", "inorganic", "biochemistry", "chemical"],
    "biology": ["biology", "genetics", "ecology", "anatomy", "physiology", "microbiology", "neuroscience"],
    "business": ["business", "economics", "finance", "marketing", "management", "accounting", "strategy"],
    "computer_science": ["computer", "programming", "algorithm", "data structure", "software", "machine learning", "AI"],
}


def _detect_subject(context_data: dict) -> str | None:
    """Detect the subject from course metadata or session context.

    Checks course tags, title, and description for subject keywords.
    Returns a subject profile ID or None for general mode.
    """
    import json

    # Check course map for subject tags
    course_map_str = context_data.get("courseMap", "")
    if course_map_str:
        try:
            course_map = json.loads(course_map_str) if isinstance(course_map_str, str) else course_map_str
            title = (course_map.get("title") or "").lower()
            tags = [t.lower() for t in (course_map.get("tags") or [])]
            desc = (course_map.get("description") or "").lower()
            search_text = f"{title} {' '.join(tags)} {desc}"

            for subject_id, keywords in _SUBJECT_KEYWORDS.items():
                if any(kw in search_text for kw in keywords):
                    return subject_id
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    # Check student profile for subject hints
    profile_str = context_data.get("studentProfile", "")
    if profile_str:
        try:
            profile = json.loads(profile_str) if isinstance(profile_str, str) else profile_str
            course_title = (profile.get("courseTitle") or "").lower()
            for subject_id, keywords in _SUBJECT_KEYWORDS.items():
                if any(kw in course_title for kw in keywords):
                    return subject_id
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    return None  # General mode — no subject-specific instructions


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


def _get_voice_mode_prompt() -> str:
    """Voice mode instructions — from voice/ module, placed in STATIC block for prompt caching."""
    return build_voice_mode_prompt()


def build_tutor_prompt(context_data: dict) -> str | tuple[str, str]:
    """Build tutor system prompt.

    Returns a tuple (static_prompt, dynamic_context) for prompt caching.
    The static part is cacheable (instructions + tags). The dynamic part
    changes every turn (student profile, board state, plan, etc.).
    """
    # Compile per-student teaching overrides from _profile notes
    teaching_overrides = _compile_teaching_overrides(context_data)

    # STATIC: tutor instructions + toolkit + tags (cacheable — identical for all students in same mode)
    teaching_mode = context_data.get("teachingMode", "text")
    is_voice = teaching_mode == "voice"

    # Detect subject from course metadata or session context
    subject_id = _detect_subject(context_data)
    tutor_prompt = build_tutor_system_prompt(voice_mode=is_voice, subject_id=subject_id)
    static_parts = [tutor_prompt, TOOLKIT_PROMPT, TAGS_PROMPT]

    scenario_skill = context_data.get("scenarioSkill")
    if scenario_skill:
        static_parts.append(scenario_skill)

    # Voice mode instructions go in STATIC block (mode is locked for entire session)
    if is_voice:
        static_parts.append(_get_voice_mode_prompt())

    static_prompt = "\n".join(static_parts)

    # DYNAMIC: context that changes per turn (not cacheable)
    parts = []

    # ─── SECTION 0: SESSION PHASE (triage overlay) ──────────────
    session_phase = context_data.get("sessionPhase")
    if session_phase == "triage":
        from app.agents.prompts.triage import TRIAGE_SYSTEM_PROMPT
        parts.append("\n═══════════════════════════════════════════════════")
        parts.append(" CURRENT MODE: TRIAGE — diagnostic before teaching")
        parts.append("═══════════════════════════════════════════════════\n")
        parts.append(TRIAGE_SYSTEM_PROMPT)
        # Include triage-specific context
        triage_ctx = context_data.get("triageContext") or {}
        if triage_ctx.get("contentBrief"):
            parts.append(f"\n{triage_ctx['contentBrief']}\n")
        elif triage_ctx.get("availableContent"):
            parts.append(f"\n[AVAILABLE CONTENT]\n{triage_ctx['availableContent']}\n")
        if triage_ctx.get("upcomingTopics"):
            parts.append(f"\n[UPCOMING TOPICS]\n{triage_ctx['upcomingTopics']}\n")
        if triage_ctx.get("lastAssessment"):
            parts.append(f"\n[LAST ASSESSMENT]\n{triage_ctx['lastAssessment']}\n")
        parts.append("")

    # ─── SECTION 0b: TEACHING OVERRIDES (per-student) ──────────
    if teaching_overrides:
        parts.append(teaching_overrides)
        parts.append("")

    # ─── COURSE CONTEXT ── REMOVED from per-turn injection ─────
    # Course map, concepts, simulations are NO LONGER sent every turn.
    # The planner gets them at session start. The tutor uses content_map tool on demand.
    # This saves ~1700 tokens per turn (~34,000 tokens per 20-turn session).

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

    # Video follow-along state
    video_state_raw = context_data.get("videoState")
    if video_state_raw:
        import json as _json
        try:
            vs = _json.loads(video_state_raw) if isinstance(video_state_raw, str) else video_state_raw
        except (ValueError, TypeError):
            vs = {}
        if vs:
            parts.append("[VIDEO FOLLOW-ALONG — Student paused a lecture video]")
            parts.append(f"Lesson: {vs.get('lessonTitle', '?')} (ID: {vs.get('lessonId', '?')})")
            parts.append(f"Paused at: {vs.get('currentTimestamp', 0):.0f}s")
            parts.append(f"Section: [{vs.get('currentSectionIndex', 0)}] {vs.get('sectionTitle', '?')}")
            parts.append("The student paused to ask you a question.\n")

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

    # Voice mode instructions are now in the STATIC block for prompt caching.
    # (see _get_voice_mode_prompt() called in static_parts above)

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


    # Housekeeping: signal is always expected, notes only every 5th turn
    housekeeping_due = context_data.get("_housekeepingDue", False)
    if housekeeping_due:
        parts.append(
            "\n[HOUSEKEEPING DUE — Include <teaching-housekeeping> with BOTH signal AND notes at the end of this message. "
            "Write your complete current understanding of the student per concept.]\n"
        )

    dynamic_context = "\n".join(parts)
    return (static_prompt, dynamic_context)


def build_planning_prompt(context_data: dict) -> str:
    """Build planning agent system prompt — works for course, BYO, and on-demand sessions."""
    from .planning import PLANNING_PROMPT
    parts = [PLANNING_PROMPT]

    # Determine grounding mode
    has_course = bool(context_data.get("courseMap"))

    if has_course:
        parts.append("\n[Course Map]\n" + str(context_data["courseMap"])[:3000])

        concepts = context_data.get("concepts")
        if concepts:
            parts.append(f"\n[Course Concepts]\n{concepts[:1000]}")

        sims = context_data.get("simulations")
        if sims:
            parts.append(f"\n[Available Simulations]\n{sims[:500]}")
    else:
        parts.append("\n[No course available — plan from your own knowledge of this subject. Do NOT try to call any tools.]")

    # BYO / session context (enriched intent, collection info)
    session_ctx_str = context_data.get("sessionContext", "")
    if session_ctx_str:
        try:
            import json as _j
            ctx = _j.loads(session_ctx_str) if isinstance(session_ctx_str, str) else session_ctx_str
            enriched = ctx.get("enriched_intent", "")
            if enriched:
                parts.append(f"\n[Enriched Intent]\n{enriched[:500]}")
            teaching_notes = ctx.get("teaching_notes", "")
            if teaching_notes:
                parts.append(f"\n[Teaching Notes]\n{teaching_notes[:500]}")
        except (ValueError, TypeError, AttributeError):
            pass

    # Student context (works for all modes)
    profile = context_data.get("studentProfile")
    if profile:
        parts.append(f"\n[Student Profile]\n{profile[:500]}")

    student_model = context_data.get("studentModel")
    if student_model:
        parts.append(f"\n[Student Model]\n{student_model[:500]}")

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
