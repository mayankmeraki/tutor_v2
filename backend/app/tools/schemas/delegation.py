"""Delegation tool schemas — handoff to sub-agents."""

from .tutor import TUTOR_TOOLS

RETURN_TO_TUTOR_TOOL = {
    "name": "return_to_tutor",
    "description": (
        "Return control to the main Tutor. Call when: task is complete, "
        "student wants to change topic, student is confused on prerequisites, "
        "or you've reached the scope limit."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "enum": ["task_complete", "scope_exceeded", "student_request", "max_turns"],
                "description": "Why control is returning to Tutor",
            },
            "summary": {
                "type": "string",
                "description": "Summary of what was covered and how the student performed",
            },
            "student_performance": {
                "type": "object",
                "description": "Performance metrics from the delegation",
                "properties": {
                    "correct": {"type": "number"},
                    "total": {"type": "number"},
                    "weak_area": {"type": "string"},
                    "strong_area": {"type": "string"},
                },
            },
        },
        "required": ["reason", "summary"],
    },
}


DELEGATION_TOOLS = [
    t for t in TUTOR_TOOLS
    if t["name"] in (
        # Unified retrieval
        "search", "fetch", "peek", "nearby", "list_contents",
        # External
        "search_images", "web_search",
        # Sim control
        "control_simulation",
    )
]
