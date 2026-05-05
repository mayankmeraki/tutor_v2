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

from app.core.config import settings
from app.core.llm import llm_call, LLMCallMetadata
from app.services.paths.path_service import (
    add_pivot,
    create_path,
    get_path,
)

log = logging.getLogger(__name__)


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
            "Emit the final learning path. Call this exactly once when you've "
            "finished designing the path. This is required — you MUST call this tool."
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


# UI tools — let the agent render rich UI in the wizard chat
UI_TOOLS = [
    {
        "name": "show_choices",
        "description": (
            "Show clickable choice buttons to the student. Use this instead of listing "
            "options in text. The student taps one and it becomes their reply."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Short question before the choices"},
                "choices": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Button text, under 25 chars"},
                            "value": {"type": "string", "description": "Value sent back when tapped"},
                        },
                        "required": ["label", "value"],
                    },
                    "description": "2-4 choices",
                },
            },
            "required": ["prompt", "choices"],
        },
    },
]

PLANNER_SYSTEM = """\
You design learning paths. You receive a student's intent and conversation context, \
then use web_search to ground the curriculum in real-world standards, and call \
emit_path to create the structured path.

A great path feels like a mentor designed a study plan for this specific person.

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
If the student's intent spans multiple courses (e.g., "teach me data science", \
"become an ML engineer"), you should:
1. **Detail the FIRST 2 phases fully** — granular sessions with subtopics.
2. **Outline remaining phases** — just 1-2 placeholder sessions per phase with the phase \
   title and a brief description. Use `type="learn"` and set `topics` to a high-level \
   list of what that phase will cover.
3. Add a note in placeholder session titles like "→ Deep Learning (details when you arrive)".
4. These placeholder phases will be expanded later with full context from completed sessions.

This way the student sees the full journey but only the immediate work is detailed. \
It avoids overwhelming them with 30+ sessions at once.

## Path design
- Skip what they know. Match their goal (job = drills, curiosity = theory, project = builds).
- Interleave: learn → learn → drill → learn → build. Never 4+ learns in a row.
- Milestone every 3-4 sessions. Builds produce something tangible.
- First session must hook — start with something exciting, not prerequisites.
- Quick: 8-12 sessions. Thorough: 14-20. Deep: 20-30.

## How to output the path
You have two options:
1. **emit_path tool** — use this for the full path at once (when you've planned everything).
2. **Inline tags** — stream nodes one by one using `<path-node>` tags in your text. \
   This lets the student see the path building in real time. Format:

```
<path-phase name="Foundations" />
<path-node title="Variables & Data Types" type="learn" targetMin="25" topics="variables, types, casting, strings, operators" />
<path-node title="Control Flow" type="learn" targetMin="30" topics="if/else, for loops, while, list comprehensions" />
<path-node title="Python Drills" type="drill" targetMin="20" topics="string ops, list problems, dict manipulation" milestone="true" />
<path-phase name="Core Skills" />
<path-node title="Functions & Modules" type="learn" targetMin="25" topics="def, args, kwargs, imports, packages" />
```

Use inline tags when building from scratch — the student sees cards appear one by one. \
Use emit_path when restructuring an existing path.

For placeholder/future phases, use:
```
<path-phase name="Deep Learning" planned="true" />
<path-node title="→ Neural networks, CNNs, training pipelines" type="learn" targetMin="0" topics="to be detailed when you arrive" placeholder="true" />
```
The `placeholder="true"` flag tells the UI to show these differently (greyed out, with a "Plan this phase" button).

Before emitting, tell the student briefly what you're building and why.\
"""

REFINE_SYSTEM = """\
You are the student's path advisor on a learning platform called Euler. You talk to them \
directly — you're helpful, sharp, and you don't waste their time.

## Your success criteria
A conversation with you should feel like talking to a smart friend who happens to know \
the subject well. You understand what they need quickly, you don't ask unnecessary questions, \
and when you make changes you just do it — you don't describe what you're about to do.

## How you work

**When the path is empty (planning phase):**
You're getting to know the student before building their path. They gave you initial \
calibration data. Your job: have a SHORT conversation (1-2 exchanges) to understand \
them better before building. ALWAYS ask at least one follow-up question on your first \
response — never jump straight to building. Good follow-ups: "What specific area within \
X interests you most?", "Any particular project or goal driving this?", "What tools or \
frameworks are you already using?"

After 1-2 exchanges (or if the student says "go"/"create"/"yes"/"ready"), call emit_path. \
Don't over-plan — 2 turns of conversation max, then build.

**When the path has sessions (editing phase):**
The student wants to modify their path. If their intent is clear ("drop the last phase", \
"add more practice") — use delete_node/add_node/modify_node tools immediately. Don't ask \
for confirmation. After changes, confirm in one short line.

**When the student asks a question:**
Answer it. Be helpful and concise. Don't turn every question into a path modification.

## What makes you good
- You sound like a person, not a bot. No bullet-point lists of options. No "Would you like me to...".
- You never reference internal IDs. You say "Session 4 (GPIO Drills)" not "n4".
- You match the student's energy. Short message → short reply.
- You use **bold** for key terms, bullet points for options, and keep paragraphs to 1-2 lines.
- Never write a wall of text. If you're asking a question, frame it as:
  **What's your goal?** (one line context)
  - Option A
  - Option B
  - Option C
- You use web_search to ground your decisions in real curricula, not guesswork.
- Only use byo_search if the student explicitly says they have uploaded materials. \
  Don't call it speculatively — most students don't have any.

## Tools & tags
- **emit_path**: Replace the entire path at once (major restructuring).
- **delete_node** / **add_node** / **modify_node**: Surgical edits to existing paths.
- **web_search**: Research curriculum structure, topic ordering, best practices.
- **byo_search**: Search the student's uploaded materials.
- **Inline `<path-node>` tags**: Stream nodes in your text for progressive rendering. \
  Use `<path-phase name="..." />` before each group, then `<path-node title="..." type="learn|drill|quiz|build" targetMin="25" topics="a, b, c" />` for each session. \
  Add `milestone="true"` for build/checkpoint nodes. The student sees each card appear as you write it.

## Guardrails
- Never modify completed sessions.
- Keep at least one build/milestone session in any path.
- Use "you/your" — you're talking to the student directly.\
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
) -> dict:
    """Run the planner agent loop until emit_path is called."""
    messages = messages_override if messages_override else [{"role": "user", "content": user_msg}]
    emitted = None

    async def _emit(event_type, **data):
        if on_progress:
            await on_progress(event_type, data)

    await _emit("status", message="Analyzing your learning goals...")

    for turn in range(max_turns):
        await _emit("status", message="Designing your path..." if turn > 0 else "Thinking...")

        all_tools = PLANNER_TOOLS + (extra_tools or [])

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
                        # Show tool usage in UI
                        _tool_msgs = {
                            "web_search": f"Searching: {block.input.get('query', '')[:50]}",
                            "byo_search": f"Checking your materials: {block.input.get('query', '')[:50]}",
                            "delete_node": f"Removing: {block.input.get('reason', block.input.get('nodeId', ''))}",
                            "add_node": f"Adding: {block.input.get('title', '')}",
                            "modify_node": f"Updating: {block.input.get('reason', block.input.get('nodeId', ''))}",
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

    result = await _run_planner_loop(
        system=REFINE_SYSTEM,
        user_msg=None,
        user_email=path.get("userId", ""),
        on_progress=on_progress,
        require_emit=False,
        extra_tools=REFINE_TOOLS if current_nodes else [],
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
