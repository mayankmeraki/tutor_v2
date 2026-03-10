from .tutor import TUTOR_SYSTEM_PROMPT
from .planning import PLANNING_PROMPT
from .toolkit import TOOLKIT_PROMPT
from .tags import TAGS_PROMPT
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


def build_tutor_prompt(context_data: dict) -> str:
    parts = [TUTOR_SYSTEM_PROMPT, TOOLKIT_PROMPT, TAGS_PROMPT]

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

    # Teaching plan from planning agent
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

    completed_topics = context_data.get("completedTopics")
    if completed_topics:
        parts.append(f"\n[COMPLETED TOPICS]\n{completed_topics}\n")

    # Agent results from completed background agents
    agent_results = context_data.get("agentResults")
    if agent_results:
        parts.append("\n═══════════════════════════════════════════════════")
        parts.append(" AGENT RESULTS — Background agents completed")
        parts.append("═══════════════════════════════════════════════════\n")
        parts.append(agent_results)

    # Delegation result from a just-ended sub-agent
    delegation_result = context_data.get("delegationResult")
    if delegation_result:
        parts.append("\n═══════════════════════════════════════════════════")
        parts.append(" DELEGATION RESULT — Sub-agent just finished")
        parts.append("═══════════════════════════════════════════════════\n")
        parts.append(delegation_result)

    # Pre-prepared assets
    prepared_assets = context_data.get("preparedAssets")
    if prepared_assets:
        parts.append(f"\n[PREPARED ASSETS]\n{prepared_assets}\n")

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

    return "\n".join(parts)
