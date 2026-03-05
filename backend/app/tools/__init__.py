"""Tool schemas and dispatcher functions for Tutor and Director agents."""

import json

from .handlers import get_section_content, get_simulation_details
from .render_diagram import render_manim_diagram
from .search_images import search_images

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
            "key points, formulas, and concepts covered. Use when a script step has a "
            '"section_ref" or when you need the professor\'s actual words to ground your teaching. '
            "Don't call for every step — only when you need specific lecture content."
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
        "name": "request_director_plan",
        "description": (
            "Request a new teaching script from the Director. Call after probing phase "
            "(first call), when the current script is nearly complete (step 3-4 of 5), "
            "fully complete, or when the student has deviated significantly. "
            "The Director will produce a new script and return it as the tool result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tutor_notes": {
                    "type": "string",
                    "description": (
                        "Your observations: per-step performance, what worked, what was hard, misconceptions found. "
                        "On first call after probing: include detected_scenario, probe_findings, and initial student read."
                    ),
                },
                "reason": {
                    "type": "string",
                    "enum": [
                        "probing_complete",
                        "script_ending",
                        "script_complete",
                        "student_stuck",
                        "topic_change",
                        "scenario_change",
                    ],
                    "description": 'Why you are requesting a new script. Use "probing_complete" after the initial probing phase.',
                },
                "chat_summary": {
                    "type": "string",
                    "description": "Brief summary of the conversation since the last director call",
                },
                "detected_scenario": {
                    "type": "string",
                    "enum": ["course", "exam_full", "exam_topic", "problem", "derivation", "conceptual", "free"],
                    "description": (
                        "The scenario you detected from the student during probing. "
                        "Required on first call (probing_complete). Optional on subsequent calls (only if scenario changed)."
                    ),
                },
                "student_model": {
                    "type": "object",
                    "description": (
                        "Your current read of the student: strengths, gaps, misconceptions, interests, pace, engagement, preferred_modality. "
                        "Include on every call so the Director has your latest observations."
                    ),
                    "properties": {
                        "strengths": {"type": "array", "items": {"type": "string"}},
                        "gaps": {"type": "array", "items": {"type": "string"}},
                        "misconceptions": {"type": "array", "items": {"type": "string"}},
                        "interests": {"type": "array", "items": {"type": "string"}},
                        "pace": {"type": "string", "enum": ["slow", "medium", "fast"]},
                        "engagement": {"type": "string", "enum": ["low", "medium", "high"]},
                        "preferred_modality": {"type": "string", "enum": ["video", "simulation", "diagram", "text", "mixed"]},
                    },
                },
            },
            "required": ["tutor_notes", "reason"],
        },
    },
    {
        "name": "get_next_topic",
        "description": (
            "Move to the next topic. Call when all steps in the current topic are complete. "
            "Returns the next topic's detailed content (steps, assets, guidelines). "
            "Section boundaries are crossed automatically when all topics in a section finish. "
            "If no more topics are available, returns a signal to wrap up."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tutor_notes": {
                    "type": "string",
                    "description": "Observations about the student during this topic",
                },
                "chat_summary": {
                    "type": "string",
                    "description": "Brief summary of what was covered in this topic",
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
                    },
                },
            },
            "required": ["tutor_notes", "chat_summary"],
        },
    },
    {
        "name": "get_next_section",
        "description": (
            "Alias for get_next_topic. Kept for backward compatibility. "
            "Prefer get_next_topic for new code."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tutor_notes": {
                    "type": "string",
                    "description": "Observations about the student during this section",
                },
                "chat_summary": {
                    "type": "string",
                    "description": "Brief summary of what was covered in this section",
                },
                "student_model": {
                    "type": "object",
                    "description": "Updated student model",
                },
            },
            "required": ["tutor_notes", "chat_summary"],
        },
    },
    {
        "name": "request_new_plan",
        "description": (
            "Abandon the current teaching plan and request a completely new one. "
            "Call only when the student fundamentally changes direction (e.g., switching "
            "from lecture to exam prep, changing topics entirely). The Director will "
            "create a fresh plan based on the new intent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why the current plan needs to be replaced",
                },
                "student_intent": {
                    "type": "string",
                    "description": "What the student wants to do now",
                },
                "detected_scenario": {
                    "type": "string",
                    "enum": ["course", "exam_full", "exam_topic", "problem", "derivation", "conceptual", "free"],
                },
                "tutor_notes": {
                    "type": "string",
                    "description": "Observations from the current session",
                },
                "chat_summary": {
                    "type": "string",
                    "description": "Summary of the conversation so far",
                },
                "student_model": {
                    "type": "object",
                    "description": "Current student model",
                },
            },
            "required": ["reason", "student_intent", "tutor_notes"],
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
]

# ── Director Tools ───────────────────────────────────────────────────────────

DIRECTOR_TOOLS = [
    {
        "name": "search_images",
        "description": (
            "Search Wikimedia Commons for educational images. "
            "Returns image URLs and captions. Use to pre-fetch real-world photos, "
            "experimental setups, or historical images for the teaching script."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": 'Search query, e.g. "photoelectric effect apparatus", "double slit experiment"',
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
        "name": "render_diagram",
        "description": (
            "Render a physics diagram or animation using Manim (Python). "
            "Write a Manim Scene class. Static diagrams (self.add) render to PNG. "
            "Animated scenes (self.play) render to MP4 video that auto-plays. "
            "Returns the URL of the rendered asset. "
            "Use for: energy level diagrams, force diagrams, graphs, vector fields, "
            "wavefunctions, derivation walkthroughs, process animations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Complete Manim Python code. Must define a Scene subclass.",
                },
                "caption": {
                    "type": "string",
                    "description": "Brief caption describing the diagram or animation",
                },
                "animated": {
                    "type": "boolean",
                    "description": "Set true if the code uses self.play() animations. Default false (static PNG).",
                },
            },
            "required": ["code"],
        },
    },
    {
        "name": "get_section_content",
        "description": (
            "Fetch detailed content for a single course section. "
            "Prefer get_multiple_sections for batch reads (saves rounds)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "number", "description": "The lesson ID from the Course Map"},
                "section_index": {"type": "number", "description": "The section index within the lesson"},
            },
            "required": ["lesson_id", "section_index"],
        },
    },
    {
        "name": "get_multiple_sections",
        "description": (
            "Batch fetch up to 4 course sections in one call. Returns all sections concatenated. "
            "PREFERRED over multiple get_section_content calls — saves tool rounds for diagrams."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sections": {
                    "type": "array",
                    "description": "Array of {lesson_id, section_index} objects (max 4)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "lesson_id": {"type": "number"},
                            "section_index": {"type": "number"},
                        },
                        "required": ["lesson_id", "section_index"],
                    },
                    "maxItems": 4,
                },
            },
            "required": ["sections"],
        },
    },
]


# ── Dispatchers ──────────────────────────────────────────────────────────────

async def execute_tutor_tool(name: str, tool_input: dict) -> str:
    if name == "search_images":
        return await search_images(tool_input["query"], tool_input.get("limit", 3))
    elif name == "get_simulation_details":
        return await get_simulation_details(tool_input["simulation_id"])
    elif name == "get_section_content":
        return await get_section_content(int(tool_input["lesson_id"]), int(tool_input["section_index"]))
    else:
        return f"Unknown tool: {name}"


async def execute_director_tool(name: str, tool_input: dict) -> str:
    if name == "search_images":
        return await search_images(tool_input["query"], tool_input.get("limit", 3))
    elif name == "render_diagram":
        try:
            media_url = await render_manim_diagram(
                tool_input["code"],
                tool_input.get("animated", False),
                tool_input.get("caption", ""),
            )
            is_video = media_url.endswith(".mp4")
            return json.dumps({
                "success": True,
                "url": media_url,
                "caption": tool_input.get("caption", "Physics diagram"),
                "type": "animation" if is_video else "diagram",
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "caption": tool_input.get("caption", "Physics diagram"),
            })
    elif name == "get_section_content":
        return await get_section_content(int(tool_input["lesson_id"]), int(tool_input["section_index"]))
    elif name == "get_multiple_sections":
        sections = (tool_input.get("sections") or [])[:4]
        import asyncio
        results = await asyncio.gather(
            *(get_section_content(int(s["lesson_id"]), int(s["section_index"])) for s in sections)
        )
        parts = []
        for i, r in enumerate(results):
            s = sections[i]
            parts.append(f"── Section {s['lesson_id']}:{s['section_index']} ──\n{r}")
        return "\n\n".join(parts)
    else:
        return f"Unknown tool: {name}"
