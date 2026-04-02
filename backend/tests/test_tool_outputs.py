"""Live tool output tests — calls actual tool implementations and prints results.

Run with: python -m pytest tests/test_tool_outputs.py -v -s
Requires: MongoDB connection, running backend services
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ═══════════════════════════════════════════════════════════════
#  Helper to run async and print results
# ═══════════════════════════════════════════════════════════════

def _print_result(tool_name, result, max_chars=2000):
    print(f"\n{'='*60}")
    print(f"  TOOL: {tool_name}")
    print(f"{'='*60}")
    if result is None:
        print("  (None returned)")
    elif isinstance(result, str):
        truncated = result[:max_chars]
        print(truncated)
        if len(result) > max_chars:
            print(f"\n  ... truncated ({len(result)} total chars)")
    else:
        print(json.dumps(result, indent=2, default=str)[:max_chars])
    print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════
#  Search Images (Wikimedia Commons — no DB needed)
# ═══════════════════════════════════════════════════════════════

class TestSearchImages:

    @pytest.mark.asyncio
    async def test_search_quantum(self):
        from app.tools.search_images import search_images
        result = await search_images("quantum entanglement diagram", limit=3)
        _print_result("search_images('quantum entanglement diagram')", result)
        assert result is not None
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_search_physics(self):
        from app.tools.search_images import search_images
        result = await search_images("double slit experiment", limit=2)
        _print_result("search_images('double slit experiment')", result)


# ═══════════════════════════════════════════════════════════════
#  Web Search (DuckDuckGo — no DB needed)
# ═══════════════════════════════════════════════════════════════

class TestWebSearch:

    @pytest.mark.asyncio
    async def test_web_search_physics(self):
        from app.tools.web_search import web_search
        result = await web_search("Bell's theorem quantum mechanics explanation", limit=3)
        _print_result("web_search('Bell's theorem quantum mechanics')", result)
        assert result is not None

    @pytest.mark.asyncio
    async def test_web_search_simple(self):
        from app.tools.web_search import web_search
        result = await web_search("photoelectric effect threshold frequency", limit=2)
        _print_result("web_search('photoelectric effect threshold frequency')", result)


# ═══════════════════════════════════════════════════════════════
#  Voice Clean Text (no DB needed)
# ═══════════════════════════════════════════════════════════════

class TestVoiceCleanText:

    def test_various_inputs(self):
        from app.services.tts_service import voice_clean_text

        samples = [
            ("Normal text", "Normal text"),
            ("{ref:eq1} Check the equation", "Check the equation"),
            ("**Bold** and *italic*", "Bold and italic"),
            ("See $$E=mc^2$$ here", "See here"),
            ("(no text)", ""),
            ("<div>HTML</div> content", "content"),
            ("$\\pi$ is about 3.14", "\\pi is about 3.14"),
            ("[Figure 1] shows the result", "shows the result"),
        ]

        print(f"\n{'='*60}")
        print(f"  TOOL: voice_clean_text")
        print(f"{'='*60}")
        for inp, expected in samples:
            result = voice_clean_text(inp)
            status = "✓" if result == expected else f"✗ got '{result}'"
            print(f"  '{inp}' → '{result}' {status}")
        print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════
#  Content Tools (require MongoDB)
# ═══════════════════════════════════════════════════════════════

class TestContentTools:
    """These require a running MongoDB with course data."""

    @pytest.mark.asyncio
    async def test_get_section_content(self):
        """Fetch section content for lesson 1, section 0."""
        try:
            from app.tools.handlers import get_section_content
            result = await get_section_content(1, 0)
            _print_result("get_section_content(lesson=1, section=0)", result)
        except Exception as e:
            _print_result("get_section_content(1, 0)", f"ERROR: {e}")

    @pytest.mark.asyncio
    async def test_get_section_brief(self):
        """Fetch brief for lesson 1, section 0."""
        try:
            from app.tools.handlers import get_section_brief
            result = await get_section_brief(1, 0)
            _print_result("get_section_brief(lesson=1, section=0)", result)
        except Exception as e:
            _print_result("get_section_brief(1, 0)", f"ERROR: {e}")

    @pytest.mark.asyncio
    async def test_get_simulation_details(self):
        """Fetch simulation details."""
        try:
            from app.tools.handlers import get_simulation_details
            # Try a common sim ID format
            result = await get_simulation_details("double-slit")
            _print_result("get_simulation_details('double-slit')", result)
        except Exception as e:
            _print_result("get_simulation_details('double-slit')", f"ERROR: {e}")

    @pytest.mark.asyncio
    async def test_content_search(self):
        """Search course content."""
        try:
            from app.services.content_service import search_content
            result = await search_content("quantum entanglement", limit=3)
            _print_result("content_search('quantum entanglement')", result)
        except Exception as e:
            _print_result("content_search('quantum entanglement')", f"ERROR: {e}")


# ═══════════════════════════════════════════════════════════════
#  BYO Tools (require MongoDB with BYO data)
# ═══════════════════════════════════════════════════════════════

class TestBYOTools:

    @pytest.mark.asyncio
    async def test_byo_list(self):
        """List BYO collection chunks."""
        try:
            from app.tools import execute_tutor_tool
            result = await execute_tutor_tool("byo_list", {"collection_id": "test_collection"})
            _print_result("byo_list('test_collection')", result)
        except Exception as e:
            _print_result("byo_list('test_collection')", f"ERROR: {e}")

    @pytest.mark.asyncio
    async def test_byo_read(self):
        """Read BYO content."""
        try:
            from app.tools import execute_tutor_tool
            result = await execute_tutor_tool("byo_read", {
                "collection_id": "test_collection",
                "query": "quantum mechanics"
            })
            _print_result("byo_read(query='quantum mechanics')", result)
        except Exception as e:
            _print_result("byo_read(query='quantum mechanics')", f"ERROR: {e}")


# ═══════════════════════════════════════════════════════════════
#  Knowledge Query (require MongoDB with student data)
# ═══════════════════════════════════════════════════════════════

class TestKnowledgeQuery:

    @pytest.mark.asyncio
    async def test_query_knowledge(self):
        """Search student knowledge notes."""
        try:
            from app.services.knowledge_state import hybrid_search_notes
            result = await hybrid_search_notes(
                course_id=1,
                user_email="test@test.com",
                query="quantum entanglement understanding",
                limit=3,
            )
            _print_result("query_knowledge('quantum entanglement understanding')", result)
        except Exception as e:
            _print_result("query_knowledge('quantum entanglement')", f"ERROR: {e}")


# ═══════════════════════════════════════════════════════════════
#  Full Context Assembly Test
# ═══════════════════════════════════════════════════════════════

class TestFullContextAssembly:
    """Show exactly what gets assembled into the tutor prompt."""

    def test_full_prompt_with_all_context(self):
        """Build a complete prompt with all context and show what the tutor sees."""
        from app.agents.prompts import build_tutor_prompt
        from app.api.routes.chat import _build_plan_accountability, _format_completed

        # Mock session state
        plan = {
            "session_objective": "Master quantum entanglement fundamentals",
            "learning_outcomes": ["superposition", "entanglement", "bell_theorem"],
            "sections": [
                {"n": 1, "title": "Quantum Basics", "topics": [
                    {"title": "Superposition", "concept": "superposition"},
                    {"title": "Measurement", "concept": "measurement"},
                ]},
                {"n": 2, "title": "Entanglement", "topics": [
                    {"title": "EPR Pairs", "concept": "entanglement"},
                    {"title": "Bell's Theorem", "concept": "bell_theorem"},
                ]},
            ],
            "_topics": [
                {"title": "Superposition", "concept": "superposition", "steps": [
                    {"n": 1, "type": "orient", "objective": "Connect to spinning coin analogy"},
                    {"n": 2, "type": "present", "objective": "Define superposition state"},
                    {"n": 3, "type": "check", "objective": "Verify understanding"},
                ]},
                {"title": "Measurement", "concept": "measurement", "steps": [
                    {"n": 1, "type": "orient", "objective": "What happens when we look?"},
                ]},
                {"title": "EPR Pairs", "concept": "entanglement", "steps": []},
                {"title": "Bell's Theorem", "concept": "bell_theorem", "steps": []},
            ]
        }

        student_model = {
            "notes": {
                "superposition": {
                    "concepts": ["superposition", "wave_function"],
                    "note": "Good grasp of coin analogy. Understands 'both at once' concept. Needs work on mathematical formalism."
                },
                "_profile": {
                    "concepts": ["_profile"],
                    "note": "Visual learner. Prefers animations over equations. Fast pace. Responds well to Socratic questions."
                }
            }
        }

        class MockSession:
            pass
        session = MockSession()
        session.current_plan = plan
        session.current_topics = plan["_topics"]
        session.current_topic_index = 1
        session.completed_topics = [{"title": "Superposition", "concept": "superposition"}]
        session.session_objective = plan["session_objective"]
        session.scope_concepts = plan["learning_outcomes"]
        session.session_scope = "Quantum entanglement foundations"
        session.student_model = student_model
        session.detour_stack = []

        context = {
            "studentProfile": json.dumps({
                "studentName": "Ishita",
                "courseId": 1,
                "experienceLevel": "beginner",
                "teachingMode": "voice",
            }),
            "courseMap": json.dumps({
                "title": "Introduction to Quantum Physics",
                "lessons": [
                    {"id": 1, "title": "Wave-Particle Duality", "sections": ["Basics", "Double Slit"]},
                    {"id": 2, "title": "Quantum States", "sections": ["Superposition", "Measurement"]},
                ]
            }),
            "knowledgeSummary": (
                "Strong: Classical mechanics, basic wave theory\n"
                "Developing: Quantum superposition (coin analogy understood)\n"
                "Gap: Mathematical formalism, Dirac notation\n"
                "Not yet covered: Entanglement, Bell's theorem"
            ),
            "studentModel": json.dumps(student_model, indent=2),
            "teachingPlan": json.dumps(plan, indent=2),
            "currentTopic": json.dumps(session.current_topics[session.current_topic_index], indent=2),
            "completedTopics": _format_completed(session.completed_topics),
            "sessionScope": "Quantum entanglement foundations",
            "planAccountability": _build_plan_accountability(session),
            "agentResults": (
                "[Enrichment Agent — content]\n"
                "Web: Found article on Bell's inequality with visual proof (phys.org/bell-inequality)\n"
                "Course: Section 2.3 covers measurement collapse with animations\n"
                "Knowledge: Student hasn't seen Dirac notation yet — avoid ket/bra for now"
            ),
            "teachingMode": "voice",
            "_housekeepingDue": True,
        }

        static, dynamic = build_tutor_prompt(context)

        # Write full prompt to file for inspection
        output = []
        output.append("=" * 80)
        output.append("FULL TUTOR PROMPT — WHAT THE MODEL ACTUALLY SEES")
        output.append("=" * 80)
        output.append("")
        output.append("─" * 40)
        output.append("STATIC PART (cached, 75K chars)")
        output.append("─" * 40)
        if isinstance(static, tuple):
            output.append(f"[Part 1: {len(static[0])} chars]")
            output.append(static[0][:500] + "\n... (truncated)")
            output.append(f"\n[Part 2: {len(static[1])} chars]")
            output.append(static[1][:500] + "\n... (truncated)")
        else:
            output.append(f"[{len(static)} chars]")
            output.append(static[:1000] + "\n... (truncated)")

        output.append("")
        output.append("─" * 40)
        output.append("DYNAMIC PART (per-turn context)")
        output.append("─" * 40)
        output.append(dynamic)

        result = "\n".join(output)

        # Write to file
        out_path = os.path.join(os.path.dirname(__file__), "output_full_prompt.txt")
        with open(out_path, "w") as f:
            f.write(result)

        print(f"\n  Full prompt written to: {out_path}")
        print(f"  Static: {len(static) if isinstance(static, str) else sum(len(p) for p in static)} chars")
        print(f"  Dynamic: {len(dynamic)} chars")
        print(f"\n  === DYNAMIC CONTEXT (what changes per turn) ===\n")
        print(dynamic)

        # Verify key sections
        assert "Ishita" in dynamic, "Student name not in prompt"
        assert "TEACHING PLAN" in dynamic, "Plan not in prompt"
        assert "Measurement" in dynamic, "Current topic not in prompt"
        assert "PLAN ACCOUNTABILITY" in dynamic, "Accountability not in prompt"
        assert "Enrichment Agent" in dynamic, "Agent results not in prompt"
        assert "HOUSEKEEPING DUE" in dynamic, "Housekeeping not in prompt"
        assert "Visual learner" in dynamic, "Teaching overrides not in prompt"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
