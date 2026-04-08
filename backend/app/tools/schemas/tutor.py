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
    # ── Knowledge / sub-agent tools (filtered out of main tutor) ─────────
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
]

