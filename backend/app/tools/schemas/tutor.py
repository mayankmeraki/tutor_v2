"""Tutor tool schemas — unified retrieval + external content + sim control.

Retrieval surface is consolidated (task #11):
  - search / fetch / peek / nearby / list_contents
    These work across BOTH course content and BYO (student-uploaded) content.
    Scope routing is explicit — tutor picks `scope` per call.
  - web_search / search_images — external, non-course content.
  - control_simulation — UI control, not retrieval.

Removed (do NOT re-add without coordination):
  byo_read, byo_list, byo_transcript_context  → fold into search/fetch/nearby
  content_read, content_peek, content_search  → replaced by fetch/peek/search
  get_section_content, get_simulation_details → replaced by fetch

The student-model + triage tools (query_knowledge, update_student_model,
complete_triage) are kept untouched — they are not part of retrieval.
"""

TUTOR_TOOLS = [
    # ─────────────────────── UNIFIED RETRIEVAL ───────────────────────
    {
        "name": "search",
        "description": (
            "Semantic search across course + student-uploaded (BYO) content. "
            "USE THIS FIRST before asking the student to clarify — grounding beats "
            "interrogation. Cheapest way to find the right material for what the "
            "student is asking. Returns a list of refs you can pass to fetch/peek/nearby.\n"
            "Scope routing:\n"
            "  'course'      — Capacity course (requires a course in context)\n"
            "  'collection'  — one BYO collection (pass collection_id)\n"
            "  'resource'    — a single BYO resource (pass resource_id)\n"
            "  'user_corpus' — all of this student's BYO materials\n"
            "  'both'        — course + student's collection, merged by score\n"
            "Note: search is MORE EXPENSIVE than fetch (runs dense + sparse + rerank). "
            "Use fetch when you already know the ref."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — concept, question, or topic.",
                },
                "scope": {
                    "type": "string",
                    "enum": ["collection", "resource", "user_corpus", "course", "both"],
                    "description": "Where to search. Default 'both' if BYO collection is in session context, else 'course'.",
                },
                "collection_id": {
                    "type": "string",
                    "description": "BYO collection id (from session context). Required for scope='collection' or 'both'.",
                },
                "resource_id": {
                    "type": "string",
                    "description": "BYO resource id. Required for scope='resource'.",
                },
                "modality_filter": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of modalities to keep (e.g. ['pdf_digital','video']).",
                },
                "k": {
                    "type": "number",
                    "description": "Max results (default 5).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch",
        "description": (
            "Resolve a ref to its full content with citation. CHEAP — one lookup, "
            "no ranking. Use when you already have a ref from search/peek/plan.\n"
            "Ref formats:\n"
            "  lesson:ID:section:IDX  — a course section (transcript + key points)\n"
            "  lesson:ID              — a whole course lesson (overview + first section)\n"
            "  sim:ID                 — a simulation (controls + AI context + entry URL)\n"
            "  chunk:ID               — a BYO parent chunk (~800 tokens of content)\n"
            "  segment:ID             — a BYO child segment (resolves to its parent)\n"
            "  resource:ID            — a BYO resource (its first chunk as entry point)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": 'Content ref — e.g. "lesson:3:section:2", "chunk:abc123", "sim:dbl-slit".',
                },
            },
            "required": ["ref"],
        },
    },
    {
        "name": "peek",
        "description": (
            "Cheap summary of a ref (~100 tokens). Title + key points + anchor. "
            "Use for planning, or to pick the right section/chunk before calling fetch. "
            "Accepts the same ref formats as fetch."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": 'Content ref — e.g. "lesson:3", "lesson:3:section:2", "chunk:abc123", "resource:xyz".',
                },
            },
            "required": ["ref"],
        },
    },
    {
        "name": "nearby",
        "description": (
            "Deterministic anchor walk around a ref. NOT semantic — returns neighbours "
            "in the source order. Use for 'what came just before/after this' questions.\n"
            "  Course sections → ±window sections in the same lesson.\n"
            "  BYO video/audio → ±window minutes around the chunk's timestamp.\n"
            "  BYO PDF/slides  → ±window pages around the chunk's page.\n"
            "  BYO text/code   → ±window adjacent chunks by index.\n"
            "Tip: to get transcript around a video timestamp, first search or peek to find "
            "the matching chunk ref, then nearby(ref=chunk:..., window=1)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": "Ref to walk from — lesson:ID:section:IDX, chunk:ID, segment:ID, resource:ID.",
                },
                "window": {
                    "type": "number",
                    "description": "Neighbour radius. Default 1. Units depend on modality (sections / pages / minutes / chunks).",
                },
            },
            "required": ["ref"],
        },
    },
    {
        "name": "list_contents",
        "description": (
            "Inventory of what's available in a scope WITHOUT a query. Returns refs "
            "you can fetch/peek. Use when the student says 'what do I have?' or you "
            "want to pick a starting point without guessing.\n"
            "  scope='course'      → lessons/sections tree\n"
            "  scope='collection'  → resources in a BYO collection (pass collection_id)\n"
            "  scope='user_corpus' → resources across all of student's BYO collections"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["collection", "user_corpus", "course"],
                    "description": "Which inventory to list.",
                },
                "collection_id": {
                    "type": "string",
                    "description": "Required for scope='collection'.",
                },
                "group_by": {
                    "type": "string",
                    "enum": ["resource", "modality", "topic", "none"],
                    "description": "How to group results (BYO only). Default 'resource'.",
                },
            },
            "required": ["scope"],
        },
    },
    # ─────────────────────── EXTERNAL CONTENT ───────────────────────
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
    # ─────────────────────── SIMULATION CONTROL ───────────────────────
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
                            "blooms": {
                                "type": "string",
                                "enum": ["remember", "understand", "apply", "analyze", "evaluate", "create"],
                                "description": (
                                    "Bloom's taxonomy level observed for this concept. "
                                    "Drives next-session calibration: teach ONE level above."
                                ),
                            },
                            "approach_tried": {
                                "type": "string",
                                "description": (
                                    "What teaching approach was used: worked_example, socratic, "
                                    "visual, algebraic, simulation, analogy, etc."
                                ),
                            },
                            "approach_worked": {
                                "type": "boolean",
                                "description": (
                                    "Did the approach land? true = student got the verify question right. "
                                    "false = student still struggled. Drives approach selection next time."
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
                    "description": "Specific lesson/section refs to use (from search results)",
                },
            },
            "required": ["diagnosed_gaps", "student_level", "recommended_start"],
        },
    },
]

