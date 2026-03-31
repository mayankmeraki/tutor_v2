"""Content resolver — maps free-text intent to available course content.

Given a student's intent ("calculus midterm prep"), finds matching courses,
lessons, and sections. Returns a structured brief that triage/planner can use.

Fast path: vector search + title matching. No LLM calls.
"""

import logging
import re
from collections import Counter

from app.core.mongodb import get_mongo_db

log = logging.getLogger(__name__)


async def resolve_content(intent: str, db_session=None) -> dict:
    """Resolve an intent string to a content brief.

    Returns:
        {
            "primary_course_id": int or None,
            "matched_courses": [
                {
                    "course_id": int,
                    "title": str,
                    "relevance": float,
                    "matched_lessons": [
                        {"lesson_id": int, "title": str, "relevance": float, "has_video": bool}
                    ]
                }
            ],
            "gaps": [str],           # Topics mentioned but no content found
            "total_matches": int,
            "resolve_method": str,   # "vector_search", "title_match", "none"
        }
    """
    if not intent or not intent.strip():
        return _empty_brief("empty_intent")

    intent = intent.strip()
    brief = {"matched_courses": [], "gaps": [], "total_matches": 0, "resolve_method": "none", "primary_course_id": None}

    # 1. Vector search across all indexed content
    try:
        from app.services.content_service import search_content
        results = await search_content(intent, limit=10)

        if results:
            brief["resolve_method"] = "vector_search"
            brief["total_matches"] = len(results)

            # Group results by courseId
            courses_map = {}
            for r in results:
                cid = r.get("courseId")
                if not cid:
                    continue
                if cid not in courses_map:
                    courses_map[cid] = {
                        "course_id": cid,
                        "title": "",
                        "matched_lessons": [],
                        "relevance": 0,
                    }
                score = r.get("score", 0.5)
                courses_map[cid]["relevance"] = max(courses_map[cid]["relevance"], score)

                if r.get("type") == "lesson":
                    courses_map[cid]["matched_lessons"].append({
                        "lesson_id": r.get("lessonId"),
                        "title": r.get("title", ""),
                        "relevance": score,
                        "has_video": bool(r.get("metadata", {}).get("video_url")),
                    })
                elif r.get("type") == "course":
                    courses_map[cid]["title"] = r.get("title", "")

            # Fill in course titles from lesson results
            if db_session:
                from sqlalchemy import select
                from app.models.course import Course
                for cid, cdata in courses_map.items():
                    if not cdata["title"]:
                        course = (await db_session.execute(
                            select(Course.title).where(Course.id == cid)
                        )).scalar_one_or_none()
                        if course:
                            cdata["title"] = course

            # Sort by relevance
            brief["matched_courses"] = sorted(
                courses_map.values(),
                key=lambda c: c["relevance"],
                reverse=True,
            )

            # Primary course = highest relevance
            if brief["matched_courses"]:
                brief["primary_course_id"] = brief["matched_courses"][0]["course_id"]

            return brief
    except Exception as e:
        log.warning("Vector search failed in resolver: %s", e)

    # 2. Fallback: title matching against courses
    if db_session:
        try:
            from sqlalchemy import select
            from app.models.course import Course
            courses = (await db_session.execute(select(Course))).scalars().all()
            intent_lower = intent.lower()
            words = [w for w in intent_lower.split() if len(w) > 3]

            for c in courses:
                title_lower = (c.title or "").lower()
                tags_lower = " ".join(t.lower() for t in (c.tags or []))
                match_score = sum(1 for w in words if w in title_lower or w in tags_lower)
                if match_score > 0:
                    brief["matched_courses"].append({
                        "course_id": c.id,
                        "title": c.title,
                        "relevance": match_score / max(len(words), 1),
                        "matched_lessons": [],  # No lesson-level matching in fallback
                    })

            if brief["matched_courses"]:
                brief["matched_courses"].sort(key=lambda c: c["relevance"], reverse=True)
                brief["primary_course_id"] = brief["matched_courses"][0]["course_id"]
                brief["resolve_method"] = "title_match"
                brief["total_matches"] = len(brief["matched_courses"])
                return brief
        except Exception as e:
            log.warning("Title match failed in resolver: %s", e)

    # 3. No match — flag the entire intent as a gap
    brief["gaps"].append(intent)
    return brief


def format_content_brief(brief: dict) -> str:
    """Format a content brief as a string for injection into agent prompts."""
    if not brief or not brief.get("matched_courses"):
        gaps = brief.get("gaps", []) if brief else []
        if gaps:
            return (
                f"[CONTENT BRIEF]\n"
                f"No matching course content found for: {', '.join(gaps)}\n"
                f"You'll need to teach from general knowledge or use web_search for material.\n"
            )
        return "[CONTENT BRIEF]\nNo content brief available.\n"

    lines = ["[CONTENT BRIEF]"]
    lines.append(f"Resolved via: {brief.get('resolve_method', '?')} ({brief.get('total_matches', 0)} matches)")
    lines.append("")

    for c in brief["matched_courses"]:
        lines.append(f"Course: {c.get('title', '?')} (id={c.get('course_id')})")
        for l in c.get("matched_lessons", [])[:8]:
            vid = " [video]" if l.get("has_video") else ""
            lines.append(f"  lesson:{l.get('lesson_id')} — {l.get('title', '?')}{vid}")
        lines.append("")

    if brief.get("gaps"):
        lines.append(f"GAPS (no content found): {', '.join(brief['gaps'])}")
        lines.append("For these topics, use web_search or teach from general knowledge.")

    return "\n".join(lines)


def _empty_brief(reason: str) -> dict:
    return {
        "primary_course_id": None,
        "matched_courses": [],
        "gaps": [],
        "total_matches": 0,
        "resolve_method": reason,
    }
