"""Tool schemas and dispatcher for the Tutor and sub-agents.

The Tutor has agent orchestration tools (spawn_agent, check_agents,
delegate_teaching, advance_topic) plus content tools (search_images,
get_simulation_details, etc.).
"""

import json
import logging

from .handlers import get_section_content, get_simulation_details, get_transcript_context, get_section_brief
from .search_images import search_images
from .web_search import web_search

log = logging.getLogger(__name__)

# ── Tutor Tools ──────────────────────────────────────────────────────────────

TUTOR_TOOLS = [
    {
        "name": "search_images",
        "description": (
            "Search Wikimedia Commons for educational images related to a topic. "
            "Returns image URLs and captions that can be displayed with <teaching-image> tags. "
            "Use when you need real-world photos, experimental setups, or historical images."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": 'Search query, e.g. "free body diagram", "double slit experiment"',
                },
                "limit": {
                    "type": "number",
                    "description": "Max results (1-5, default 3)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for supplementary information not available in course materials. "
            "Returns summaries and URLs from general web sources. "
            "Use when: you need a real-world example, current data, a diagram/image not in Wikimedia, "
            "a formula derivation, historical context, or any information beyond what the course provides. "
            "Prefer course materials first — use this to supplement, not replace."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": 'Search query — be specific. e.g. "photoelectric effect threshold frequency graph"',
                },
                "limit": {
                    "type": "number",
                    "description": "Max results (1-8, default 5)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_simulation_details",
        "description": (
            "Get full details for a specific simulation by ID, including ai_context, "
            "controls, guided exercises, and content URLs. Use when you want to guide "
            "the student through a specific simulation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "simulation_id": {
                    "type": "string",
                    "description": "The simulation ID from the Available Simulations context",
                },
            },
            "required": ["simulation_id"],
        },
    },
    {
        "name": "content_map",
        "description": (
            "Get the course/content structure overview — modules, lessons, sections, "
            "timestamps, and available resources. Call this ONCE at session start to "
            "understand what content is available. Do NOT call every turn — the structure "
            "doesn't change. Use the plan and current topic for navigation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_section_content",
        "description": (
            "Fetch detailed content for a specific course section — transcript segments, "
            "key points, formulas, and concepts covered. Use when you need the professor's "
            "actual words to ground your teaching. Don't call for every step — only when "
            "you need specific lecture content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lesson_id": {
                    "type": "number",
                    "description": "The lesson ID from the Course Map",
                },
                "section_index": {
                    "type": "number",
                    "description": "The section index within the lesson",
                },
            },
            "required": ["lesson_id", "section_index"],
        },
    },
    {
        "name": "control_simulation",
        "description": (
            "Control the student's active simulation by setting parameters or clicking buttons. "
            "Only works when the student has a simulation open (Active Simulation State in context). "
            "Use this to demo experiments, set up specific scenarios, or reset the simulation. "
            "The student will see the changes happen in real-time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "description": "Ordered list of actions to perform on the simulation",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["set_parameter", "click_button"],
                                "description": "Type of action",
                            },
                            "name": {"type": "string", "description": "Parameter name (for set_parameter)"},
                            "value": {"type": "string", "description": "Parameter value to set (for set_parameter)"},
                            "label": {"type": "string", "description": "Button label (for click_button)"},
                        },
                        "required": ["action"],
                    },
                },
            },
            "required": ["steps"],
        },
    },
    # ── Knowledge state tools ─────────────────────────────────────────────
    {
        "name": "query_knowledge",
        "description": (
            "Look up what you know about the student's understanding. "
            "Query by concept name, tag, module, or topic. "
            "Use this BEFORE teaching a concept to adapt your approach, "
            "or when the student seems confused to check their background."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Concept name, tag, module, or topic to search for",
                },
            },
            "required": ["query"],
        },
    },
    # ── Agent orchestration tools ──────────────────────────────────────────
    {
        "name": "spawn_agent",
        "description": (
            "Start a background agent to do work while you continue teaching. "
            "Results arrive in [AGENT RESULTS] on your next turn. "
            "Built-in types: 'planning' (plans next section). "
            "For interactive visualizations, use <teaching-widget> tag directly instead of agents. "
            "Any other type creates a custom LLM agent with your task/instructions as its prompt. "
            "Examples: 'research', 'problem_gen', 'content', 'analysis', 'worked_example'. "
            "CRITICAL: Always give the student something to do when spawning — "
            "assessment tag + spawn_agent in the same message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": (
                        "Agent type. 'planning' has built-in behavior. "
                        "Any other string creates a custom agent — name it descriptively."
                    ),
                },
                "task": {
                    "type": "string",
                    "description": (
                        "What the agent should do. Be specific and detailed. "
                        "For planning: starting topic, student model, observations. "
                        "For custom agents: the full task description."
                    ),
                },
                "instructions": {
                    "type": "string",
                    "description": "Additional instructions or context for the agent (optional)",
                },
            },
            "required": ["type", "task"],
        },
    },
    {
        "name": "check_agents",
        "description": (
            "Check status of all background agents and collect any completed results. "
            "Returns agent statuses and any newly completed results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "delegate_teaching",
        "description": (
            "Hand off a bounded teaching task to a focused sub-agent. "
            "The sub-agent takes over for the next N turns and returns a summary. "
            "USE FOR: problem drills (5-8 turns), simulation exploration, exam quizzes, "
            "worked example sequences, or any bounded interactive task. "
            "DON'T USE FOR: introducing new concepts, handling confusion, short interactions (<3 turns)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "What the sub-agent should teach/drill",
                },
                "instructions": {
                    "type": "string",
                    "description": (
                        "Specific instructions for the sub-agent. Include: what to cover, "
                        "difficulty progression, what to track, when to return. "
                        "The sub-agent gets core teaching behaviors + your instructions."
                    ),
                },
                "agent_type": {
                    "type": "string",
                    "description": (
                        "Descriptive label for this delegation. Examples: 'practice_drill', "
                        "'sim_explore', 'exam_quiz', 'worked_examples', 'concept_review'. "
                        "Default: 'practice_drill'"
                    ),
                },
                "max_turns": {
                    "type": "number",
                    "description": "Maximum turns before returning control (default: 6, max: 10)",
                },
            },
            "required": ["topic", "instructions"],
        },
    },
    {
        "name": "reset_plan",
        "description": (
            "Scrap the current teaching plan entirely and clear the sidebar. "
            "Use when the student's direction fundamentally changes and the current plan "
            "is no longer relevant — e.g. they need to go back to basics, want a different "
            "topic, or revealed a prerequisite gap that invalidates the current plan. "
            "After calling this, immediately spawn a new planning agent with the updated intent. "
            "The student sees the plan sidebar clear and then repopulate with the new plan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why the plan is being scrapped (for logging)",
                },
                "keep_scope": {
                    "type": "boolean",
                    "description": (
                        "If true, keep the session objective/scope (plan changes but goal stays). "
                        "If false, also reset session objective/scope (student wants something different). "
                        "Default: false."
                    ),
                },
            },
            "required": ["reason"],
        },
    },
    {
        "name": "modify_plan",
        "description": (
            "Modify the current teaching plan without scrapping it. Three actions:\n"
            "- insert_prereq: You discovered the student is missing a prerequisite. "
            "Push the current position onto a detour stack, insert prerequisite topics, "
            "and teach those first. When done, call modify_plan(action='end_detour') to resume.\n"
            "- end_detour: Pop the detour stack and resume where you left off before the detour.\n"
            "- skip: Skip the current topic (student already knows it) and advance to the next."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["insert_prereq", "end_detour", "skip"],
                    "description": "The plan modification action to take.",
                },
                "prereq_topics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "concept": {"type": "string"},
                        },
                        "required": ["title", "concept"],
                    },
                    "description": "Topics to insert as prerequisites (for insert_prereq only).",
                },
                "reason": {
                    "type": "string",
                    "description": "Why this plan change is needed.",
                },
            },
            "required": ["action", "reason"],
        },
    },
    {
        "name": "advance_topic",
        "description": (
            "Mark the current topic complete and move to the next planned topic. "
            "If no more topics remain, returns a signal to spawn a planning agent or wrap up."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tutor_notes": {
                    "type": "string",
                    "description": "Observations about the student during this topic",
                },
                "student_model": {
                    "type": "object",
                    "description": "Updated student model",
                    "properties": {
                        "strengths": {"type": "array", "items": {"type": "string"}},
                        "gaps": {"type": "array", "items": {"type": "string"}},
                        "misconceptions": {"type": "array", "items": {"type": "string"}},
                        "pace": {"type": "string"},
                        "engagement": {"type": "string"},
                        "preferred_modality": {"type": "string"},
                    },
                },
            },
            "required": ["tutor_notes"],
        },
    },
    {
        "name": "request_board_image",
        "description": (
            "Request a snapshot of the current board-draw canvas, including both your "
            "drawings and any student annotations. Use when you need to see what the "
            "student drew or annotated on the shared board. The image will be captured "
            "and sent as the next user message. Only works when a board-draw spotlight "
            "is currently active."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why you need to see the board (helps with context)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "fetch_asset",
        "description": (
            "Retrieve the full content of a previous board-draw or widget by its asset_id. "
            "Returns the complete JSONL drawing commands (for board-draws) or HTML/CSS/JS code "
            "(for widgets). Use this when you need the original content to resume drawing on "
            "a previous board via <teaching-board-draw-resume> or to understand a widget's "
            "code before sending <teaching-widget-update>. Asset IDs are shown in the "
            "[Previous Boards] and [Reusable Widgets] context sections."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_id": {
                    "type": "string",
                    "description": "The asset_id to retrieve (e.g., 'spot-ref-a3b7c1d2')",
                },
            },
            "required": ["asset_id"],
        },
    },
    {
        "name": "handoff_to_assessment",
        "description": (
            "Hand off to the Assessment Agent for a section checkpoint. "
            "Call this when a teaching section is complete and the student should be assessed "
            "on the concepts just taught. Provide a detailed brief including: what concepts "
            "to test, student weaknesses/strengths observed during teaching, recommended "
            "question types and difficulty, and content grounding references. "
            "The assessment agent will take over, conduct the checkpoint, and return results "
            "when complete. You will receive the results in [ASSESSMENT RESULTS] on your "
            "next turn after the assessment ends."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {
                    "type": "object",
                    "description": "The section being assessed",
                    "properties": {
                        "index": {"type": "number", "description": "Section index"},
                        "title": {"type": "string", "description": "Section title"},
                    },
                    "required": ["index", "title"],
                },
                "conceptsTested": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Concept names to test in this checkpoint",
                },
                "studentProfile": {
                    "type": "object",
                    "description": "What you observed about the student during teaching",
                    "properties": {
                        "weaknesses": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Concepts or skills the student struggled with",
                        },
                        "strengths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Concepts or skills the student demonstrated well",
                        },
                        "engagementStyle": {
                            "type": "string",
                            "description": "How the student best engages (visual, textual, etc.)",
                        },
                    },
                },
                "plan": {
                    "type": "object",
                    "description": "Assessment plan — question count, types, difficulty",
                    "properties": {
                        "questionCount": {
                            "type": "object",
                            "properties": {
                                "min": {"type": "number", "description": "Minimum questions (default 3)"},
                                "max": {"type": "number", "description": "Maximum questions (default 5)"},
                            },
                        },
                        "startDifficulty": {
                            "type": "string",
                            "enum": ["easy", "medium", "hard"],
                            "description": "Starting difficulty level (default medium)",
                        },
                        "types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Recommended question types: mcq, numerical, freetext, notebook-derivation, drawing, fillblank",
                        },
                        "focusAreas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Areas to focus assessment on (60% of questions)",
                        },
                        "avoid": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Concepts to skip — student already demonstrated mastery",
                        },
                    },
                },
                "conceptNotes": {
                    "type": "object",
                    "description": "Per-concept observations from teaching. Keys are concept names, values are your notes.",
                },
                "contentGrounding": {
                    "type": "object",
                    "description": "References to course content for question grounding",
                    "properties": {
                        "lessonId": {"type": "number"},
                        "sectionIndices": {"type": "array", "items": {"type": "number"}},
                        "keyExamples": {"type": "array", "items": {"type": "string"}},
                        "professorPhrasing": {"type": "string"},
                    },
                },
            },
            "required": ["section", "conceptsTested"],
        },
    },
    {
        "name": "update_student_model",
        "description": (
            "Your private notebook on this student. Called automatically every ~5 turns. "
            "Write freehand notes tagged with concept names. UPSERT: if a note for a "
            "concept already exists, your new note REPLACES it — always write the "
            "CURRENT complete picture, not incremental updates. One note per concept. "
            "Use concepts: ['_profile'] for student-wide observations (pace, style)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "notes": {
                    "type": "array",
                    "description": (
                        "Freehand notes tagged with concept names. One note per concept cluster. "
                        "If the concept was covered before, REWRITE the note with current state — "
                        "don't create a new note with slightly different tags.\n\n"
                        "TAG RULES (critical for deduplication):\n"
                        "- Use lowercase_underscore format: 'wave_function', NOT 'Wave Function'\n"
                        "- Use the SAME tag every time for the same concept — don't invent variants\n"
                        "- Check [Student Notes] in context — if a concept is already noted, use its EXACT tag\n"
                        "- Primary tag = the main concept. Secondary = subtopics.\n"
                        "- Special: '_profile' for student-wide notes (pace, modality, preferences)\n"
                        "- NEVER create two notes for the same concept with different tag spellings"
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "concepts": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Concept tags in lowercase_underscore format. "
                                    "Primary tag first, subtopics after. "
                                    "Examples: ['schrodinger_equation'], ['wave_function', 'probability'], "
                                    "['_profile']. Tags are auto-normalized to lowercase."
                                ),
                            },
                            "lesson": {
                                "type": "string",
                                "description": "Lesson context, e.g. 'lesson_2'.",
                            },
                            "note": {
                                "type": "string",
                                "description": (
                                    "Complete freehand observation. Cover: mastery level, what they can "
                                    "solve, what trips them up, what approach worked/failed, what to do "
                                    "next time. Write the FULL picture — this REPLACES any previous note "
                                    "on this concept."
                                ),
                            },
                        },
                        "required": ["concepts", "note"],
                    },
                },
            },
            "required": ["notes"],
        },
    },
]


# ── Sub-agent tool (only available during delegation) ────────────────────────

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


# ── Delegation tools (subset for sub-agents) ────────────────────────────────

DELEGATION_TOOLS = [
    t for t in TUTOR_TOOLS
    if t["name"] in ("search_images", "web_search", "get_simulation_details", "get_section_content", "control_simulation")
]


# ── Assessment Agent tools ──────────────────────────────────────────────────

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

# Assessment tools: content tools + knowledge tools + completion tools
ASSESSMENT_TOOLS = [
    t for t in TUTOR_TOOLS
    if t["name"] in ("search_images", "web_search", "get_section_content", "query_knowledge", "update_student_model")
] + [COMPLETE_ASSESSMENT_TOOL, HANDBACK_TO_TUTOR_TOOL]


# ── MQL Tool Schemas (BYO Material Query Layer) ─────────────────────────────

MQL_TOOLS = [
    {
        "name": "browse_topics",
        "description": (
            "List all topics in the student's collection with difficulty and exercise counts. "
            "Like 'ls' — shows what's available to teach. Start here to plan a session."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "browse_topic",
        "description": (
            "Open a specific topic — shows its chunks, concepts, exercises, and assets. "
            "Like opening a directory. Use to plan how to teach a specific topic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic_id": {"type": "string", "description": "The topicId to explore"},
            },
            "required": ["topic_id"],
        },
    },
    {
        "name": "get_flow",
        "description": (
            "Read the teaching sequence — chapters with ordered topics and estimated times. "
            "Like reading a README. Use to understand the recommended learning path."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "read_chunk",
        "description": (
            "Read a content chunk — full transcript, key points, formulas, linked visuals. "
            "Like 'cat' — the actual content to teach from. Use when delivering a lesson."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chunk_id": {"type": "string", "description": "The chunkId to read"},
            },
            "required": ["chunk_id"],
        },
    },
    {
        "name": "search_content",
        "description": (
            "Text search across all chunks in the collection. "
            "Like 'grep' — find where a concept or topic is discussed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search text (concept name, formula, keyword)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "grep_material",
        "description": (
            "Search within a specific material's chunks. "
            "Like 'grep file' — narrower search within one document/video."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "material_id": {"type": "string", "description": "The materialId to search within"},
                "query": {"type": "string", "description": "Search text"},
            },
            "required": ["material_id", "query"],
        },
    },
    {
        "name": "find_concept",
        "description": (
            "Look up a concept by name — definition, prerequisites, formulas, where it appears. "
            "Use before teaching a concept to see its full context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "concept_name": {"type": "string", "description": "Concept name or alias to find"},
            },
            "required": ["concept_name"],
        },
    },
    {
        "name": "search_concepts",
        "description": (
            "Fuzzy search across all concepts in the collection. "
            "Use when you're not sure of the exact concept name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_exercises",
        "description": (
            "Get practice problems, optionally filtered by topic or difficulty. "
            "Use for drills, assessments, or checking if exercises exist for a topic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic_id": {"type": "string", "description": "Filter by topicId (optional)"},
                "difficulty": {
                    "type": "string",
                    "enum": ["beginner", "intermediate", "advanced"],
                    "description": "Filter by difficulty (optional)",
                },
                "limit": {"type": "number", "description": "Max results (default 5)"},
            },
        },
    },
    {
        "name": "get_mastery",
        "description": (
            "Get student's mastery state — completed topics, concept levels, observations. "
            "Use to adapt teaching approach based on what the student knows."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "log_observation",
        "description": (
            "Log a mastery observation about the student's understanding of a concept. "
            "Use after interactions that reveal what the student knows or struggles with."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "concept_id": {
                    "type": "string",
                    "description": "Concept name or ID",
                },
                "observation": {
                    "type": "string",
                    "description": (
                        "Freehand observation. Cover: mastery level, what they can do, "
                        "what trips them up, what approach worked."
                    ),
                },
            },
            "required": ["concept_id", "observation"],
        },
    },
    {
        "name": "get_assets",
        "description": (
            "Get teaching assets — diagrams, board captures, video clips — for a topic. "
            "Use to find visual aids to show the student."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic_id": {"type": "string", "description": "Filter by topicId (optional)"},
                "asset_type": {
                    "type": "string",
                    "enum": ["board", "equation", "diagram", "slide", "chart"],
                    "description": "Filter by type (optional)",
                },
                "limit": {"type": "number", "description": "Max results (default 10)"},
            },
        },
    },
]


# ── Dispatchers ──────────────────────────────────────────────────────────────

async def execute_tutor_tool(name: str, tool_input: dict) -> str:
    try:
        if name == "search_images":
            return await search_images(tool_input["query"], tool_input.get("limit", 3))
        elif name == "web_search":
            return await web_search(tool_input["query"], tool_input.get("limit", 5))
        elif name == "get_simulation_details":
            return await get_simulation_details(tool_input["simulation_id"])
        elif name == "content_map":
            # Returns the course structure — fetched from session context
            # The actual data comes from chat.py which has the course_id
            return "Use the teaching plan for navigation. Call get_section_content(lesson_id, section_index) for specific content."
        elif name == "get_section_content":
            return await get_section_content(int(tool_input["lesson_id"]), int(tool_input["section_index"]))
        elif name == "get_transcript_context":
            return await get_transcript_context(int(tool_input["lesson_id"]), float(tool_input["timestamp"]))
        elif name == "get_section_brief":
            return await get_section_brief(int(tool_input["lesson_id"]), int(tool_input["section_index"]))
        elif name in ("resume_video", "seek_video"):
            return "OK"  # control tools handled by chat.py SSE
        else:
            return f"Unknown tool: {name}"
    except KeyError as e:
        log.warning("Tool %s missing required param: %s", name, e)
        return f"Tool error: missing required parameter {e}"
    except Exception:
        log.error("Tool %s failed", name, exc_info=True)
        return f"Tool {name} encountered an error. Try a different approach."


async def execute_mql_tool(name: str, tool_input: dict, collection_id: str, user_email: str, session_id: str = "") -> str:
    """Execute a Material Query Layer tool."""
    from app.services.mql import (
        browse_topic,
        browse_topics,
        find_concept,
        get_assets,
        get_exercises,
        get_flow,
        get_mastery,
        grep_material,
        log_observation,
        read_chunk,
        search_concepts,
        search_content,
    )

    try:
        if name == "browse_topics":
            return await browse_topics(collection_id)
        elif name == "browse_topic":
            return await browse_topic(collection_id, tool_input["topic_id"])
        elif name == "get_flow":
            return await get_flow(collection_id)
        elif name == "read_chunk":
            return await read_chunk(collection_id, tool_input["chunk_id"])
        elif name == "search_content":
            return await search_content(collection_id, tool_input["query"])
        elif name == "grep_material":
            return await grep_material(collection_id, tool_input["material_id"], tool_input["query"])
        elif name == "find_concept":
            return await find_concept(collection_id, tool_input["concept_name"])
        elif name == "search_concepts":
            return await search_concepts(collection_id, tool_input["query"])
        elif name == "get_exercises":
            return await get_exercises(
                collection_id,
                topic_id=tool_input.get("topic_id"),
                difficulty=tool_input.get("difficulty"),
                limit=int(tool_input.get("limit", 5)),
            )
        elif name == "get_mastery":
            return await get_mastery(collection_id, user_email)
        elif name == "log_observation":
            return await log_observation(
                collection_id, user_email,
                tool_input["concept_id"], tool_input["observation"],
                session_id=session_id,
            )
        elif name == "get_assets":
            return await get_assets(
                collection_id,
                topic_id=tool_input.get("topic_id"),
                asset_type=tool_input.get("asset_type"),
                limit=int(tool_input.get("limit", 10)),
            )
        else:
            return f"Unknown MQL tool: {name}"
    except KeyError as e:
        log.warning("MQL tool %s missing required param: %s", name, e)
        return f"Tool error: missing required parameter {e}"
    except Exception:
        log.error("MQL tool %s failed", name, exc_info=True)
        return f"Tool {name} encountered an error. Try a different approach."


# Set of MQL tool names for dispatch routing
MQL_TOOL_NAMES = {t["name"] for t in MQL_TOOLS}

# ── Video Follow-Along Tools ─────────────────────────────────────────────────

VIDEO_FOLLOW_TOOLS = [
    t for t in TUTOR_TOOLS if t["name"] in ("search_images", "web_search", "get_section_content", "update_student_model")
] + [
    {"name": "get_transcript_context", "description": "Get the professor's words around a specific moment in the lecture (~60s before, ~30s after). Use to understand what the student just heard.", "input_schema": {"type": "object", "properties": {"lesson_id": {"type": "number"}, "timestamp": {"type": "number", "description": "Seconds"}}, "required": ["lesson_id", "timestamp"]}},
    {"name": "get_section_brief", "description": "Get a concise teaching brief for a lecture section: key points, examples, how the professor frames it.", "input_schema": {"type": "object", "properties": {"lesson_id": {"type": "number"}, "section_index": {"type": "number"}}, "required": ["lesson_id", "section_index"]}},
    {"name": "resume_video", "description": "Resume video playback. Call when you've answered the student's question. Do NOT ask 'shall we continue?' — just call this.", "input_schema": {"type": "object", "properties": {"message": {"type": "string", "description": "Optional brief note before resuming"}}, "required": []}},
    {"name": "seek_video", "description": "Seek the video to a specific timestamp. Use to point the student to a relevant moment.", "input_schema": {"type": "object", "properties": {"timestamp": {"type": "number"}, "reason": {"type": "string"}}, "required": ["timestamp"]}},
    {"name": "capture_video_frame", "description": "Capture a screenshot of what the student is currently seeing in the video. Returns the frame as an image. Use when you need to see what's on screen — diagrams, equations, slides, board work — to give a better answer.", "input_schema": {"type": "object", "properties": {}, "required": []}},
]

VIDEO_CONTROL_TOOLS = {"resume_video", "seek_video", "capture_video_frame"}

VIDEO_CONTROL_TOOLS = {"resume_video", "seek_video"}
