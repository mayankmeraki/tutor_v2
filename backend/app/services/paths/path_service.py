"""Path service — CRUD + business logic for learning paths."""

import logging
import uuid
from datetime import datetime, timezone

from app.core.mongodb import get_tutor_db

log = logging.getLogger(__name__)


# ─── Collection accessor ───────────────────────────────────────────

def _paths():
    return get_tutor_db()["paths"]


async def ensure_path_indexes():
    coll = _paths()
    await coll.create_index("pathId", unique=True)
    await coll.create_index([("userId", 1), ("status", 1)])
    await coll.create_index([("userId", 1), ("createdAt", -1)])
    log.info("Path indexes ensured")


# ─── CRUD ──────────────────────────────────────────────────────────

async def create_path(
    user_email: str,
    title: str,
    description: str,
    wizard: dict,
    nodes: list[dict],
) -> dict:
    """Create a new path from wizard output + planner skeleton."""
    path_id = f"path_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    # Assign node IDs and defaults
    for i, node in enumerate(nodes):
        node.setdefault("nodeId", f"n{i+1}")
        node["order"] = i + 1
        node.setdefault("status", "pending")
        node.setdefault("sessionId", None)
        node.setdefault("milestone", False)
        node.setdefault("topics", [])

    doc = {
        "pathId": path_id,
        "userId": user_email,
        "title": title,
        "description": description,
        "status": "active",
        "createdAt": now,
        "completedAt": None,
        "wizard": wizard,
        "nodes": nodes,
        "pathNotes": [],
        "pivots": [],
        "chatHistory": [],
        "retrospective": None,
    }
    await _paths().insert_one(doc)
    doc.pop("_id", None)
    log.info("Path created: %s (%d nodes) for %s", path_id, len(nodes), user_email)
    return doc


async def get_path(path_id: str) -> dict | None:
    doc = await _paths().find_one({"pathId": path_id})
    if doc:
        doc.pop("_id", None)
    return doc


async def get_paths_for_user(user_email: str, status: str | None = None) -> list[dict]:
    """Get all paths for a user, optionally filtered by status."""
    query = {"userId": user_email}
    if status:
        query["status"] = status
    cursor = _paths().find(query).sort("createdAt", -1)
    docs = []
    async for doc in cursor:
        doc.pop("_id", None)
        docs.append(doc)
    return docs


async def update_path(path_id: str, update: dict) -> dict | None:
    result = await _paths().find_one_and_update(
        {"pathId": path_id},
        {"$set": update},
        return_document=True,
    )
    if result:
        result.pop("_id", None)
    return result


async def delete_path(path_id: str) -> bool:
    result = await _paths().delete_one({"pathId": path_id})
    return result.deleted_count > 0


# ─── Node operations ──────────────────────────────────────────────

async def update_node_status(
    path_id: str, node_id: str, status: str, session_id: str | None = None
) -> dict | None:
    """Update a single node's status (and optionally link a session)."""
    update_fields = {f"nodes.$[elem].status": status}
    if session_id:
        update_fields[f"nodes.$[elem].sessionId"] = session_id

    result = await _paths().find_one_and_update(
        {"pathId": path_id},
        {"$set": update_fields},
        array_filters=[{"elem.nodeId": node_id}],
        return_document=True,
    )
    if result:
        result.pop("_id", None)
    return result


async def update_node_note(path_id: str, node_id: str, note: str) -> dict | None:
    """Update a node's student calibration note (what they know, want to focus on)."""
    result = await _paths().find_one_and_update(
        {"pathId": path_id},
        {"$set": {"nodes.$[elem].studentNote": note}},
        array_filters=[{"elem.nodeId": node_id}],
        return_document=True,
    )
    if result:
        result.pop("_id", None)
    return result


async def remove_node(path_id: str, node_id: str) -> dict | None:
    """Remove a node from the path and re-number remaining nodes."""
    result = await _paths().find_one_and_update(
        {"pathId": path_id},
        {"$pull": {"nodes": {"nodeId": node_id}}},
        return_document=True,
    )
    if result:
        # Re-number orders
        nodes = result.get("nodes", [])
        for i, n in enumerate(nodes):
            n["order"] = i + 1
        await _paths().update_one(
            {"pathId": path_id},
            {"$set": {"nodes": nodes}},
        )
        result.pop("_id", None)
    return result


async def reorder_nodes(path_id: str, node_ids: list[str]) -> dict | None:
    """Reorder nodes according to the given nodeId list."""
    path = await get_path(path_id)
    if not path:
        return None
    node_map = {n["nodeId"]: n for n in path.get("nodes", [])}
    reordered = []
    for i, nid in enumerate(node_ids):
        if nid in node_map:
            node = node_map[nid]
            node["order"] = i + 1
            reordered.append(node)
    # Append any nodes not in the list (shouldn't happen, but safety)
    for n in path.get("nodes", []):
        if n["nodeId"] not in {r["nodeId"] for r in reordered}:
            n["order"] = len(reordered) + 1
            reordered.append(n)
    result = await _paths().find_one_and_update(
        {"pathId": path_id},
        {"$set": {"nodes": reordered}},
        return_document=True,
    )
    if result:
        result.pop("_id", None)
    return result


async def insert_node(path_id: str, node_data: dict) -> dict | None:
    """Insert a new node into the path."""
    path = await get_path(path_id)
    if not path:
        return None
    nodes = path.get("nodes", [])
    after_id = node_data.get("afterNodeId")

    new_node = {
        "nodeId": f"n_add_{uuid.uuid4().hex[:6]}",
        "title": node_data.get("title", "New session"),
        "type": node_data.get("type", "learn"),
        "targetMin": node_data.get("targetMin", 30),
        "milestone": node_data.get("milestone", False),
        "topics": node_data.get("topics", []),
        "subtitle": node_data.get("subtitle", ""),
        "phase": node_data.get("phase", ""),
        "status": "pending",
        "sessionId": None,
        "studentNote": "",
    }

    if after_id:
        for i, n in enumerate(nodes):
            if n["nodeId"] == after_id:
                nodes.insert(i + 1, new_node)
                break
        else:
            nodes.append(new_node)
    else:
        nodes.append(new_node)

    # Re-number
    for i, n in enumerate(nodes):
        n["order"] = i + 1

    result = await _paths().find_one_and_update(
        {"pathId": path_id},
        {"$set": {"nodes": nodes}},
        return_document=True,
    )
    if result:
        result.pop("_id", None)
    return result


async def append_chat(path_id: str, messages: list[dict]) -> None:
    """Append chat messages to the path's chatHistory. Max 100 messages kept."""
    await _paths().update_one(
        {"pathId": path_id},
        {
            "$push": {"chatHistory": {"$each": messages, "$slice": -100}},
        },
    )


async def get_next_pending_node(path_id: str) -> dict | None:
    """Return the first pending node in a path."""
    doc = await get_path(path_id)
    if not doc:
        return None
    for node in doc.get("nodes", []):
        if node.get("status") == "pending":
            return node
    return None


# ─── Path notes (reflection outputs) ──────────────────────────────

async def add_path_notes(path_id: str, notes: list[dict]) -> dict | None:
    """Append reflection notes to the path."""
    now = datetime.now(timezone.utc).isoformat()
    for note in notes:
        note.setdefault("createdAt", now)

    result = await _paths().find_one_and_update(
        {"pathId": path_id},
        {"$push": {"pathNotes": {"$each": notes}}},
        return_document=True,
    )
    if result:
        result.pop("_id", None)
    return result


async def add_pivot(path_id: str, pivot: dict) -> dict | None:
    """Record a proposed or applied pivot."""
    pivot.setdefault("createdAt", datetime.now(timezone.utc).isoformat())
    pivot.setdefault("accepted", False)

    result = await _paths().find_one_and_update(
        {"pathId": path_id},
        {"$push": {"pivots": pivot}},
        return_document=True,
    )
    if result:
        result.pop("_id", None)
    return result


async def apply_pivot(path_id: str, new_nodes: list[dict], pivot_index: int) -> dict | None:
    """Apply a pivot — replace downstream nodes and mark pivot as accepted."""
    # Assign IDs to new nodes
    for i, node in enumerate(new_nodes):
        node.setdefault("nodeId", f"n{i+1}")
        node["order"] = i + 1
        node.setdefault("status", "pending")
        node.setdefault("sessionId", None)
        node.setdefault("milestone", False)
        node.setdefault("topics", [])

    result = await _paths().find_one_and_update(
        {"pathId": path_id},
        {
            "$set": {
                "nodes": new_nodes,
                f"pivots.{pivot_index}.accepted": True,
            }
        },
        return_document=True,
    )
    if result:
        result.pop("_id", None)
    return result


async def complete_path(path_id: str, retrospective: dict) -> dict | None:
    """Mark a path as completed with a retrospective summary."""
    return await update_path(path_id, {
        "status": "completed",
        "completedAt": datetime.now(timezone.utc).isoformat(),
        "retrospective": retrospective,
    })
