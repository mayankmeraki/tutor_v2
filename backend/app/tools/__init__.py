"""Tool schemas + dispatcher for the Tutor and sub-agents."""

import logging

from .schemas import (
    TUTOR_TOOLS,
    DELEGATION_TOOLS,
    RETURN_TO_TUTOR_TOOL,
    ASSESSMENT_TOOLS,
    COMPLETE_ASSESSMENT_TOOL,
    HANDBACK_TO_TUTOR_TOOL,
)
from .search_images import search_images
from .web_search import web_search
from .retrieval import (
    search_tool,
    fetch_tool,
    peek_tool,
    nearby_tool,
    list_contents_tool,
)

log = logging.getLogger(__name__)


# ── Dispatcher ───────────────────────────────────────────────────────────────

async def execute_tutor_tool(
    name: str,
    tool_input: dict,
    *,
    context_data: dict | None = None,
) -> str:
    """Execute a tool call. `context_data` (the turn's studentProfile +
    sessionContext) is threaded through so retrieval tools can resolve
    user_id / collection_id without re-querying."""
    try:
        # ── Unified retrieval (BYO scopes only) ──
        if name == "search":
            return await search_tool(tool_input, context_data=context_data)
        elif name == "fetch":
            return await fetch_tool(tool_input, context_data=context_data)
        elif name == "peek":
            return await peek_tool(tool_input, context_data=context_data)
        elif name == "nearby":
            return await nearby_tool(tool_input, context_data=context_data)
        elif name == "list_contents":
            return await list_contents_tool(tool_input, context_data=context_data)

        # ── Student knowledge ──
        elif name == "query_knowledge":
            query = tool_input.get("query", "")
            if not query:
                return "No student knowledge records available."
            try:
                import json as _json
                ctx = context_data or {}
                profile_str = ctx.get("studentProfile", "")
                profile = _json.loads(profile_str) if isinstance(profile_str, str) and profile_str else (profile_str if isinstance(profile_str, dict) else {})
                user_email = profile.get("userEmail") or profile.get("userId") or ""
                if user_email:
                    from app.services.student_model.service import hybrid_search_notes
                    return await hybrid_search_notes(user_email, query)
            except Exception as e:
                log.debug("query_knowledge failed: %s", e)
            return "No student knowledge records available."

        elif name == "update_student_model":
            return "Student model updated."

        # ── External content ──
        elif name == "search_images":
            return await search_images(tool_input["query"], tool_input.get("limit", 3))
        elif name == "web_search":
            return await web_search(tool_input["query"], tool_input.get("limit", 5))

        # ── DSA / System Design / Mock Interview tools ──
        elif name == "run_code":
            from .code_execution import handle_run_code
            return await handle_run_code(tool_input, context_data or {})

        elif name == "push_code":
            return {
                "text": "Code pushed to editor.",
                "__ws_event": {
                    "type": "CODE_PUSH",
                    "data": {
                        "code": tool_input.get("code", ""),
                        "language": tool_input.get("language", "python"),
                        "highlight_lines": tool_input.get("highlight_lines", []),
                        "replace": tool_input.get("replace", True),
                    },
                },
            }

        elif name == "draw_on_canvas":
            return {
                "text": "Drawing added to canvas.",
                "__ws_event": {
                    "type": "CANVAS_DRAW",
                    "data": {
                        "shapes": tool_input.get("shapes", []),
                        "connections": tool_input.get("connections", []),
                        "clear": tool_input.get("clear", False),
                    },
                },
            }

        else:
            log.warning("Unknown tool: %s", name)
            return f"Unknown tool: {name}"
    except KeyError as e:
        log.warning("Tool %s missing required param: %s", name, e)
        return f"Tool error: missing required parameter {e}"
    except Exception:
        log.error("Tool %s failed", name, exc_info=True)
        return f"Tool {name} encountered an error. Try a different approach."
