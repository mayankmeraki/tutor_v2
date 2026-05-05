"""Path context builder — loads path data and formats it for the tutor prompt.

Called at session start (or reconnect) when the session is linked to a path.
Produces a dict that gets JSON-serialized into context_data["pathContext"]
and injected into the tutor's dynamic prompt section.

Key design: the tutor needs to know:
  1. The full path plan (all nodes, their types, status)
  2. Which node the student is currently on
  3. ALL reflection notes from ANY prior session (not just sequential)
  4. The student's goal and background from the wizard
  5. What's upcoming so the tutor can foreshadow
  6. Whether the student jumped here out of order
"""

import logging

from app.services.paths.path_service import get_path

log = logging.getLogger(__name__)


async def build_path_context(path_id: str, node_id: str) -> dict | None:
    """Build path context for a session that's part of a learning path.

    Returns a dict ready to be serialized into context_data["pathContext"].
    Returns None if the path doesn't exist.
    """
    path = await get_path(path_id)
    if not path:
        return None

    nodes = path.get("nodes", [])
    current_node = None
    current_idx = -1
    for i, n in enumerate(nodes):
        if n.get("nodeId") == node_id:
            current_node = n
            current_idx = i
            break

    if not current_node:
        log.warning("Node %s not found in path %s", node_id, path_id)
        return None

    # ── Collect ALL notes from any node that has been touched ──
    # Not just sequential — student may jump around
    all_notes = path.get("pathNotes", [])

    # Separate into categories for the prompt
    strengths = [n for n in all_notes if n.get("kind") == "strength"]
    gaps = [n for n in all_notes if n.get("kind") == "gap"]
    handovers = [n for n in all_notes if n.get("kind") == "handover"]
    observations = [n for n in all_notes if n.get("kind") == "observation"]

    # ── Build the full node map (so tutor sees the big picture) ──
    node_map = []
    for n in nodes:
        node_map.append({
            "order": n.get("order", 0),
            "nodeId": n.get("nodeId", ""),
            "title": n.get("title", ""),
            "type": n.get("type", ""),
            "status": n.get("status", "pending"),
            "targetMin": n.get("targetMin", 30),
            "milestone": n.get("milestone", False),
            "topics": n.get("topics", []),
            "subtitle": n.get("subtitle", ""),
            "hasSession": bool(n.get("sessionId")),
            "studentNote": n.get("studentNote", ""),
        })

    # ── Upcoming nodes (after current) ──
    upcoming = []
    for n in nodes[current_idx + 1:current_idx + 4]:
        upcoming.append({
            "order": n.get("order", 0),
            "title": n.get("title", ""),
            "type": n.get("type", ""),
            "targetMin": n.get("targetMin", 30),
            "topics": n.get("topics", []),
        })

    # ── Detect if student jumped out of order ──
    # If there are pending nodes before this one, the student skipped ahead
    skipped_ahead = any(
        n.get("status") == "pending"
        for n in nodes[:current_idx]
    )

    # ── Completed nodes summary ──
    completed_nodes = [n for n in nodes if n.get("status") == "completed"]
    active_nodes = [n for n in nodes if n.get("status") == "active"]

    return {
        "pathId": path_id,
        "title": path.get("title", ""),
        "description": path.get("description", ""),
        "wizard": path.get("wizard", {}),
        "totalNodes": len(nodes),
        "completedCount": len(completed_nodes),
        "activeCount": len(active_nodes),
        "currentNode": {
            "nodeId": node_id,
            "title": current_node.get("title", ""),
            "type": current_node.get("type", "learn"),
            "order": current_node.get("order", 0),
            "targetMin": current_node.get("targetMin", 30),
            "milestone": current_node.get("milestone", False),
            "topics": current_node.get("topics", []),
            "subtitle": current_node.get("subtitle", ""),
            "studentNote": current_node.get("studentNote", ""),
        },
        "nodeMap": node_map,
        "skippedAhead": skipped_ahead,
        "priorNotes": {
            "strengths": strengths[-10:],   # Last 10 of each
            "gaps": gaps[-10:],
            "handovers": handovers[-5:],
            "observations": observations[-5:],
        },
        "upcomingNodes": upcoming,
        # Include pivot history so tutor knows what changed
        "recentPivots": [
            {"reason": p.get("reason", ""), "accepted": p.get("accepted", False)}
            for p in (path.get("pivots") or [])[-3:]
        ],
    }
