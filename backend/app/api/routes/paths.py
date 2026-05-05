"""REST endpoints for learning paths."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.routes.auth import get_optional_user
from app.services.paths.path_service import (
    add_path_notes,
    add_pivot,
    apply_pivot,
    complete_path,
    create_path,
    delete_path,
    get_next_pending_node,
    get_path,
    get_paths_for_user,
    update_node_status,
    update_path,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/paths", tags=["paths"])


# ─── List & create ─────────────────────────────────────────────────

@router.get("")
async def list_paths(status: str | None = None, user: dict = Depends(get_optional_user)):
    """List all paths for the authenticated user."""
    docs = await get_paths_for_user(user["email"], status=status)
    return docs


@router.post("")
async def create(request: Request, user: dict = Depends(get_optional_user)):
    """Create a new path from wizard + planner output.

    Body: { title, description, wizard: {...}, nodes: [...] }
    """
    body = await request.json()
    title = body.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    doc = await create_path(
        user_email=user["email"],
        title=title,
        description=body.get("description", ""),
        wizard=body.get("wizard", {}),
        nodes=body.get("nodes", []),
    )
    return doc


# ─── Wizard questions (agent-generated) ───────────────────────────

@router.post("/wizard")
async def wizard_questions(request: Request, user: dict = Depends(get_optional_user)):
    """Generate dynamic wizard questions for a given intent.

    Body: { intent }
    Returns: { questions: [{ key, question, chips: [{ label, value }], freeText? }] }
    """
    body = await request.json()
    intent = body.get("intent", "").strip()
    if not intent:
        raise HTTPException(status_code=400, detail="intent is required")

    from app.services.paths.path_planner import generate_wizard_questions

    questions = await generate_wizard_questions(intent)
    return {"questions": questions}


# ─── Plan a new path (wizard → LLM → skeleton) ───────────────────

@router.post("/plan")
async def plan_path(request: Request, user: dict = Depends(get_optional_user)):
    """Run the path planner agent: wizard answers → node skeleton.

    Streams SSE events with progress updates, then the final path doc.
    Body: { intent, ...wizard_answers }
    """
    import asyncio
    import json as _json
    from fastapi.responses import StreamingResponse
    from app.services.paths.path_planner import plan_path as _plan

    body = await request.json()
    intent = body.get("intent", "").strip()
    if not intent:
        raise HTTPException(status_code=400, detail="intent is required")

    wizard_answers = {k: v for k, v in body.items() if k != "intent"}

    # Progress callback — called by the planner agent during tool use
    progress_events = asyncio.Queue()

    async def _on_progress(event_type: str, data: dict):
        await progress_events.put({"type": event_type, **data})

    async def _stream():
        # Start planning in background
        plan_task = asyncio.create_task(
            _plan(
                user_email=user["email"],
                intent=intent,
                wizard_answers=wizard_answers,
                on_progress=_on_progress,
            )
        )

        # Yield progress events as SSE while planning runs
        while not plan_task.done():
            try:
                event = await asyncio.wait_for(progress_events.get(), timeout=0.5)
                yield f"data: {_json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                pass

        # Drain remaining events
        while not progress_events.empty():
            event = await progress_events.get()
            yield f"data: {_json.dumps(event)}\n\n"

        # Get result or error
        try:
            doc = plan_task.result()
            yield f"data: {_json.dumps({'type': 'path_ready', 'path': doc})}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ─── Chat persistence ─────────────────────────────────────────────
# Note: The /refine endpoint auto-saves user + agent messages after each turn.
# This endpoint is for manual/bulk saves only (e.g. wizard onboarding messages).

@router.post("/{path_id}/chat")
async def save_chat(path_id: str, request: Request, user: dict = Depends(get_optional_user)):
    """Append chat messages to the path. Body: { messages: [{role, text}] }"""
    body = await request.json()
    msgs = body.get("messages", [])
    if msgs:
        from app.services.paths.path_service import append_chat
        await append_chat(path_id, msgs)
    return {"ok": True}


# ─── Single path ───────────────────────────────────────────────────

@router.get("/{path_id}")
async def get(path_id: str, user: dict = Depends(get_optional_user)):
    doc = await get_path(path_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Path not found")
    return doc


@router.patch("/{path_id}")
async def patch(path_id: str, request: Request, user: dict = Depends(get_optional_user)):
    """Partial update (title, description, status)."""
    body = await request.json()
    allowed = {"title", "description", "status"}
    update = {k: v for k, v in body.items() if k in allowed}
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    doc = await update_path(path_id, update)
    if not doc:
        raise HTTPException(status_code=404, detail="Path not found")
    return {"ok": True}


@router.delete("/{path_id}")
async def delete(path_id: str, user: dict = Depends(get_optional_user)):
    ok = await delete_path(path_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Path not found")
    return {"ok": True}


# ─── Node operations ──────────────────────────────────────────────

@router.get("/{path_id}/next")
async def next_node(path_id: str, user: dict = Depends(get_optional_user)):
    """Get the next pending node for this path."""
    node = await get_next_pending_node(path_id)
    if not node:
        return {"done": True, "node": None}
    return {"done": False, "node": node}


@router.post("/{path_id}/nodes/{node_id}/start")
async def start_node(path_id: str, node_id: str, request: Request, user: dict = Depends(get_optional_user)):
    """Mark a node as active and optionally link a session."""
    body = await request.json()
    session_id = body.get("sessionId")
    doc = await update_node_status(path_id, node_id, "active", session_id=session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Path or node not found")
    return {"ok": True}


@router.post("/{path_id}/nodes/{node_id}/complete")
async def complete_node(path_id: str, node_id: str, user: dict = Depends(get_optional_user)):
    """Mark a node as completed."""
    doc = await update_node_status(path_id, node_id, "completed")
    if not doc:
        raise HTTPException(status_code=404, detail="Path or node not found")
    return {"ok": True}


@router.patch("/{path_id}/nodes/{node_id}/note")
async def update_note(path_id: str, node_id: str, request: Request, user: dict = Depends(get_optional_user)):
    """Update a node's student calibration note.

    Body: { note: "I already know basic sorting, want practice on edge cases" }
    """
    body = await request.json()
    note = body.get("note", "")
    from app.services.paths.path_service import update_node_note
    doc = await update_node_note(path_id, node_id, note)
    if not doc:
        raise HTTPException(status_code=404, detail="Path or node not found")
    return {"ok": True}


@router.delete("/{path_id}/nodes/{node_id}")
async def delete_node(path_id: str, node_id: str, user: dict = Depends(get_optional_user)):
    """Remove a node from the path."""
    from app.services.paths.path_service import remove_node
    doc = await remove_node(path_id, node_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Path or node not found")
    return {"ok": True}


@router.post("/{path_id}/nodes/reorder")
async def reorder_nodes(path_id: str, request: Request, user: dict = Depends(get_optional_user)):
    """Reorder nodes. Body: { nodeIds: ["n1","n3","n2",...] }"""
    body = await request.json()
    node_ids = body.get("nodeIds", [])
    if not node_ids:
        raise HTTPException(status_code=400, detail="nodeIds required")
    from app.services.paths.path_service import reorder_nodes as _reorder
    doc = await _reorder(path_id, node_ids)
    if not doc:
        raise HTTPException(status_code=404, detail="Path not found")
    return {"ok": True}


@router.post("/{path_id}/nodes/add")
async def add_node(path_id: str, request: Request, user: dict = Depends(get_optional_user)):
    """Add a new node. Body: { afterNodeId?, title, type, targetMin, topics }"""
    body = await request.json()
    from app.services.paths.path_service import insert_node
    doc = await insert_node(path_id, body)
    if not doc:
        raise HTTPException(status_code=404, detail="Path not found")
    return {"ok": True, "path": doc}


@router.post("/{path_id}/nodes/{node_id}/skip")
async def skip_node(path_id: str, node_id: str, user: dict = Depends(get_optional_user)):
    """Skip a node (e.g., student already knows the topic)."""
    doc = await update_node_status(path_id, node_id, "skipped")
    if not doc:
        raise HTTPException(status_code=404, detail="Path or node not found")
    return {"ok": True}


# ─── Reflection & pivots ──────────────────────────────────────────

@router.post("/{path_id}/reflect")
async def reflect(path_id: str, request: Request, user: dict = Depends(get_optional_user)):
    """Run the reflection agent after a node completes.

    Body: { nodeId, sessionId }
    """
    body = await request.json()
    node_id = body.get("nodeId")
    session_id = body.get("sessionId")
    if not node_id or not session_id:
        raise HTTPException(status_code=400, detail="nodeId and sessionId required")

    from app.services.paths.reflection_agent import reflect_on_node

    result = await reflect_on_node(path_id, node_id, session_id)
    return result


@router.post("/{path_id}/refine")
async def refine(path_id: str, request: Request, user: dict = Depends(get_optional_user)):
    """Natural-language path refinement — streams SSE progress.

    Body: { message: "shorter please, drop stretch phase" }
    """
    import asyncio
    import json as _json
    from fastapi.responses import StreamingResponse
    from app.services.paths.path_planner import refine_path

    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    from app.services.paths.path_service import append_chat

    progress_events = asyncio.Queue()

    async def _on_progress(event_type: str, data: dict):
        await progress_events.put({"type": event_type, **data})

    async def _stream():
        refine_task = asyncio.create_task(
            refine_path(path_id, message, on_progress=_on_progress)
        )

        while not refine_task.done():
            try:
                event = await asyncio.wait_for(progress_events.get(), timeout=0.5)
                yield f"data: {_json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                pass

        while not progress_events.empty():
            event = await progress_events.get()
            yield f"data: {_json.dumps(event)}\n\n"

        try:
            result = refine_task.result()
            # Save BOTH user + agent messages AFTER refine completes (single write, no duplicates)
            agent_text = result.get("message", "") or result.get("reason", "") or result.get("_chat_response", "")
            msgs_to_save = [{"role": "user", "text": message}]
            if agent_text:
                msgs_to_save.append({"role": "agent", "text": agent_text})
            await append_chat(path_id, msgs_to_save)
            yield f"data: {_json.dumps({'type': 'refine_ready', 'result': result})}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.post("/{path_id}/pivots/{pivot_index}/apply")
async def apply_pivot_route(
    path_id: str, pivot_index: int, request: Request, user: dict = Depends(get_optional_user)
):
    """Apply a proposed pivot (accept the node changes)."""
    body = await request.json()
    new_nodes = body.get("nodes")
    if not new_nodes:
        raise HTTPException(status_code=400, detail="nodes list required")
    doc = await apply_pivot(path_id, new_nodes, pivot_index)
    if not doc:
        raise HTTPException(status_code=404, detail="Path not found")
    return {"ok": True}


# ─── Completion ────────────────────────────────────────────────────

@router.post("/{path_id}/complete")
async def complete(path_id: str, request: Request, user: dict = Depends(get_optional_user)):
    """Mark path as completed with retrospective.

    Body: { strengths: [...], gaps: [...], totalTimeMin, totalSessions }
    """
    body = await request.json()
    doc = await complete_path(path_id, body)
    if not doc:
        raise HTTPException(status_code=404, detail="Path not found")
    return {"ok": True}
