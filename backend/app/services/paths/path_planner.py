"""Path planner — tool-using LLM agent that generates learning path skeletons.

Uses Sonnet (MODEL_MID) in an agentic loop:
  1. Receives wizard answers (intent, background, goal, depth, prereqs)
  2. Can call tools: web_search (discover curriculum structure), byo_search
     (find student's existing materials to incorporate), search_images
  3. Produces a structured node skeleton matching the UI contract
  4. Content is NOT generated here — each node hydrates lazily at start time
"""

import json
import logging
import re

from app.core.config import settings
from app.core.llm import llm_call, LLMCallMetadata
from app.services.paths.path_service import (
    add_pivot,
    create_path,
    get_path,
)

log = logging.getLogger(__name__)

# Patterns that indicate the model THINKS it built a path (used for the
# "described in prose without emitting tags" retry. Matches things like
# "there's your path", "16 sessions", "your foundations phase", etc.
_BUILD_CLAIM_RE = re.compile(
    r"\b(here(?:'?s| is)|there(?:'?s| is)) (?:your |a |the )path\b"
    r"|\b\d+\s+session[s]?\b"
    r"|\bfoundations? (?:phase|first)\b"
    r"|\bbuilt (?:your |a |the )path\b"
    r"|\bbuilding it now\b",
    re.IGNORECASE,
)


# ── Tool definitions for the planner agent ──────────────────────────

PLANNER_TOOLS = [
    {
        "name": "web_search",
        "description": (
            "Search the web to discover curriculum structure, prerequisite chains, "
            "standard topic ordering, or recommended resources for a subject. "
            "Use this to ground the path in real-world curricula rather than guessing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query, e.g. 'embedded C curriculum roadmap topics'",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "byo_search",
        "description": (
            "Search the student's uploaded (BYO) materials to find content they "
            "already have. If a student says 'I have lecture notes on X', this will "
            "find relevant chunks. Use this to incorporate their materials into the path."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query across student's materials.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "emit_path",
        "description": (
            "Replace the entire path with a fresh skeleton. ONLY use this for full "
            "restructuring of an already-populated path (e.g. the student says "
            "'rebuild from scratch' or 'completely redo this'). NEVER use it to "
            "create a brand-new path — for that, stream <path-phase /> and "
            "<path-node /> tags inline in your reply text instead so cards render "
            "progressively on the client."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Path title, under 60 chars. Include the end goal. E.g. 'ESP32 firmware — from C to a Wi-Fi temp logger'",
                },
                "description": {
                    "type": "string",
                    "description": "1-2 sentence journey summary.",
                },
                "estimatedHours": {
                    "type": "number",
                    "description": "Total estimated hours for the entire path.",
                },
                "milestoneCount": {
                    "type": "integer",
                    "description": "Number of milestone/build nodes in the path.",
                },
                "nodes": {
                    "type": "array",
                    "description": "Ordered list of session nodes.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "What the student will learn/do. Under 50 chars.",
                            },
                            "type": {
                                "type": "string",
                                "enum": ["learn", "drill", "quiz", "build"],
                                "description": (
                                    "learn: Concept teaching (board + voice, BYO materials). "
                                    "drill: Practice problems (code editor, problem bank). "
                                    "quiz: Quick checkpoint (assessment, 10-15 min). "
                                    "build: Hands-on project milestone (editor + canvas, longer)."
                                ),
                            },
                            "targetMin": {
                                "type": "integer",
                                "description": "Estimated minutes (10-90).",
                            },
                            "milestone": {
                                "type": "boolean",
                                "description": "true for key checkpoints/builds (every 3-5 nodes).",
                            },
                            "subtitle": {
                                "type": "string",
                                "description": "Short subtitle/description for this node. E.g. 'pointers, types, comp' or 'bit-fields, masks, shifts'",
                            },
                            "phase": {
                                "type": "string",
                                "description": "Phase name this node belongs to. E.g. 'Foundations', 'Talk to Hardware', 'Build Your Project'. Group 2-4 nodes per phase.",
                            },
                            "topics": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "3-5 specific subtopics covered in this session. These are the concepts Euler will teach. E.g. ['mean & median', 'variance & std dev', 'normal distribution', 'histograms']",
                            },
                        },
                        "required": ["title", "type", "targetMin", "milestone", "topics", "phase"],
                    },
                },
            },
            "required": ["title", "description", "nodes", "estimatedHours", "milestoneCount"],
        },
    },
]

# Extra tools available during refine (direct node manipulation)
REFINE_TOOLS = [
    {
        "name": "delete_node",
        "description": "Remove a specific node from the path. Use when the student asks to drop/remove a topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nodeId": {"type": "string", "description": "The nodeId to remove (e.g. 'n3')"},
                "reason": {"type": "string", "description": "Brief reason shown to student"},
            },
            "required": ["nodeId", "reason"],
        },
    },
    {
        "name": "add_node",
        "description": "Add a new session node to the path. Use when the student asks for more content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "afterNodeId": {"type": "string", "description": "Insert after this nodeId. Empty string to append at end."},
                "title": {"type": "string", "description": "Session title"},
                "type": {"type": "string", "enum": ["learn", "drill", "quiz", "build"]},
                "targetMin": {"type": "integer", "description": "Estimated minutes"},
                "topics": {"type": "array", "items": {"type": "string"}},
                "subtitle": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["title", "type", "targetMin", "reason"],
        },
    },
    {
        "name": "modify_node",
        "description": "Modify an existing node (change title, type, time, or topics).",
        "input_schema": {
            "type": "object",
            "properties": {
                "nodeId": {"type": "string", "description": "The nodeId to modify"},
                "title": {"type": "string"},
                "type": {"type": "string", "enum": ["learn", "drill", "quiz", "build"]},
                "targetMin": {"type": "integer"},
                "topics": {"type": "array", "items": {"type": "string"}},
                "subtitle": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["nodeId", "reason"],
        },
    },
]


# ── Shared design rules — used by both PLANNER_SYSTEM (legacy /plan) and
#    REFINE_SYSTEM (wizard chat). Kept as a single string so they can never
#    drift apart and contradict each other.

_PATH_DESIGN_RULES = """\
## Hierarchy — think like a textbook
- **Phase** = a mini-course or module (e.g., "Python Foundations", "Statistics for ML"). \
  3-5 sessions per phase. Name phases after what the student will be able to DO after \
  completing them, not abstract category names.
- **Session** = a chapter-level topic (e.g., "Descriptive Statistics", "Control Flow"). \
  Each session is ONE focused teaching unit, 20-40 minutes.
- **Topics** (the `topics` array) = subtopics within the session. These are what Euler \
  actually teaches — the specific concepts. E.g., for a "Descriptive Statistics" session: \
  ["mean & median", "variance & std dev", "distributions", "histograms"]. \
  List 3-5 specific subtopics per session. This is what the student sees on the card.

## Granularity rules
- NEVER make a session that's a whole subject ("Math for Data Science" — too broad).
- Each session = ONE chapter of a textbook. The topics = sections within that chapter.
- Session times: learns 20-35m, drills 15-25m, quizzes 10-15m, builds 30-50m. Max 50m.

## Broad intents (multi-course scope)
If the student's intent spans multiple courses (e.g., "teach me data science"):
1. **Detail the FIRST 2 phases fully** — granular sessions with subtopics.
2. **Outline remaining phases** — 1-2 placeholder sessions per phase with the phase \
   title and a brief description (`placeholder="true"`).
3. The student sees the full journey but only the immediate work is detailed.

## Path design
- Skip what they know. Match their goal (job = drills, curiosity = theory, project = builds).
- Interleave: learn → learn → drill → learn → build. Never 4+ learns in a row.
- Milestone every 3-4 sessions. Builds produce something tangible.
- First session must hook — start with something exciting, not prerequisites.
- Quick: 8-12 sessions. Thorough: 14-20. Deep: 20-30.\
"""

# ── PLANNER_SYSTEM is used ONLY by the legacy /api/v1/paths/plan endpoint
#    (one-shot path generation, no chat). It REQUIRES emit_path because that
#    endpoint reads the structured nodes from the tool call. The wizard
#    chat does NOT use this prompt — it uses REFINE_SYSTEM below.

PLANNER_SYSTEM = """\
You design learning paths from a student's wizard answers. Use web_search ONCE to \
ground the curriculum in real curricula, then call emit_path with the full path.

A great path feels like a mentor designed a study plan for this specific person.

""" + _PATH_DESIGN_RULES + """

## How to output
You MUST call the `emit_path` tool with the structured path. This endpoint runs \
in one shot — there is no streaming chat — so inline `<path-phase>`/`<path-node>` \
tags will not be rendered. Build the entire path in one emit_path call.\
"""

REFINE_SYSTEM = """\
You are the student's path advisor on Euler. Building a path should feel \
COLLABORATIVE — you put a draft on the table fast, the student steers. They \
should always feel they're driving.

## Three modes — only one applies per turn

**Mode A: Path is empty AND student hasn't said "go" yet**
You have the wizard answers. Ask ONE sharp follow-up that helps you tailor the \
path. Examples: "What's the project or interview driving this?", "Any specific \
area within X (say deployment, or core theory) that matters most?", "Are you \
already using PyTorch / sklearn / nothing yet?". One question, no preamble. \
DO NOT build yet.

**Mode B: Path is empty AND student said "go" / "yes" / "build it" / similar**
Build the draft RIGHT NOW using inline `<path-phase>` and `<path-node>` tags. \
See "Build sequence" below. This is the ONLY time you build for an empty path.

**Mode C: Path already has sessions (editing)**
The student wants surgical changes. Use `delete_node` / `add_node` / `modify_node` \
tools — don't ask for confirmation. After the edit, confirm in one line and ask \
one specific follow-up.

## Build sequence (Mode B only)

Cards on the right panel come from `<path-node />` tags in your reply text. \
Anything else you write is chat. The UI parses tags out and renders one card \
per `<path-node />`. **No tags = no cards = student thinks Euler is broken.**

Required structure of your reply — ALL of this happens in ONE reply:

1. (Optional) ≤6-word acknowledgement on its own line. ("Building this now.") \
   You may also skip this and start with `<path-phase` directly.
2. IMMEDIATELY emit the first `<path-phase name="..." />`. No describing the \
   phase first.
3. Stream `<path-node />` tags inside that phase, one per line.
4. THEN emit the NEXT `<path-phase name="..." />` and ITS nodes. Continue \
   until ALL phases are emitted.
5. ONLY AFTER every phase + every node has been emitted, write the iteration \
   question (see below).

### Path size targets — no skimping
A draft path MUST contain:
- **At least 3 phases** (3-5 is normal for a balanced path).
- **At least 8 sessions total**, more for thorough/deep depth.
- At least one `type="build"` or milestone session toward the end.
- Quick depth: 8-12 sessions across 3 phases.
- Thorough depth: 14-20 sessions across 3-4 phases.
- Deep depth: 20-30 sessions across 4-5 phases.

### CRITICAL: do not stop after Phase 1
The single most common failure mode: emit Phase 1 with 1-2 sessions, then \
write "Want me to continue with the rest?" or jump to iteration questions. \
**This is broken UX.** The student sees one lonely card while you brag in \
chat about "5 phases, 18 hours". They cannot meaningfully refine a 1-phase \
stub. They CAN refine a complete 14-session draft.

Rules:
- If you mention a number of phases (e.g. "5 phases") in chat, you MUST \
  emit that many `<path-phase>` tags in the SAME reply.
- If you mention a total time (e.g. "~18h"), the sum of `targetMin` across \
  ALL emitted nodes must roughly match.
- "Continuing the build now…" or "Should I add Phase 2?" mid-reply = forbidden.
- Iteration questions ONLY come after the LAST `<path-node>`.

Example reply (note: full skeleton in one go):

```
Building this — let's iterate.
<path-phase name="Foundations" />
<path-node title="Python for ML: NumPy & Pandas" type="learn" targetMin="35" topics="arrays, dataframes, indexing, broadcasting" />
<path-node title="Math Essentials for ML" type="learn" targetMin="30" topics="vectors, derivatives, probability" />
<path-node title="Foundations Drills" type="drill" targetMin="20" topics="numpy ops, pandas filtering" milestone="true" />
<path-phase name="Core ML" />
<path-node title="Linear & Logistic Regression" type="learn" targetMin="35" topics="loss, gradient descent, classification" />
<path-node title="Trees, Random Forests, Boosting" type="learn" targetMin="40" topics="decision trees, ensembles, XGBoost" />
<path-node title="Eval, Cross-Validation, Metrics" type="learn" targetMin="30" topics="train/val/test, ROC, AUC, F1" />
<path-node title="Core ML Drills" type="drill" targetMin="25" topics="model selection, debugging, baseline" />
<path-phase name="Modern + Deep Learning" />
<path-node title="Neural Networks Foundations" type="learn" targetMin="35" topics="perceptron, backprop, layers" />
<path-node title="PyTorch / TensorFlow Basics" type="learn" targetMin="40" topics="tensors, autograd, training loops" />
<path-node title="Computer Vision or NLP Track" type="learn" targetMin="35" topics="CNN basics OR transformer basics" />
<path-phase name="Capstone" />
<path-node title="Build: End-to-End ML Project" type="build" targetMin="60" topics="data, train, evaluate, deploy" milestone="true" />
<path-node title="Interview Prep + ML Concepts Drill" type="drill" targetMin="30" topics="bias-variance, overfitting, leakage" />

**~7 hours across 4 phases.** Two directions to steer:
- **More practice early?** I can swap the Trees session for a drill block.
- **Deeper on DL?** I can split Phase 3 into CV + NLP separately (+3h).

What lands?
```

## Iteration question — REQUIRED after every build or edit

After tags / after a tool call, write a short refinement prompt with 2-3 \
SPECIFIC options based on what you just built. Reference real session titles \
or phase names so the student can say "yes do option B" easily.

Good iteration prompts:
- "**Want more practice?** I leaned theory-heavy in Phase 2. I can swap the \
  Trees session for a drill, or add a third phase of mixed practice."
- "**Too much / too little?** ~12 hours total. I can compress to 6h by \
  cutting Trees, or add Deep Learning at the end (+4h)."
- "**The Build session** — Kaggle-style competition, recommendation engine, \
  or a deployment exercise? I'll spec it accordingly."

Bad iteration prompts (NEVER do):
- "Let me know if you want any changes!" (passive)
- "Anything else?" (vague)
- "I hope this helps!" (closes the door)

""" + _PATH_DESIGN_RULES + """

## Voice rules
- Talk like a smart friend, not a bot. No "I'd be happy to" or "Would you \
  like me to".
- Use "you/your" — direct address.
- Match the student's energy. Short message → short reply.
- Never reference internal IDs. Say "Session 4 (Linear Regression)" not "n4".
- **Bold** key terms; keep paragraphs to 1-2 lines.

## Tool guide
- `<path-phase>` / `<path-node>` tags (inline in reply text) — the ONLY way \
  to build a new path. Required for Mode B.
- `delete_node` / `add_node` / `modify_node` — surgical edits in Mode C. \
  Use them immediately when intent is clear; never ask for confirmation.
- `emit_path` — full rebuild of an already-populated path only (Mode C with \
  major restructure). NEVER for empty paths in Mode B.
- `web_search` — call AT MOST once during a build to ground curriculum. \
  Don't re-call unless major pivot.
- `byo_search` — only if the student explicitly references their uploaded \
  materials. Otherwise it's wasted latency.

## Guardrails
- Never modify completed sessions.
- Keep at least one build/milestone session in any path.
- After ANY tag emission or tool call, end with ONE specific iteration question.\
"""


# ── Helpers ─────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def _resp_text(resp) -> str:
    """Extract concatenated text from an LLMResponse's content blocks."""
    parts = []
    for block in resp.content:
        if block.type == "text" and block.text:
            parts.append(block.text)
    return "".join(parts)


async def _execute_planner_tool(name: str, tool_input: dict, user_email: str, path_id: str = None) -> str:
    """Execute a tool call from the planner agent."""
    if name == "web_search":
        from app.tools.web_search import web_search
        return await web_search(tool_input.get("query", ""), limit=5)

    elif name == "byo_search":
        query = tool_input.get("query", "")
        if not query or not user_email:
            return "No BYO materials found."
        try:
            import sys, os
            _byo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
            if _byo_root not in sys.path:
                sys.path.insert(0, _byo_root)
            from byo.retrieval.service import search as byo_search_fn
            results = await byo_search_fn(
                user_id=user_email,
                query=query,
                scope="user_corpus",
                k=5,
            )
            if not results:
                return "No BYO materials found matching that query."
            lines = []
            for r in results:
                title = getattr(r, "title", "") or getattr(r, "resource_name", "") or "Untitled"
                snippet = (getattr(r, "content", "") or "")[:200]
                lines.append(f"- {title}: {snippet}")
            return f"Student's uploaded materials matching '{query}':\n" + "\n".join(lines)
        except Exception as e:
            log.debug("byo_search in planner failed: %s", e)
            return "BYO search unavailable."

    elif name == "emit_path":
        return "Path emitted."

    # ── Direct node manipulation tools (refine mode) ──
    elif name == "delete_node" and path_id:
        node_id = tool_input.get("nodeId", "")
        from app.services.paths.path_service import remove_node
        doc = await remove_node(path_id, node_id)
        if doc:
            return f"Removed node {node_id}. Path now has {len(doc.get('nodes', []))} nodes."
        return f"Node {node_id} not found."

    elif name == "add_node" and path_id:
        from app.services.paths.path_service import insert_node
        doc = await insert_node(path_id, tool_input)
        if doc:
            return f"Added '{tool_input.get('title', '?')}'. Path now has {len(doc.get('nodes', []))} nodes."
        return "Failed to add node."

    elif name == "modify_node" and path_id:
        node_id = tool_input.get("nodeId", "")
        update_fields = {}
        for k in ("title", "type", "targetMin", "topics", "subtitle"):
            if k in tool_input:
                update_fields[f"nodes.$[elem].{k}"] = tool_input[k]
        if update_fields:
            from app.services.paths.path_service import _paths
            await _paths().update_one(
                {"pathId": path_id},
                {"$set": update_fields},
                array_filters=[{"elem.nodeId": node_id}],
            )
            return f"Modified node {node_id}."
        return "Nothing to modify."

    return f"Unknown tool: {name}"


async def _user_has_byo_collections(user_email: str) -> bool:
    """Cheap check: does the user have any BYO collections at all?

    Used to decide whether to expose ``byo_search`` to the planner. Without
    this, the model often calls ``byo_search`` speculatively even when the
    user has uploaded nothing — wasting an LLM round-trip and 5+ seconds.
    """
    if not user_email:
        return False
    try:
        from app.core.mongodb import get_mongo_db
        db = get_mongo_db()
        # find_one is faster than count_documents and good enough for a boolean.
        doc = await db.collections.find_one({"user_id": user_email}, {"_id": 1})
        return doc is not None
    except Exception as e:
        log.debug("BYO collection check failed (assuming none): %s", e)
        return False


async def _run_planner_loop(
    system: str,
    user_msg: str,
    user_email: str,
    max_turns: int = 6,
    on_progress=None,
    require_emit: bool = True,
    extra_tools: list | None = None,
    path_id: str | None = None,
    messages_override: list | None = None,
    tags_only: bool = False,
) -> dict:
    """Run the planner agent loop until emit_path is called.

    Args:
        tags_only: If True, removes `emit_path` from the available tools.
            Used by the wizard chat (Mode B) where the only way to build a
            new path is by streaming inline `<path-phase>` and `<path-node>`
            tags. Without this filter the model often defaults to
            emit_path which produces a long silent gap on the client and
            contradicts the system prompt.
    """
    messages = messages_override if messages_override else [{"role": "user", "content": user_msg}]
    emitted = None

    async def _emit(event_type, **data):
        if on_progress:
            await on_progress(event_type, data)

    await _emit("status", message="Analyzing your learning goals...")

    # Filter out byo_search if the user has no BYO collections — otherwise
    # the model wastes a turn calling it speculatively.
    has_byo = await _user_has_byo_collections(user_email)
    base_tools = list(PLANNER_TOOLS)
    if not has_byo:
        base_tools = [t for t in base_tools if t["name"] != "byo_search"]
    if tags_only:
        # Force the agent to use inline <path-phase>/<path-node> tags by
        # removing emit_path entirely. require_emit must also be False so
        # the loop doesn't try to coerce a tool call that doesn't exist.
        base_tools = [t for t in base_tools if t["name"] != "emit_path"]

    for turn in range(max_turns):
        await _emit("status", message="Designing your path..." if turn > 0 else "Thinking...")

        all_tools = base_tools + (extra_tools or [])

        # Use streaming when on_progress is set (for real-time text display)
        if on_progress:
            from app.core.llm import llm_stream
            resp = None
            async with await llm_stream(
                model=settings.MODEL_MID,
                system=system,
                messages=messages,
                max_tokens=8192,
                tools=all_tools,
                metadata=LLMCallMetadata(caller="path_planner"),
            ) as stream:
                async for delta in stream.text_stream:
                    if delta:
                        await _emit("agent_text", text=delta)
                resp = await stream.get_final_message()
        else:
            resp = await llm_call(
                model=settings.MODEL_MID,
                system=system,
                messages=messages,
                max_tokens=8192,
                tools=all_tools,
                metadata=LLMCallMetadata(caller="path_planner"),
            )

        # Check for tool use
        if resp.stop_reason == "tool_use":
            assistant_content = []
            tool_results = []

            for block in resp.content:
                if block.type == "text" and block.text:
                    assistant_content.append({"type": "text", "text": block.text})
                    # Only emit if not already streamed above
                    if not on_progress:
                        await _emit("agent_text", text=block.text)
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

                    if block.name == "emit_path":
                        emitted = block.input
                        node_count = len(block.input.get("nodes", []))
                        title = block.input.get("title", "")
                        await _emit("tool_call", tool="emit_path",
                                    message=f"Building path: {title} ({node_count} sessions)")

                        # Save nodes to DB IMMEDIATELY so frontend can render
                        if path_id and emitted.get("nodes"):
                            _nodes = emitted["nodes"]
                            for i, _n in enumerate(_nodes):
                                _n.setdefault("nodeId", f"n{i+1}")
                                _n["order"] = i + 1
                                _n.setdefault("status", "pending")
                                _n.setdefault("sessionId", None)
                                _n.setdefault("milestone", False)
                                _n.setdefault("topics", [])
                            from app.services.paths.path_service import update_path as _up
                            await _up(path_id, {
                                "nodes": _nodes,
                                "title": emitted.get("title", ""),
                                "description": emitted.get("description", ""),
                                "status": "active",
                            })
                            await _emit("artifact_update", pathId=path_id)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "Path emitted successfully.",
                        })
                    else:
                        # Show tool usage in UI. For node-manipulation tools we
                        # try to surface the actual session title (looked up
                        # from the live path) instead of a generic "reason"
                        # field — otherwise the agent emits 3 identical
                        # "Removing: phase 5" cards when it deletes 3 nodes,
                        # which feels broken.
                        _node_title = ""
                        if block.name in ("delete_node", "modify_node") and path_id:
                            try:
                                from app.services.paths.path_service import get_path
                                _live = await get_path(path_id)
                                _nid = block.input.get("nodeId", "")
                                for _n in (_live or {}).get("nodes", []):
                                    if _n.get("nodeId") == _nid:
                                        _node_title = _n.get("title", "")[:60]
                                        break
                            except Exception:
                                _node_title = ""

                        _delete_label = (
                            f"Removing: {_node_title}" if _node_title
                            else f"Removing: {block.input.get('reason', block.input.get('nodeId', ''))}"
                        )
                        _modify_label = (
                            f"Updating: {_node_title}" if _node_title
                            else f"Updating: {block.input.get('reason', block.input.get('nodeId', ''))}"
                        )
                        _tool_msgs = {
                            "web_search": f"Searching: {block.input.get('query', '')[:50]}",
                            "byo_search": f"Checking your materials: {block.input.get('query', '')[:50]}",
                            "delete_node": _delete_label,
                            "add_node": f"Adding: {block.input.get('title', '')}",
                            "modify_node": _modify_label,
                        }
                        await _emit("tool_call", tool=block.name,
                                    message=_tool_msgs.get(block.name, f"Using {block.name}..."),
                                    query=block.input.get("query", ""))

                        result = await _execute_planner_tool(block.name, block.input, user_email, path_id=path_id)

                        await _emit("tool_result", tool=block.name,
                                    message=f"Found results" if "found" not in str(result).lower()[:50] else "")

                        # If a node manipulation tool was used, signal artifact refresh
                        if block.name in ("delete_node", "add_node", "modify_node"):
                            await _emit("artifact_update", pathId=path_id)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

            if emitted:
                return emitted

        elif resp.stop_reason == "end_turn":
            raw_text = _resp_text(resp) or ""
            # If NOT streaming mode, emit the full text at once
            if raw_text and not on_progress:
                await _emit("agent_text", text=raw_text)

            text = _strip_fences(raw_text)
            if text:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass

            # Hallucination recovery: agent claimed to build a path in prose but
            # never emitted a single <path-node> tag. The client has nothing to
            # render. Retry once with a forcing prompt before giving up. We
            # detect this by a "build claim" pattern in the text + zero tags.
            tag_count = raw_text.count("<path-node")
            phase_count = raw_text.count("<path-phase")
            looks_like_build_claim = bool(_BUILD_CLAIM_RE.search(raw_text))
            if (
                not require_emit
                and tag_count == 0
                and looks_like_build_claim
                and turn < max_turns - 1
            ):
                log.info("Planner agent described path in prose without tags — forcing retry")
                messages.append({"role": "assistant", "content": raw_text})
                messages.append({
                    "role": "user",
                    "content": (
                        "Your previous reply described the path in prose but didn't "
                        "emit any <path-node> tags, so the UI has nothing to render. "
                        "Re-do that reply now: emit the literal `<path-phase name=\"...\" />` "
                        "and `<path-node title=\"...\" type=\"...\" targetMin=\"...\" "
                        "topics=\"...\" />` tags — one tag per session. No prose "
                        "describing the path. Tags only."
                    ),
                })
                # Tell the client to discard the failed prose from the chat
                # bubble — otherwise the user sees "There's your path — N
                # sessions" leftover in chat alongside the actual cards.
                await _emit("stream_reset", reason="retry_after_no_tags")
                await _emit("status", message="Building cards now…")
                continue

            # Skimpy build recovery: tags_only mode is on, the agent emitted
            # SOME tags but far fewer than a real path needs (e.g. 1 phase /
            # 1 session, then jumped straight to "here's your path, want to
            # adjust X?"). The client UI shows a single lonely card while
            # the chat brags about "5 phases, 18h". Continue building.
            #
            # Note: we do NOT stream_reset here. The 1-2 tags already
            # rendered on the client are valid; we just want to append more.
            if (
                not require_emit
                and tags_only
                and turn < max_turns - 1
                and (tag_count < 6 or phase_count < 2)
                and tag_count > 0
            ):
                log.info(
                    "Planner agent emitted skimpy path (%d nodes, %d phases) — forcing continuation",
                    tag_count, phase_count,
                )
                messages.append({"role": "assistant", "content": raw_text})
                missing = []
                if phase_count < 2:
                    missing.append(f"at least 2 phases (you only emitted {phase_count})")
                if tag_count < 6:
                    missing.append(f"at least 6 sessions (you only emitted {tag_count})")
                missing_str = " and ".join(missing)
                messages.append({
                    "role": "user",
                    "content": (
                        f"You stopped early. A real path needs {missing_str}. "
                        "Continue the build NOW: emit additional `<path-phase />` and "
                        "`<path-node />` tags directly — keep the same momentum, "
                        "don't repeat what you already emitted. Cover the rest of the "
                        "topic so the path actually delivers on what you promised. "
                        "After the path is fully built (all phases + sessions), THEN "
                        "ask one specific iteration question. Tags first, prose after."
                    ),
                })
                await _emit("status", message="Building more sessions…")
                continue

            # If emit_path is not required, return the text as a chat response
            if not require_emit:
                return {"_chat_response": raw_text}

            messages.append({"role": "assistant", "content": _resp_text(resp) or ""})
            messages.append({
                "role": "user",
                "content": "You must call the emit_path tool with the final path. Please do so now.",
            })
        else:
            break

    if not require_emit:
        return {"_chat_response": "I can help you refine the path. What would you like to change?"}
    raise ValueError(f"Path planner did not emit a path after {max_turns} turns")


# ── Wizard question generator ───────────────────────────────────────

WIZARD_SYSTEM = """\
Generate 3 quick-tap questions to calibrate a learning path. The questions are \
specific to the topic — not generic survey questions.

What the path planner needs: (1) what to skip (prior knowledge), (2) what to emphasize \
(their goal), (3) how much to cover (time investment).

Output a JSON array. Each item: {"key": "string", "question": "string", "chips": [{"label": "string", "value": "string"}]}

3 questions. 3-4 chips each. Labels under 18 chars. Chips should sound human \
("Never touched it", "Know the basics") not robotic ("beginner", "intermediate"). \
Third question's chips must include values "quick", "thorough", or "deep". \
Questions must be specific to the topic — for ML ask about Python/math, \
for embedded ask about C/hardware, for interviews ask about experience level.

JSON array only, no markdown.\
"""


async def generate_wizard_questions(intent: str) -> list[dict]:
    """Generate dynamic wizard questions tailored to the student's intent."""
    resp = await llm_call(
        model=settings.MODEL_FAST,
        system=WIZARD_SYSTEM,
        messages=[{"role": "user", "content": f"Student intent: {intent}"}],
        max_tokens=1500,
        metadata=LLMCallMetadata(caller="path_wizard"),
    )

    text = _strip_fences(_resp_text(resp) or "")
    try:
        questions = json.loads(text)
        if isinstance(questions, list) and questions:
            log.info("Wizard generated %d questions for '%s'", len(questions), intent[:40])
            return questions
    except json.JSONDecodeError:
        log.warning("Wizard returned invalid JSON: %s", text[:200])

    # Fallback — minimal questions
    return [
        {
            "key": "background",
            "question": "Where are you starting?",
            "chips": [
                {"label": "Total beginner", "value": "beginner"},
                {"label": "Some basics", "value": "some_basics"},
                {"label": "Intermediate", "value": "intermediate"},
                {"label": "Advanced", "value": "advanced"},
            ],
        },
        {
            "key": "goal",
            "question": "What's your goal?",
            "chips": [
                {"label": "Job prep", "value": "job_prep"},
                {"label": "Project", "value": "project"},
                {"label": "Course work", "value": "coursework"},
                {"label": "Curiosity", "value": "curiosity"},
            ],
        },
        {
            "key": "depth",
            "question": "How deep do you want to go?",
            "chips": [
                {"label": "Quick overview · ~4h", "value": "quick"},
                {"label": "Solid understanding · ~8h", "value": "thorough"},
                {"label": "Deep mastery · ~12h", "value": "deep"},
            ],
        },
    ]


# ── Public API ──────────────────────────────────────────────────────

async def plan_path(
    user_email: str,
    intent: str,
    wizard_answers: dict | None = None,
    on_progress=None,
    # Legacy params — still supported
    background: str = "",
    goal: str = "",
    depth: str = "thorough",
    prereqs: list[str] | None = None,
) -> dict:
    """Generate a learning path skeleton from wizard inputs."""

    # Build user message from wizard answers (agent-generated keys)
    if wizard_answers:
        answers_text = "\n".join(f"{k}: {v}" for k, v in wizard_answers.items() if v)
        user_msg = f"Student intent: {intent}\n\nWizard answers:\n{answers_text}"
    else:
        user_msg = (
            f"Student intent: {intent}\n"
            f"Background: {background or 'not specified'}\n"
            f"Goal: {goal or 'learn the topic well'}\n"
            f"Depth: {depth}\n"
            f"Known prereqs: {', '.join(prereqs) if prereqs else 'none specified'}"
        )

    result = await _run_planner_loop(
        system=PLANNER_SYSTEM,
        user_msg=user_msg,
        user_email=user_email,
        on_progress=on_progress,
    )

    title = result.get("title", intent[:60])
    description = result.get("description", "")
    nodes = result.get("nodes", [])

    if not nodes:
        raise ValueError("Path planner returned empty node list")

    # Create and persist the path
    doc = await create_path(
        user_email=user_email,
        title=title,
        description=description,
        wizard={
            "intent": intent,
            **(wizard_answers or {
                "background": background,
                "goal": goal,
                "depth": depth,
                "prereqs": prereqs or [],
            }),
        },
        nodes=nodes,
    )

    # Attach planner metadata for frontend
    doc["estimatedHours"] = result.get("estimatedHours", 0)
    doc["milestoneCount"] = result.get("milestoneCount", 0)

    log.info(
        "Path planned: %s — %d nodes, ~%.1fh total",
        title, len(nodes),
        result.get("estimatedHours", sum(n.get("targetMin", 30) for n in nodes) / 60),
    )
    return doc


async def refine_path(path_id: str, user_message: str, on_progress=None) -> dict:
    """Refine or discuss a path based on a natural-language user message.

    Returns either:
      - {"type": "chat", "message": "..."} for conversational responses
      - {"type": "changes", "reason": ..., "diff": ..., "proposedNodes": ..., ...} for structural changes
    """
    path = await get_path(path_id)
    if not path:
        raise ValueError(f"Path {path_id} not found")

    # Format current path state
    nodes_lines = []
    for n in path.get("nodes", []):
        status_mark = {"completed": "DONE", "skipped": "SKIPPED", "active": "IN PROGRESS"}.get(n["status"], "pending")
        nodes_lines.append(
            f"  [{status_mark}] Session {n.get('order', '?')} (id={n['nodeId']}): {n['title']} · {n['type']} · {n['targetMin']}m"
            + (" · MILESTONE" if n.get("milestone") else "")
        )

    notes_lines = []
    for note in path.get("pathNotes", [])[-10:]:
        notes_lines.append(f"  [{note['kind']}] {note.get('concept', '')}: {note.get('detail', '')}")

    # Build system context (path state — injected as first message)
    system_context = (
        f"Path: {path['title']}\n"
        f"Description: {path['description']}\n"
        f"Nodes ({len(path['nodes'])} total):\n" + "\n".join(nodes_lines) + "\n"
    )
    if notes_lines:
        system_context += "\nReflection notes:\n" + "\n".join(notes_lines) + "\n"

    # Build conversation messages from chat history
    chat_history = path.get("chatHistory", [])
    messages_for_llm = [{"role": "user", "content": f"[PATH CONTEXT — not a student message]\n{system_context}"}]
    messages_for_llm.append({"role": "assistant", "content": "Got it. I have the full path context. How can I help?"})

    # Replay prior conversation turns (ensure proper role alternation)
    for msg in chat_history[-20:]:
        role = "user" if msg.get("role") == "user" else "assistant"
        text = msg.get("text", "")
        if not text:
            continue
        # Ensure alternation — merge consecutive same-role messages
        if messages_for_llm and messages_for_llm[-1]["role"] == role:
            messages_for_llm[-1]["content"] += "\n" + text
        else:
            messages_for_llm.append({"role": role, "content": text})

    # Add the current message (ensure it's a user turn)
    if messages_for_llm and messages_for_llm[-1]["role"] == "user":
        messages_for_llm[-1]["content"] += "\n" + user_message
    else:
        messages_for_llm.append({"role": "user", "content": user_message})

    current_nodes = path.get("nodes", [])
    is_new_path = not current_nodes

    result = await _run_planner_loop(
        system=REFINE_SYSTEM,
        user_msg=None,
        user_email=path.get("userId", ""),
        on_progress=on_progress,
        require_emit=False,
        # When the path is empty, ONLY surgical-edit tools make no sense
        # and emit_path is forbidden by REFINE_SYSTEM. Pass an empty extras
        # list and tags_only=True so the model is forced down the streaming
        # tag path. When the path has sessions, surface delete/add/modify
        # for surgical edits.
        extra_tools=[] if is_new_path else REFINE_TOOLS,
        tags_only=is_new_path,
        path_id=path_id,
        messages_override=messages_for_llm,
    )

    # Check if agent just responded conversationally (no path changes)
    if "_chat_response" in result:
        return {"type": "chat", "message": result["_chat_response"]}

    # If result has nodes, it's a structural change
    proposed_nodes = result.get("nodes", [])
    if not proposed_nodes:
        # Agent used emit_path but with empty nodes — treat as chat
        return {"type": "chat", "message": result.get("description", result.get("title", "No changes needed."))}

    current_nodes = path.get("nodes", [])
    diff = result.get("diff", _compute_diff(current_nodes, proposed_nodes))

    # If path is empty (planning phase) — apply nodes directly, don't create a proposal
    if not current_nodes:
        # Assign IDs and save directly
        for i, node in enumerate(proposed_nodes):
            node.setdefault("nodeId", f"n{i+1}")
            node["order"] = i + 1
            node.setdefault("status", "pending")
            node.setdefault("sessionId", None)
            node.setdefault("milestone", False)
            node.setdefault("topics", [])
        await update_path(path_id, {
            "nodes": proposed_nodes,
            "title": result.get("title", path.get("title", "")),
            "description": result.get("description", path.get("description", "")),
            "status": "active",
        })
        total_min = sum(n.get("targetMin", 30) for n in proposed_nodes)
        return {
            "type": "created",
            "reason": result.get("reason", ""),
            "nodeCount": len(proposed_nodes),
            "estimatedHours": round(total_min / 60, 1),
        }

    # Existing path — save as pivot proposal
    pivot = {
        "triggeredBy": "user",
        "nodeId": None,
        "reason": result.get("reason", user_message),
        "diff": diff,
        "proposedNodes": proposed_nodes,
    }
    await add_pivot(path_id, pivot)

    updated = await get_path(path_id)
    pivot_index = len(updated.get("pivots", [])) - 1

    total_min = sum(n.get("targetMin", 30) for n in proposed_nodes)
    return {
        "type": "changes",
        "reason": result.get("reason", ""),
        "diff": diff,
        "proposedNodes": proposed_nodes,
        "pivotIndex": pivot_index,
        "currentNodes": current_nodes,
        "estimatedHours": round(total_min / 60, 1),
        "nodeCount": len(proposed_nodes),
    }


def _compute_diff(old_nodes: list[dict], new_nodes: list[dict]) -> dict:
    """Compute a simple diff between old and new node lists."""
    old_titles = {n.get("nodeId", ""): n.get("title", "") for n in old_nodes}
    new_titles = {n.get("nodeId", ""): n.get("title", "") for n in new_nodes}

    old_ids = set(old_titles.keys())
    new_ids = set(new_titles.keys())

    added = [new_titles[nid] for nid in (new_ids - old_ids) if nid]
    removed = [old_titles[nid] for nid in (old_ids - new_ids) if nid]
    modified = []
    for nid in old_ids & new_ids:
        if nid and old_titles[nid] != new_titles[nid]:
            modified.append(f"{old_titles[nid]} -> {new_titles[nid]}")

    return {"added": added, "removed": removed, "modified": modified}
