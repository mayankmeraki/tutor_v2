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
        "name": "spawn_agent",
        "description": (
            "Spawn a sub-agent to do focused work in the background. "
            "Give it a clear task and specific instructions. "
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
            },
            "required": ["task", "instructions"],
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
                        "Artifact content — structure depends on type. "
                        "Flashcards: {cards: [{front, back}]}. "
                        "Notes/summary/cheat_sheet: {markdown: '...'}. "
                        "Plan: {steps: [{title, description, duration}]}. "
                        "Practice problems: {problems: [{question, solution, difficulty}]}. "
                        "Or any custom structure that fits."
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
                "teaching_notes": {
                    "type": "string",
                    "description": "Notes for the Tutor about this student (weak areas, preferences, what to address)",
                },
            },
            "required": ["skill", "enriched_intent"],
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
        "name": "ask_permission",
        "description": (
            "Ask the student for permission before taking a significant action. "
            "Shows a yes/no card. Wait for their response before proceeding. "
            "Use before: starting sessions, creating large artifacts, navigating away."
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
                    "description": "Label for the 'yes' button. Example: 'Start session', 'Create flashcards'",
                },
                "deny_label": {
                    "type": "string",
                    "description": "Label for the 'no' button. Example: 'Not now', 'Skip'",
                },
                "action_data": {
                    "type": "object",
                    "description": "Data to pass back if the student approves. Used by the follow-up action.",
                },
            },
            "required": ["question", "action_label"],
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

async def _run_sub_agent(task: str, instructions: str) -> dict:
    """Run a sub-agent — a focused Haiku call with specific instructions."""
    import httpx
    from app.core.config import settings

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
                    "model": settings.MODEL_FAST,
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

    # Save to rendered directory
    rendered_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "rendered")
    os.makedirs(rendered_dir, exist_ok=True)
    filepath = os.path.join(rendered_dir, f"doc-{doc_id}.html")

    with open(filepath, "w") as f:
        f.write(html)

    # Store metadata in MongoDB
    try:
        from app.core.mongodb import get_mongo_db
        db = get_mongo_db()
        from datetime import datetime
        await db.documents.insert_one({
            "document_id": doc_id,
            "user_id": user_id,
            "title": title,
            "format": "html",
            "filepath": filepath,
            "created_at": datetime.utcnow(),
        })
    except Exception as e:
        log.warning("Failed to save document metadata: %s", e)

    return {
        "document_id": doc_id,
        "title": title,
        "format": "html",
        "download_url": f"/rendered/doc-{doc_id}.html",
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

    elif name == "search_materials":
        db = _get_db()
        query = input_data["query"]
        col_id = input_data.get("collection_id")
        filter_q = {"user_id": user_context.get("email", "")}
        if col_id:
            filter_q["collection_id"] = col_id
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
        context_parts = []
        if user_context.get("student_model"):
            context_parts.append(f"Student model: {json.dumps(user_context['student_model'])[:500]}")
        if user_context.get("session_history"):
            context_parts.append(f"Recent sessions: {json.dumps(user_context['session_history'])[:500]}")
        if user_context.get("collections"):
            context_parts.append(f"Collections: {json.dumps(user_context['collections'])[:300]}")
        return "\n".join(context_parts) if context_parts else "No student context available (new student)."

    elif name == "spawn_agent":
        result = await _run_sub_agent(input_data["task"], input_data["instructions"])
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
    user_message_parts = [user_input]
    if attachments:
        for att in attachments:
            user_message_parts.append(f"\n[Attached: {att.get('filename', 'file')} ({att.get('mime_type', '?')})]")

    messages = [{"role": "system", "content": system_prompt}]

    # Append conversation history (keep last 20 turns to avoid token overflow)
    if history:
        for h in history[-20:]:
            role = h.get("role", "user")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": h.get("content", "")})

    messages.append({"role": "user", "content": "\n".join(user_message_parts)})

    tools_spec = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in ORCHESTRATOR_TOOLS]

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

        # Execute tool calls
        assistant_msg = {"role": "assistant", "content": full_text or None, "tool_calls": tool_calls}
        messages.append(assistant_msg)

        tool_results = []

        for tc in tool_calls:
            func = tc["function"]
            tool_name = func["name"]
            try:
                tool_input = json.loads(func["arguments"])
            except json.JSONDecodeError:
                tool_input = {}

            yield ToolCallStart(tool_name=tool_name, tool_input=tool_input, call_id=tc["id"])

            result = await _execute_tool(tool_name, tool_input, user_context)

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
