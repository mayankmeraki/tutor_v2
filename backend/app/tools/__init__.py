"""Tool schemas and dispatcher for the Tutor and sub-agents.

The Tutor has agent orchestration tools (spawn_agent, check_agents,
delegate_teaching, advance_topic) plus content tools (search_images,
get_simulation_details, etc.).
"""

import json

from .handlers import get_section_content, get_simulation_details
from .search_images import search_images
from .web_search import web_search

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
        "name": "log_knowledge",
        "description": (
            "Record a freehand observation about the student's understanding. "
            "Write naturally — what they understood, what confused them, "
            "misconceptions spotted, how they performed on a problem, their "
            "reasoning quality. These notes persist across sessions and build "
            "a profile you can search later with query_knowledge."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": (
                        "Your observation in natural language. Be specific: "
                        "'Student correctly derived F=ma for the inclined plane problem "
                        "but forgot to decompose weight into components initially. "
                        "After a hint about the coordinate system, solved it correctly.'"
                    ),
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional short labels for search. Examples: "
                        "'newtons_laws', 'gap', 'strong', 'misconception', 'module-2'"
                    ),
                },
            },
            "required": ["note"],
        },
    },
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
            "Built-in types: 'planning' (plans next section), 'asset' (fetches images/content), "
            "'visual_gen' (generates interactive HTML/JS simulations). "
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
                        "Agent type. 'planning' and 'asset' have built-in behavior. "
                        "Any other string creates a custom agent — name it descriptively."
                    ),
                },
                "task": {
                    "type": "string",
                    "description": (
                        "What the agent should do. Be specific and detailed. "
                        "For planning: starting topic, student model, observations. "
                        "For asset: JSON array of asset specs. "
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


# ── Dispatchers ──────────────────────────────────────────────────────────────

async def execute_tutor_tool(name: str, tool_input: dict) -> str:
    if name == "search_images":
        return await search_images(tool_input["query"], tool_input.get("limit", 3))
    elif name == "web_search":
        return await web_search(tool_input["query"], tool_input.get("limit", 5))
    elif name == "get_simulation_details":
        return await get_simulation_details(tool_input["simulation_id"])
    elif name == "get_section_content":
        return await get_section_content(int(tool_input["lesson_id"]), int(tool_input["section_index"]))
    else:
        return f"Unknown tool: {name}"
