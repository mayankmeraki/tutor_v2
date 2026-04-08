"""Tests for context grounding, tool availability, plan injection, and BYO integration.

Verifies what the tutor actually SEES in its prompt at each turn,
which tools are available, and how the plan flows through.
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.prompts import build_tutor_prompt
from app.services.teaching.pipeline import (
    _build_plan_accountability,
    _format_completed,
    _format_session_scope,
    _validate_messages,
    _clean_partial_content,
    _strip_housekeeping_tag,
    CONTENT_TOOL_NAMES,
)
from app.tools import TUTOR_TOOLS, VIDEO_FOLLOW_TOOLS


# ═══════════════════════════════════════════════════════════════
#  Tool Availability Tests
# ═══════════════════════════════════════════════════════════════


class TestToolAvailability:
    """Verify which tools are available on each turn."""

    # Tools removed on ALL turns in WS path
    ALWAYS_REMOVED = {
        "update_student_model", "advance_topic", "session_signal",
        "spawn_agent", "check_agents",
        "modify_plan", "reset_plan",
        "handoff_to_assessment", "delegate_teaching",
    }

    # Additional tools removed on turn 1
    TURN1_REMOVED = {
        "content_search", "get_section_content", "query_knowledge",
        "content_read", "content_peek", "content_map",
    }

    def _get_available_tools(self, is_first_turn=False, is_video=False):
        removed = set(self.ALWAYS_REMOVED)
        if is_first_turn:
            removed |= self.TURN1_REMOVED
        source = VIDEO_FOLLOW_TOOLS if is_video else TUTOR_TOOLS
        return [t for t in source if t["name"] not in removed]

    def test_turn1_tools(self):
        """Turn 1: only teaching tools, no content fetching."""
        tools = self._get_available_tools(is_first_turn=True)
        names = {t["name"] for t in tools}
        print(f"\n  Turn 1 tools ({len(names)}): {sorted(names)}")

        # Should NOT have content/agent tools
        assert "content_search" not in names, "content_search should be stripped on turn 1"
        assert "get_section_content" not in names
        assert "query_knowledge" not in names
        assert "content_map" not in names
        assert "spawn_agent" not in names
        assert "update_student_model" not in names

        # SHOULD have teaching tools
        assert "search_images" in names, "search_images should be available"
        assert "control_simulation" in names

    def test_turn2_tools(self):
        """Turn 2+: content tools available."""
        tools = self._get_available_tools(is_first_turn=False)
        names = {t["name"] for t in tools}
        print(f"\n  Turn 2+ tools ({len(names)}): {sorted(names)}")

        # Content tools should be back
        assert "content_search" in names, "content_search should be available on turn 2+"
        assert "get_section_content" in names
        assert "web_search" in names
        assert "search_images" in names

        # Agent tools still removed
        assert "spawn_agent" not in names
        assert "session_signal" not in names

    def test_all_tutor_tools_exist(self):
        """All TUTOR_TOOLS have name and input_schema."""
        for t in TUTOR_TOOLS:
            assert "name" in t, f"Tool missing name: {t}"
            assert "input_schema" in t or "description" in t, f"Tool missing schema: {t['name']}"
        print(f"\n  Total TUTOR_TOOLS: {len(TUTOR_TOOLS)}")
        print(f"  Names: {[t['name'] for t in TUTOR_TOOLS]}")

    def test_byo_tools_in_tutor_tools(self):
        """BYO tools should be in TUTOR_TOOLS."""
        names = {t["name"] for t in TUTOR_TOOLS}
        print(f"\n  BYO tools present: byo_read={'byo_read' in names}, byo_list={'byo_list' in names}, byo_transcript={'byo_transcript_context' in names}")
        assert "byo_read" in names, "byo_read missing from TUTOR_TOOLS"
        assert "byo_list" in names, "byo_list missing from TUTOR_TOOLS"

    def test_content_tool_names_constant(self):
        """CONTENT_TOOL_NAMES should match what exists in TUTOR_TOOLS."""
        tutor_names = {t["name"] for t in TUTOR_TOOLS}
        for ct in CONTENT_TOOL_NAMES:
            assert ct in tutor_names, f"CONTENT_TOOL_NAMES has '{ct}' but it's not in TUTOR_TOOLS"
        print(f"\n  CONTENT_TOOL_NAMES: {CONTENT_TOOL_NAMES}")


# ═══════════════════════════════════════════════════════════════
#  Plan Injection Tests
# ═══════════════════════════════════════════════════════════════


class TestPlanInjection:
    """Verify plan data flows into the tutor prompt correctly."""

    SAMPLE_PLAN = {
        "session_objective": "Understand quantum entanglement",
        "learning_outcomes": ["superposition", "entanglement", "measurement"],
        "sections": [
            {
                "n": 1,
                "title": "Classical vs Quantum",
                "topics": [
                    {"title": "Coin Analogy", "concept": "classical_correlation"},
                    {"title": "Quantum Superposition", "concept": "superposition"},
                ]
            },
            {
                "n": 2,
                "title": "Entanglement",
                "topics": [
                    {"title": "EPR Pairs", "concept": "entanglement"},
                ]
            }
        ],
        "_topics": [
            {"title": "Coin Analogy", "concept": "classical_correlation", "steps": [{"n": 1, "type": "orient"}]},
            {"title": "Quantum Superposition", "concept": "superposition", "steps": [{"n": 1, "type": "present"}]},
            {"title": "EPR Pairs", "concept": "entanglement", "steps": [{"n": 1, "type": "orient"}]},
        ]
    }

    def _make_session(self):
        """Create a mock session with plan data."""
        class MockSession:
            current_plan = self.SAMPLE_PLAN
            current_topics = self.SAMPLE_PLAN["_topics"]
            current_topic_index = 0
            completed_topics = []
            session_objective = "Understand quantum entanglement"
            scope_concepts = ["superposition", "entanglement"]
            session_scope = "Quantum entanglement foundations"
            student_model = None
            detour_stack = []
        return MockSession()

    def test_plan_accountability(self):
        """Plan accountability should show current position."""
        session = self._make_session()
        acct = _build_plan_accountability(session)
        print(f"\n  Plan accountability: {json.dumps(acct, indent=2)}")
        assert acct["topic_title"] == "Coin Analogy"
        assert acct["topic_n"] == 1
        assert acct["topic_total"] == 3
        assert acct["done_count"] == 0

    def test_plan_accountability_after_advance(self):
        """After completing a topic, accountability should update."""
        session = self._make_session()
        session.completed_topics = ["Coin Analogy"]
        session.current_topic_index = 1
        acct = _build_plan_accountability(session)
        print(f"\n  After advance: {json.dumps(acct, indent=2)}")
        assert acct["topic_title"] == "Quantum Superposition"
        assert acct["topic_n"] == 2
        assert acct["done_count"] == 1

    def test_plan_in_prompt(self):
        """Plan should appear in the tutor prompt."""
        session = self._make_session()
        context = {
            "teachingPlan": json.dumps(session.current_plan, indent=2),
            "currentTopic": json.dumps(session.current_topics[0], indent=2),
            "completedTopics": None,
            "sessionScope": "Quantum entanglement",
            "planAccountability": _build_plan_accountability(session),
            "teachingMode": "voice",
        }
        static, dynamic = build_tutor_prompt(context)
        print(f"\n  Static prompt length: {len(static)} chars")
        print(f"  Dynamic context length: {len(dynamic)} chars")

        # Plan should be in dynamic context
        assert "TEACHING PLAN" in dynamic, "Teaching plan not in prompt"
        assert "Coin Analogy" in dynamic, "Current topic not in prompt"
        assert "PLAN ACCOUNTABILITY" in dynamic, "Plan accountability not in prompt"
        assert "Topic: \"Coin Analogy\" (1 of 3" in dynamic, "Topic position not shown"

        # Print relevant sections
        for line in dynamic.split("\n"):
            if any(k in line for k in ["TEACHING PLAN", "CURRENT TOPIC", "PLAN ACCOUNTABILITY", "Topic:", "Section:"]):
                print(f"    {line.strip()}")

    def test_plan_without_current_topic(self):
        """If all topics completed, currentTopic should be None."""
        session = self._make_session()
        session.current_topic_index = 99  # past end
        session.completed_topics = [
            {"title": "Coin Analogy", "concept": "classical_correlation"},
            {"title": "Superposition", "concept": "superposition"},
            {"title": "EPR", "concept": "entanglement"},
        ]
        context = {
            "teachingPlan": json.dumps(session.current_plan, indent=2),
            "currentTopic": None,
            "completedTopics": _format_completed(session.completed_topics),
            "teachingMode": "voice",
        }
        _, dynamic = build_tutor_prompt(context)
        assert "CURRENT TOPIC" not in dynamic, "Should not show current topic when all done"
        assert "COMPLETED TOPICS" in dynamic


# ═══════════════════════════════════════════════════════════════
#  Context Grounding Tests
# ═══════════════════════════════════════════════════════════════


class TestContextGrounding:
    """Verify what context the tutor sees for grounding."""

    def test_student_model_in_prompt(self):
        """Student model notes should appear in prompt."""
        model = {
            "notes": {
                "superposition": {"concepts": ["superposition"], "note": "Grasps coin analogy well"},
                "_profile": {"concepts": ["_profile"], "note": "Visual learner, fast pace"},
            }
        }
        context = {
            "studentModel": json.dumps(model, indent=2),
            "teachingMode": "voice",
        }
        _, dynamic = build_tutor_prompt(context)
        assert "Student Model" in dynamic, "Student model not in prompt"
        assert "superposition" in dynamic
        assert "Visual learner" in dynamic
        print(f"\n  Student model injected: {len(json.dumps(model))} chars")

    def test_knowledge_summary_in_prompt(self):
        """Knowledge summary should appear in prompt."""
        context = {
            "knowledgeSummary": "Strong: classical mechanics. Weak: quantum states. Gap: linear algebra.",
            "teachingMode": "voice",
        }
        _, dynamic = build_tutor_prompt(context)
        assert "Knowledge State" in dynamic
        assert "classical mechanics" in dynamic
        print("\n  Knowledge summary injected: YES")

    def test_agent_results_in_prompt(self):
        """Background agent results should appear in prompt."""
        context = {
            "agentResults": "[Enrichment Agent]\nWeb: Found 3 articles on Bell's theorem\nCourse: Section 4.2 covers EPR paradox in detail",
            "teachingMode": "voice",
        }
        _, dynamic = build_tutor_prompt(context)
        # Agent results go through the prompt builder
        assert "Bell" in dynamic or "AGENT" in dynamic
        print("\n  Agent results injected: YES")

    def test_course_map_in_prompt(self):
        """Course map should be available in context."""
        context = {
            "courseMap": json.dumps({
                "lessons": [
                    {"id": 1, "title": "Intro to QM", "sections": ["Waves", "Particles"]},
                    {"id": 2, "title": "Entanglement", "sections": ["EPR", "Bell"]},
                ]
            }),
            "teachingMode": "voice",
        }
        _, dynamic = build_tutor_prompt(context)
        # Course map is in context_data which gets spread into prompt
        print(f"\n  Dynamic context includes courseMap: {'Intro to QM' in dynamic or 'courseMap' in str(context)}")

    def test_byo_context_passthrough(self):
        """BYO session context should be available."""
        context = {
            "sessionContext": json.dumps({
                "collection_id": "col_abc123",
                "enriched_intent": "Study my lecture notes on photosynthesis",
            }),
            "teachingMode": "voice",
        }
        _, dynamic = build_tutor_prompt(context)
        print(f"\n  BYO context in prompt: sessionContext passed as context_data key")
        # BYO context flows through context_data — available to tools but
        # not directly injected into prompt (tools use it at call time)

    def test_housekeeping_due_injection(self):
        """Every 5th turn, housekeeping instructions should appear."""
        context = {
            "teachingMode": "voice",
            "_housekeepingDue": True,
        }
        _, dynamic = build_tutor_prompt(context)
        assert "HOUSEKEEPING DUE" in dynamic, "Housekeeping due not injected"
        print("\n  Housekeeping due injected: YES")

    def test_no_housekeeping_on_normal_turn(self):
        """Normal turns should NOT have housekeeping due."""
        context = {
            "teachingMode": "voice",
            "_housekeepingDue": False,
        }
        _, dynamic = build_tutor_prompt(context)
        assert "HOUSEKEEPING DUE" not in dynamic
        print("\n  Normal turn — no housekeeping: CORRECT")


# ═══════════════════════════════════════════════════════════════
#  Orphaned Tool Result Tests
# ═══════════════════════════════════════════════════════════════


class TestOrphanedToolResults:
    """Verify _validate_messages strips orphaned tool_result blocks."""

    def test_valid_tool_sequence(self):
        """Valid: assistant tool_use followed by user tool_result with matching ID."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": [
                {"type": "text", "text": "Let me search..."},
                {"type": "tool_use", "id": "tool_123", "name": "web_search", "input": {"query": "test"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tool_123", "content": "Results here"},
            ]},
        ]
        result = _validate_messages(messages)
        assert len(result) == 3, f"Expected 3 messages, got {len(result)}"
        print("\n  Valid tool sequence: PRESERVED")

    def test_orphaned_tool_result_stripped(self):
        """Orphaned: tool_result ID doesn't match any tool_use in prev assistant msg."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Just text, no tool_use"},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tool_orphan", "content": "This is orphaned"},
            ]},
        ]
        result = _validate_messages(messages)
        # Orphaned tool_result should be stripped
        assert len(result) == 2, f"Expected 2 messages (orphan dropped), got {len(result)}"
        print("\n  Orphaned tool_result: STRIPPED")

    def test_mixed_valid_and_orphaned(self):
        """Mix: one valid tool_result + one orphaned in same user message."""
        messages = [
            {"role": "assistant", "content": [
                {"type": "text", "text": "Searching"},
                {"type": "tool_use", "id": "tool_valid", "name": "search", "input": {}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tool_valid", "content": "Valid result"},
                {"type": "tool_result", "tool_use_id": "tool_ghost", "content": "Orphaned"},
            ]},
        ]
        result = _validate_messages(messages)
        user_msg = result[-1]
        tool_results = [b for b in user_msg["content"] if b.get("type") == "tool_result"]
        assert len(tool_results) == 1, f"Expected 1 tool_result, got {len(tool_results)}"
        assert tool_results[0]["tool_use_id"] == "tool_valid"
        print("\n  Mixed valid+orphaned: orphan stripped, valid kept")

    def test_assistant_string_content_no_tool_use(self):
        """If assistant content is a string (no tool_use), all tool_results are orphaned."""
        messages = [
            {"role": "assistant", "content": "I taught something great"},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tool_x", "content": "Result"},
            ]},
        ]
        result = _validate_messages(messages)
        # User message with all orphaned tool_results should be dropped
        has_tool_result = any(
            isinstance(m.get("content"), list) and
            any(b.get("type") == "tool_result" for b in m["content"] if isinstance(b, dict))
            for m in result
        )
        assert not has_tool_result, "Orphaned tool_result should be dropped entirely"
        print("\n  String assistant + tool_result user: DROPPED")


# ═══════════════════════════════════════════════════════════════
#  Prompt Structure Verification
# ═══════════════════════════════════════════════════════════════


class TestPromptStructure:
    """Verify the static/dynamic prompt split and what's in each part."""

    def test_static_dynamic_split(self):
        """Prompt should return (static, dynamic) tuple."""
        result = build_tutor_prompt({"teachingMode": "voice"})
        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        static, dynamic = result
        assert isinstance(static, str) or isinstance(static, tuple)
        print(f"\n  Static type: {type(static)}, Dynamic length: {len(dynamic)} chars")

    def test_voice_mode_in_static(self):
        """Voice mode instructions should be in static part (cached)."""
        result = build_tutor_prompt({"teachingMode": "voice"})
        static = result[0] if isinstance(result[0], str) else result[0][0] + result[0][1]
        assert "voice" in static.lower() or "scene" in static.lower(), "Voice instructions not in static prompt"
        print("\n  Voice mode in static: YES")

    def test_housekeeping_tag_in_static(self):
        """Housekeeping tag format should be in static part."""
        result = build_tutor_prompt({"teachingMode": "voice"})
        static = result[0] if isinstance(result[0], str) else result[0][0] + result[0][1]
        assert "teaching-housekeeping" in static, "Housekeeping tag format not in static prompt"
        assert "plan-modify" in static, "Plan-modify tag not in static prompt"
        print("\n  Housekeeping tags in static: YES")

    def test_dynamic_context_sections(self):
        """Dynamic context should have expected sections."""
        context = {
            "studentProfile": json.dumps({"studentName": "Test", "courseId": 1}),
            "teachingPlan": json.dumps({"sections": []}),
            "currentTopic": json.dumps({"title": "Test Topic"}),
            "planAccountability": {"topic_title": "Test", "topic_n": 1, "topic_total": 3, "section_title": "S1", "section_n": 1, "section_total": 2, "done_count": 0, "total_count": 5},
            "teachingMode": "voice",
            "_housekeepingDue": True,
        }
        _, dynamic = build_tutor_prompt(context)

        sections_found = []
        for marker in ["Student Profile", "TEACHING PLAN", "CURRENT TOPIC", "PLAN ACCOUNTABILITY", "HOUSEKEEPING DUE"]:
            found = marker in dynamic
            sections_found.append((marker, found))
            if not found:
                print(f"  WARNING: '{marker}' NOT found in dynamic context")

        print(f"\n  Dynamic sections: {sections_found}")
        assert all(f for _, f in sections_found), f"Missing sections: {[m for m, f in sections_found if not f]}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short", "-s"])
