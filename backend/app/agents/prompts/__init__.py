from .director import DIRECTOR_SYSTEM_PROMPT
from .tutor import TUTOR_SYSTEM_PROMPT
from .toolkit import TOOLKIT_PROMPT
from .scenarios.course_follow import SKILL_COURSE
from .scenarios.exam import SKILL_EXAM_FULL
from .scenarios.exam_topic import SKILL_EXAM_TOPIC
from .scenarios.derivation import SKILL_DERIVATION
from .scenarios.conceptual import SKILL_CONCEPTUAL
from .scenarios.curiosity import SKILL_FREE

SKILL_MAP: dict[str, str | None] = {
    "course": SKILL_COURSE,
    "exam_full": SKILL_EXAM_FULL,
    "exam_topic": SKILL_EXAM_TOPIC,
    "problem": None,
    "derivation": SKILL_DERIVATION,
    "conceptual": SKILL_CONCEPTUAL,
    "free": SKILL_FREE,
}


def build_director_prompt(context_data: dict) -> str:
    parts = [DIRECTOR_SYSTEM_PROMPT]

    parts.append("\n═══════════════════════════════════════════════════")
    parts.append(" COURSE CONTEXT")
    parts.append("═══════════════════════════════════════════════════\n")

    field_labels = [
        ("studentProfile", "Student Profile"),
        ("courseMap", "Course Map"),
        ("concepts", "Course Concepts"),
        ("simulations", "Available Simulations"),
        ("knowledgeState", "Student Knowledge State"),
        ("studentModel", "Student Model"),
        ("studentIntent", "Student Intent"),
        ("pauseNote", "Pause Note"),
        ("previousScript", "Previous Script"),
        ("tutorNotes", "Tutor Notes"),
        ("sessionHistory", "Session History"),
        ("chatHistory", "Recent Conversation"),
    ]
    for key, label in field_labels:
        val = context_data.get(key)
        if val:
            parts.append(f"[{label}]\n{val}\n")

    return "\n".join(parts)


def build_tutor_prompt(context_data: dict) -> str:
    parts = [TUTOR_SYSTEM_PROMPT, TOOLKIT_PROMPT]

    scenario_skill = context_data.get("scenarioSkill")
    if scenario_skill:
        parts.append("\n═══════════════════════════════════════════════════")
        parts.append(" ACTIVE SCENARIO SKILL — Follow this for pacing and assessment")
        parts.append("═══════════════════════════════════════════════════\n")
        parts.append(scenario_skill)

    parts.append("\n═══════════════════════════════════════════════════")
    parts.append(" COURSE CONTEXT (pre-loaded — this is your source of truth)")
    parts.append("═══════════════════════════════════════════════════\n")

    context_fields = [
        ("studentProfile", "Student Profile"),
        ("courseMap", "Course Map"),
        ("concepts", "Course Concepts"),
        ("simulations", "Available Simulations"),
        ("sessionMetrics", "Session Metrics"),
        ("activeSimulation", "Active Simulation State"),
    ]
    for key, label in context_fields:
        val = context_data.get(key)
        if val:
            parts.append(f"[{label}]\n{val}\n")

    # Topic-based execution: teaching plan + current topic
    teaching_plan = context_data.get("teachingPlan")
    if teaching_plan:
        parts.append("═══════════════════════════════════════════════════")
        parts.append(" TEACHING PLAN — Full outline of all sections and topics")
        parts.append("═══════════════════════════════════════════════════\n")
        parts.append(teaching_plan)

    current_topic = context_data.get("currentTopic")
    if current_topic:
        parts.append("\n═══════════════════════════════════════════════════")
        parts.append(" CURRENT TOPIC — Execute these steps now")
        parts.append("═══════════════════════════════════════════════════\n")
        parts.append(current_topic)

    # Backward compat: currentSection (older plans)
    current_section = context_data.get("currentSection")
    if current_section and not current_topic:
        parts.append("\n═══════════════════════════════════════════════════")
        parts.append(" CURRENT SECTION — Execute these steps now")
        parts.append("═══════════════════════════════════════════════════\n")
        parts.append(current_section)

    completed_sections = context_data.get("completedSections")
    if completed_sections:
        parts.append(f"\n[COMPLETED SECTIONS]\n{completed_sections}\n")

    # Legacy: full script (for backward compatibility during transition)
    current_script = context_data.get("currentScript")
    if current_script and not current_topic and not current_section:
        parts.append("═══════════════════════════════════════════════════")
        parts.append(" CURRENT SCRIPT — Execute this step by step")
        parts.append("═══════════════════════════════════════════════════\n")
        parts.append(current_script)

    return "\n".join(parts)
