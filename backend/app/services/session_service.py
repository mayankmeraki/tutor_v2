"""Session service — CRUD for tutor_v2.sessions + LLM summary generation."""

import json
import logging
from datetime import datetime, timezone

import anthropic

from app.core.config import settings
from app.core.mongodb import get_tutor_db

log = logging.getLogger(__name__)

# ─── Collection accessor ───────────────────────────────────────────

def _sessions():
    return get_tutor_db()["sessions"]


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
    ).sort("startedAt", -1)
    docs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        docs.append(doc)
    return docs


async def get_sessions_for_user(course_id: int, user_email: str) -> list[dict]:
    """Return all sessions for a user (by email) + course, newest first."""
    cursor = _sessions().find(
        {"courseId": course_id, "userEmail": user_email},
    ).sort("startedAt", -1)
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
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model=settings.SUMMARIZATION_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response
        response_text = message.content[0].text.strip()

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
{{"headline": "3-4 word headline", "description": "One sentence describing what happened"}}

Session info:
- Session #{number}
- Student intent: {intent}
- Objective: {objective}
- Sections covered: {sections}
- Duration: {duration} minutes
- Performance: {performance}"""


async def generate_session_headline(session: dict) -> dict:
    """Call Claude Haiku to generate a short headline for a session."""
    number = session.get("number", 1)
    intent = session.get("intent", {}).get("raw", "") or "follow course"
    objective = session.get("plan", {}).get("sessionObjective", "") or "N/A"
    section_titles = [s.get("title", "") for s in session.get("sections", [])]
    sections_str = ", ".join(section_titles) if section_titles else "N/A"
    duration = round(session.get("durationSec", 0) / 60)
    score = session.get("metrics", {}).get("assessmentScore", {})
    performance = f"{score.get('pct', 0)}% ({score.get('correct', 0)}/{score.get('total', 0)})" if score.get("total") else "N/A"

    prompt = HEADLINE_PROMPT.format(
        number=number,
        intent=intent,
        objective=objective,
        sections=sections_str,
        duration=duration,
        performance=performance,
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model=settings.SUMMARIZATION_MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(response_text)
        log.info("Session headline generated for session #%d: %s", number, result.get("headline"))
        return {
            "headline": result.get("headline", f"Session {number}"),
            "description": result.get("description", ""),
        }
    except anthropic.BadRequestError as e:
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


async def get_sessions_with_headlines(course_id: int, student_name: str) -> list[dict]:
    """Return all sessions for a student+course with AI-generated headlines.

    If a session has no cached headline, generate one and store it.
    """
    sessions = await get_sessions_for_student(course_id, student_name)
    for s in sessions:
        if s.get("headline"):
            continue
        # Generate and cache
        hl = await generate_session_headline(s)
        s["headline"] = hl["headline"]
        s["headlineDescription"] = hl["description"]
        # Persist to MongoDB so we don't regenerate next time
        try:
            await _sessions().update_one(
                {"sessionId": s["sessionId"]},
                {"$set": {"headline": hl["headline"], "headlineDescription": hl["description"]}},
            )
        except Exception as e:
            log.warning("Failed to cache headline for session %s: %s", s.get("sessionId"), e)
    return sessions


async def get_sessions_with_headlines_by_email(course_id: int, user_email: str) -> list[dict]:
    """Return all sessions for a user (by email) + course with AI-generated headlines."""
    sessions = await get_sessions_for_user(course_id, user_email)
    for s in sessions:
        if s.get("headline"):
            continue
        hl = await generate_session_headline(s)
        s["headline"] = hl["headline"]
        s["headlineDescription"] = hl["description"]
        try:
            await _sessions().update_one(
                {"sessionId": s["sessionId"]},
                {"$set": {"headline": hl["headline"], "headlineDescription": hl["description"]}},
            )
        except Exception as e:
            log.warning("Failed to cache headline for session %s: %s", s.get("sessionId"), e)
    return sessions


# ─── Backend State Sync ──────────────────────────────────────

async def sync_backend_state(session_id: str, session) -> None:
    """Persist in-memory Session fields to MongoDB after each chat turn.

    All backend-managed fields live under `backendState` to avoid conflicts
    with frontend-managed fields (transcript, sections, metrics, plan, coursePosition).
    `generatedVisuals` is top-level since both frontend and backend need it.
    """
    await _sessions().update_one(
        {"sessionId": session_id},
        {"$set": {
            "backendState": {
                "studentModel": session.student_model,
                "tutorNotes": session.tutor_notes,
                "currentPlan": session.current_plan,
                "currentTopics": session.current_topics,
                "currentTopicIndex": session.current_topic_index,
                "completedTopics": session.completed_topics,
                "sessionObjective": session.session_objective,
                "sessionScope": session.session_scope,
                "scopeConcepts": session.scope_concepts,
                "activeScenario": session.active_scenario,
            },
            "generatedVisuals": session.generated_visuals,
        }},
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
