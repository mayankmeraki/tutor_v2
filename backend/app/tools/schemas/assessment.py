"""Assessment tool schemas — completion, handback."""

from .tutor import TUTOR_TOOLS

COMPLETE_ASSESSMENT_TOOL = {
    "name": "complete_assessment",
    "description": (
        "End the assessment checkpoint with results. Call when: you've asked the "
        "maximum number of questions, OR the minimum is met and the student got "
        "3+ correct in a row. Include the full results JSON with per-concept "
        "scores and observations. Control returns to the Tutor."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "object",
                "properties": {
                    "correct": {"type": "number"},
                    "total": {"type": "number"},
                    "pct": {"type": "number"},
                },
                "required": ["correct", "total", "pct"],
            },
            "perConcept": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "concept": {"type": "string"},
                        "correct": {"type": "number"},
                        "total": {"type": "number"},
                        "mastery": {"type": "string", "enum": ["strong", "developing", "weak"]},
                    },
                },
            },
            "updatedNotes": {
                "type": "object",
                "description": "Per-concept assessment observations with STUDENT REASONING for wrong answers. Keys are concept names.",
            },
            "studentQuestions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Questions the student asked during the checkpoint that the tutor should follow up on.",
            },
            "recommendation": {
                "type": "string",
                "description": "One sentence for the tutor about what to do next. Be specific about strategy.",
            },
            "overallMastery": {
                "type": "string",
                "enum": ["strong", "developing", "weak"],
            },
        },
        "required": ["score", "overallMastery"],
    },
}


HANDBACK_TO_TUTOR_TOOL = {
    "name": "handback_to_tutor",
    "description": (
        "End the assessment early and return to the Tutor. Call when: "
        "student got 2+ wrong on the same concept, student says 'I don't know' "
        "2+ times, student asks to stop, or student gives empty/garbage answers. "
        "Include partial results and what the student got stuck on."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "enum": ["student_struggling", "student_declined", "student_needs_help", "student_disengaged"],
            },
            "questionsCompleted": {"type": "number"},
            "score": {
                "type": "object",
                "properties": {
                    "correct": {"type": "number"},
                    "total": {"type": "number"},
                },
            },
            "stuckOn": {
                "type": "string",
                "description": "What the student couldn't do — specific observation. Include their reasoning if available.",
            },
            "studentQuestions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Questions the student asked during the checkpoint that need tutor follow-up. These reveal where curiosity or confusion lives.",
            },
            "studentState": {
                "type": "string",
                "description": "Student's emotional/engagement state if notable (frustrated, anxious, curious, disengaged, confused). Helps tutor calibrate tone on resume.",
            },
            "updatedNotes": {
                "type": "object",
                "description": "Per-concept assessment observations with STUDENT REASONING for each wrong answer.",
            },
            "recommendation": {
                "type": "string",
                "description": "One sentence for the tutor about how to re-approach. Be specific about strategy.",
            },
        },
        "required": ["reason", "questionsCompleted", "recommendation"],
    },
}


ASSESSMENT_TOOLS = [
    t for t in TUTOR_TOOLS
    if t["name"] in (
        "search_images", "web_search", "get_section_content",
        "query_knowledge", "update_student_model",
        "content_read", "content_peek",
        "byo_read", "byo_list",
    )
] + [COMPLETE_ASSESSMENT_TOOL, HANDBACK_TO_TUTOR_TOOL]

