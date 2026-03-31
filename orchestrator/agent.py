"""Orchestrator agent — dynamic agentic loop.

The Orchestrator is an LLM agent (Haiku for speed) with tools.
It runs an agentic loop: reason → call tools → get results → reason → ...
until it has everything to respond to the student.

Sub-agents are spawned dynamically with custom instructions.
Each sub-agent is a focused Haiku call that returns structured results.

Usage:
    async for message in orchestrate(user_input, user_context):
        # message is one of: TextDelta, ToolCall, SubAgentResult,
        #                     ArtifactCreated, SessionStart, Done
        yield message
"""

from __future__ import annotations

import asyncio
import json
import logging
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
    """Streamed text content from the Orchestrator."""
    text: str
    type: str = "text_delta"


@dataclass
class ToolCallStart:
    """Orchestrator is calling a tool."""
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
    """An artifact (flashcards, notes, plan) was created."""
    artifact_id: str
    artifact_type: str
    title: str
    preview: dict
    type: str = "artifact_created"


@dataclass
class SessionStart:
    """Orchestrator is handing off to the Tutor."""
    session_id: str
    context: dict  # TutorSessionContext
    type: str = "session_start"


@dataclass
class Done:
    """Orchestrator loop complete."""
    turns_used: int
    type: str = "done"


# ── Orchestrator tools ──────────────────────────────────────────────────

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
        "name": "spawn_agent",
        "description": (
            "Spawn a sub-agent to do focused work in the background. "
            "Give it a clear task and specific instructions. "
            "Results will be available when the sub-agent completes. "
            "Use for: reading materials, analysing exams, building plans, creating content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "What the sub-agent should do. Be specific and detailed.",
                },
                "instructions": {
                    "type": "string",
                    "description": "Detailed instructions for the sub-agent. Include format of expected output.",
                },
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tool names the sub-agent should have access to.",
                },
            },
            "required": ["task", "instructions"],
        },
    },
    {
        "name": "create_artifact",
        "description": (
            "Create a study aid for the student — flashcards, revision notes, "
            "study plan, summary, or custom curriculum. "
            "The artifact is saved permanently and shown inline to the student."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["flashcards", "revision_notes", "study_plan", "summary", "curriculum"],
                    "description": "Type of artifact to create",
                },
                "title": {"type": "string", "description": "Title for the artifact"},
                "content": {
                    "type": "object",
                    "description": "Artifact content (type-specific). Flashcards: {cards: [{front, back}]}. Notes: {markdown: '...'}. Plan: {sessions: [...]}.",
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
        "name": "start_tutor_session",
        "description": (
            "Start a teaching session on the Board. "
            "Build an enriched TutorSessionContext with all the information "
            "the Tutor needs: skill, mode, plan, content refs, student context. "
            "The student will be redirected to the Board."
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
                "teaching_notes": {
                    "type": "string",
                    "description": "Notes for the Tutor about this student (weak areas, preferences, what to address)",
                },
            },
            "required": ["skill", "enriched_intent"],
        },
    },
    {
        "name": "respond_inline",
        "description": (
            "Respond to the student inline on the Home screen. "
            "Use for: quick answers, clarification questions, presenting options. "
            "Do NOT use this if you need to start a teaching session — use start_tutor_session instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Response text (markdown supported)"},
                "actions": {
                    "type": "array",
                    "description": "Action buttons to show",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "action": {"type": "string", "description": "start_session, save_artifact, modify, etc."},
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

async def _run_sub_agent(task: str, instructions: str, tools: list[str] | None = None) -> dict:
    """Run a sub-agent — a focused Haiku call with specific instructions.

    The sub-agent gets its own context (no conversation history from parent).
    It returns structured JSON results.
    """
    import httpx
    from backend.app.core.config import settings

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        return {"error": "No API key"}

    prompt = f"""You are a focused sub-agent. Your task:

{task}

Instructions:
{instructions}

Output your results as JSON. Be thorough but concise."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "anthropic/claude-haiku-4-5-20251001",
                    "max_tokens": 4000,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            if resp.status_code != 200:
                return {"error": f"API {resp.status_code}"}

            text = resp.json()["choices"][0]["message"]["content"]

            # Try to parse as JSON
            try:
                # Strip markdown fences
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3].rstrip()
                return json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}

    except Exception as e:
        log.error("Sub-agent failed: %s", e)
        return {"error": str(e)}


# ── Tool execution ──────────────────────────────────────────────────────

async def _execute_tool(name: str, input_data: dict, user_context: dict) -> str:
    """Execute an Orchestrator tool. Returns result as string."""

    if name == "search_courses":
        from backend.app.services.content_service import search_content
        results = await search_content(input_data["query"], limit=5)
        if not results:
            return "No matching courses found."
        lines = ["Matching courses:"]
        for r in results:
            lines.append(f"  - {r.get('title', '?')} (course:{r.get('courseId', '?')}, {r.get('type', '?')})")
        return "\n".join(lines)

    elif name == "search_materials":
        db_fn = _get_db_fn()
        db = db_fn()
        query = input_data["query"]
        col_id = input_data.get("collection_id")
        filter_q = {"user_id": user_context.get("email", "")}
        if col_id:
            filter_q["collection_id"] = col_id
        # Simple text search across chunks
        filter_q["$or"] = [
            {"content": {"$regex": query, "$options": "i"}},
            {"topics": {"$regex": query, "$options": "i"}},
        ]
        cursor = db.byo_chunks.find(filter_q, {"_id": 0, "chunk_id": 1, "content": 1, "topics": 1, "collection_id": 1}).limit(5)
        results = [doc async for doc in cursor]
        if not results:
            return "No matching materials found in your uploads."
        lines = ["From your materials:"]
        for r in results:
            preview = r.get("content", "")[:80]
            lines.append(f"  chunk:{r.get('chunk_id', '?')} — {preview}...")
        return "\n".join(lines)

    elif name == "get_student_context":
        # Return student model + session history
        email = user_context.get("email", "")
        context_parts = []
        if user_context.get("student_model"):
            context_parts.append(f"Student model: {json.dumps(user_context['student_model'])[:500]}")
        if user_context.get("session_history"):
            context_parts.append(f"Recent sessions: {json.dumps(user_context['session_history'])[:500]}")
        if user_context.get("collections"):
            context_parts.append(f"Collections: {json.dumps(user_context['collections'])[:300]}")
        return "\n".join(context_parts) if context_parts else "No student context available (new student)."

    elif name == "spawn_agent":
        task = input_data["task"]
        instructions = input_data["instructions"]
        result = await _run_sub_agent(task, instructions)
        return json.dumps(result)

    elif name == "create_artifact":
        db_fn = _get_db_fn()
        db = db_fn()
        artifact_id = str(uuid.uuid4())[:12]
        from datetime import datetime
        doc = {
            "artifact_id": artifact_id,
            "user_id": user_context.get("email", ""),
            "type": input_data["type"],
            "title": input_data["title"],
            "content": input_data.get("content", {}),
            "source": input_data.get("source", {}),
            "tags": [],
            "created_at": datetime.utcnow(),
        }
        await db.artifacts.insert_one(doc)
        return json.dumps({"artifact_id": artifact_id, "type": input_data["type"], "title": input_data["title"], "saved": True})

    elif name == "start_tutor_session":
        # Build TutorSessionContext and return session start signal
        session_id = str(uuid.uuid4())
        context = {
            "session_id": session_id,
            "skill": input_data.get("skill", "free"),
            "mode": input_data.get("mode", "teaching"),
            "enriched_intent": input_data.get("enriched_intent", ""),
            "plan": input_data.get("plan", []),
            "course_id": input_data.get("course_id"),
            "collection_id": input_data.get("collection_id"),
            "teaching_notes": input_data.get("teaching_notes", ""),
        }
        return json.dumps({"action": "start_session", "session_id": session_id, "context": context})

    elif name == "respond_inline":
        return json.dumps({"action": "respond", "text": input_data["text"], "actions": input_data.get("actions", [])})

    return f"Unknown tool: {name}"


def _get_db_fn():
    from backend.app.core.mongodb import get_mongo_db
    return get_mongo_db


# ── Main orchestration loop ─────────────────────────────────────────────

async def orchestrate(
    user_input: str,
    user_context: dict,
    attachments: list[dict] | None = None,
) -> AsyncIterator:
    """Run the Orchestrator's agentic loop.

    Streams messages to the frontend as the Orchestrator reasons,
    calls tools, spawns sub-agents, and builds its response.

    Args:
        user_input: What the student typed
        user_context: {email, student_model, session_history, collections}
        attachments: Temp file attachments [{filename, mime_type, content}]
    """
    import httpx
    from backend.app.core.config import settings

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        yield TextDelta(text="Configuration error — no API key.")
        yield Done(turns_used=0)
        return

    # Build system prompt
    from orchestrator.prompts.orchestrator import build_orchestrator_prompt
    system_prompt = build_orchestrator_prompt(user_context)

    # Build initial message
    user_message_parts = [user_input]
    if attachments:
        for att in attachments:
            user_message_parts.append(f"\n[Attached: {att.get('filename', 'file')} ({att.get('mime_type', '?')})]")

    messages = [{"role": "user", "content": "\n".join(user_message_parts)}]

    turns = 0
    while turns < MAX_TURNS:
        turns += 1

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "anthropic/claude-haiku-4-5-20251001",
                        "max_tokens": 4000,
                        "system": system_prompt,
                        "messages": messages,
                        "tools": [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in ORCHESTRATOR_TOOLS],
                    },
                )

                if resp.status_code != 200:
                    yield TextDelta(text=f"Error: API returned {resp.status_code}")
                    break

                data = resp.json()
                choice = data["choices"][0]
                message = choice["message"]

        except Exception as e:
            yield TextDelta(text=f"Error: {str(e)[:100]}")
            break

        # Stream text content
        if message.get("content"):
            yield TextDelta(text=message["content"])

        # Check for tool calls
        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            # No tool calls = final response
            break

        # Execute tool calls (parallel where possible)
        assistant_msg = {"role": "assistant", "content": message.get("content", ""), "tool_calls": tool_calls}
        messages.append(assistant_msg)

        tool_results = []
        tasks = []

        for tc in tool_calls:
            func = tc["function"]
            tool_name = func["name"]
            try:
                tool_input = json.loads(func["arguments"])
            except json.JSONDecodeError:
                tool_input = {}

            yield ToolCallStart(tool_name=tool_name, tool_input=tool_input, call_id=tc["id"])

            # Execute tool
            result = await _execute_tool(tool_name, tool_input, user_context)

            yield ToolCallResult(tool_name=tool_name, result=result[:200], call_id=tc["id"])

            # Check for special actions
            try:
                result_data = json.loads(result)
                if result_data.get("action") == "start_session":
                    yield SessionStart(
                        session_id=result_data["session_id"],
                        context=result_data["context"],
                    )
                elif result_data.get("action") == "respond":
                    # Inline response is the final output
                    pass
                elif result_data.get("saved"):
                    yield ArtifactCreated(
                        artifact_id=result_data.get("artifact_id", ""),
                        artifact_type=result_data.get("type", ""),
                        title=result_data.get("title", ""),
                        preview=result_data,
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
