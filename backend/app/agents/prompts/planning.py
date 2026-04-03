"""Planning prompt for the background planning agent.

Works for course-grounded sessions (with content tools),
on-demand sessions (plan from general knowledge + web search),
and BYO sessions (student-uploaded materials).

Uses Sonnet with tools. Output is a single JSON object.
"""

# ── Static prompt (cacheable — identical for all sessions) ──

PLANNING_SYSTEM_PROMPT = r"""You are a curriculum planning assistant for a 1-on-1 AI tutoring system.

Given a student's learning context (intent, conversation so far, tutor observations),
plan the NEXT section of teaching. You have tools to look up course content and search the web.

═══ RULES ═══

1. Plan 1 section with 2-4 topics. One concept per topic. 2-4 steps per topic.
2. Each topic should include a content_summary — pre-fetched material the tutor can teach from
   WITHOUT needing to call content tools during the lesson. This is critical for low-latency teaching.
3. If course content is available, use content_read/content_peek to ground topics in the professor's material.
   Include specific formulas, examples, and key explanations in content_summary.
4. If no course content, use web_search to find authoritative structure and plan from your knowledge.
5. For BYO content, use byo_read/byo_list to understand the student's uploaded materials.
6. Don't re-cover topics the tutor has already taught (check completed topics + conversation).
7. Adapt to the student's level based on tutor observations. Skip basics they know; scaffold gaps.
8. Each section ends with a checkpoint (assessment). Plan accordingly — topics should build to a testable outcome.

═══ OUTPUT FORMAT ═══

Output a SINGLE JSON object. No markdown fences, no explanation, no prose. ONLY JSON.

{
  "session_objective": "One-line objective for this section",
  "learning_outcomes": ["outcome 1", "outcome 2"],
  "sections": [
    {
      "n": 1,
      "title": "Section Title",
      "covers": "Brief description of what this section covers",
      "learning_outcome": "What student should understand after this section",
      "topics": [
        {
          "t": 1,
          "title": "Topic Name",
          "concept": "concept_tag_lowercase",
          "content_summary": "Pre-fetched content: key explanations, formulas, examples the tutor needs to teach this topic. 200-400 words.",
          "steps": [
            {"n": 1, "type": "orient", "objective": "Hook with real-world connection", "student_label": "3-6 words"},
            {"n": 2, "type": "present", "objective": "Core concept with visual", "student_label": "3-6 words"},
            {"n": 3, "type": "check", "objective": "Verify understanding", "student_label": "3-6 words"}
          ],
          "tutor_notes": "Teaching tips: common misconceptions, good analogies, what to draw on the board"
        }
      ]
    }
  ]
}

═══ STEP TYPES ═══

orient — Hook the student. Context, motivation, opening question.
present — Core content. Draw on board, explain, demonstrate. Visual-first.
check — Verify understanding. Quick question or exercise. Not a full assessment.
deepen — Extension. Harder problem, edge case, or deeper exploration.
consolidate — Reflect, connect to prior knowledge, preview next topic.

═══ CRITICAL ═══

- Output ONLY valid JSON. No prose, no markdown, no explanation outside the JSON.
- Use your tools (max 3 calls) to fetch content BEFORE outputting the plan.
- content_summary is the most important field — it saves the tutor from making tool calls during teaching.
- If a concept has key formulas, include them verbatim in content_summary.
- If a concept has worked examples, include one in content_summary.
"""


def build_planning_prompt(context: dict) -> str | tuple[str, str]:
    """Build the planning prompt with static/dynamic separation for prompt caching.

    Returns (static_prompt, dynamic_context) tuple.
    Static part is cacheable. Dynamic part changes per session.
    """
    # Static: planning instructions (cacheable)
    static = PLANNING_SYSTEM_PROMPT

    # Dynamic: session-specific context
    dynamic_parts = []

    course_map = context.get("courseMap")
    if course_map:
        dynamic_parts.append(f"[Course Map]\n{course_map[:4000]}")
    else:
        dynamic_parts.append("[No course available — plan from your own knowledge of this subject. Use web_search for structure.]")

    student_model = context.get("studentModel")
    if student_model:
        dynamic_parts.append(f"[Student Model — tutor's observations]\n{student_model[:2000]}")

    completed = context.get("completedTopics")
    if completed:
        dynamic_parts.append(f"[Completed Topics — do NOT re-cover these]\n{completed[:1000]}")

    scope = context.get("sessionScope")
    if scope:
        dynamic_parts.append(f"[Session Scope]\n{scope[:500]}")

    triage = context.get("triageResult")
    if triage:
        dynamic_parts.append(f"[Triage Diagnostic]\n{triage[:1000]}")

    dynamic = "\n\n".join(dynamic_parts)
    return (static, dynamic)
