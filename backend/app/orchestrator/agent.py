"""Euler — the Orchestrator agent with dynamic agentic loop.

Euler is the student-facing AI counsellor on Capacity.
It runs an agentic loop: reason -> call tools -> get results -> reason -> ...
until it has everything to respond to the student.

Sub-agents are spawned dynamically with custom instructions.
Each sub-agent is a focused Haiku call that returns structured results.

Usage:
    async for message in orchestrate(user_input, user_context):
        # message is one of: TextDelta, ToolCall, SubAgentResult,
        #                     ArtifactCreated, SessionStart, PermissionRequest, etc.
        yield message
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

log = logging.getLogger(__name__)

MAX_TURNS = 10  # max tool-use turns before forcing a response
MAX_BUDGET_USD = 0.05  # max cost per orchestration


# ── Message types (yielded to the frontend) ─────────────────────────────

@dataclass
class TextDelta:
    """Streamed text content from Euler."""
    text: str
    type: str = "text_delta"


@dataclass
class ToolCallStart:
    """Euler is calling a tool."""
    tool_name: str
    tool_input: dict
    call_id: str = ""
    type: str = "tool_call_start"


@dataclass
class ToolCallResult:
    """Tool returned a result."""
    tool_name: str
    result: str
    call_id: str = ""
    type: str = "tool_call_result"


@dataclass
class SubAgentSpawned:
    """A sub-agent was spawned for a background task."""
    agent_id: str
    task: str
    type: str = "subagent_spawned"


@dataclass
class SubAgentResult:
    """A sub-agent completed and returned results."""
    agent_id: str
    result: dict
    type: str = "subagent_result"


@dataclass
class ArtifactCreated:
    """An artifact was created (any type — flashcards, notes, cheat sheet, etc.)."""
    artifact_id: str
    artifact_type: str
    title: str
    content: dict
    type: str = "artifact_created"


@dataclass
class DocumentGenerated:
    """A downloadable document (PDF, etc.) was generated."""
    document_id: str
    title: str
    format: str
    download_url: str
    type: str = "document_generated"


@dataclass
class SessionStart:
    """Euler is handing off to the Tutor for teaching."""
    session_id: str
    context: dict  # TutorSessionContext
    type: str = "session_start"


@dataclass
class NavigateUI:
    """Euler wants to navigate the student to a specific page."""
    target: str  # /courses/5, /session/abc, /home
    label: str
    type: str = "navigate_ui"


@dataclass
class PermissionRequest:
    """Euler is asking the student for permission before taking an action."""
    permission_id: str
    question: str
    action_label: str  # "Start session", "Create flashcards"
    deny_label: str    # "Not now", "Skip"
    context: dict      # Extra data for the action
    type: str = "permission_request"


@dataclass
class Done:
    """Euler loop complete."""
    turns_used: int
    type: str = "done"


# ── Euler tools ──────────────────────────────────────────────────────

ORCHESTRATOR_TOOLS = [
    {
        "name": "search_courses",
        "description": "Search the course catalog for relevant structured courses.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_materials",
        "description": "Search the student's uploaded materials (BYO collections).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "collection_id": {"type": "string", "description": "Specific collection to search (optional)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_student_context",
        "description": "Get the student's learning history, mastery state, and preferences.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spawn_agents",
        "description": (
            "Spawn one or more focused sub-agents that run IN PARALLEL. "
            "Each agent has access to byo_read, byo_list, and search_courses tools. "
            "Use to parallelise work: reading different parts of uploaded materials, "
            "searching courses while analysing content, reading index vs questions vs topics simultaneously. "
            "Returns all results at once. More agents = more throughput, but each costs ~2-5s."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agents": {
                    "type": "array",
                    "description": "Array of agents to spawn in parallel. Each is independent.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "What this agent should do. Be specific — include collection_id, chunk ranges, etc.",
                            },
                            "instructions": {
                                "type": "string",
                                "description": "Detailed instructions. Include what tools to use and what format to return.",
                            },
                        },
                        "required": ["task", "instructions"],
                    },
                    "minItems": 1,
                    "maxItems": 5,
                },
            },
            "required": ["agents"],
        },
    },
    {
        "name": "create_artifact",
        "description": (
            "Create any study aid for the student. Type is freeform — flashcards, revision notes, "
            "study plan, summary, cheat sheet, formula sheet, comparison table, timeline, "
            "practice problems, or anything else that helps. Saved permanently and shown inline."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Artifact type — freeform. Examples: flashcards, revision_notes, study_plan, summary, cheat_sheet, formula_sheet, practice_problems, comparison_table, timeline",
                },
                "title": {"type": "string", "description": "Title for the artifact"},
                "content": {
                    "type": "object",
                    "description": (
                        "Artifact content — structure depends on type. Always prefer 'markdown' for rich text.\n"
                        "Flashcards: {cards: [{front, back}]}.\n"
                        "Notes/summary/cheat_sheet/formula_sheet: {markdown: '# Title\\n## Section\\n...'}.\n"
                        "Plan: {steps: [{title, description, duration}]}.\n"
                        "Practice problems: {problems: [{question, solution, difficulty}]}.\n"
                        "HTML interactive: {html: '<html>...</html>'}.\n"
                        "For ALL text-heavy artifacts, use {markdown: '...'} with full markdown formatting "
                        "(headers, bold, lists, tables, code blocks, LaTeX $...$). This renders beautifully."
                    ),
                },
                "source": {
                    "type": "object",
                    "description": "What sources this was created from. {collection_id, course_id, resource_ids}",
                },
            },
            "required": ["type", "title", "content"],
        },
    },
    {
        "name": "generate_document",
        "description": (
            "Generate a downloadable document (PDF, formatted notes). "
            "Use for: reference sheets, formula cards, study guides the student can print or save."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Document title"},
                "content_markdown": {
                    "type": "string",
                    "description": "Document content in markdown. Supports headers, lists, tables, LaTeX math ($...$).",
                },
                "format": {
                    "type": "string",
                    "enum": ["pdf", "html"],
                    "description": "Output format. Default: pdf",
                },
            },
            "required": ["title", "content_markdown"],
        },
    },
    {
        "name": "byo_read",
        "description": (
            "Read actual content from a student's uploaded materials collection. "
            "Use BEFORE starting a BYO session to see the real questions, text, and topics. "
            "Returns chunk content — paste key excerpts into enriched_intent for the Tutor."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_id": {
                    "type": "string",
                    "description": "BYO collection ID (from search_materials results)",
                },
                "query": {
                    "type": "string",
                    "description": "Search within the collection — topic, question text, or keyword",
                },
                "chunk_index": {
                    "type": "number",
                    "description": "Specific chunk index to read (0-based)",
                },
            },
            "required": ["collection_id"],
        },
    },
    {
        "name": "byo_list",
        "description": (
            "List all chunks/sections in a BYO collection with their topics and labels. "
            "Use to understand what content is available in the student's uploaded material."
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
        "name": "background_generate",
        "description": (
            "Spawn a long-running generation task in the background. Returns immediately — "
            "the orchestrator should tell the student it's being generated and move on. "
            "The agent runs with full tool access (byo_read, byo_list, search_courses, text_to_speech) "
            "and can do multi-step work: read materials → synthesize → generate output. "
            "Results are saved as learning aids (audio, documents, notes, study plans). "
            "Use for anything that takes >5s: audio digests, compiled revision notes, "
            "study plans from uploaded content, document generation, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": (
                        "What to produce. Be specific about the output format and content. "
                        "E.g. 'Generate an audio revision podcast covering chapters 1-3 of the uploaded textbook' "
                        "or 'Compile a PDF formula sheet from the calculus course sections 1-6'."
                    ),
                },
                "title": {
                    "type": "string",
                    "description": "Title for the learning aid (what the student sees). E.g. 'Calculus — Audio Revision'",
                },
                "output_type": {
                    "type": "string",
                    "enum": ["audio", "document", "notes", "study_plan", "flashcards"],
                    "description": "What kind of artifact to produce.",
                },
                "context": {
                    "type": "object",
                    "description": (
                        "Context for the agent — collection_ids, course_ids, specific content, voice preferences. "
                        "Pass everything the agent needs to do its job without further interaction."
                    ),
                },
            },
            "required": ["task", "title", "output_type"],
        },
    },
    {
        "name": "start_tutor_session",
        "description": (
            "Start a teaching session on the Board. "
            "Build an enriched TutorSessionContext with all the information "
            "the Tutor needs. The student will be redirected to the Board."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "skill": {
                    "type": "string",
                    "description": "Teaching skill: course_follow, exam_prep, homework_help, watch_along, free",
                },
                "mode": {
                    "type": "string",
                    "description": "Session mode: teaching, watch_along, quiz",
                },
                "enriched_intent": {
                    "type": "string",
                    "description": "Natural language description of what the student needs. The Tutor reads this.",
                },
                "plan": {
                    "type": "array",
                    "description": "Teaching plan steps (optional — Tutor's planner builds one if not provided)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "type": {"type": "string"},
                            "content_refs": {"type": "array", "items": {"type": "string"}},
                            "teaching_notes": {"type": "string"},
                        },
                    },
                },
                "course_id": {"type": "integer", "description": "Course ID if following a course"},
                "collection_id": {"type": "string", "description": "Collection ID if using BYO materials"},
                "resource_id": {"type": "string", "description": "BYO resource ID for video watch-along"},
                "teaching_notes": {
                    "type": "string",
                    "description": "Notes for the Tutor about this student (weak areas, preferences, what to address)",
                },
            },
            "required": ["skill", "enriched_intent"],
        },
    },
    {
        "name": "process_video_url",
        "description": (
            "Process a YouTube URL or video link for watch-along. Creates a BYO resource, "
            "extracts the transcript, and returns the resource_id + collection_id. "
            "Use this when a student pastes a video link and wants to watch it with you. "
            "After processing, use start_tutor_session with mode='watch_along' and the "
            "returned collection_id + resource_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "YouTube or video URL",
                },
                "title": {
                    "type": "string",
                    "description": "Title for the video (optional — will auto-detect)",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "navigate_ui",
        "description": (
            "Navigate the student to a specific page in the platform. "
            "Use for: showing a course, opening a lesson, going to their materials."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "URL path to navigate to. Examples: /courses/5, /session/abc-123, /home",
                },
                "label": {
                    "type": "string",
                    "description": "Human-readable label for the navigation. Example: 'View MIT 8.04 course'",
                },
            },
            "required": ["target", "label"],
        },
    },
    {
        "name": "search_sessions",
        "description": (
            "Search the student's past teaching sessions. Returns session summaries. "
            "Use when: student asks to continue where they left off, references a past topic, "
            "or you want to check what they've already covered."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — topic, subject, or keyword from past sessions",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "ask_permission",
        "description": (
            "Ask the student for permission before starting a teaching session. "
            "Shows a yes/no card. The student clicks to approve or decline. "
            "IMPORTANT: Include the FULL session config in action_data so the session "
            "can start directly when the student clicks yes — no round-trip needed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask. Be specific about what you'll do.",
                },
                "action_label": {
                    "type": "string",
                    "description": "Label for the 'yes' button. Example: 'Start session', 'Start watch-along'",
                },
                "deny_label": {
                    "type": "string",
                    "description": "Label for the 'no' button. Example: 'Not now', 'Skip'",
                },
                "action_data": {
                    "type": "object",
                    "description": (
                        "Session config — MUST include all fields needed to start the session: "
                        "skill (course_follow/exam_prep/free/watch_along), "
                        "mode (teaching/watch_along), "
                        "enriched_intent (what to teach), "
                        "course_id (if following a course), "
                        "collection_id (if using BYO materials), "
                        "resource_id (REQUIRED for watch-along — the BYO resource to play)."
                    ),
                },
            },
            "required": ["question", "action_label", "action_data"],
        },
    },
    {
        "name": "respond_inline",
        "description": (
            "Respond to the student inline on the Home screen. "
            "Use for: quick answers, clarification questions, presenting options. "
            "Do NOT use this if you need to start a teaching session."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Response text (markdown supported)"},
                "actions": {
                    "type": "array",
                    "description": "Action buttons to show below the response",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "action": {"type": "string", "description": "start_session, create_artifact, navigate, etc."},
                            "data": {"type": "object"},
                        },
                    },
                },
            },
            "required": ["text"],
        },
    },
]


# ── Sub-agent execution ─────────────────────────────────────────────────

# Tools available to sub-agents (read-only access to content)
SUB_AGENT_TOOLS = [
    {
        "name": "byo_read",
        "description": "Read content from student's uploaded materials. Returns actual text from their PDF/doc.",
        "parameters": {
            "type": "object",
            "properties": {
                "collection_id": {"type": "string", "description": "BYO collection ID"},
                "query": {"type": "string", "description": "Search within collection"},
                "chunk_index": {"type": "number", "description": "Specific chunk index (0-based)"},
            },
            "required": ["collection_id"],
        },
    },
    {
        "name": "byo_list",
        "description": "List all chunks in a BYO collection with topics, labels, token counts.",
        "parameters": {
            "type": "object",
            "properties": {
                "collection_id": {"type": "string", "description": "BYO collection ID"},
            },
            "required": ["collection_id"],
        },
    },
    {
        "name": "search_courses",
        "description": "Search the course catalog for relevant courses.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
]

MAX_SUB_AGENT_TURNS = 5  # max tool-use turns per sub-agent


async def _execute_sub_agent_tool(name: str, tool_input: dict, user_context: dict) -> str:
    """Execute a tool within a sub-agent context."""
    if name == "byo_read":
        from app.tools import _execute_byo_read
        return await _execute_byo_read(tool_input)
    elif name == "byo_list":
        from app.tools import _execute_byo_list
        return await _execute_byo_list(tool_input)
    elif name == "search_courses":
        # Reuse the main orchestrator's search_courses logic
        return await _execute_tool("search_courses", tool_input, user_context)
    return f"Unknown tool: {name}"


async def _run_sub_agent(task: str, instructions: str, user_context: dict | None = None) -> dict:
    """Run a sub-agent with an agentic loop — can use BYO + search tools.

    Unlike the old single-shot approach, sub-agents now get up to MAX_SUB_AGENT_TURNS
    of tool use so they can read materials, search content, and build thorough answers.
    """
    import httpx
    from app.core.config import settings

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        return {"error": "No API key"}

    user_context = user_context or {}

    system_prompt = f"""You are a focused research sub-agent. Complete your task thoroughly using the tools available.

Your task: {task}

Instructions: {instructions}

When done, output a clear summary of what you found. Include specific details — chunk indices,
question text, topic names, course IDs — so the orchestrator can use your findings directly."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Begin your task."},
    ]
    tools_spec = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}} for t in SUB_AGENT_TOOLS]
    # Add web search so sub-agents can research topics
    tools_spec.append({"type": "openrouter:web_search", "parameters": {"max_results": 3, "search_context_size": "low"}})

    final_text = ""

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            for turn in range(MAX_SUB_AGENT_TURNS):
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": settings.MODEL_FAST,
                        "max_tokens": 4000,
                        "temperature": 0,
                        "messages": messages,
                        "tools": tools_spec,
                    },
                )
                if resp.status_code != 200:
                    return {"error": f"API {resp.status_code}", "partial": final_text}

                choice = resp.json()["choices"][0]
                msg = choice["message"]
                text = msg.get("content", "") or ""
                tool_calls = msg.get("tool_calls", [])

                # If no tool calls, the agent is done
                if not tool_calls:
                    final_text = text
                    break

                # Agent wants to use tools — execute them and continue
                messages.append(msg)
                for tc in tool_calls:
                    fn = tc["function"]
                    try:
                        tool_input = json.loads(fn["arguments"])
                    except json.JSONDecodeError:
                        tool_input = {}

                    log.debug("Sub-agent tool: %s(%s)", fn["name"], list(tool_input.keys()))
                    result = await _execute_sub_agent_tool(fn["name"], tool_input, user_context)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result[:2000],  # cap tool results to stay in context
                    })

            else:
                # Hit MAX_SUB_AGENT_TURNS — return whatever we have
                final_text = text or "Agent reached turn limit."

        # Try to parse final output as JSON
        if final_text:
            try:
                if final_text.startswith("```"):
                    final_text = final_text.split("\n", 1)[1] if "\n" in final_text else final_text[3:]
                if final_text.endswith("```"):
                    final_text = final_text[:-3].rstrip()
                return json.loads(final_text)
            except (json.JSONDecodeError, ValueError):
                return {"text": final_text}
        return {"text": ""}

    except Exception as e:
        log.error("Sub-agent failed: %s", e)
        return {"error": str(e), "partial": final_text}


async def _run_parallel_agents(
    agents: list[dict],
    user_context: dict | None = None,
) -> list[dict]:
    """Run multiple sub-agents in parallel. Returns results in same order.

    Each agent dict has: {task: str, instructions: str}
    All agents run concurrently via asyncio.gather.
    """
    tasks = [
        _run_sub_agent(a["task"], a["instructions"], user_context)
        for a in agents
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    final = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            log.error("Parallel agent %d failed: %s", i, r)
            final.append({"error": str(r), "agent_index": i})
        else:
            r["agent_index"] = i
            final.append(r)
    return final


# ── TTS generation ────────────────────────────────────────────────────

# ElevenLabs voice presets
TTS_VOICES = {
    "default": "pNInz6obpgDQGcFmaJgB",  # Adam — clear, neutral
    "warm": "EXAVITQu4vr4xnSDxMaL",     # Bella — warm, friendly
    "clear": "21m00Tcm4TlvDq8ikWAM",    # Rachel — clear, professional
    "deep": "VR6AewLTigWG4xSOukaG",     # Arnold — deep, authoritative
}

# ElevenLabs chunk limit (~5000 chars per request for reliable output)
TTS_CHUNK_SIZE = 4500


async def _submit_background_job(
    task: str, title: str, output_type: str,
    context: dict, user_context: dict,
) -> dict:
    """Submit a background generation job. Returns immediately with a placeholder artifact.

    The agent runs in the background with full tool access:
    - byo_read, byo_list (read student materials)
    - search_courses (find course content)
    - text_to_speech (generate audio)
    - save_artifact (store the final result)

    The placeholder appears in Learning Aids as "Processing..." and updates when done.
    """
    import hashlib
    from datetime import datetime

    user_id = user_context.get("email", "")
    job_id = hashlib.sha256(f"{user_id}:{title}:{time.time()}".encode()).hexdigest()[:16]

    # Create placeholder artifact immediately
    db = _get_db()
    await db.artifacts.insert_one({
        "artifact_id": job_id,
        "user_id": user_id,
        "type": output_type,
        "title": title,
        "status": "processing",
        "content": {},
        "created_at": datetime.utcnow(),
    })

    # Spawn the background agent
    asyncio.create_task(_run_background_generation(
        job_id=job_id,
        task=task,
        title=title,
        output_type=output_type,
        context=context,
        user_context=user_context,
    ))

    log.info("Background job submitted: %s (%s) — %s", job_id[:8], output_type, task[:60])

    return {
        "artifact_id": job_id,
        "type": output_type,
        "title": title,
        "status": "processing",
        "message": f"Generating in the background. It will appear in your Learning Aids when ready.",
        "saved": True,
        "content": {"status": "processing"},
    }


# ── Background generation tools ──────────────────────────────────────

BACKGROUND_AGENT_TOOLS = [
    {
        "name": "byo_read",
        "description": "Read content from student's uploaded materials.",
        "parameters": {
            "type": "object",
            "properties": {
                "collection_id": {"type": "string"},
                "query": {"type": "string"},
                "chunk_index": {"type": "number"},
            },
            "required": ["collection_id"],
        },
    },
    {
        "name": "byo_list",
        "description": "List all chunks in a BYO collection.",
        "parameters": {
            "type": "object",
            "properties": {"collection_id": {"type": "string"}},
            "required": ["collection_id"],
        },
    },
    {
        "name": "search_courses",
        "description": "Search the course catalog.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "text_to_speech",
        "description": (
            "Convert text to spoken audio. Returns audio bytes saved to storage. "
            "Write text in natural spoken style — conversational, clear. "
            "For podcasts/digests: use a warm, engaging tone with pauses ('...'). "
            "For revision: use a clear, structured tone with emphasis on key terms."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to speak (max ~5000 chars per call, chain for longer)"},
                "voice": {"type": "string", "enum": ["default", "warm", "clear", "deep"]},
            },
            "required": ["text"],
        },
    },
    {
        "name": "save_result",
        "description": "Save the final generated content as the artifact. Call this when done.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "object",
                    "description": "The artifact content. Structure depends on type: "
                    "{markdown: '...'} for notes/documents, {cards: [{front, back}]} for flashcards, "
                    "{audio_url: '...'} for audio, {steps: [{title, description}]} for study plans.",
                },
            },
            "required": ["content"],
        },
    },
]

MAX_BACKGROUND_TURNS = 15  # more turns for complex generation


async def _execute_background_tool(name: str, tool_input: dict, job_context: dict) -> str:
    """Execute a tool within a background generation agent."""
    user_context = job_context.get("user_context", {})

    if name == "byo_read":
        from app.tools import _execute_byo_read
        return await _execute_byo_read(tool_input)
    elif name == "byo_list":
        from app.tools import _execute_byo_list
        return await _execute_byo_list(tool_input)
    elif name == "search_courses":
        return await _execute_tool("search_courses", tool_input, user_context)
    elif name == "text_to_speech":
        return await _execute_tts_tool(tool_input, job_context)
    elif name == "save_result":
        return await _save_background_result(tool_input, job_context)
    return f"Unknown tool: {name}"


async def _execute_tts_tool(tool_input: dict, job_context: dict) -> str:
    """Generate audio from text using ElevenLabs TTS. Returns the audio URL."""
    from app.core.config import settings

    api_key = settings.ELEVENLABS_API_KEY
    if not api_key:
        return "Error: No ElevenLabs API key configured"

    voice = tool_input.get("voice", "default")
    voice_id = TTS_VOICES.get(voice, TTS_VOICES["default"])
    text = tool_input.get("text", "")
    if not text:
        return "Error: No text provided"

    try:
        from elevenlabs import ElevenLabs
        client = ElevenLabs(api_key=api_key)

        chunks = _chunk_text_for_tts(text)
        audio_segments = []
        for chunk in chunks:
            loop = asyncio.get_event_loop()
            def _gen(c=chunk):
                return b"".join(client.text_to_speech.convert(
                    voice_id=voice_id, text=c,
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                ))
            segment = await loop.run_in_executor(None, _gen)
            audio_segments.append(segment)

        full_audio = b"".join(audio_segments)

        # Save to storage
        from byo.storage import default_storage
        import hashlib
        user_id = job_context.get("user_id", "")
        audio_id = hashlib.sha256(f"{user_id}:{time.time()}".encode()).hexdigest()[:12]
        filename = f"audio-{audio_id}.mp3"
        storage_path = await default_storage.save(full_audio, user_id, "audio-artifacts", filename)

        # Save resource for serving
        from datetime import datetime
        db = _get_db()
        await db.byo_resources.insert_one({
            "resource_id": audio_id,
            "user_id": user_id,
            "collection_id": "audio-artifacts",
            "source_type": "generated",
            "mime_type": "audio/mpeg",
            "original_name": filename,
            "storage_path": storage_path,
            "file_size": len(full_audio),
            "status": "ready",
            "created_at": datetime.utcnow(),
        })

        audio_url = f"/api/v1/byo/audio/{audio_id}"
        # Store in job context for save_result
        job_context.setdefault("generated_audio", []).append(audio_url)

        return f"Audio generated: {audio_url} ({len(full_audio)} bytes, ~{round(len(text)/15)}s)"

    except Exception as e:
        return f"TTS error: {str(e)[:200]}"


async def _save_background_result(tool_input: dict, job_context: dict) -> str:
    """Save final result — updates the placeholder artifact from processing → ready."""
    db = _get_db()
    job_id = job_context["job_id"]
    content = tool_input.get("content", {})

    # Merge any generated audio URLs
    if job_context.get("generated_audio"):
        content["audio_url"] = job_context["generated_audio"][-1]  # use last one
        if len(job_context["generated_audio"]) > 1:
            content["all_audio_urls"] = job_context["generated_audio"]

    await db.artifacts.update_one(
        {"artifact_id": job_id},
        {"$set": {"status": "ready", "content": content}},
    )
    return "Artifact saved successfully. It will appear in the student's Learning Aids."


async def _run_background_generation(
    job_id: str, task: str, title: str, output_type: str,
    context: dict, user_context: dict,
):
    """Background agent that runs a multi-step generation pipeline.

    Has access to: byo_read, byo_list, search_courses, text_to_speech, save_result.
    Runs an agentic loop until it calls save_result or hits the turn limit.
    """
    import httpx
    from app.core.config import settings

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        await _update_artifact_status(job_id, "error", error="No API key")
        return

    user_id = user_context.get("email", "")
    job_context = {"job_id": job_id, "user_id": user_id, "user_context": user_context}

    system_prompt = f"""You are a background generation agent. Your task:

{task}

Output type: {output_type}
Title: {title}

Context: {json.dumps(context)[:2000]}

You have tools to:
1. Read student materials (byo_read, byo_list) — use collection_ids from context
2. Search courses (search_courses) — find relevant course content
3. Generate audio (text_to_speech) — convert text to spoken audio
4. Save result (save_result) — call this when done with the final content

WORKFLOW:
1. Gather any needed content using byo_read/search_courses
2. Synthesize/transform the content into the requested output
3. For audio: write a spoken-style script, then call text_to_speech
4. Call save_result with the final content

IMPORTANT: Always end by calling save_result. The content structure depends on output_type:
- audio: {{audio_url: "..."}} (auto-populated from text_to_speech)
- notes/document: {{markdown: "..."}}
- flashcards: {{cards: [{{front: "...", back: "..."}}]}}
- study_plan: {{steps: [{{title: "...", description: "..."}}]}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Begin generating."},
    ]
    tools_spec = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}} for t in BACKGROUND_AGENT_TOOLS]

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            for turn in range(MAX_BACKGROUND_TURNS):
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": settings.MODEL_FAST,
                        "max_tokens": 8000,
                        "temperature": 0,
                        "messages": messages,
                        "tools": tools_spec,
                    },
                )
                if resp.status_code != 200:
                    log.error("Background agent API error: %d", resp.status_code)
                    await _update_artifact_status(job_id, "error", error=f"API error {resp.status_code}")
                    return

                msg = resp.json()["choices"][0]["message"]
                tool_calls = msg.get("tool_calls", [])

                if not tool_calls:
                    # Agent finished without calling save_result — save text as markdown
                    text = msg.get("content", "")
                    if text:
                        await _save_background_result(
                            {"content": {"markdown": text}}, job_context
                        )
                    break

                messages.append(msg)
                for tc in tool_calls:
                    fn = tc["function"]
                    try:
                        ti = json.loads(fn["arguments"])
                    except json.JSONDecodeError:
                        ti = {}

                    log.info("Background agent [%s] tool: %s", job_id[:8], fn["name"])
                    result = await _execute_background_tool(fn["name"], ti, job_context)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result[:3000],
                    })

                    # If save_result was called, we're done
                    if fn["name"] == "save_result":
                        log.info("Background job %s complete", job_id[:8])
                        return

        log.warning("Background job %s hit turn limit", job_id[:8])
        await _update_artifact_status(job_id, "error", error="Generation took too long")

    except Exception as e:
        log.error("Background job %s failed: %s", job_id[:8], e)
        await _update_artifact_status(job_id, "error", error=str(e)[:200])


async def _update_artifact_status(artifact_id: str, status: str, **extra):
    """Update artifact status in MongoDB."""
    db = _get_db()
    updates = {"status": status}
    if extra.get("error"):
        updates["error"] = extra["error"]
    await db.artifacts.update_one(
        {"artifact_id": artifact_id},
        {"$set": updates},
    )


def _chunk_text_for_tts(text: str) -> list[str]:
    """Split text into chunks suitable for TTS API calls.

    Splits at sentence boundaries to avoid cutting mid-word.
    Each chunk is ≤ TTS_CHUNK_SIZE chars.
    """
    if len(text) <= TTS_CHUNK_SIZE:
        return [text]

    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 > TTS_CHUNK_SIZE:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current += " " + sentence if current else sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text[:TTS_CHUNK_SIZE]]


# ── Document generation ─────────────────────────────────────────────────

async def _generate_pdf(title: str, content_markdown: str, user_id: str) -> dict:
    """Generate a PDF from markdown content. Returns {document_id, download_url}."""
    import os
    import hashlib

    doc_id = hashlib.sha256(f"{user_id}:{title}:{time.time()}".encode()).hexdigest()[:16]

    # Store as HTML (browser renders to PDF via print)
    # In production, use weasyprint or similar
    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>{title}</title>
<style>
body {{ font-family: 'Inter', sans-serif; max-width: 700px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; line-height: 1.7; }}
h1 {{ font-size: 1.8rem; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; }}
h2 {{ font-size: 1.4rem; margin-top: 2em; }}
h3 {{ font-size: 1.1rem; }}
code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
pre {{ background: #f3f4f6; padding: 16px; border-radius: 8px; overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #d1d5db; padding: 8px 12px; text-align: left; }}
th {{ background: #f9fafb; font-weight: 600; }}
blockquote {{ border-left: 3px solid #6366f1; margin-left: 0; padding-left: 16px; color: #4b5563; }}
@media print {{ body {{ margin: 0; }} }}
</style>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
</head><body>
<h1>{title}</h1>
<div id="content">{content_markdown}</div>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script>
document.getElementById('content').innerHTML = marked.parse(document.getElementById('content').textContent);
</script>
</body></html>"""

    # Store HTML content in MongoDB (no filesystem dependency)
    try:
        from app.core.mongodb import get_mongo_db
        db = get_mongo_db()
        from datetime import datetime
        await db.documents.insert_one({
            "document_id": doc_id,
            "user_id": user_id,
            "title": title,
            "format": "html",
            "html_content": html,
            "markdown_source": content_markdown,
            "created_at": datetime.utcnow(),
        })
    except Exception as e:
        log.warning("Failed to save document: %s", e)

    return {
        "document_id": doc_id,
        "title": title,
        "format": "html",
        "download_url": f"/api/v1/documents/{doc_id}",
    }


# ── Tool execution ──────────────────────────────────────────────────────

async def _execute_tool(name: str, input_data: dict, user_context: dict) -> str:
    """Execute an Euler tool. Returns result as string."""

    if name == "search_courses":
        # Get full course catalog
        all_courses = []
        try:
            from app.api.routes.content import _courses_cache
            all_courses = _courses_cache.get("data") or []
            if not all_courses:
                from app.core.database import async_session_maker
                from sqlalchemy import select
                from app.models.course import Course
                async with async_session_maker() as db:
                    rows = (await db.execute(select(Course))).scalars().all()
                    all_courses = [{"id": c.id, "title": c.title, "description": c.description,
                                    "lesson_count": 0, "module_count": 0} for c in rows]
        except Exception:
            pass

        # For broad queries ("what courses", "what do you have", "show me"), return full catalog
        query_lower = input_data["query"].lower()
        is_browse = any(w in query_lower for w in ["course", "available", "have", "offer", "catalog", "all", "show", "browse", "list"])

        if is_browse and all_courses:
            lines = [f"FULL COURSE CATALOG ({len(all_courses)} courses):"]
            for c in all_courses:
                lines.append(
                    f"\n- **{c.get('title', '?')}** (id={c['id']})"
                    f"\n  {c.get('lesson_count', '?')} lessons, {c.get('module_count', '?')} modules"
                    f"\n  {(c.get('description') or '')[:120]}"
                    f"\n  Explore: /courses/{c['id']}"
                )
            return "\n".join(lines)

        # For specific topic queries, use vector search
        from app.services.content_resolver import resolve_content, format_content_brief
        brief = await resolve_content(input_data["query"])

        if not brief.get("matched_courses"):
            # Fallback: check catalog by title match
            q_words = [w for w in query_lower.split() if len(w) > 2]
            title_matches = [c for c in all_courses
                             if any(w in (c.get("title") or "").lower() for w in q_words)]
            if title_matches:
                lines = [f"Found {len(title_matches)} course(s) by title:"]
                for c in title_matches:
                    lines.append(f"\n- **{c.get('title')}** (id={c['id']}) — {c.get('lesson_count', '?')} lessons"
                                 f"\n  {(c.get('description') or '')[:120]}"
                                 f"\n  Explore: /courses/{c['id']}")
                return "\n".join(lines)
            return "No matching courses found. The Tutor can still teach this topic on-demand (skill='free')."

        # Enrich vector search results with catalog metadata
        result = format_content_brief(brief)
        catalog = {c["id"]: c for c in all_courses}
        extras = []
        for mc in brief["matched_courses"]:
            cid = mc.get("course_id")
            c = catalog.get(cid, {})
            if c:
                has_video = any(l.get("has_video") for l in mc.get("matched_lessons", []))
                extras.append(
                    f"\nCourse detail — {c.get('title', '?')} (id={cid}):"
                    f"\n  {c.get('lesson_count', '?')} lessons, {c.get('module_count', '?')} modules"
                    f"\n  {(c.get('description') or '')[:150]}"
                    f"\n  Has video lectures: {'yes' if has_video else 'unknown'}"
                    f"\n  Explore: /courses/{cid}"
                )
        if extras:
            result += "\n" + "\n".join(extras)
        return result

    elif name in ("byo_read", "byo_list"):
        from app.tools import _execute_byo_read, _execute_byo_list
        if name == "byo_read":
            return await _execute_byo_read(input_data)
        else:
            return await _execute_byo_list(input_data)

    elif name == "search_materials":
        db = _get_db()
        email = user_context.get("email", "")
        query = input_data.get("query", "")
        col_id = input_data.get("collection_id")

        # First: list user's collections so Euler knows what's available
        collections = []
        async for col in db.collections.find(
            {"user_id": email},
            {"_id": 0, "collection_id": 1, "title": 1, "status": 1, "stats": 1},
        ).sort("created_at", -1).limit(10):
            collections.append(col)

        if not collections:
            return "You haven't uploaded any materials yet. You can upload PDFs, notes, or other study materials from the Materials tab."

        # Build collection IDs for this user
        user_col_ids = [c["collection_id"] for c in collections]

        # Search chunks across user's collections
        chunk_filter = {"collection_id": {"$in": user_col_ids}}
        if col_id:
            chunk_filter = {"collection_id": col_id}

        if query.strip():
            # Try regex search on content
            words = [w for w in query.strip().split() if len(w) > 2]
            if words:
                word_patterns = [{"content": {"$regex": w, "$options": "i"}} for w in words[:5]]
                chunk_filter["$or"] = word_patterns

        cursor = db.byo_chunks.find(
            chunk_filter,
            {"_id": 0, "chunk_id": 1, "content": 1, "topics": 1, "collection_id": 1, "labels": 1},
        ).limit(8)
        chunks = [doc async for doc in cursor]

        # Fetch resources for video collections (needed for watch-along)
        col_resources = {}
        for col in collections:
            tags = col.get("tags", [])
            title_lower = (col.get("title", "") or "").lower()
            if any(t in tags for t in ("video", "youtube", "watch_along")) or "video" in title_lower or "youtube" in title_lower:
                res_cursor = db.byo_resources.find(
                    {"collection_id": col["collection_id"]},
                    {"_id": 0, "resource_id": 1, "source_url": 1, "mime_type": 1},
                ).limit(3)
                col_resources[col["collection_id"]] = [r async for r in res_cursor]

        # Build response
        lines = [f"Student has {len(collections)} uploaded material(s):"]
        for col in collections:
            stats = col.get("stats", {})
            chunk_count = stats.get('chunks', 0)
            status = col.get('status', '?')
            # Give Euler a clearer picture of readiness
            if status == 'ready' and chunk_count > 0:
                readiness = f"ready, {chunk_count} chunks available"
            elif status == 'ready' and chunk_count == 0:
                readiness = "ready but no text content extracted (file may be viewable)"
            elif status == 'processing':
                readiness = "still processing"
            elif status == 'error':
                readiness = "processing failed"
            else:
                readiness = status

            # Include resource_id + source_url for video collections (needed for watch-along)
            resources = col_resources.get(col["collection_id"], [])
            resource_info = ""
            if resources:
                rid = resources[0].get("resource_id", "")
                src = resources[0].get("source_url", "")
                resource_info = f", resource_id:{rid}"
                if src:
                    resource_info += f", source_url:{src}"
            lines.append(f"  - {col.get('title', '?')} (collection_id:{col['collection_id']}{resource_info}, {readiness})")

        if chunks:
            lines.append(f"\nContent matches ({len(chunks)} chunks):")
            for c in chunks:
                preview = c.get("content", "")[:120].replace("\n", " ")
                lines.append(f"  - {preview}...")
        elif query.strip():
            lines.append(f"\nNo content matched '{query}' — but the materials are available. Try browsing by collection.")

        return "\n".join(lines)

    elif name == "search_sessions":
        from app.core.mongodb import get_tutor_db
        sdb = get_tutor_db()
        email = user_context.get("email", "")
        query = input_data.get("query", "")
        if not query.strip():
            return "Please provide a search query."

        cursor = sdb["sessions"].find(
            {
                "userEmail": email,
                "$or": [
                    {"headline": {"$regex": re.escape(query), "$options": "i"}},
                    {"headlineDescription": {"$regex": re.escape(query), "$options": "i"}},
                    {"intent.raw": {"$regex": re.escape(query), "$options": "i"}},
                    {"plan.sessionObjective": {"$regex": re.escape(query), "$options": "i"}},
                ],
            },
            {"_id": 0, "sessionId": 1, "courseId": 1, "headline": 1,
             "headlineDescription": 1, "startedAt": 1, "status": 1,
             "durationSec": 1, "plan.sessionObjective": 1},
        ).sort("startedAt", -1).limit(5)

        sessions = [doc async for doc in cursor]
        if not sessions:
            return f"No past sessions found matching '{query}'."

        lines = [f"Found {len(sessions)} session(s):"]
        for s in sessions:
            sid = s.get("sessionId", "?")
            headline = s.get("headline") or s.get("plan", {}).get("sessionObjective") or "Teaching session"
            status = s.get("status", "?")
            dur = f"{round(s.get('durationSec', 0) / 60)} min" if s.get("durationSec") else ""
            lines.append(f"  - {headline} ({status}, {dur}) — resume: /session/{sid}")
        lines.append("\nTo resume a session, use navigate_ui with the /session/{id} path.")
        return "\n".join(lines)

    elif name == "get_student_context":
        context_parts = []
        if user_context.get("student_model"):
            context_parts.append(f"Student model: {json.dumps(user_context['student_model'])[:500]}")
        if user_context.get("session_history"):
            context_parts.append(f"Recent sessions: {json.dumps(user_context['session_history'])[:500]}")
        if user_context.get("collections"):
            context_parts.append(f"Collections: {json.dumps(user_context['collections'])[:300]}")
        return "\n".join(context_parts) if context_parts else "No student context available (new student)."

    elif name == "spawn_agents":
        agents = input_data.get("agents", [])
        if not agents:
            return json.dumps({"error": "No agents specified"})

        log.info("Spawning %d parallel sub-agents", len(agents))
        for i, a in enumerate(agents):
            log.info("  Agent %d: %s", i, a.get("task", "?")[:80])

        results = await _run_parallel_agents(agents, user_context)

        # Emit spawned/result events for each agent
        # (handled inline — the results are returned together)
        return json.dumps({
            "agent_count": len(agents),
            "results": results,
        })

    elif name == "background_generate":
        # Long-running — create placeholder immediately, run generation in background.
        result = await _submit_background_job(
            task=input_data["task"],
            title=input_data["title"],
            output_type=input_data["output_type"],
            context=input_data.get("context", {}),
            user_context=user_context,
        )
        return json.dumps(result)

    elif name == "create_artifact":
        db = _get_db()
        artifact_id = str(uuid.uuid4())[:12]
        from datetime import datetime
        doc = {
            "artifact_id": artifact_id,
            "user_id": user_context.get("email", ""),
            "type": input_data["type"],
            "title": input_data["title"],
            "content": input_data.get("content", {}),
            "source": input_data.get("source", {}),
            "created_at": datetime.utcnow(),
        }
        await db.artifacts.insert_one(doc)
        return json.dumps({
            "artifact_id": artifact_id,
            "type": input_data["type"],
            "title": input_data["title"],
            "content": input_data.get("content", {}),
            "saved": True,
        })

    elif name == "generate_document":
        result = await _generate_pdf(
            title=input_data["title"],
            content_markdown=input_data["content_markdown"],
            user_id=user_context.get("email", ""),
        )
        return json.dumps(result)

    elif name == "process_video_url":
        # Create a BYO collection + resource for the video, kick off processing
        url = input_data["url"]
        title = input_data.get("title", "")
        user_email = user_context.get("email", "")

        db = _get_db()
        collection_id = str(uuid.uuid4())[:12]
        resource_id = str(uuid.uuid4())

        # Auto-detect title from YouTube
        if not title and ("youtube.com" in url or "youtu.be" in url):
            try:
                import re as _re
                # Try to get title from yt-dlp (fast metadata only)
                import yt_dlp
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get("title", "")
            except Exception:
                title = "YouTube Video"

        title = title or "Video"

        # Create collection
        await db.collections.insert_one({
            "collection_id": collection_id,
            "user_id": user_email,
            "title": title,
            "description": f"Video: {url}",
            "intent": "watch_along",
            "status": "processing",
            "stats": {"resources": 1, "chunks": 0, "topics": []},
            "tags": ["video", "watch_along"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })

        # Create resource
        mime = "application/x-youtube" if ("youtube" in url or "youtu.be" in url) else "video/mp4"
        await db.byo_resources.insert_one({
            "resource_id": resource_id,
            "collection_id": collection_id,
            "user_id": user_email,
            "source_type": "url",
            "mime_type": mime,
            "original_name": title,
            "source_url": url,
            "storage_path": None,
            "file_size": 0,
            "status": "queued",
            "progress": 0.0,
            "meta": {},
            "chunk_count": 0,
            "created_at": datetime.utcnow(),
        })

        # Submit processing job
        try:
            from byo.pipeline.orchestrator import submit_processing_job
            job_id = await submit_processing_job(
                resource_id, collection_id, user_email,
                {"mime_type": mime, "source_url": url},
            )
            log.info("Video processing started: %s → job %s", url[:60], job_id[:8] if job_id else "?")
        except Exception as e:
            log.warning("Video processing submit failed: %s", e)

        return json.dumps({
            "collection_id": collection_id,
            "resource_id": resource_id,
            "title": title,
            "source_url": url,
            "status": "processing",
            "message": f"Processing '{title}' — transcript will be ready in 1-2 minutes. "
                       f"You can start a watch-along session now; the transcript will load as it processes.",
        })

    elif name == "start_tutor_session":
        session_id = str(uuid.uuid4())
        context = {
            "session_id": session_id,
            "skill": input_data.get("skill", "free"),
            "mode": input_data.get("mode", "teaching"),
            "enriched_intent": input_data.get("enriched_intent", ""),
            "plan": input_data.get("plan", []),
            "course_id": input_data.get("course_id"),
            "collection_id": input_data.get("collection_id"),
            "resource_id": input_data.get("resource_id"),
            "teaching_notes": input_data.get("teaching_notes", ""),
        }
        return json.dumps({"action": "start_session", "session_id": session_id, "context": context})

    elif name == "navigate_ui":
        return json.dumps({
            "action": "navigate",
            "target": input_data["target"],
            "label": input_data.get("label", "Go"),
        })

    elif name == "ask_permission":
        perm_id = str(uuid.uuid4())[:8]
        return json.dumps({
            "action": "permission",
            "permission_id": perm_id,
            "question": input_data["question"],
            "action_label": input_data["action_label"],
            "deny_label": input_data.get("deny_label", "Not now"),
            "action_data": input_data.get("action_data", {}),
        })

    elif name == "respond_inline":
        return json.dumps({
            "action": "respond",
            "text": input_data["text"],
            "actions": input_data.get("actions", []),
        })

    return f"Unknown tool: {name}"


def _get_db():
    from app.core.mongodb import get_mongo_db
    return get_mongo_db()


# ── Main orchestration loop ─────────────────────────────────────────────

async def orchestrate(
    user_input: str,
    user_context: dict,
    attachments: list[dict] | None = None,
    history: list[dict] | None = None,
) -> AsyncIterator:
    """Run Euler's agentic loop.

    Streams messages to the frontend as Euler reasons,
    calls tools, spawns sub-agents, and builds its response.

    Args:
        history: Prior conversation turns [{role: "user"|"assistant", content: "..."}]
    """
    import httpx
    from app.core.config import settings

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        yield TextDelta(text="Configuration error — no API key.")
        yield Done(turns_used=0)
        return

    # Build system prompt
    from app.orchestrator.prompts.orchestrator import build_orchestrator_prompt
    system_prompt = build_orchestrator_prompt(user_context)

    # Build message list: system + history + new user message
    messages = [{"role": "system", "content": system_prompt}]

    # Append conversation history (keep last 20 turns to avoid token overflow)
    if history:
        for h in history[-20:]:
            role = h.get("role", "user")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": h.get("content", "")})

    # Build user message — multimodal if attachments present
    # OpenRouter: all file types use image_url with data:{mime};base64,{data} URI
    # Supports: images, PDFs, audio, video natively
    if attachments:
        content_parts = [{"type": "text", "text": user_input}]
        for att in attachments:
            mime = att.get("mime_type", "")
            data = att.get("data", "")
            if data and mime:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{data}"},
                })
        messages.append({"role": "user", "content": content_parts})
    else:
        messages.append({"role": "user", "content": user_input})

    tools_spec = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in ORCHESTRATOR_TOOLS]

    # Add OpenRouter web search server tool — model decides when to search
    tools_spec.append({
        "type": "openrouter:web_search",
        "parameters": {
            "max_results": 5,
            "search_context_size": "medium",
        },
    })

    turns = 0
    while turns < MAX_TURNS:
        turns += 1
        log.info("Euler turn %d, %d messages", turns, len(messages))

        full_text = ""
        tool_calls = []  # accumulated from stream chunks
        tool_call_args = {}  # {index: args_str}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": settings.euler_model,
                        "max_tokens": 4000,
                        "messages": messages,
                        "tools": tools_spec,
                        "stream": True,
                        # Prompt caching: route to Anthropic for cache support
                        "provider": {
                            "order": ["Anthropic"],
                            "allow_fallbacks": True,
                        },
                    },
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        log.error("Euler API %d (turn %d): %s", resp.status_code, turns, body[:500])
                        yield TextDelta(text=f"Error: API returned {resp.status_code}")
                        break

                    buffer = ""
                    async for raw in resp.aiter_text():
                        buffer += raw
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue
                            payload = line[6:]
                            if payload == "[DONE]":
                                break
                            try:
                                chunk = json.loads(payload)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})

                                # Stream text tokens immediately
                                if delta.get("content"):
                                    yield TextDelta(text=delta["content"])
                                    full_text += delta["content"]

                                # Accumulate tool calls
                                if delta.get("tool_calls"):
                                    for tc in delta["tool_calls"]:
                                        idx = tc.get("index", 0)
                                        # Ensure slot exists with required fields
                                        while len(tool_calls) <= idx:
                                            tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                                        if tc.get("id"):
                                            tool_calls[idx]["id"] = tc["id"]
                                        if tc.get("function", {}).get("name"):
                                            tool_calls[idx]["function"]["name"] = tc["function"]["name"]
                                        if tc.get("function", {}).get("arguments"):
                                            tool_calls[idx]["function"]["arguments"] += tc["function"]["arguments"]

                            except (json.JSONDecodeError, IndexError, KeyError):
                                continue

        except Exception as e:
            yield TextDelta(text=f"Error: {str(e)[:100]}")
            break

        # No tool calls = final response, done
        if not tool_calls:
            break

        # Execute tool calls — run independent calls in parallel
        assistant_msg = {"role": "assistant", "content": full_text or None, "tool_calls": tool_calls}
        messages.append(assistant_msg)

        # Signal all tool calls starting
        for tc in tool_calls:
            func = tc["function"]
            try:
                tool_input = json.loads(func["arguments"])
            except json.JSONDecodeError:
                tool_input = {}
            yield ToolCallStart(tool_name=func["name"], tool_input=tool_input, call_id=tc["id"])

        # Execute all tool calls concurrently
        async def _exec_one(tc_item):
            func = tc_item["function"]
            try:
                ti = json.loads(func["arguments"])
            except json.JSONDecodeError:
                ti = {}
            return await _execute_tool(func["name"], ti, user_context)

        results_list = await asyncio.gather(
            *[_exec_one(tc) for tc in tool_calls],
            return_exceptions=True,
        )

        tool_results = []
        for tc, result in zip(tool_calls, results_list):
            func = tc["function"]
            tool_name = func["name"]

            if isinstance(result, Exception):
                log.error("Tool %s failed: %s", tool_name, result)
                result = f"Tool {tool_name} encountered an error: {str(result)[:200]}"

            # Send more of the result for search tools so frontend can render cards
            preview_len = 600 if tool_name.startswith("search") else 200
            yield ToolCallResult(tool_name=tool_name, result=result[:preview_len], call_id=tc["id"])

            # Check for special actions and emit typed messages
            try:
                result_data = json.loads(result)
                if not isinstance(result_data, dict):
                    result_data = {}

                if result_data.get("action") == "start_session":
                    yield SessionStart(
                        session_id=result_data["session_id"],
                        context=result_data["context"],
                    )
                elif result_data.get("action") == "navigate":
                    yield NavigateUI(
                        target=result_data["target"],
                        label=result_data.get("label", "Go"),
                    )
                elif result_data.get("action") == "permission":
                    yield PermissionRequest(
                        permission_id=result_data["permission_id"],
                        question=result_data["question"],
                        action_label=result_data["action_label"],
                        deny_label=result_data.get("deny_label", "Not now"),
                        context=result_data.get("action_data", {}),
                    )
                elif result_data.get("saved"):
                    yield ArtifactCreated(
                        artifact_id=result_data.get("artifact_id", ""),
                        artifact_type=result_data.get("type", ""),
                        title=result_data.get("title", ""),
                        content=result_data.get("content", {}),
                    )
                elif result_data.get("download_url"):
                    yield DocumentGenerated(
                        document_id=result_data.get("document_id", ""),
                        title=result_data.get("title", ""),
                        format=result_data.get("format", "html"),
                        download_url=result_data["download_url"],
                    )

            except (json.JSONDecodeError, TypeError):
                pass

            tool_results.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

        messages.extend(tool_results)

    yield Done(turns_used=turns)
