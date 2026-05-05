from .tutor import build_tutor_system_prompt
from .planning import PLANNING_SYSTEM_PROMPT, build_planning_prompt as _build_planning_prompt_base
from .toolkit import TOOLKIT_PROMPT
from .tags import TAGS_PROMPT
from .assessment import ASSESSMENT_SYSTEM_PROMPT
from .teaching_delegate import build_delegation_prompt
from .voice import build_voice_mode_prompt


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
    """Detect the subject from session context.

    Checks the student intent and session context for subject keywords.
    Returns a subject profile ID or None for general mode.
    """
    import json

    candidates: list[str] = []

    profile_str = context_data.get("studentProfile", "")
    if profile_str:
        try:
            profile = json.loads(profile_str) if isinstance(profile_str, str) else profile_str
            for k in ("subject", "topic", "intent", "studentIntent"):
                v = profile.get(k)
                if isinstance(v, str):
                    candidates.append(v.lower())
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    sc = context_data.get("sessionContext", "")
    if sc:
        try:
            sc_obj = json.loads(sc) if isinstance(sc, str) else sc
            for k in ("subject", "topic", "intent"):
                v = sc_obj.get(k) if isinstance(sc_obj, dict) else None
                if isinstance(v, str):
                    candidates.append(v.lower())
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    if not candidates:
        return None

    search_text = " ".join(candidates)
    for subject_id, keywords in _SUBJECT_KEYWORDS.items():
        if any(kw in search_text for kw in keywords):
            return subject_id

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
    """Parse session metrics and inject NEW_STUDENT or RETURNING_STUDENT tag.

    For on-demand / DSA / SD sessions that don't have course metrics,
    fall back to counting the user's total sessions in MongoDB so that
    the "first ever session" intro doesn't fire on every topic.
    """
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

    # Fallback for on-demand / DSA / SD sessions: count total sessions for this user
    if not session_count:
        user_email = context_data.get("userEmail", "")
        if user_email:
            try:
                from app.core.mongodb import get_tutor_db
                import asyncio
                db = get_tutor_db()
                # Quick count — use the sync pymongo method via motor's underlying client
                _count = db.sessions.delegate.count_documents(
                    {"userEmail": user_email}, limit=10
                )
                session_count = _count
            except Exception:
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

    Two sources of adaptation:
      1. _profile notes (observed across sessions) → explicit overrides
      2. Smart defaults (when no _profile exists yet) → explain-first

    Returns an override block string injected into the tutor's prompt.
    """
    import json as _json

    student_model = context_data.get("studentModel", "")
    has_profile = False
    profile_text = ""

    if student_model:
        try:
            model = _json.loads(student_model) if isinstance(student_model, str) else student_model
        except (ValueError, TypeError):
            model = {}

        # Find _profile notes
        notes = model.get("notes", [])
        if isinstance(notes, list):
            for note in notes:
                concepts = note.get("concepts", [])
                if "_profile" in concepts:
                    profile_text += note.get("note", "") + "\n"
                    has_profile = True
        elif isinstance(notes, dict):
            for key, note in notes.items():
                if "_profile" in key:
                    if isinstance(note, str):
                        profile_text += note + "\n"
                    elif isinstance(note, dict):
                        profile_text += note.get("note", "") + "\n"
                    has_profile = True

    overrides = []
    overrides.append("═══ TEACHING STYLE — THIS STUDENT ═══")
    overrides.append("")

    if has_profile and profile_text.strip():
        # ── Known student: override from observations ──
        overrides.append("OBSERVED TEACHING PROFILE (from past sessions):")
        overrides.append(profile_text.strip())
        overrides.append("")
        overrides.append("APPLY THESE OBSERVATIONS:")
        overrides.append("  - Honor specific modality/style preferences recorded above.")
        overrides.append("  - If notes say 'approach X worked' → use approach X again.")
        overrides.append("  - If notes say 'approach X failed' → use a DIFFERENT approach.")
        overrides.append("  - TOPIC-SPECIFIC observations override general preferences.")
        overrides.append("  - Keep adapting: if something new works, update the profile.")
    else:
        # ── New student (session 1): smart defaults ──
        overrides.append("NEW STUDENT — no profile yet. Using evidence-based defaults:")
        overrides.append("")
        overrides.append("DEFAULT TEACHING STYLE: EXPLAIN FIRST")
        overrides.append("  - Lead with direct explanations + worked examples.")
        overrides.append("  - Do NOT default to Socratic questioning.")
        overrides.append("  - Use questions for VERIFICATION (after explaining), not discovery.")
        overrides.append("  - Keep responses SHORT (1-2 sentences in chat, content on board).")
        overrides.append("  - If the student asks 'why?' or challenges your explanation,")
        overrides.append("    THAT is the moment to go deeper / use Socratic — they're ready.")
        overrides.append("")
        overrides.append("SIGNAL DETECTION (update _profile after observing):")
        overrides.append("  - Asks 'why?' / 'what if?' → curious, try Socratic next topic")
        overrides.append("  - Short replies ('ok', 'yeah') → keep explaining, don't probe")
        overrides.append("  - 'Just tell me' → frustrated, give direct answers")
        overrides.append("  - Solves fast → advanced, skip scaffolding, challenge harder")
        overrides.append("  - Long pauses → needs smaller steps, more visuals")

    # Add topic-type specific guidance if available
    current_topic = context_data.get("currentTopic", "")
    if current_topic:
        try:
            topic = _json.loads(current_topic) if isinstance(current_topic, str) else current_topic
            if isinstance(topic, dict):
                steps = topic.get("steps", [])
                if steps and isinstance(steps, list):
                    delivery = steps[0].get("delivery_pattern", "")
                    if delivery:
                        overrides.append("")
                        overrides.append(f"CURRENT TOPIC DELIVERY HINT: {delivery}")
                        overrides.append("  Adapt your style to this pattern, but student")
                        overrides.append("  preferences (above) take priority.")
        except (ValueError, TypeError, IndexError, KeyError):
            pass

    return "\n".join(overrides)


def _get_voice_mode_prompt() -> str:
    """Voice mode instructions — from voice/ module, placed in STATIC block for prompt caching."""
    return build_voice_mode_prompt()


def _inject_path_context(parts: list[str], context_data: dict):
    """Inject learning path context when this session is part of a path.

    Gives the tutor:
      - Full path plan with node statuses (completed/active/pending)
      - ALL reflection notes from any prior session (not just sequential)
      - Student's wizard answers (goal, background, depth)
      - Whether the student jumped out of order
      - Handover instructions from the last reflection
      - Upcoming nodes for foreshadowing
    """
    import json as _json

    path_context = context_data.get("pathContext")
    if not path_context:
        return

    if isinstance(path_context, str):
        try:
            path_context = _json.loads(path_context)
        except (ValueError, TypeError):
            return

    if not isinstance(path_context, dict):
        return

    cur = path_context.get("currentNode", {})
    node_title = cur.get("title", "")
    node_type = cur.get("type", "")
    node_order = cur.get("order", 0)
    node_topics = cur.get("topics", [])
    total_nodes = path_context.get("totalNodes", 0)
    completed = path_context.get("completedCount", 0)

    # ── Focus subtopic resolution ──────────────────────────────────
    # Three sources, in order of priority:
    #   1. Live `focusSubtopic` (per-turn, set by FE when student clicked
    #      a specific Learn → button)
    #   2. `currentNode.studentNote` parsed for "Start from: X"
    #   3. None
    import re as _re
    focus_subtopic = (path_context.get("focusSubtopic") or "").strip()
    student_note_raw = (cur.get("studentNote") or "").strip()
    if not focus_subtopic and student_note_raw:
        _m = _re.match(r"^\s*Start from:\s*(.+)$", student_note_raw, _re.IGNORECASE)
        if _m:
            focus_subtopic = _m.group(1).strip()
    # The "general" note is whatever's left after we've extracted the
    # "Start from: X" directive (so we don't double-surface it).
    student_note_general = "" if (
        student_note_raw.lower().startswith("start from:") and focus_subtopic
    ) else student_note_raw

    parts.append("\n═══════════════════════════════════════════════════")
    parts.append(" PATH CONTEXT — this session is part of a structured learning path")
    parts.append("═══════════════════════════════════════════════════\n")
    parts.append(f"Path: {path_context.get('title', '')}")
    parts.append(f"Description: {path_context.get('description', '')}")
    parts.append(f"Current node: {node_order}/{total_nodes} — \"{node_title}\" ({node_type})")
    parts.append(f"Progress: {completed}/{total_nodes} completed")

    # ── Subtopic list — mark focus + which were already covered ─────
    # "Covered" = appeared as a strength tag/concept in a prior reflection
    # for this same node. (Gaps are still incomplete by definition.)
    prior_for_subtopics = path_context.get("priorNotes", {}) or {}
    _covered_terms: set[str] = set()
    cur_node_id = cur.get("nodeId")
    for _s in prior_for_subtopics.get("strengths", []):
        if _s.get("nodeId") == cur_node_id:
            _concept = (_s.get("concept") or "").strip().lower()
            if _concept:
                _covered_terms.add(_concept)
            for _tag in (_s.get("tags") or []):
                _t = str(_tag).strip().lower()
                if _t:
                    _covered_terms.add(_t)

    def _is_covered(topic: str) -> bool:
        t = (topic or "").strip().lower()
        if not t:
            return False
        if t in _covered_terms:
            return True
        # Loose token match — handles "gradient descent" matching tag "gradient_descent"
        norm = t.replace("_", " ").replace("-", " ")
        return any(
            norm == c.replace("_", " ").replace("-", " ")
            or norm in c.replace("_", " ").replace("-", " ")
            or c.replace("_", " ").replace("-", " ") in norm
            for c in _covered_terms
        )

    if node_topics:
        _topic_lines = []
        _focus_lower = focus_subtopic.lower() if focus_subtopic else ""
        for t in node_topics:
            tag = ""
            if focus_subtopic and t.strip().lower() == _focus_lower:
                tag = " ← FOCUS (start here)"
            elif _is_covered(t):
                tag = " ✓ (covered in prior session — light-touch only)"
            _topic_lines.append(f"  • {t}{tag}")
        parts.append("This node covers:")
        parts.extend(_topic_lines)
    elif focus_subtopic:
        parts.append(f"FOCUS: \"{focus_subtopic}\"")

    # Strong directive when a specific subtopic was clicked
    if focus_subtopic:
        parts.append("")
        parts.append(
            f"⚡ STUDENT CLICKED \"{focus_subtopic}\" — START THERE."
        )
        parts.append(
            "  • Open the session on this subtopic specifically."
        )
        parts.append(
            "  • Other topics in this node are fair game later, but lead with this one."
        )
        parts.append(
            "  • If the focus is one slice of a broader concept, say so explicitly: "
            "\"You picked X — let's go deep on that. We'll come back to Y, Z after.\""
        )

    # Student's self-reported calibration note for THIS node
    if student_note_general:
        parts.append(f"\nSTUDENT'S OWN NOTE FOR THIS NODE: \"{student_note_general}\"")
        parts.append("  → Honor this. If they say they know X, skip it. If they want practice, give problems.")

    # Wizard context
    wizard = path_context.get("wizard", {})
    if wizard:
        parts.append(f"\nStudent profile (from path setup):")
        for k, v in wizard.items():
            if v and k != "intent":
                parts.append(f"  {k}: {v}")

    # Out-of-order jump detection
    if path_context.get("skippedAhead"):
        parts.append(
            "\n⚠ STUDENT JUMPED AHEAD — there are uncompleted nodes before this one. "
            "Don't assume they covered earlier topics. Ask if unclear about prerequisites."
        )

    # Full path plan overview (compact)
    node_map = path_context.get("nodeMap", [])
    if node_map:
        parts.append("\nFULL PATH PLAN:")
        for nm in node_map:
            status = nm.get("status", "pending")
            marker = {"completed": "✓", "active": "▶", "skipped": "⏭"}.get(status, "○")
            current_marker = " ← YOU ARE HERE" if nm.get("nodeId") == cur.get("nodeId") else ""
            sn = f' — student says: "{nm["studentNote"]}"' if nm.get("studentNote") else ""
            parts.append(
                f"  {marker} {nm['order']}. {nm['title']} ({nm['type']}, {nm['targetMin']}m)"
                f"{current_marker}{sn}"
            )

    # ── Prior notes (from ALL touched sessions, not just sequential) ──
    prior = path_context.get("priorNotes", {})

    strengths = prior.get("strengths", [])
    if strengths:
        parts.append("\nSTRENGTHS (demonstrated in prior sessions — don't re-teach unless asked):")
        for s in strengths:
            node_ref = f" [from node {s.get('nodeId', '?')}]" if s.get("nodeId") else ""
            parts.append(f"  ✓ {s.get('concept', '')}: {s.get('detail', '')}{node_ref}")

    gaps = prior.get("gaps", [])
    if gaps:
        parts.append("\nGAPS (struggled in prior sessions — reinforce proactively):")
        for g in gaps:
            node_ref = f" [from node {g.get('nodeId', '?')}]" if g.get("nodeId") else ""
            parts.append(f"  ⚠ {g.get('concept', '')}: {g.get('detail', '')}{node_ref}")

    handovers = prior.get("handovers", [])
    if handovers:
        parts.append("\nHANDOVER INSTRUCTIONS (from reflection agent — follow these):")
        for h in handovers:
            parts.append(f"  → {h.get('detail', '')}")

    observations = prior.get("observations", [])
    if observations:
        parts.append("\nOBSERVATIONS (general notes from prior sessions):")
        for o in observations:
            parts.append(f"  · {o.get('detail', '')}")

    # Upcoming nodes
    upcoming = path_context.get("upcomingNodes", [])
    if upcoming:
        parts.append("\nUPCOMING (so you can foreshadow and connect):")
        for u in upcoming:
            topics = ", ".join(u.get("topics", []))
            parts.append(f"  {u['order']}. {u['title']} ({u['type']}){f' — {topics}' if topics else ''}")

    # Recent pivots (path was modified)
    pivots = path_context.get("recentPivots", [])
    if pivots:
        accepted = [p for p in pivots if p.get("accepted")]
        if accepted:
            parts.append(f"\nPATH WAS RECENTLY MODIFIED: {accepted[-1].get('reason', '')}")

    # Node-type-specific instructions
    parts.append(f"\n── NODE TYPE: {node_type.upper()} ──")
    if node_type == "learn":
        parts.append("Teach the concepts using the board with animations and worked examples.")
        parts.append("Use BYO materials if available. End with a quick pulse check to verify understanding.")
        parts.append("Focus specifically on: " + (", ".join(node_topics) if node_topics else node_title))
    elif node_type == "drill":
        parts.append("This is a practice session. Push problems to the code editor using push_code.")
        parts.append("Let the student solve, give hints only when stuck. Track which they get right.")
        parts.append("Use run_code to test their solutions. Aim for 3-5 problems.")
    elif node_type == "quiz":
        parts.append("Run a focused assessment: 5-8 questions covering this node's topics.")
        parts.append("Keep it to 10-15 minutes. Report results clearly at the end.")
        parts.append("Results feed the reflection agent to update the path.")
    elif node_type == "build":
        parts.append("Guide a hands-on project. The student should produce something tangible.")
        parts.append("Use push_code for starter code, then let them drive implementation.")
        parts.append("Break it into clear milestones. This should feel like building, not lecturing.")

    parts.append(
        "\n── PATH RULES ──"
        "\n• Reference prior findings naturally ('You nailed register access last time — let's build on that')"
        "\n• Don't re-teach strengths unless the student asks"
        "\n• Address gaps proactively — weave remediation into this node's content"
        "\n• If the student jumped ahead, check prerequisites don't assume prior coverage"
        "\n• Your <notes> will feed the reflection agent — tag concepts clearly"
        "\n• Stay focused on THIS node's topics — don't drift to other nodes"
    )
    parts.append("")


def build_tutor_prompt(context_data: dict) -> str | tuple[str, str]:
    """Build tutor system prompt.

    Returns a tuple (static_prompt, dynamic_context) for prompt caching.
    The static part is cacheable (instructions + tags). The dynamic part
    changes every turn (student profile, board state, plan, etc.).
    """
    # Compile per-student teaching overrides from _profile notes
    teaching_overrides = _compile_teaching_overrides(context_data)

    # STATIC: tutor instructions + toolkit + tags (cacheable — identical for all students)

    # Detect subject from course metadata or session context
    subject_id = _detect_subject(context_data)
    session_mode = context_data.get("session_mode", "general")
    # Extract mock company for company-specific prompt composition
    _mock_company = None
    if session_mode == "mock_interview":
        try:
            import json as _mj
            _sc_raw = context_data.get("sessionContext", "")
            _sc_parsed = _mj.loads(_sc_raw) if isinstance(_sc_raw, str) and _sc_raw else (_sc_raw if isinstance(_sc_raw, dict) else {})
            _mock_company = _sc_parsed.get("company") or _sc_parsed.get("interviewState", {}).get("company")
        except Exception:
            pass
    prompt_sections = context_data.get("prompt_sections")
    tutor_prompt = build_tutor_system_prompt(
        prompt_sections=prompt_sections,
        subject_id=subject_id,
        session_mode=session_mode,
        mock_company=_mock_company,
    )
    static_parts = [tutor_prompt, TOOLKIT_PROMPT, TAGS_PROMPT]

    # Voice mode instructions (locked for entire session — voice is the only mode)
    static_parts.append(_get_voice_mode_prompt())

    # ── SESSION-STABLE content (cacheable within a session) ──
    # Teaching plan, BYO preloaded content — same for every turn in this session.
    # Appended to static_parts BEFORE joining so they're inside the cached block.

    teaching_plan = context_data.get("teachingPlan")
    if teaching_plan:
        try:
            import json as _tpj
            _tp = _tpj.loads(teaching_plan) if isinstance(teaching_plan, str) else teaching_plan
            _deep = _tp.pop("deep_content", None)

            _core = _tp.pop("core_insight", None)
            _framework = _tp.pop("framework", None)
            _patterns = _tp.pop("patterns", None)
            _hard = _tp.pop("what_makes_it_hard", None)
            _faang = _tp.pop("faang_expectations", None)
            _visuals = _tp.pop("visual_ideas", None)
            _probs = _tp.pop("problems_by_purpose", None)
            _cp = _tp.pop("competitive_programming", None)
            _connects = _tp.pop("connects_to", None)

            _plan_parts = [f"\n═══ TEACHING PLAN — {_tp.get('title', 'Topic')} ═══\n"]

            if _core:
                _plan_parts.append("\n## CORE INSIGHT — the one thing the student must understand\n")
                _plan_parts.append(f"{_core if isinstance(_core, str) else _tpj.dumps(_core, indent=2)}\n")

            if _framework:
                _plan_parts.append("\n## FRAMEWORK — reusable code templates (use these to teach)\n")
                if isinstance(_framework, str):
                    _plan_parts.append(f"{_framework}\n")
                elif isinstance(_framework, dict):
                    if _framework.get('description'):
                        _plan_parts.append(f"{_framework['description']}\n")
                    for tmpl in (_framework.get('code_templates') or []):
                        if isinstance(tmpl, dict):
                            _plan_parts.append(f"\n### {tmpl.get('name', 'Template')}\n{tmpl.get('code', '')}\n")
                        elif isinstance(tmpl, str):
                            _plan_parts.append(f"\n{tmpl}\n")

            if _patterns:
                _plan_parts.append("\n## PATTERNS — sub-patterns the student must learn to recognize\n")
                for i, p in enumerate(_patterns, 1):
                    if isinstance(p, dict):
                        _plan_parts.append(f"\n### Pattern {i}: {p.get('name', '?')}")
                        _recog = p.get('recognition') or p.get('description') or p.get('when', '')
                        if _recog:
                            _plan_parts.append(f"\nWhen to use: {_recog}")
                        _hint = p.get('template_hint') or ''
                        if _hint:
                            _plan_parts.append(f"\nApproach: {_hint}")
                        probs = p.get('classic_problems') or p.get('examples') or []
                        if probs:
                            prob_strs = []
                            for pr in probs[:4]:
                                if isinstance(pr, dict):
                                    lc = pr.get('leetcode') or pr.get('leetcode_number') or '?'
                                    prob_strs.append(f"LC {lc} {pr.get('name', '')} ({pr.get('difficulty', '?')})")
                                elif isinstance(pr, str):
                                    prob_strs.append(pr)
                            _plan_parts.append(f"\nProblems: {', '.join(prob_strs)}")
                        _diff = p.get('difficulty_range', '')
                        if _diff:
                            _plan_parts.append(f"\nDifficulty: {_diff}\n")

            if _hard:
                _plan_parts.append("\n## WHAT MAKES IT HARD — failure modes to watch for\n")
                if isinstance(_hard, str):
                    _plan_parts.append(f"{_hard}\n")
                elif isinstance(_hard, list):
                    for item in _hard:
                        if isinstance(item, str):
                            _plan_parts.append(f"  - {item}\n")
                        elif isinstance(item, dict):
                            _plan_parts.append(f"  - {item.get('issue', item.get('name', ''))}: {item.get('description', item.get('detail', ''))}\n")
                else:
                    _plan_parts.append(f"{_tpj.dumps(_hard, indent=2)}\n")

            if _faang:
                _plan_parts.append("\n## FAANG EXPECTATIONS — calibrate to student level\n")
                if isinstance(_faang, dict):
                    for level, desc in _faang.items():
                        _plan_parts.append(f"  {level}: {desc if isinstance(desc, str) else _tpj.dumps(desc)}\n")
                elif isinstance(_faang, str):
                    _plan_parts.append(f"{_faang}\n")

            if _probs:
                _plan_parts.append("\n## PROBLEMS BY PURPOSE — use these to structure the session\n")
                if isinstance(_probs, dict):
                    for purpose, prob_list in _probs.items():
                        if isinstance(prob_list, list) and prob_list:
                            _plan_parts.append(f"\n  {purpose}:")
                            for pr in prob_list[:4]:
                                if isinstance(pr, dict):
                                    lc = pr.get('leetcode') or pr.get('leetcode_number') or '?'
                                    _plan_parts.append(f"    - LC {lc} {pr.get('name', '')} — {pr.get('why', '')}")
                                elif isinstance(pr, str):
                                    _plan_parts.append(f"    - {pr}")

            if _visuals:
                _plan_parts.append("\n## VISUAL IDEAS — animation/board suggestions\n")
                for v in (_visuals if isinstance(_visuals, list) else [_visuals]):
                    _plan_parts.append(f"  - {v}\n")

            if _connects:
                _plan_parts.append(f"\n## CONNECTS TO: {', '.join(_connects) if isinstance(_connects, list) else _connects}\n")

            if _cp:
                _plan_parts.append("\n## COMPETITIVE PROGRAMMING (advanced students only)\n")
                if isinstance(_cp, dict):
                    techs = _cp.get('key_techniques', [])
                    if techs:
                        _plan_parts.append(f"  Techniques: {', '.join(techs[:5])}\n")
                    gotchas = _cp.get('gotchas', [])
                    if gotchas:
                        _plan_parts.append(f"  Gotchas: {'; '.join(gotchas[:3])}\n")

            # Legacy fields as compact JSON
            for k in ['canonical_problems', 'visual_examples', 'key_ideas', 'introduction']:
                _tp.pop(k, None)
            _remaining = {k: v for k, v in _tp.items() if v and k not in ('slug', 'type', 'title', 'category', 'updated_at')}
            if _remaining:
                _plan_parts.append(f"\n[PLAN DETAILS]\n{_tpj.dumps(_remaining, indent=2)}\n")

            if _deep and isinstance(_deep, str):
                _max = 8000
                _trunc = _deep[:_max] + ("\n...[truncated]" if len(_deep) > _max else "")
                _plan_parts.append(f"\n[TEACHING CONTENT — Reference material]\n{_trunc}")

            static_parts.append("\n".join(_plan_parts))
        except Exception:
            static_parts.append(f"\n[TEACHING PLAN]\n{teaching_plan if isinstance(teaching_plan, str) else str(teaching_plan)}")

    # BYO preloaded content (same for entire session)
    # If synthesis is present (starts with "[COLLECTION --"), use a richer header
    _byo_preloaded = context_data.get("_byoPreloaded")
    if _byo_preloaded:
        if _byo_preloaded.startswith("[COLLECTION --"):
            static_parts.append(
                "\n═══ BYO KNOWLEDGE MAP — Synthesized from student's uploads ═══\n"
                "Use this map to navigate content: topics, resources, practice questions, and suggested path.\n"
                "Cite sources by resource name + page/timestamp when teaching.\n\n"
                f"{_byo_preloaded}\n"
            )
        else:
            static_parts.append(f"\n═══ BYO CONTENT — Student's uploaded materials ═══\n{_byo_preloaded}\n")

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
        # Low-signal intent override: the input was JUST a URL / empty /
        # one word. The tutor must NOT pick a topic. Force a single
        # clarifying question and complete_triage on the next reply.
        _ls_reason = triage_ctx.get("lowSignalReason")
        if _ls_reason:
            _ls_text = (triage_ctx.get("lowSignalText") or "").strip()
            if _ls_reason == "youtube_url_only":
                _block = (
                    "\n[LOW-SIGNAL INTENT — YouTube URL]\n"
                    f"The student's only input is a YouTube URL: {_ls_text}\n"
                    "You CANNOT open videos, fetch transcripts, or read the page. Do NOT guess what the video is about.\n"
                    "Do NOT pick a topic like 'Networking', 'System Design', 'DSA', etc.\n"
                    "Respond ONLY with one short clarifying question. Example:\n"
                    "  \"Quick one — I can't open videos directly. What topic from this would you like me to walk you through?\"\n"
                    "Draw a minimal board (title + the question). When the student replies with an actual topic, call complete_triage.\n"
                )
            elif _ls_reason == "url_only":
                _block = (
                    "\n[LOW-SIGNAL INTENT — bare URL]\n"
                    f"The student's only input is a URL: {_ls_text}\n"
                    "You cannot fetch external pages. Do NOT invent a topic from the URL.\n"
                    "Ask one short clarifying question: 'What topic from this would you like me to teach?' "
                    "Then call complete_triage once they answer.\n"
                )
            elif _ls_reason == "empty_intent":
                _block = (
                    "\n[LOW-SIGNAL INTENT — no input]\n"
                    "The student gave no topic. Ask one short, friendly question to find out what they "
                    "want to learn today. Do NOT pick a topic on their behalf.\n"
                )
            else:  # too_few_words / fallback
                _block = (
                    "\n[LOW-SIGNAL INTENT — only one word]\n"
                    f"The student input is too short to safely teach from: {_ls_text!r}.\n"
                    "Ask one short clarifying question to scope the topic. Do NOT guess.\n"
                )
            parts.append(_block)
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
    # The planner gets them at session start. The tutor uses search/fetch/peek
    # on demand. This saves ~1700 tokens per turn.

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

    # ─── SECTION 2b: PATH CONTEXT (cross-session memory) ─────
    _inject_path_context(parts, context_data)

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

    # ─── DSA / SD / Mock Interview state ──────────────────────
    if session_mode in ("dsa", "sd", "mock_interview"):
        parts.append("\n═══════════════════════════════════════════════════")
        _mode_labels = {"dsa": "DSA CODING", "sd": "SYSTEM DESIGN", "mock_interview": "MOCK INTERVIEW"}
        parts.append(f" {_mode_labels.get(session_mode, 'DSA')} MODE")
        parts.append("═══════════════════════════════════════════════════\n")

        _problem_data = context_data.get("problemData")
        if _problem_data:
            parts.append(f"[Problem Metadata]\n{_problem_data}\n")

        _active_panels = context_data.get("activePanels")
        if _active_panels:
            _panel_strs = []
            for _p in _active_panels:
                if isinstance(_p, str):
                    _panel_strs.append(_p)
                elif isinstance(_p, dict) and _p.get("id") == "media-viewer":
                    _t = _p.get("currentTime", 0)
                    _min = int(_t // 60)
                    _sec = int(_t % 60)
                    _dur = _p.get("duration", 0)
                    _dur_min = int(_dur // 60) if _dur else "?"
                    _paused = " PAUSED" if _p.get("paused") else " playing"
                    _spd = _p.get("speed", 1)
                    _panel_strs.append(
                        f"media-viewer ({_p.get('title','')}{_paused} at {_min}:{_sec:02d}/{_dur_min}min, speed={_spd}x)"
                    )
                elif isinstance(_p, dict):
                    _panel_strs.append(str(_p.get("id", _p)))
            parts.append(f"[ACTIVE UI PANELS: {', '.join(_panel_strs)}]\n")
        else:
            parts.append("[ACTIVE UI PANELS: none — use <euler-ui> tags to show code-editor, sd-canvas, or media-viewer]\n")

        _code_state = context_data.get("codeState")
        if _code_state:
            import json as _cj
            _cs = _cj.loads(_code_state) if isinstance(_code_state, str) else _code_state
            _code_content = _cs.get('code', '')
            if _code_content.strip():
                parts.append(f"[STUDENT'S CODE EDITOR — current contents, written by the student]\n<code-state lang=\"{_cs.get('lang', 'python')}\">\n{_code_content}\n</code-state>\n")
            else:
                parts.append("[STUDENT'S CODE EDITOR — empty. Use push_code tool to send starter code.]\n")

            # Test results from last run
            _test_results = context_data.get("testResults")
            if not _test_results:
                try:
                    import json as _trj
                    _sc_for_tests = _trj.loads(context_data.get("sessionContext", "{}")) if isinstance(context_data.get("sessionContext"), str) else context_data.get("sessionContext", {})
                    _test_results = _sc_for_tests.get("testResults")
                except Exception:
                    pass
            if _test_results:
                _tr = _test_results if isinstance(_test_results, dict) else {}
                _passed = _tr.get("passed", 0)
                _total = _tr.get("total", 0)
                parts.append(f"[LAST TEST RUN — {_passed}/{_total} passed]")
                for _r in (_tr.get("results") or [])[:10]:
                    _tag = "✓ PASS" if _r.get("passed") else "✗ FAIL"
                    _inp = str(_r.get("input", ""))[:60]
                    _exp = str(_r.get("expected", ""))[:40]
                    _act = str(_r.get("actual", ""))[:40]
                    _err = str(_r.get("error", ""))[:60]
                    if _r.get("passed"):
                        parts.append(f"  {_tag} | input: {_inp}")
                    else:
                        parts.append(f"  {_tag} | input: {_inp} | expected: {_exp} | got: {_act}" + (f" | error: {_err}" if _err else ""))
                parts.append("")

        _canvas_state = context_data.get("canvasState")
        if _canvas_state:
            import json as _cj2
            _cvs = _cj2.loads(_canvas_state) if isinstance(_canvas_state, str) else _canvas_state
            _elements = _cvs.get("elements", []) if isinstance(_cvs, dict) else []
            if _elements:
                _lines = ["[CANVAS — element index (use IDs to reference/modify)]"]
                for _el in _elements:
                    _lbl = f' "{_el.get("label")}"' if _el.get("label") else ""
                    _src = " (tutor)" if _el.get("source") == "tutor" else ""
                    _lines.append(f"  {_el.get('id','?')}: {_el.get('type','?')}{_lbl}{_src}")
                parts.append("\n".join(_lines) + "\n")
            else:
                parts.append("[CANVAS — empty. Use draw_on_canvas to add components.]\n")

        _interview_state = context_data.get("interviewState")
        if _interview_state:
            parts.append(
                f'<interview-state phase="{_interview_state.get("phase", "")}" '
                f'elapsed="{_interview_state.get("elapsed", "")}" '
                f'hints_used="{_interview_state.get("hints_used", 0)}" '
                f'silence="{_interview_state.get("silence", "0s")}" '
                f'timer_minutes="{_interview_state.get("timer_minutes", 45)}" '
                f'company="{_interview_state.get("company", "generic")}" />\n'
            )

    # Auto-injected transcript / section context (pre-fetched by chat route)
    transcript_ctx = context_data.get("_autoTranscript")
    section_ctx = context_data.get("_autoSectionContent")
    if transcript_ctx or section_ctx:
        parts.append("\n╔══════════════════════════════════════════════════════════╗")
        parts.append("║  PRE-LOADED CONTEXT — DO NOT FETCH THIS VIA TOOLS        ║")
        parts.append("║  Only use tools if student asks about a DIFFERENT section.║")
        parts.append("╚══════════════════════════════════════════════════════════╝\n")

        if transcript_ctx:
            parts.append("[TRANSCRIPT]")
            if len(transcript_ctx) > 1500:
                transcript_ctx = transcript_ctx[:1500] + "\n[... truncated]"
            parts.append(transcript_ctx)

        if section_ctx:
            parts.append("\n[SECTION CONTENT — key points, formulas, examples]")
            if len(section_ctx) > 2000:
                section_ctx = section_ctx[:2000] + "\n[... truncated]"
            parts.append(section_ctx)

        parts.append(
            "\n⚠️ The above content is ALREADY HERE. Do NOT call additional fetch/peek/search "
            "for this section. Those tools are ONLY for looking up OTHER content the student asks about.\n"
        )

    active_sim = context_data.get("activeSimulation")
    if active_sim:
        parts.append(f"[Active Simulation State]\n{active_sim}\n")

    active_board = context_data.get("activeBoard")
    if active_board:
        parts.append(f"[ACTIVE BOARD — what the student sees on the board right now]\n{active_board}\n")

    previous_boards = context_data.get("previousBoards")
    if previous_boards:
        parts.append(f"[PREVIOUS BOARDS — completed board-draws this session]\n{previous_boards}\n")

    # Teaching plan is now in the STATIC (cached) block above.

    current_topic = context_data.get("currentTopic")
    if current_topic:
        parts.append("\n[CURRENT TOPIC — Execute these steps now]\n")
        parts.append(current_topic)

    concept_research = context_data.get("conceptResearch")
    if concept_research:
        parts.append(
            "\n[CONCEPT RESEARCH — pre-generated material for this topic. "
            "Use as ground truth: the calibration question, mechanism, "
            "counterfactual, applications, and discrimination problems.]\n"
        )
        parts.append(concept_research)

    completed_topics = context_data.get("completedTopics")
    if completed_topics:
        parts.append(f"\n[COMPLETED TOPICS]\n{completed_topics}\n")

    session_scope = context_data.get("sessionScope")
    if session_scope:
        parts.append(f"\n[SESSION SCOPE]\n{session_scope}\n")

    # BYO scope — when the student picked an uploaded collection, surface
    # the collection_id directly so the tutor knows to fetch from it on
    # turn 1 instead of asking clueless clarification questions.
    session_ctx_str = context_data.get("sessionContext")
    if session_ctx_str:
        try:
            import json as _json
            sc = _json.loads(session_ctx_str) if isinstance(session_ctx_str, str) else session_ctx_str
            cid = sc.get("collection_id") if isinstance(sc, dict) else None
            if cid:
                mode = (sc.get("mode") or "teach") if isinstance(sc, dict) else "teach"
                enriched = (sc.get("enriched_intent") or "").strip() if isinstance(sc, dict) else ""
                resource_ids = sc.get("resource_ids") if isinstance(sc, dict) else None
                byo_lines = [
                    "[BYO SCOPE — student is teaching from their own uploads]",
                    f"Collection: {cid}",
                    f"Mode: {mode}",
                ]
                if resource_ids and isinstance(resource_ids, list):
                    byo_lines.append(f"Filtered to {len(resource_ids)} specific file(s) — search ONLY within these.")
                if enriched:
                    byo_lines.append(f"Stated goal: {enriched[:300]}")
                byo_lines.extend([
                    "",
                    "RULES — MANDATORY:",
                    f"  - Ground every claim in the collection content. Use search(scope='collection', collection_id='{cid}'"
                    + (f", resource_id=...) for specific files" if resource_ids else ")") + " if you need more.",
                    "  - Cite inline: (page N, resource name) so the student knows where it came from.",
                    "  - Never ask 'which subject / which paper' — the content below already tells you.",
                    "  - Use <prefetch_context> tag to pre-load content for the next turn (avoids tool call latency).",
                ])
                parts.append("\n" + "\n".join(byo_lines) + "\n")

                # BYO preloaded content is now in the STATIC (cached) block.

        except (ValueError, TypeError, AttributeError):
            pass

    # Inject prefetched content from <prefetch_context> tag (requested by tutor last turn)
    prefetched = context_data.get("_prefetchedContent")
    if prefetched:
        parts.append(
            "\n[PREFETCHED CONTENT — you requested this via <prefetch_context> last turn]\n"
            "Use this content DIRECTLY. No tool call needed — it's already here.\n\n"
            f"{prefetched}\n"
        )

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
            "For prereq gaps, use <plan-modify action=\"insert\" ... />. "
            "To skip a topic the student knows, use <plan-modify action=\"skip\" />."
        )
        parts.append("\n".join(acct_lines) + "\n")

    # Checkpoint and pace injection — structural forcing for assessment gating
    checkpoint_pace = context_data.get("checkpointAndPace")
    if checkpoint_pace:
        parts.append(checkpoint_pace + "\n")

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
            "When discussion is complete and the student is ready, emit "
            "<signal progress=\"complete\" .../> in housekeeping to advance.\n"
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


def build_planning_prompt(context_data: dict) -> str | tuple[str, str]:
    """Build planning agent system prompt with prompt caching support.

    Delegates to planning.py which returns (static, dynamic) tuple.
    """
    return _build_planning_prompt_base(context_data)


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

    # Session context (lighter than tutor — no simulations, no plan, no agents)
    parts.append("\n═══════════════════════════════════════════════════")
    parts.append(" SESSION CONTEXT")
    parts.append("═══════════════════════════════════════════════════\n")

    for key, label in [
        ("studentProfile", "Student Profile"),
        ("concepts", "Concepts"),
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

search(query, scope?)
  Semantic search over the student's uploaded (BYO) content. Use to find
  refs when you don't have them. scope: "collection" | "user_corpus" | "resource".

fetch(ref)
  Get the full content for a ref. Use to ground your questions in the
  student's exact material. Refs: chunk:ID, segment:ID, resource:ID.

peek(ref)
  Cheap summary (~100 tokens). Use to pick the right chunk quickly.

query_knowledge(query)
  Look up what you know about this student's understanding of a concept.
  Use before questioning to calibrate difficulty.

update_student_model(notes)
  Record your assessment observations. Call ONCE at the end with all results.
  Each note: { concepts: ["concept_name"], note: "Assessment: ..." }

search_images(query, limit)
  Find images if you need a visual for a question scenario.

web_search(query, limit)
  Supplementary info for question grounding (rare — prefer BYO content).

TOOLS YOU DO NOT HAVE (assessment is focused):
  Plan/agent control (handled by main tutor via housekeeping tags).
  Use complete_assessment / handback_to_tutor to return control.

Keep it simple: search/fetch → ask question → evaluate → log."""
