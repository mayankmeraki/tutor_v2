"""Orchestrator — Dynamic agentic loop for student-facing interactions.

The Orchestrator is the counsellor. It lives on the Home screen and handles:
- Intent understanding (what does the student need?)
- Content discovery (search courses, materials)
- Artifact creation (flashcards, notes, study plans)
- Session creation (enriched context handoff to Tutor)
- Inline responses (quick answers, clarification)

Architecture: dynamic agentic loop (like Claude Code's Agent SDK).
The LLM decides what to do, spawns sub-agents with specific
instructions, awaits results, reasons, spawns more. Not a fixed graph.
"""
