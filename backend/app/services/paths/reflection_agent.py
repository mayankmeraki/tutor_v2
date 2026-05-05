"""Reflection agent — runs after each path node completes.

Uses Haiku (MODEL_FAST) to analyze the session and produce:
  1. Structured concept notes (strengths / gaps / observations)
  2. Path pivot proposals (insert remediation, skip ahead, swap nodes)
  3. Concept mastery updates for the student model

This is the bridge between isolated sessions and the continuous path.
The output feeds into:
  - path.pathNotes[] — so future sessions know what happened
  - path.pivots[] — UI shows proposed changes, student confirms
  - student mastery — persistent across all paths
"""

import json
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.llm import llm_call, LLMCallMetadata
from app.services.paths.path_service import (
    add_path_notes,
    add_pivot,
    get_path,
    update_node_status,
)
from app.services.session.session_service import get_session

log = logging.getLogger(__name__)


REFLECTION_SYSTEM = """\
You are a learning reflection engine for Euler, an AI tutoring platform. \
A student just finished a session that is part of a structured learning path.

You will receive:
- The path context (title, nodes, prior notes)
- The session transcript and tutor notes from the just-completed node
- The node's target topic and type

Your job is to produce structured reflection output.

## VOICE — CRITICAL
Write EVERYTHING in second person, directly to the student: "you", "your", never \
"the student", "student has", "they". This text is shown directly to the learner.

## Output format (JSON)

{
  "sessionSummary": "1-2 sentence summary addressed to the student. E.g. 'You covered register access patterns and nailed the address arithmetic. The volatile keyword tripped you up twice.'",

  "concepts": [
    {
      "concept": "register access patterns",
      "kind": "strength",
      "confidence": 0.85,
      "evidence": "You connected address arithmetic to bit manipulation without any prompting",
      "tags": ["mmio", "registers", "bit-ops"]
    },
    {
      "concept": "volatile keyword",
      "kind": "gap",
      "confidence": 0.7,
      "evidence": "You re-asked twice and couldn't explain why compiler reordering matters",
      "tags": ["volatile", "c-keywords"]
    }
  ],

  "pivotProposal": null or {
    "reason": "Why the path should change — addressed to 'you'",
    "changes": [
      {"action": "insert_after", "afterNodeId": "n4", "node": {"title": "...", "type": "learn", "targetMin": 15, "topics": [...]}},
      {"action": "skip", "nodeId": "n6", "reason": "You already demonstrated this"},
      {"action": "modify", "nodeId": "n5", "field": "targetMin", "newValue": 60, "reason": "You need more time here"}
    ]
  },

  "teachingSignals": {
    "pacePreference": "normal" | "slow" | "fast",
    "respondsBestTo": "examples" | "theory" | "analogies" | "hands-on",
    "attentionSpanMin": 25,
    "noteForNextNode": "Start with a quick volatile recap before GPIO exercises"
  }
}

## Rules
1. Only flag concepts you have EVIDENCE for — don't guess mastery from topic coverage alone
2. Strengths need active demonstration (you explained, solved, connected ideas)
3. Gaps need repeated struggle or explicit confusion
4. Pivots should be conservative — only propose when there's clear signal
5. Teaching signals should capture what ACTUALLY worked, not what was planned
6. Keep concept names normalized — use the same term the field uses, not creative rephrasings
7. ALL text in sessionSummary, evidence, and reason fields MUST use "you/your" — NEVER "student/they"

Respond with ONLY the JSON object.\
"""


def _extract_session_context(session: dict) -> str:
    """Extract the relevant teaching signals from a session for reflection."""
    lines = []

    # Intent & topic
    intent = session.get("intent", {})
    if isinstance(intent, dict):
        lines.append(f"Intent: {intent.get('raw', 'unknown')}")
    elif isinstance(intent, str):
        lines.append(f"Intent: {intent}")

    # Headline
    headline = session.get("headline") or session.get("title")
    if headline:
        lines.append(f"Topic: {headline}")

    # Metrics
    metrics = session.get("metrics", {})
    if metrics:
        lines.append(f"Turns: {metrics.get('totalTurns', '?')}, Student responses: {metrics.get('studentResponses', '?')}")

    # Duration
    duration = session.get("durationSec")
    if duration:
        lines.append(f"Duration: {duration // 60}m {duration % 60}s")

    # Sections summary
    sections = session.get("sections", [])
    if sections:
        section_names = [s.get("title", "unnamed") for s in sections[:5]]
        lines.append(f"Sections covered: {', '.join(section_names)}")

    # Backend state signals
    bs = session.get("backendState", {}) or {}

    # Tutor notes (the gold — this is what the tutor observed)
    tutor_notes = bs.get("tutor_notes") or bs.get("notes") or ""
    if tutor_notes:
        lines.append(f"\n--- Tutor's internal notes ---\n{tutor_notes[:3000]}")

    # Last assessment summary
    assessment = bs.get("last_assessment_summary") or ""
    if assessment:
        lines.append(f"\n--- Assessment summary ---\n{assessment[:1500]}")

    # Last signals (pacing, engagement)
    signals = bs.get("last_signals") or ""
    if signals:
        lines.append(f"\n--- Teaching signals ---\n{signals[:1000]}")

    # Extract key transcript moments (first + last user messages, any confusion signals)
    transcript = session.get("transcript", [])
    if not transcript:
        transcript = bs.get("messages", [])

    if transcript:
        user_msgs = [m for m in transcript if m.get("role") == "user"]
        if user_msgs:
            first_msg = _get_text(user_msgs[0])
            lines.append(f"\nFirst student message: {first_msg[:300]}")
            if len(user_msgs) > 1:
                last_msg = _get_text(user_msgs[-1])
                lines.append(f"Last student message: {last_msg[:300]}")
            lines.append(f"Total student messages: {len(user_msgs)}")

    # DSA state (code, test results)
    dsa_state = bs.get("dsaState") or {}
    if dsa_state:
        if dsa_state.get("testResults"):
            lines.append(f"Code test results: {json.dumps(dsa_state['testResults'])[:500]}")
        if dsa_state.get("code"):
            lines.append(f"Final code ({len(dsa_state['code'])} chars)")

    return "\n".join(lines)


def _get_text(msg: dict) -> str:
    """Extract text from a message (handles string or content-blocks format)."""
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return str(content)


def _format_path_context(path: dict, current_node_id: str) -> str:
    """Format the path context for the reflection agent."""
    lines = [
        f"Path: {path['title']}",
        f"Description: {path['description']}",
        f"Wizard intent: {path.get('wizard', {}).get('intent', 'unknown')}",
        f"Student background: {path.get('wizard', {}).get('background', 'unknown')}",
        f"Goal: {path.get('wizard', {}).get('goal', 'unknown')}",
        "",
        "Node list:",
    ]
    for n in path.get("nodes", []):
        marker = ">>> JUST COMPLETED" if n["nodeId"] == current_node_id else n["status"]
        lines.append(f"  {n['nodeId']} · {n['title']} · {n['type']} · {n['targetMin']}m [{marker}]")

    # Prior notes
    prior_notes = path.get("pathNotes", [])
    if prior_notes:
        lines.append("\nPrior reflection notes:")
        for note in prior_notes[-15:]:
            lines.append(f"  [{note['kind']}] {note.get('concept', '')}: {note.get('detail', '')}")

    return "\n".join(lines)


async def reflect_on_node(path_id: str, node_id: str, session_id: str) -> dict:
    """Run post-session reflection for a completed path node.

    Returns the reflection result with concepts, pivot proposals, and teaching signals.
    """
    path = await get_path(path_id)
    if not path:
        raise ValueError(f"Path {path_id} not found")

    session = await get_session(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    # Do NOT auto-mark as completed — student decides when a node is done.
    # Just link the session to the node if not already linked.
    current_node_doc = None
    for n in path.get("nodes", []):
        if n.get("nodeId") == node_id:
            current_node_doc = n
            break
    if current_node_doc and not current_node_doc.get("sessionId"):
        await update_node_status(path_id, node_id, "active", session_id=session_id)

    # Build context for the reflection agent
    path_context = _format_path_context(path, node_id)
    session_context = _extract_session_context(session)

    # Find the current node info
    current_node = None
    for n in path.get("nodes", []):
        if n["nodeId"] == node_id:
            current_node = n
            break

    user_msg = (
        f"## Path context\n{path_context}\n\n"
        f"## Completed node\n"
        f"Node: {current_node['title'] if current_node else node_id}\n"
        f"Type: {current_node['type'] if current_node else 'unknown'}\n"
        f"Target: {current_node['targetMin'] if current_node else '?'}m\n\n"
        f"## Session data\n{session_context}"
    )

    resp = await llm_call(
        model=settings.MODEL_FAST,
        system=REFLECTION_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
        max_tokens=4096,
        metadata=LLMCallMetadata(caller="path_reflection"),
    )

    # Extract text from content blocks
    text = "".join(b.text for b in resp.content if b.type == "text" and b.text).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        log.error("Reflection agent returned invalid JSON: %s", text[:200])
        result = {
            "sessionSummary": "Reflection failed to parse",
            "concepts": [],
            "pivotProposal": None,
            "teachingSignals": {},
        }

    # ── Persist concepts as path notes ──
    concepts = result.get("concepts", [])
    if concepts:
        notes = []
        for c in concepts:
            notes.append({
                "nodeId": node_id,
                "kind": c.get("kind", "observation"),
                "concept": c.get("concept", ""),
                "detail": c.get("evidence", ""),
                "confidence": c.get("confidence", 0.5),
                "tags": c.get("tags", []),
            })
        await add_path_notes(path_id, notes)
        log.info(
            "Reflection: %d concepts (%d strengths, %d gaps) for %s/%s",
            len(concepts),
            sum(1 for c in concepts if c.get("kind") == "strength"),
            sum(1 for c in concepts if c.get("kind") == "gap"),
            path_id[:12], node_id,
        )

    # ── Handle pivot proposals ──
    pivot_proposal = result.get("pivotProposal")
    pivot_index = None
    if pivot_proposal:
        # Build the proposed node diff
        changes = pivot_proposal.get("changes", [])
        diff = {"added": [], "removed": [], "modified": []}
        proposed_nodes = list(path.get("nodes", []))  # Start from current

        for change in changes:
            action = change.get("action")
            if action == "insert_after":
                after_id = change.get("afterNodeId")
                new_node = change.get("node", {})
                new_node["nodeId"] = f"n_ins_{len(proposed_nodes)+1}"
                new_node["status"] = "pending"
                new_node["sessionId"] = None
                diff["added"].append(new_node.get("title", ""))
                # Insert after the specified node
                for i, n in enumerate(proposed_nodes):
                    if n["nodeId"] == after_id:
                        proposed_nodes.insert(i + 1, new_node)
                        break
            elif action == "skip":
                skip_id = change.get("nodeId")
                for n in proposed_nodes:
                    if n["nodeId"] == skip_id and n["status"] == "pending":
                        diff["removed"].append(n.get("title", ""))
                        n["status"] = "skipped"
            elif action == "modify":
                mod_id = change.get("nodeId")
                field = change.get("field")
                new_val = change.get("newValue")
                for n in proposed_nodes:
                    if n["nodeId"] == mod_id:
                        old_val = n.get(field)
                        n[field] = new_val
                        diff["modified"].append(f"{n.get('title', '')}: {field} {old_val} -> {new_val}")

        pivot = {
            "triggeredBy": "reflection",
            "nodeId": node_id,
            "reason": pivot_proposal.get("reason", ""),
            "diff": diff,
            "proposedNodes": proposed_nodes,
        }
        await add_pivot(path_id, pivot)
        updated = await get_path(path_id)
        pivot_index = len(updated.get("pivots", [])) - 1

        log.info("Reflection proposed pivot for %s: %s", path_id[:12], pivot_proposal.get("reason", "")[:100])

    # ── Persist teaching signals to path doc ──
    teaching_signals = result.get("teachingSignals", {})
    if teaching_signals:
        note_for_next = teaching_signals.get("noteForNextNode", "")
        if note_for_next:
            await add_path_notes(path_id, [{
                "nodeId": node_id,
                "kind": "handover",
                "concept": "next_node_instruction",
                "detail": note_for_next,
            }])

    # ── Build the response for the frontend ──
    # This is the UI contract for the reflection overlay (Stage 5 in mockup)
    strengths = [c for c in concepts if c.get("kind") == "strength"]
    gaps = [c for c in concepts if c.get("kind") == "gap"]

    return {
        "sessionSummary": result.get("sessionSummary", ""),
        "strengths": [
            {
                "title": s.get("concept", ""),
                "detail": s.get("evidence", ""),
                "tags": s.get("tags", []),
            }
            for s in strengths
        ],
        "gaps": [
            {
                "title": g.get("concept", ""),
                "detail": g.get("evidence", ""),
                "tags": g.get("tags", []),
            }
            for g in gaps
        ],
        "pivot": {
            "reason": pivot_proposal.get("reason", "") if pivot_proposal else None,
            "diff": diff if pivot_proposal else None,
            "pivotIndex": pivot_index,
        } if pivot_proposal else None,
        "teachingSignals": teaching_signals,
        "nodeId": node_id,
        "nodeDone": True,
    }
