"""Session service — CRUD for tutor_v2.sessions + LLM summary generation."""

import json
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.llm import llm_call, LLMBadRequestError
from app.core.mongodb import get_tutor_db

log = logging.getLogger(__name__)

# ─── Collection accessor ───────────────────────────────────────────

def _sessions():
    return get_tutor_db()["sessions"]


async def ensure_session_indexes():
    """Create indexes on frequently queried fields."""
    coll = _sessions()
    await coll.create_index("sessionId", unique=True)
    await coll.create_index([("courseId", 1), ("studentName", 1)])
    await coll.create_index([("courseId", 1), ("userEmail", 1)])
    await coll.create_index("startedAt")
    log.info("Session indexes ensured")


# ─── CRUD ───────────────────────────────────────────────────────────

async def create_session(session_data: dict) -> dict:
    """Insert a new session document. Returns the inserted document."""
    session_data.setdefault("createdAt", datetime.now(timezone.utc).isoformat())
    result = await _sessions().insert_one(session_data)
    session_data["_id"] = str(result.inserted_id)
    return session_data


async def get_session(session_id: str) -> dict | None:
    """Fetch a session by its sessionId field (UUID, not Mongo _id)."""
    doc = await _sessions().find_one({"sessionId": session_id})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def update_session(session_id: str, update: dict) -> dict | None:
    """Partial update via $set. Returns the updated document."""
    result = await _sessions().find_one_and_update(
        {"sessionId": session_id},
        {"$set": update},
        return_document=True,
    )
    if result:
        result["_id"] = str(result["_id"])
    return result


async def get_sessions_for_student(course_id: int, student_name: str) -> list[dict]:
    """Return all sessions for a student+course, newest first."""
    cursor = _sessions().find(
        {"courseId": course_id, "studentName": student_name},
        {
            "backendState.messages": 0,
            "backendState.conversationSummary": 0,
            "generatedVisuals": 0,
        },
    ).sort("startedAt", -1).limit(50)
    docs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        docs.append(doc)
    return docs


async def get_sessions_for_user(course_id: int, user_email: str) -> list[dict]:
    """Return all sessions for a user (by email) + course, newest first.

    Uses projection to exclude heavy fields (backendState.messages, generatedVisuals)
    that can be megabytes per session and cause timeouts on large collections.
    """
    cursor = _sessions().find(
        {"courseId": course_id, "userEmail": user_email},
        {
            "backendState.messages": 0,
            "backendState.conversationSummary": 0,
            "generatedVisuals": 0,
        },
    ).sort("startedAt", -1).limit(50)
    docs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        docs.append(doc)
    return docs


# ─── LLM Summary Generation ────────────────────────────────────────

SECTION_SUMMARY_PROMPT = """\
Summarize this teaching section transcript. Return ONLY valid JSON:
{{
  "text": "2-3 sentence summary of what happened",
  "keyPoints": ["point1", "point2"],
  "conceptsCovered": ["concept_name1"],
  "studentPerformance": "strong|moderate|weak",
  "misconceptions": ["if any, else empty array"]
}}

Section title: {title}
Learning outcome: {learning_outcome}

Transcript:
{transcript}"""


async def generate_section_summary(
    section_transcript: list[dict],
    section_info: dict,
    session_id: str | None = None,
) -> dict:
    """Call Claude Haiku to summarize a section's transcript.

    Returns {text, keyPoints, conceptsCovered, studentPerformance, misconceptions}.
    """
    # Format transcript for the LLM
    lines = []
    for msg in section_transcript:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        lines.append(f"[{role}] {content}")
    transcript_text = "\n".join(lines)

    prompt = SECTION_SUMMARY_PROMPT.format(
        title=section_info.get("title", "Unknown"),
        learning_outcome=section_info.get("learningOutcome", "Not specified"),
        transcript=transcript_text,
    )

    try:
        from app.core.llm import LLMCallMetadata
        response = await llm_call(
            model=settings.SUMMARIZATION_MODEL,
            system="",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            metadata=LLMCallMetadata(session_id=session_id, caller="summarization"),
        )

        # Extract text from response
        response_text = response.content[0].text.strip()

        # Parse JSON from response (handle markdown code blocks)
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        summary = json.loads(response_text)
        log.info(
            "Section summary generated: %s — %s",
            section_info.get("title", "?"),
            summary.get("studentPerformance", "?"),
        )
        return summary

    except Exception as e:
        log.error("Failed to generate section summary: %s", e, exc_info=True)
        return {
            "text": f"Summary generation failed: {str(e)[:100]}",
            "keyPoints": [],
            "conceptsCovered": [],
            "studentPerformance": "unknown",
            "misconceptions": [],
        }


HEADLINE_PROMPT = """\
Generate a short headline and description for this tutoring session. Return ONLY valid JSON:
{{"headline": "3-5 word headline describing the topic", "description": "One sentence describing what happened"}}

Session info:
- Student intent: {intent}
- Objective: {objective}
- Sections covered: {sections}
- Duration: {duration} minutes
- Performance: {performance}
- Conversation preview: {transcript_preview}"""


def _has_enough_data_for_headline(session: dict) -> bool:
    """Check if a session has enough content to generate a meaningful headline."""
    transcript = session.get("transcript", [])
    sections = session.get("sections", [])
    intent = (session.get("intent", {}) or {}).get("raw", "")
    # Need at least: some transcript OR sections OR a specific intent
    return len(transcript) >= 2 or len(sections) > 0 or bool(intent)


def _extract_transcript_preview(session: dict, max_chars: int = 500) -> str:
    """Extract a brief preview of the conversation for headline generation."""
    transcript = session.get("transcript", [])
    if not transcript:
        return "N/A"
    preview_parts = []
    chars = 0
    for msg in transcript[:10]:  # First 10 messages max
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
            )
        # Strip teaching tags for brevity
        import re
        content = re.sub(r'<teaching-[^>]*>[\s\S]*?</teaching-[^>]*>', '[visual]', content)
        content = re.sub(r'<teaching-[^/]*?/>', '', content)
        line = f"{role}: {content[:100]}"
        if chars + len(line) > max_chars:
            break
        preview_parts.append(line)
        chars += len(line)
    return "\n".join(preview_parts) if preview_parts else "N/A"


async def generate_session_headline(session: dict) -> dict:
    """Call Claude Haiku to generate a short headline for a session."""
    number = session.get("number", 1)
    intent = (session.get("intent", {}) or {}).get("raw", "") or "follow course"
    objective = session.get("plan", {}).get("sessionObjective", "") or "N/A"
    section_titles = [s.get("title", "") for s in session.get("sections", [])]
    sections_str = ", ".join(section_titles) if section_titles else "N/A"
    duration = round(session.get("durationSec", 0) / 60)
    score = session.get("metrics", {}).get("assessmentScore", {})
    performance = f"{score.get('pct', 0)}% ({score.get('correct', 0)}/{score.get('total', 0)})" if score.get("total") else "N/A"
    transcript_preview = _extract_transcript_preview(session)

    prompt = HEADLINE_PROMPT.format(
        number=number,
        intent=intent,
        objective=objective,
        sections=sections_str,
        duration=duration,
        performance=performance,
        transcript_preview=transcript_preview,
    )

    try:
        response = await llm_call(
            model=settings.SUMMARIZATION_MODEL,
            system="",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
        )
        response_text = response.content[0].text.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(response_text)
        log.info("Session headline generated for session #%d: %s", number, result.get("headline"))
        return {
            "headline": result.get("headline", f"Session {number}"),
            "description": result.get("description", ""),
        }
    except LLMBadRequestError as e:
        err_body = getattr(e, "body", {}) or {}
        err_msg = err_body.get("error", {}).get("message", "") if isinstance(err_body, dict) else str(e)
        if "credit" in err_msg.lower() or "billing" in err_msg.lower():
            log.warning("Headline generation skipped (billing): %s", err_msg)
        else:
            log.error("Failed to generate session headline: %s", e)
        return {"headline": f"Session {number}", "description": ""}
    except Exception as e:
        log.error("Failed to generate session headline: %s", e)
        return {"headline": f"Session {number}", "description": ""}


async def _enrich_sessions_with_headlines(sessions: list[dict]) -> list[dict]:
    """Return sessions immediately with fallback headlines.

    Fires background tasks for missing headlines — NEVER blocks the response.
    On next dashboard load, cached headlines from MongoDB will be used.
    """
    import asyncio
    import re as _re

    needs_generation = []

    for s in sessions:
        existing = s.get("headline", "")
        is_stale = bool(_re.match(r"^Session \d+$", existing))

        if existing and not is_stale:
            continue  # Good headline cached

        if not _has_enough_data_for_headline(s):
            if not existing:
                # Use intent as fallback title
                intent = (s.get("intent", {}) or {}).get("raw", "")
                s["headline"] = intent or f"Session {s.get('number', '?')}"
                s["headlineDescription"] = ""
            continue

        # Needs generation — use fallback now, generate in background
        if not existing or is_stale:
            intent = (s.get("intent", {}) or {}).get("raw", "")
            sec = (s.get("sections") or [{}])[0] if s.get("sections") else {}
            s["headline"] = intent or sec.get("title", "") or f"Session {s.get('number', '?')}"
            needs_generation.append(s)

    # Fire background tasks for headline generation (non-blocking)
    if needs_generation:
        # Limit to 3 concurrent generations to avoid rate limits
        async def _gen_headline_bg(session_doc):
            try:
                hl = await generate_session_headline(session_doc)
                await _sessions().update_one(
                    {"sessionId": session_doc["sessionId"]},
                    {"$set": {"headline": hl["headline"], "headlineDescription": hl["description"]}},
                )
                log.info("Background headline cached: %s → %s",
                         session_doc.get("sessionId", "?")[:8], hl["headline"])
            except Exception as e:
                log.warning("Background headline failed: %s", e)

        # Fire and forget — don't await
        for s in needs_generation[:5]:  # Cap at 5 to avoid spam
            asyncio.create_task(_gen_headline_bg(s))

    return sessions


async def get_sessions_with_headlines(course_id: int, student_name: str) -> list[dict]:
    """Return all sessions for a student+course with AI-generated headlines."""
    sessions = await get_sessions_for_student(course_id, student_name)
    return await _enrich_sessions_with_headlines(sessions)


async def get_sessions_with_headlines_by_email(course_id: int, user_email: str) -> list[dict]:
    """Return all sessions for a user (by email) + course with AI-generated headlines."""
    sessions = await get_sessions_for_user(course_id, user_email)
    return await _enrich_sessions_with_headlines(sessions)


# ─── Semantic Session Search ──────────────────────────────────

async def search_sessions_semantic(
    course_id: int,
    user_email: str,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Search sessions using text matching + knowledge note vector search.

    1. Text match: headline, description, intent, topic titles
    2. Vector match: find relevant concept notes → match to sessions that covered them
    Results are merged, deduplicated, and ranked.
    """
    import asyncio
    import re

    query_lower = query.lower().strip()
    if not query_lower:
        return []

    # Load all sessions for this user+course
    all_sessions = await get_sessions_for_user(course_id, user_email)
    if not all_sessions:
        return []

    # Enrich with headlines (cached — fast after first call)
    all_sessions = await _enrich_sessions_with_headlines(all_sessions)

    # ── Text matching (fast, always works) ──
    scored: list[tuple[float, dict]] = []
    query_terms = query_lower.split()

    for s in all_sessions:
        score = 0.0
        searchable = " ".join(filter(None, [
            s.get("headline", ""),
            s.get("headlineDescription", ""),
            (s.get("intent") or {}).get("raw", "") if isinstance(s.get("intent"), dict) else str(s.get("intent", "")),
            s.get("backendState", {}).get("sessionObjective", "") if isinstance(s.get("backendState"), dict) else "",
        ])).lower()

        # Score: each query term found
        for term in query_terms:
            if term in searchable:
                score += 2.0

        # Bonus: check completed topics
        bs = s.get("backendState", {}) if isinstance(s.get("backendState"), dict) else {}
        topics = bs.get("completedTopics", []) or []
        for topic in topics:
            title = (topic.get("title", "") + " " + topic.get("concept", "")).lower()
            for term in query_terms:
                if term in title:
                    score += 1.5

        if score > 0:
            scored.append((score, s))

    # ── Vector matching (semantic — may fail gracefully) ──
    try:
        from app.services.knowledge_state import vector_search_notes
        vector_results = await vector_search_notes(course_id, user_email, query, limit=5)

        if vector_results:
            # Find which sessions covered these concepts
            concept_tags = set()
            for vr in vector_results:
                for tag in vr.get("tags", []):
                    concept_tags.add(tag.lower())

            # Boost sessions that covered matching concepts
            session_ids_scored = {id(s): score for score, s in scored}
            for s in all_sessions:
                bs = s.get("backendState", {}) if isinstance(s.get("backendState"), dict) else {}
                topics = bs.get("completedTopics", []) or bs.get("currentTopics", []) or []
                for topic in topics:
                    concept = topic.get("concept", "").lower()
                    title = topic.get("title", "").lower()
                    for tag in concept_tags:
                        if tag in concept or tag in title:
                            existing = next((i for i, (_, es) in enumerate(scored) if es.get("sessionId") == s.get("sessionId")), None)
                            if existing is not None:
                                scored[existing] = (scored[existing][0] + 3.0, scored[existing][1])
                            else:
                                scored.append((3.0, s))
                            break
    except Exception as e:
        log.debug("Vector search in session search failed (graceful): %s", e)

    # Deduplicate by sessionId, keep highest score
    seen = {}
    for score, s in scored:
        sid = s.get("sessionId", id(s))
        if sid not in seen or score > seen[sid][0]:
            seen[sid] = (score, s)

    # Sort by score desc, then by date desc
    results = sorted(seen.values(), key=lambda x: (-x[0], x[1].get("startedAt", "")))
    return [s for _, s in results[:limit]]


# ─── Backend State Sync ──────────────────────────────────────

async def sync_backend_state(session_id: str, session) -> None:
    """Persist in-memory Session fields to MongoDB after each chat turn.

    All backend-managed fields live under `backendState` to avoid conflicts
    with frontend-managed fields (transcript, sections, metrics, plan, coursePosition).
    `generatedVisuals` is top-level since both frontend and backend need it.
    """
    backend_state = {
        "studentModel": session.student_model,
        "studentIntent": session.student_intent,
        "tutorNotes": session.tutor_notes,
        "assistantTurnCount": session.assistant_turn_count,
        "sessionStatus": session.session_status,
        "completionReason": session.completion_reason,
        "teachingMode": session.teaching_mode,
        "currentPlan": session.current_plan,
        "currentTopics": session.current_topics,
        "currentTopicIndex": session.current_topic_index,
        "completedTopics": session.completed_topics,
        "detourStack": session.detour_stack,
        "sessionObjective": session.session_objective,
        "sessionScope": session.session_scope,
        "scopeConcepts": session.scope_concepts,
        "activeScenario": session.active_scenario,
        "llmCostCents": session.llm_cost_cents,
        "llmTotalInputTokens": session.llm_total_input_tokens,
        "llmTotalOutputTokens": session.llm_total_output_tokens,
        "llmCallCount": session.llm_call_count,
        "conversationSummary": session.conversation_summary,
        "summaryCoverCount": session.summary_covers_through,
        "assetRegistry": session.asset_registry,
        "messages": session.messages,
    }

    if session.assessment_result:
        backend_state["assessmentResult"] = session.assessment_result
    if session.pre_assessment_note:
        backend_state["preAssessmentNote"] = session.pre_assessment_note
    if session.last_assessment_summary:
        backend_state["lastAssessmentSummary"] = session.last_assessment_summary

    # Persist in-flight delegation state so it survives server restarts
    if session.delegation:
        d = session.delegation
        backend_state["delegation"] = {
            "agentType": d.agent_type,
            "systemPrompt": d.system_prompt,
            "maxTurns": d.max_turns,
            "turnsUsed": d.turns_used,
            "topic": d.topic,
            "instructions": d.instructions,
        }

    # Persist in-flight assessment agent state
    if session.assessment:
        a = session.assessment
        backend_state["assessmentAgent"] = {
            "systemPrompt": a.system_prompt,
            "brief": a.brief,
            "sectionTitle": a.section_title,
            "conceptsTested": a.concepts_tested,
            "questionsAsked": a.questions_asked,
            "maxQuestions": a.max_questions,
            "minQuestions": a.min_questions,
            "turnsUsed": a.turns_used,
            "maxTurns": a.max_turns,
            "messages": a.messages,
        }

    update_doc = {
        "backendState": backend_state,
        "generatedVisuals": session.generated_visuals,
    }

    await _sessions().update_one(
        {"sessionId": session_id},
        {"$set": update_doc},
        upsert=False,
    )


async def load_backend_state(session_id: str) -> dict | None:
    """Load backend state from MongoDB for session restoration."""
    doc = await _sessions().find_one(
        {"sessionId": session_id},
        {"backendState": 1, "generatedVisuals": 1},
    )
    return doc


async def summarize_section(session_id: str, section_index: int) -> dict:
    """Read a section's transcript from the session, generate summary, store it back.

    Returns the generated summary dict.
    """
    session = await get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    sections = session.get("sections", [])
    section = None
    for s in sections:
        if s.get("index") == section_index:
            section = s
            break

    if section is None:
        raise ValueError(f"Section {section_index} not found in session {session_id}")

    transcript = section.get("transcript", [])
    if not transcript:
        # Fall back to full transcript filtered by section index
        transcript = [
            m for m in session.get("transcript", [])
            if m.get("sectionIndex") == section_index
        ]

    summary = await generate_section_summary(transcript, section)

    # Store summary in section
    await _sessions().update_one(
        {"sessionId": session_id, "sections.index": section_index},
        {"$set": {f"sections.$.summary": summary}},
    )

    # Update summaries.sectionDigests
    raw_token_count = sum(len(m.get("content", "")) // 4 for m in transcript)
    digest = {
        "sectionIndex": section_index,
        "title": section.get("title", ""),
        "digest": summary.get("text", ""),
        "conceptsCovered": summary.get("conceptsCovered", []),
        "studentPerformance": summary.get("studentPerformance", "unknown"),
        "rawTokenCount": raw_token_count,
    }

    await _sessions().update_one(
        {"sessionId": session_id},
        {
            "$push": {"summaries.sectionDigests": digest},
            "$inc": {"summaries.totalRawTokens": raw_token_count},
        },
    )

    # Regenerate session summary from all digests
    updated_session = await get_session(session_id)
    digests = updated_session.get("summaries", {}).get("sectionDigests", [])
    if digests:
        session_summary_parts = []
        for d in digests:
            perf = f" ({d.get('studentPerformance', '?')})" if d.get("studentPerformance") else ""
            session_summary_parts.append(f"{d.get('title', '?')}{perf}")
        objective = updated_session.get("plan", {}).get("sessionObjective", "")
        scenario = updated_session.get("intent", {}).get("scenario", "course")
        session_summary = (
            f"Session {updated_session.get('number', '?')}: "
            f"{scenario}. "
            f"Covered: {', '.join(session_summary_parts)}."
        )
        total_summarized = sum(len(d.get("digest", "")) // 4 for d in digests)
        await _sessions().update_one(
            {"sessionId": session_id},
            {"$set": {
                "summaries.sessionSummary": session_summary,
                "summaries.totalSummarizedTokens": total_summarized,
            }},
        )

    log.info("Section %d summary stored for session %s", section_index, session_id)
    return summary
