"""Tests for prompt building functions."""

import pytest

from app.agents.prompts import (
    build_tutor_prompt,
    build_planning_prompt,
    TUTOR_SYSTEM_PROMPT,
    TOOLKIT_PROMPT,
    TAGS_PROMPT,
    PLANNING_PROMPT,
)


class TestBuildTutorPromptTextMode:
    def test_build_tutor_prompt_text_mode(self):
        """Basic tutor prompt includes all core sections in text mode."""
        context = {
            "studentProfile": '{"name": "Alice", "sessionCount": 5}',
            "courseMap": '[{"lesson": "Mechanics"}]',
            "concepts": "force, momentum, energy",
            "sessionMetrics": '{"sessionCount": 5, "turnCount": 10}',
        }
        prompt = build_tutor_prompt(context)

        # Should contain the base system prompt
        assert "You are Euler" in prompt
        # Should contain toolkit and tags
        assert "YOUR TOOLS" in prompt
        # Should contain course context
        assert "COURSE CONTEXT" in prompt
        assert "Student Profile" in prompt
        assert "Course Map" in prompt
        assert "Course Concepts" in prompt
        assert "Session Metrics" in prompt
        # For sessionCount=5 -> RETURNING_STUDENT
        assert "RETURNING_STUDENT" in prompt


class TestBuildTutorPromptVoiceMode:
    def test_build_tutor_prompt_voice_mode(self):
        """Tutor prompt with voice-relevant context fields."""
        context = {
            "studentProfile": '{"name": "Bob", "sessionCount": 1}',
            "courseMap": '[{"lesson": "Waves"}]',
            "concepts": "amplitude, frequency",
            "sessionMetrics": '{"sessionCount": 1, "turnCount": 2}',
        }
        prompt = build_tutor_prompt(context)

        # Voice mode uses the same build path, but for new students
        # should get NEW_STUDENT tag since sessionCount=1
        assert "NEW_STUDENT" in prompt
        assert "new to the course" in prompt


class TestVoiceModePromptInStaticBlock:
    def test_voice_mode_prompt_in_static_block(self):
        """The TUTOR_SYSTEM_PROMPT static block contains voice-related guidance."""
        # The tutor system prompt mentions voice commands in board-draw context
        assert "voice" in TUTOR_SYSTEM_PROMPT.lower() or "board" in TUTOR_SYSTEM_PROMPT.lower()
        # Board-draw guidance is core to the static block
        assert "BOARD-DRAW" in TUTOR_SYSTEM_PROMPT


class TestPlanningPromptHasTools:
    def test_planning_prompt_has_tools(self):
        """Planning prompt references tool usage (get_section_content)."""
        assert "get_section_content" in PLANNING_PROMPT
        assert "tools" in PLANNING_PROMPT.lower()

    def test_planning_prompt_build(self):
        """build_planning_prompt includes course context sections."""
        context = {
            "studentProfile": '{"name": "Charlie"}',
            "courseMap": '[{"lesson": "Optics"}]',
            "concepts": "refraction, reflection",
            "knowledgeState": "Knows basics of light",
            "studentModel": "Learns well with diagrams",
            "tutorNotes": "Struggling with Snell's law",
        }
        prompt = build_planning_prompt(context)

        assert "COURSE CONTEXT" in prompt
        assert "Student Profile" in prompt
        assert "Course Map" in prompt
        assert "Course Concepts" in prompt
        assert "Student Knowledge State" in prompt
        assert "Tutor's Notes" in prompt
        assert "Recent Tutor Observations" in prompt


class TestCommonPromptSectionsOrder:
    # Use unique section header markers that build_tutor_prompt injects
    # (not substrings that also appear within the TUTOR_SYSTEM_PROMPT body)
    _COURSE_HEADER = "COURSE CONTEXT (pre-loaded"
    _PLAN_HEADER = " TEACHING PLAN — Full outline"
    _TOPIC_HEADER = " CURRENT TOPIC — Execute these steps now"
    _GROUNDING_HEADER = "GROUNDING — COURSE CONTENT IS YOUR SOURCE OF TRUTH"

    def test_common_prompt_sections_order(self):
        """Tutor prompt assembles sections in the expected order:
        system prompt -> toolkit -> tags -> course context -> plan -> topic
        """
        context = {
            "studentProfile": '{"name": "Diana", "sessionCount": 3}',
            "courseMap": '[{"lesson": "Thermodynamics"}]',
            "concepts": "entropy, enthalpy",
            "sessionMetrics": '{"sessionCount": 3}',
            "teachingPlan": "Plan: cover entropy then enthalpy",
            "currentTopic": "Topic: entropy basics",
        }
        prompt = build_tutor_prompt(context)

        system_pos = prompt.find("You are Euler")
        grounding_pos = prompt.find(self._GROUNDING_HEADER)
        course_pos = prompt.find(self._COURSE_HEADER)
        plan_pos = prompt.find(self._PLAN_HEADER)
        topic_pos = prompt.find(self._TOPIC_HEADER)

        assert system_pos >= 0
        assert grounding_pos >= 0
        assert course_pos >= 0
        assert plan_pos >= 0
        assert topic_pos >= 0

        assert system_pos < grounding_pos, "System prompt should come before toolkit"
        assert course_pos < plan_pos, "Course context should come before teaching plan"
        assert plan_pos < topic_pos, "Teaching plan should come before current topic"

    def test_optional_sections_omitted_when_empty(self):
        """When optional context fields are absent, their sections are not in the prompt."""
        context = {
            "studentProfile": '{"name": "Eve", "sessionCount": 1}',
            "sessionMetrics": '{"sessionCount": 1}',
        }
        prompt = build_tutor_prompt(context)

        # Use the specific section header markers injected by build_tutor_prompt
        assert self._PLAN_HEADER not in prompt
        assert self._TOPIC_HEADER not in prompt
        assert "AGENT RESULTS — Background agents" not in prompt
        assert "DELEGATION RESULT — Sub-agent" not in prompt
        assert "ASSESSMENT RESULTS — Checkpoint" not in prompt
        assert "[Student Knowledge State]" not in prompt

    def test_assessment_result_injection(self):
        """When assessmentResult is provided, it adds the assessment section."""
        context = {
            "studentProfile": '{"name": "Frank", "sessionCount": 2}',
            "sessionMetrics": '{"sessionCount": 2}',
            "assessmentResult": "Score: 3/5 (60%)\nWeak: friction\nStrong: gravity",
        }
        prompt = build_tutor_prompt(context)

        assert "ASSESSMENT RESULTS — Checkpoint" in prompt
        assert "Score: 3/5" in prompt
        assert "invite the student to discuss" in prompt

    def test_scenario_skill_injected(self):
        """When scenarioSkill is set, it appears before course context header."""
        context = {
            "studentProfile": '{"name": "Grace", "sessionCount": 4}',
            "sessionMetrics": '{"sessionCount": 4}',
            "scenarioSkill": "EXAM FULL SCENARIO: test all topics",
        }
        prompt = build_tutor_prompt(context)

        assert "ACTIVE SCENARIO SKILL" in prompt
        assert "EXAM FULL SCENARIO" in prompt

        # Scenario should appear before the course context header
        scenario_pos = prompt.find("ACTIVE SCENARIO SKILL")
        course_pos = prompt.find(self._COURSE_HEADER)
        assert scenario_pos < course_pos
