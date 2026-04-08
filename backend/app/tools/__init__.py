"""Tool schemas + dispatcher for the Tutor and sub-agents."""

import logging

from .schemas import (
    TUTOR_TOOLS,
    DELEGATION_TOOLS,
    RETURN_TO_TUTOR_TOOL,
    ASSESSMENT_TOOLS,
    COMPLETE_ASSESSMENT_TOOL,
    HANDBACK_TO_TUTOR_TOOL,
    VIDEO_FOLLOW_TOOLS,
    VIDEO_CONTROL_TOOLS,
)
from .handlers import get_section_content, get_simulation_details, get_transcript_context, get_section_brief
from .search_images import search_images
from .web_search import web_search
from .byo import _execute_byo_read, _execute_byo_list, _execute_byo_transcript

log = logging.getLogger(__name__)


# ── Dispatcher ───────────────────────────────────────────────────────────────

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

