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
            "Search Google Images for educational visuals. Returns image titles + URLs. "
            "Embed results on the board with: <teaching-image src=\"URL\" caption=\"title\" /> "
            "Use for diagrams, photos, experimental setups, or anything visual that helps explain."
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
        "name": "content_read",
        "description": (
            "Get full teaching content for a ref — transcript, key points, formulas. "
            "Use when grounding your teaching in actual lecture content. "
            "Refs: lesson:ID:section:IDX for a specific section, lesson:ID for a lesson overview, "
            "sim:ID for simulation details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": 'Content ref, e.g. "lesson:3:section:2" or "lesson:5"',
                },
            },
            "required": ["ref"],
        },
    },
    {
        "name": "content_peek",
        "description": (
            "Quick look at a ref — title, concepts, key points (~100 tokens). "
            "Use for planning or finding the right section before reading full content. "
            "For lesson refs: returns section listing with refs. "
            "For section refs: returns compact teaching brief."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": 'Content ref, e.g. "lesson:3" or "lesson:3:section:2"',
                },
            },
            "required": ["ref"],
        },
    },
    {
        "name": "content_search",
        "description": (
            "Search across all course content for a topic or concept. "
            "Returns matching items with refs you can pass to content_read or content_peek. "
            "Use when the student asks about something not in the current plan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — concept name, topic, or question",
                },
                "limit": {
                    "type": "number",
                    "description": "Max results (default 5)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "byo_read",
        "description": (
            "Read content from the student's uploaded materials (BYO). "
            "Use when teaching from student's own PDFs, notes, or documents. "
            "Provide the collection_id (from session context) and optionally a chunk index or search query. "
            "Returns the actual text content from their uploaded material."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_id": {
                    "type": "string",
                    "description": "BYO collection ID (from session context or enriched_intent)",
                },
                "query": {
                    "type": "string",
                    "description": "Search within the collection — topic, question text, or keyword",
                },
                "chunk_index": {
                    "type": "number",
                    "description": "Specific chunk index to read (0-based). Use when you know the exact chunk.",
                },
            },
            "required": ["collection_id"],
        },
    },
    {
        "name": "byo_list",
        "description": (
            "List all chunks/sections in a BYO collection with their topics and labels. "
            "Use to understand what content is available in the student's uploaded material "
            "before deciding what to teach."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_id": {
                    "type": "string",
                    "description": "BYO collection ID",
                },
            },
            "required": ["collection_id"],
        },
    },
    {
        "name": "byo_transcript_context",
        "description": (
            "Get the transcript around a specific timestamp in a BYO video. "
            "Use during video watch-along sessions to understand what the student just heard. "
            "Returns ~60s of transcript centered on the timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "BYO resource ID of the video being watched",
                },
                "timestamp": {
                    "type": "number",
                    "description": "Current video position in seconds",
                },
            },
            "required": ["resource_id", "timestamp"],
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
    {
        "name": "complete_triage",
        "description": (
            "Call this when triage is done — you've gathered enough diagnostic signal "
            "to plan the session. Include your findings: what gaps you found, what's strong, "
            "and where to start teaching. After calling this, you'll transition to teaching mode."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "diagnosed_gaps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific weak areas found during triage",
                },
                "confirmed_strong": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Areas the student demonstrated strength in",
                },
                "student_level": {
                    "type": "string",
                    "description": "One-line characterization of where the student is",
                },
                "recommended_start": {
                    "type": "string",
                    "description": "Where to begin teaching and what approach to use",
                },
                "content_refs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific lesson/section refs to use (from content_search)",
                },
            },
            "required": ["diagnosed_gaps", "student_level", "recommended_start"],
        },
    },
    {
        "name": "session_signal",
        "description": (
            "Emit a session signal after your teaching response. Call this at the end "
            "of each teaching turn to indicate progress and student state. "
            "This helps the system know when to run checkpoints or adjust approach."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "section_progress": {
                    "type": "string",
                    "enum": ["in_progress", "wrapping_up", "complete"],
                    "description": "Current section teaching progress",
                },
                "student_state": {
                    "type": "string",
                    "enum": ["engaged", "confused", "struggling", "ahead"],
                    "description": "How the student seems based on their responses",
                },
                "needs_diagnostic": {
                    "type": "boolean",
                    "description": (
                        "Set true if student seems fundamentally lost — "
                        "missing prerequisites, not just confused on current topic"
                    ),
                },
            },
            "required": ["section_progress", "student_state"],
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
    if t["name"] in (
        "search_images", "web_search", "get_simulation_details",
        "get_section_content", "control_simulation",
        "content_read", "content_peek", "content_search",
        "byo_read", "byo_list", "byo_transcript_context",
    )
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
    if t["name"] in (
        "search_images", "web_search", "get_section_content",
        "query_knowledge", "update_student_model",
        "content_read", "content_peek",
        "byo_read", "byo_list",
    )
] + [COMPLETE_ASSESSMENT_TOOL, HANDBACK_TO_TUTOR_TOOL]


# ── Dispatchers ──────────────────────────────────────────────────────────────

async def execute_tutor_tool(name: str, tool_input: dict) -> str:
    try:
        if name == "search_images":
            return await search_images(tool_input["query"], tool_input.get("limit", 3))
        elif name == "web_search":
            return await web_search(tool_input["query"], tool_input.get("limit", 5))
        elif name == "get_simulation_details":
            return await get_simulation_details(tool_input["simulation_id"])
        elif name in ("content_map", "content_read", "content_peek", "content_search"):
            # Handled by adapter in chat.py (needs course_id + db session)
            return "Content tool must be routed through the adapter. Check chat.py dispatch."
        elif name == "byo_read":
            return await _execute_byo_read(tool_input)
        elif name == "byo_list":
            return await _execute_byo_list(tool_input)
        elif name == "byo_transcript_context":
            return await _execute_byo_transcript(tool_input)
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



# ── BYO Content Tool Implementations ─────────────────────────────────────────

async def _execute_byo_read(tool_input: dict) -> str:
    """Read content from a BYO collection."""
    from app.core.mongodb import get_mongo_db
    db = get_mongo_db()

    collection_id = tool_input.get("collection_id", "")
    query = tool_input.get("query", "")
    chunk_index = tool_input.get("chunk_index")

    if not collection_id:
        return "Error: collection_id is required"

    if chunk_index is not None:
        # Read specific chunk
        doc = await db.byo_chunks.find_one(
            {"collection_id": collection_id, "index": int(chunk_index)},
            {"_id": 0, "content": 1, "topics": 1, "labels": 1, "anchor": 1},
        )
        if not doc:
            return f"No chunk found at index {chunk_index} in collection {collection_id}"
        return f"[BYO Chunk {chunk_index}]\nTopics: {', '.join(doc.get('topics', []))}\n\n{doc.get('content', '')}"

    if query:
        # Search within collection
        import re
        words = [w for w in query.strip().split() if len(w) > 2]
        if not words:
            return "Search query too short"
        conditions = []
        for w in words[:5]:
            conditions.append({"content": {"$regex": re.escape(w), "$options": "i"}})
        cursor = db.byo_chunks.find(
            {"collection_id": collection_id, "$or": conditions},
            {"_id": 0, "index": 1, "content": 1, "topics": 1},
        ).limit(3)
        results = []
        async for doc in cursor:
            results.append(f"[Chunk {doc.get('index', '?')}] Topics: {', '.join(doc.get('topics', []))}\n{doc.get('content', '')[:500]}")
        if not results:
            return f"No matching content found for '{query}' in this collection."
        return "\n\n---\n\n".join(results)

    # No query — return first few chunks as overview
    cursor = db.byo_chunks.find(
        {"collection_id": collection_id},
        {"_id": 0, "index": 1, "content": 1, "topics": 1},
    ).sort("index", 1).limit(3)
    results = []
    async for doc in cursor:
        results.append(f"[Chunk {doc.get('index', '?')}] Topics: {', '.join(doc.get('topics', []))}\n{doc.get('content', '')[:400]}")
    if not results:
        # Check collection status for a better error message
        col = await db.collections.find_one(
            {"collection_id": collection_id},
            {"status": 1, "title": 1},
        )
        if col and col.get("status") == "processing":
            return f"Collection '{col.get('title', '?')}' is still being processed."
        elif col and col.get("status") == "error":
            return f"Collection '{col.get('title', '?')}' had a processing error — content could not be extracted."
        return "Collection has no text content. The original file may still be viewable but text extraction produced no results."
    return "\n\n---\n\n".join(results)


async def _execute_byo_list(tool_input: dict) -> str:
    """List chunks in a BYO collection."""
    from app.core.mongodb import get_mongo_db
    db = get_mongo_db()

    collection_id = tool_input.get("collection_id", "")
    if not collection_id:
        return "Error: collection_id is required"

    cursor = db.byo_chunks.find(
        {"collection_id": collection_id},
        {"_id": 0, "index": 1, "topics": 1, "labels": 1, "tokens": 1},
    ).sort("index", 1).limit(30)

    lines = [f"Chunks in collection {collection_id}:"]
    async for doc in cursor:
        topics = ", ".join(doc.get("topics", [])[:3])
        labels = ", ".join(doc.get("labels", [])[:2])
        lines.append(f"  [{doc.get('index', '?')}] {topics} ({labels}) — {doc.get('tokens', 0)} tokens")

    if len(lines) == 1:
        # Check if collection exists and its status
        col = await db.collections.find_one(
            {"collection_id": collection_id},
            {"status": 1, "title": 1},
        )
        if not col:
            return "Collection not found. Check the collection_id."
        status = col.get("status", "unknown")
        title = col.get("title", "?")
        if status == "processing":
            return f"Collection '{title}' is still being processed. Content will be available once processing completes."
        elif status == "error":
            return f"Collection '{title}' had a processing error — the content could not be extracted."
        return f"Collection '{title}' is ready but has no extractable text content. The original file may still be viewable."
    return "\n".join(lines)


async def _execute_byo_transcript(tool_input: dict) -> str:
    """Get transcript context around a timestamp in a BYO video."""
    from app.core.mongodb import get_mongo_db
    db = get_mongo_db()

    resource_id = tool_input.get("resource_id", "")
    timestamp = float(tool_input.get("timestamp", 0))
    if not resource_id:
        return "Error: resource_id is required"

    # Get resource info
    resource = await db.byo_resources.find_one(
        {"resource_id": resource_id},
        {"_id": 0, "original_name": 1, "source_url": 1, "collection_id": 1},
    )
    if not resource:
        return "Resource not found."

    # Find chunks around the timestamp (~60s window)
    t_start = max(0, timestamp - 30)
    t_end = timestamp + 30

    cursor = db.byo_chunks.find(
        {
            "resource_id": resource_id,
            "$or": [
                # Chunk starts or ends within our window
                {"anchor.start_time": {"$gte": t_start, "$lte": t_end}},
                {"anchor.end_time": {"$gte": t_start, "$lte": t_end}},
                # Chunk spans our entire window (mega-chunk)
                {"$and": [
                    {"anchor.start_time": {"$lte": t_start}},
                    {"anchor.end_time": {"$gte": t_end}},
                ]},
            ],
        },
        {"_id": 0, "content": 1, "anchor": 1, "topics": 1, "index": 1},
    ).sort("index", 1).limit(5)

    chunks = [doc async for doc in cursor]

    # Fallback: index-based
    if not chunks:
        est_index = max(0, int(timestamp / 30))
        cursor = db.byo_chunks.find(
            {"resource_id": resource_id, "index": {"$gte": max(0, est_index - 1), "$lte": est_index + 1}},
            {"_id": 0, "content": 1, "anchor": 1, "topics": 1, "index": 1},
        ).sort("index", 1).limit(3)
        chunks = [doc async for doc in cursor]

    if not chunks:
        return f"No transcript found around {int(timestamp)}s in this video."

    lines = [f"Transcript around {int(timestamp)}s in '{resource.get('original_name', '?')}':"]
    for c in chunks:
        content = c.get("content", "")
        anchor = c.get("anchor", {})
        chunk_start = anchor.get("start_time", 0) or 0
        chunk_end = anchor.get("end_time", 0) or 0

        # For mega-chunks (spanning entire video), extract just the relevant portion
        if chunk_end - chunk_start > 120 and content:
            import re
            # Parse timestamped lines: [M:SS] text or [MM:SS] text
            ts_lines = re.findall(r'\[(\d+:\d{2})\]\s*(.+?)(?=\n\[|\Z)', content, re.DOTALL)
            if ts_lines:
                relevant = []
                for ts_str, text in ts_lines:
                    parts = ts_str.split(':')
                    sec = int(parts[0]) * 60 + int(parts[1])
                    if t_start - 10 <= sec <= t_end + 10:
                        relevant.append(f"[{ts_str}] {text.strip()}")
                if relevant:
                    lines.append("\n".join(relevant))
                    continue
        # Short chunk or no timestamp parsing — use full content
        start = anchor.get("start_time")
        ts = f"[{int(start // 60)}:{int(start % 60):02d}] " if start is not None else ""
        lines.append(f"{ts}{content[:800]}")

    return "\n\n".join(lines)


# ── Video Follow-Along Tools ─────────────────────────────────────────────────

# Video follow-along tools: transcript + section content for CURRENT timestamp are
# PRE-INJECTED in the prompt. Tools below are for looking up OTHER sections/timestamps.
# Each tool returns EVERYTHING in one call (transcript + key points + teaching brief) —
# no need to chain multiple tools.
VIDEO_FOLLOW_TOOLS = [
    {"name": "get_transcript_context", "description": "Get transcript + key points + teaching brief around a DIFFERENT timestamp (not the current one — that's already in your context). Returns everything in one call: transcript window, summary, key points, professor's framing, examples. ONE call is enough — do NOT also call get_section_content or get_section_brief.", "input_schema": {"type": "object", "properties": {"lesson_id": {"type": "number"}, "timestamp": {"type": "number", "description": "Seconds"}}, "required": ["lesson_id", "timestamp"]}},
    {"name": "get_section_content", "description": "Get full content for a DIFFERENT section (not the current one — that's already in your context). Returns transcript + key points + teaching brief + formulas all in one call. ONE call is enough.", "input_schema": {"type": "object", "properties": {"lesson_id": {"type": "number"}, "section_index": {"type": "number"}}, "required": ["lesson_id", "section_index"]}},
    {"name": "resume_video", "description": "Resume video playback. Call when you've answered the student's question. Do NOT ask 'shall we continue?' — just call this.", "input_schema": {"type": "object", "properties": {"message": {"type": "string", "description": "Optional brief note before resuming"}}, "required": []}},
    {"name": "seek_video", "description": "Seek the video to a specific timestamp. Use to point the student to a relevant moment.", "input_schema": {"type": "object", "properties": {"timestamp": {"type": "number"}, "reason": {"type": "string"}}, "required": ["timestamp"]}},
    # capture_video_frame disabled — cross-origin blocks it for YouTube streams
    # {"name": "capture_video_frame", ...},
]

VIDEO_CONTROL_TOOLS = {"resume_video", "seek_video"}
