"""Tutor tool schemas — search, content, BYO, board capture, etc."""

TUTOR_TOOLS = [
    {
        "name": "search_images",
        "description": (
            "Search Google Images for educational visuals. Returns image titles + URLs. "
            "Embed results on the board with: <teaching-image src=\"URL\" caption=\"title\" /> "
            "Use for diagrams, photos, experimental setups, or anything visual that helps explain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": 'Search query, e.g. "free body diagram", "double slit experiment"',
                },
                "limit": {
                    "type": "number",
                    "description": "Max results (1-5, default 3)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for supplementary information not available in course materials. "
            "Returns summaries and URLs from general web sources. "
            "Use when: you need a real-world example, current data, a diagram/image not in Wikimedia, "
            "a formula derivation, historical context, or any information beyond what the course provides. "
            "Prefer course materials first — use this to supplement, not replace."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": 'Search query — be specific. e.g. "photoelectric effect threshold frequency graph"',
                },
                "limit": {
                    "type": "number",
                    "description": "Max results (1-8, default 5)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_simulation_details",
        "description": (
            "Get full details for a specific simulation by ID, including ai_context, "
            "controls, guided exercises, and content URLs. Use when you want to guide "
            "the student through a specific simulation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "simulation_id": {
                    "type": "string",
                    "description": "The simulation ID from the Available Simulations context",
                },
            },
            "required": ["simulation_id"],
        },
    },
    {
        "name": "content_map",
        "description": (
            "Get the course/content structure overview — modules, lessons, sections, "
            "timestamps, and available resources. Call this ONCE at session start to "
            "understand what content is available. Do NOT call every turn — the structure "
            "doesn't change. Use the plan and current topic for navigation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_section_content",
        "description": (
            "Fetch detailed content for a specific course section — transcript segments, "
            "key points, formulas, and concepts covered. Use when you need the professor's "
            "actual words to ground your teaching. Don't call for every step — only when "
            "you need specific lecture content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lesson_id": {
                    "type": "number",
                    "description": "The lesson ID from the Course Map",
                },
                "section_index": {
                    "type": "number",
                    "description": "The section index within the lesson",
                },
            },
            "required": ["lesson_id", "section_index"],
        },
    },
    {
        "name": "content_read",
        "description": (
            "Get full teaching content for a ref — transcript, key points, formulas. "
            "Use when grounding your teaching in actual lecture content. "
            "Refs: lesson:ID:section:IDX for a specific section, lesson:ID for a lesson overview, "
            "sim:ID for simulation details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": 'Content ref, e.g. "lesson:3:section:2" or "lesson:5"',
                },
            },
            "required": ["ref"],
        },
    },
    {
        "name": "content_peek",
        "description": (
            "Quick look at a ref — title, concepts, key points (~100 tokens). "
            "Use for planning or finding the right section before reading full content. "
            "For lesson refs: returns section listing with refs. "
            "For section refs: returns compact teaching brief."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": 'Content ref, e.g. "lesson:3" or "lesson:3:section:2"',
                },
            },
            "required": ["ref"],
        },
    },
    {
        "name": "content_search",
        "description": (
            "Search across all course content for a topic or concept. "
            "Returns matching items with refs you can pass to content_read or content_peek. "
            "Use when the student asks about something not in the current plan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — concept name, topic, or question",
                },
                "limit": {
                    "type": "number",
                    "description": "Max results (default 5)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "byo_read",
        "description": (
            "Read content from the student's uploaded materials (BYO). "
            "Use when teaching from student's own PDFs, notes, or documents. "
            "Provide the collection_id (from session context) and optionally a chunk index or search query. "
            "Returns the actual text content from their uploaded material."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_id": {
                    "type": "string",
                    "description": "BYO collection ID (from session context or enriched_intent)",
                },
                "query": {
                    "type": "string",
                    "description": "Search within the collection — topic, question text, or keyword",
                },
                "chunk_index": {
                    "type": "number",
                    "description": "Specific chunk index to read (0-based). Use when you know the exact chunk.",
                },
            },
            "required": ["collection_id"],
        },
    },
    {
        "name": "byo_list",
        "description": (
            "List all chunks/sections in a BYO collection with their topics and labels. "
            "Use to understand what content is available in the student's uploaded material "
            "before deciding what to teach."
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
        "name": "byo_transcript_context",
        "description": (
            "Get the transcript around a specific timestamp in a BYO video. "
            "Use during video watch-along sessions to understand what the student just heard. "
            "Returns ~60s of transcript centered on the timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_id": {
                    "type": "string",
                    "description": "BYO resource ID of the video being watched",
                },
                "timestamp": {
                    "type": "number",
                    "description": "Current video position in seconds",
                },
            },
            "required": ["resource_id", "timestamp"],
        },
    },
    {
        "name": "control_simulation",
        "description": (
            "Control the student's active simulation by setting parameters or clicking buttons. "
            "Only works when the student has a simulation open (Active Simulation State in context). "
            "Use this to demo experiments, set up specific scenarios, or reset the simulation. "
            "The student will see the changes happen in real-time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "description": "Ordered list of actions to perform on the simulation",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["set_parameter", "click_button"],
                                "description": "Type of action",
                            },
                            "name": {"type": "string", "description": "Parameter name (for set_parameter)"},
                            "value": {"type": "string", "description": "Parameter value to set (for set_parameter)"},
                            "label": {"type": "string", "description": "Button label (for click_button)"},
                        },
                        "required": ["action"],
                    },
                },
            },
            "required": ["steps"],
        },
    },
    # ── Knowledge state tools ─────────────────────────────────────────────
    {
        "name": "query_knowledge",
        "description": (
            "Look up what you know about the student's understanding. "
            "Query by concept name, tag, module, or topic. "
            "Use this BEFORE teaching a concept to adapt your approach, "
            "or when the student seems confused to check their background."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Concept name, tag, module, or topic to search for",
                },
            },
            "required": ["query"],
        },
    },
    # ── Agent orchestration tools ──────────────────────────────────────────
    {
        "name": "spawn_agent",
        "description": (
            "Start a background agent to do work while you continue teaching. "
            "Results arrive in [AGENT RESULTS] on your next turn. "
            "Built-in types: 'planning' (plans next section). "
            "For interactive visualizations, use <teaching-widget> tag directly instead of agents. "
            "Any other type creates a custom LLM agent with your task/instructions as its prompt. "
            "Examples: 'research', 'problem_gen', 'content', 'analysis', 'worked_example'. "
            "CRITICAL: Always give the student something to do when spawning — "
            "assessment tag + spawn_agent in the same message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": (
                        "Agent type. 'planning' has built-in behavior. "
                        "Any other string creates a custom agent — name it descriptively."
                    ),
                },
                "task": {
                    "type": "string",
                    "description": (
                        "What the agent should do. Be specific and detailed. "
                        "For planning: starting topic, student model, observations. "
                        "For custom agents: the full task description."
                    ),
                },
                "instructions": {
                    "type": "string",
                    "description": "Additional instructions or context for the agent (optional)",
                },
            },
            "required": ["type", "task"],
        },
    },
    {
        "name": "check_agents",
        "description": (
            "Check status of all background agents and collect any completed results. "
            "Returns agent statuses and any newly completed results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "delegate_teaching",
        "description": (
            "Hand off a bounded teaching task to a focused sub-agent. "
            "The sub-agent takes over for the next N turns and returns a summary. "
            "USE FOR: problem drills (5-8 turns), simulation exploration, exam quizzes, "
            "worked example sequences, or any bounded interactive task. "
            "DON'T USE FOR: introducing new concepts, handling confusion, short interactions (<3 turns)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "What the sub-agent should teach/drill",
                },
                "instructions": {
                    "type": "string",
                    "description": (
                        "Specific instructions for the sub-agent. Include: what to cover, "
                        "difficulty progression, what to track, when to return. "
                        "The sub-agent gets core teaching behaviors + your instructions."
                    ),
                },
                "agent_type": {
                    "type": "string",
                    "description": (
                        "Descriptive label for this delegation. Examples: 'practice_drill', "
                        "'sim_explore', 'exam_quiz', 'worked_examples', 'concept_review'. "
                        "Default: 'practice_drill'"
                    ),
                },
                "max_turns": {
                    "type": "number",
                    "description": "Maximum turns before returning control (default: 6, max: 10)",
                },
            },
            "required": ["topic", "instructions"],
        },
    },
    {
        "name": "reset_plan",
        "description": (
            "Scrap the current teaching plan entirely and clear the sidebar. "
            "Use when the student's direction fundamentally changes and the current plan "
            "is no longer relevant — e.g. they need to go back to basics, want a different "
            "topic, or revealed a prerequisite gap that invalidates the current plan. "
            "After calling this, immediately spawn a new planning agent with the updated intent. "
            "The student sees the plan sidebar clear and then repopulate with the new plan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why the plan is being scrapped (for logging)",
                },
                "keep_scope": {
                    "type": "boolean",
                    "description": (
                        "If true, keep the session objective/scope (plan changes but goal stays). "
                        "If false, also reset session objective/scope (student wants something different). "
                        "Default: false."
                    ),
                },
            },
            "required": ["reason"],
        },
    },
    {
        "name": "modify_plan",
        "description": (
            "Modify the current teaching plan without scrapping it. Three actions:\n"
            "- insert_prereq: You discovered the student is missing a prerequisite. "
            "Push the current position onto a detour stack, insert prerequisite topics, "
            "and teach those first. When done, call modify_plan(action='end_detour') to resume.\n"
            "- end_detour: Pop the detour stack and resume where you left off before the detour.\n"
            "- skip: Skip the current topic (student already knows it) and advance to the next."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["insert_prereq", "end_detour", "skip"],
                    "description": "The plan modification action to take.",
                },
                "prereq_topics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "concept": {"type": "string"},
                        },
                        "required": ["title", "concept"],
                    },
                    "description": "Topics to insert as prerequisites (for insert_prereq only).",
                },
                "reason": {
                    "type": "string",
                    "description": "Why this plan change is needed.",
                },
            },
            "required": ["action", "reason"],
        },
    },
    {
        "name": "advance_topic",
        "description": (
            "Mark the current topic complete and move to the next planned topic. "
            "If no more topics remain, returns a signal to spawn a planning agent or wrap up."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tutor_notes": {
                    "type": "string",
                    "description": "Observations about the student during this topic",
                },
                "student_model": {
                    "type": "object",
                    "description": "Updated student model",
                    "properties": {
                        "strengths": {"type": "array", "items": {"type": "string"}},
                        "gaps": {"type": "array", "items": {"type": "string"}},
                        "misconceptions": {"type": "array", "items": {"type": "string"}},
                        "pace": {"type": "string"},
                        "engagement": {"type": "string"},
                        "preferred_modality": {"type": "string"},
                    },
                },
            },
            "required": ["tutor_notes"],
        },
    },
    {
        "name": "request_board_image",
        "description": (
            "Request a snapshot of the current board-draw canvas, including both your "
            "drawings and any student annotations. Use when you need to see what the "
            "student drew or annotated on the shared board. The image will be captured "
            "and sent as the next user message. Only works when a board-draw spotlight "
            "is currently active."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why you need to see the board (helps with context)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "fetch_asset",
        "description": (
            "Retrieve the full content of a previous board-draw or widget by its asset_id. "
            "Returns the complete JSONL drawing commands (for board-draws) or HTML/CSS/JS code "
            "(for widgets). Use this when you need the original content to resume drawing on "
            "a previous board via <teaching-board-draw-resume> or to understand a widget's "
            "code before sending <teaching-widget-update>. Asset IDs are shown in the "
            "[Previous Boards] and [Reusable Widgets] context sections."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_id": {
                    "type": "string",
                    "description": "The asset_id to retrieve (e.g., 'spot-ref-a3b7c1d2')",
                },
            },
            "required": ["asset_id"],
        },
    },
    {
        "name": "handoff_to_assessment",
        "description": (
            "Hand off to the Assessment Agent for a section checkpoint. "
            "Call this when a teaching section is complete and the student should be assessed "
            "on the concepts just taught. Provide a detailed brief including: what concepts "
            "to test, student weaknesses/strengths observed during teaching, recommended "
            "question types and difficulty, and content grounding references. "
            "The assessment agent will take over, conduct the checkpoint, and return results "
            "when complete. You will receive the results in [ASSESSMENT RESULTS] on your "
            "next turn after the assessment ends."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {
                    "type": "object",
                    "description": "The section being assessed",
                    "properties": {
                        "index": {"type": "number", "description": "Section index"},
                        "title": {"type": "string", "description": "Section title"},
                    },
                    "required": ["index", "title"],
                },
                "conceptsTested": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Concept names to test in this checkpoint",
                },
                "studentProfile": {
                    "type": "object",
                    "description": "What you observed about the student during teaching",
                    "properties": {
                        "weaknesses": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Concepts or skills the student struggled with",
                        },
                        "strengths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Concepts or skills the student demonstrated well",
                        },
                        "engagementStyle": {
                            "type": "string",
                            "description": "How the student best engages (visual, textual, etc.)",
                        },
                    },
                },
                "plan": {
                    "type": "object",
                    "description": "Assessment plan — question count, types, difficulty",
                    "properties": {
                        "questionCount": {
                            "type": "object",
                            "properties": {
                                "min": {"type": "number", "description": "Minimum questions (default 3)"},
                                "max": {"type": "number", "description": "Maximum questions (default 5)"},
                            },
                        },
                        "startDifficulty": {
                            "type": "string",
                            "enum": ["easy", "medium", "hard"],
                            "description": "Starting difficulty level (default medium)",
                        },
                        "types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Recommended question types: mcq, numerical, freetext, notebook-derivation, drawing, fillblank",
                        },
                        "focusAreas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Areas to focus assessment on (60% of questions)",
                        },
                        "avoid": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Concepts to skip — student already demonstrated mastery",
                        },
                    },
                },
                "conceptNotes": {
                    "type": "object",
                    "description": "Per-concept observations from teaching. Keys are concept names, values are your notes.",
                },
                "contentGrounding": {
                    "type": "object",
                    "description": "References to course content for question grounding",
                    "properties": {
                        "lessonId": {"type": "number"},
                        "sectionIndices": {"type": "array", "items": {"type": "number"}},
                        "keyExamples": {"type": "array", "items": {"type": "string"}},
                        "professorPhrasing": {"type": "string"},
                    },
                },
            },
            "required": ["section", "conceptsTested"],
        },
    },
    {
        "name": "update_student_model",
        "description": (
            "Your private notebook on this student. Called automatically every ~5 turns. "
            "Write freehand notes tagged with concept names. UPSERT: if a note for a "
            "concept already exists, your new note REPLACES it — always write the "
            "CURRENT complete picture, not incremental updates. One note per concept. "
            "Use concepts: ['_profile'] for student-wide observations (pace, style)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "notes": {
                    "type": "array",
                    "description": (
                        "Freehand notes tagged with concept names. One note per concept cluster. "
                        "If the concept was covered before, REWRITE the note with current state — "
                        "don't create a new note with slightly different tags.\n\n"
                        "TAG RULES (critical for deduplication):\n"
                        "- Use lowercase_underscore format: 'wave_function', NOT 'Wave Function'\n"
                        "- Use the SAME tag every time for the same concept — don't invent variants\n"
                        "- Check [Student Notes] in context — if a concept is already noted, use its EXACT tag\n"
                        "- Primary tag = the main concept. Secondary = subtopics.\n"
                        "- Special: '_profile' for student-wide notes (pace, modality, preferences)\n"
                        "- NEVER create two notes for the same concept with different tag spellings"
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "concepts": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Concept tags in lowercase_underscore format. "
                                    "Primary tag first, subtopics after. "
                                    "Examples: ['schrodinger_equation'], ['wave_function', 'probability'], "
                                    "['_profile']. Tags are auto-normalized to lowercase."
                                ),
                            },
                            "lesson": {
                                "type": "string",
                                "description": "Lesson context, e.g. 'lesson_2'.",
                            },
                            "note": {
                                "type": "string",
                                "description": (
                                    "Complete freehand observation. Cover: mastery level, what they can "
                                    "solve, what trips them up, what approach worked/failed, what to do "
                                    "next time. Write the FULL picture — this REPLACES any previous note "
                                    "on this concept."
                                ),
                            },
                        },
                        "required": ["concepts", "note"],
                    },
                },
            },
            "required": ["notes"],
        },
    },
    {
        "name": "complete_triage",
        "description": (
            "Call this when triage is done — you've gathered enough diagnostic signal "
            "to plan the session. Include your findings: what gaps you found, what's strong, "
            "and where to start teaching. After calling this, you'll transition to teaching mode."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "diagnosed_gaps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific weak areas found during triage",
                },
                "confirmed_strong": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Areas the student demonstrated strength in",
                },
                "student_level": {
                    "type": "string",
                    "description": "One-line characterization of where the student is",
                },
                "recommended_start": {
                    "type": "string",
                    "description": "Where to begin teaching and what approach to use",
                },
                "content_refs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific lesson/section refs to use (from content_search)",
                },
            },
            "required": ["diagnosed_gaps", "student_level", "recommended_start"],
        },
    },
    {
        "name": "session_signal",
        "description": (
            "Emit a session signal after your teaching response. Call this at the end "
            "of each teaching turn to indicate progress and student state. "
            "This helps the system know when to run checkpoints or adjust approach."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "section_progress": {
                    "type": "string",
                    "enum": ["in_progress", "wrapping_up", "complete"],
                    "description": "Current section teaching progress",
                },
                "student_state": {
                    "type": "string",
                    "enum": ["engaged", "confused", "struggling", "ahead"],
                    "description": "How the student seems based on their responses",
                },
                "needs_diagnostic": {
                    "type": "boolean",
                    "description": (
                        "Set true if student seems fundamentally lost — "
                        "missing prerequisites, not just confused on current topic"
                    ),
                },
            },
            "required": ["section_progress", "student_state"],
        },
    },
]

