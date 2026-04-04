from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_optional_user
from app.core.database import get_db
from app.services.content_service import (
    get_course_concepts,
    get_course_with_hierarchy,
    get_lesson_sections_lightweight,
    get_section_full,
    search_content,
)

router = APIRouter(prefix="/api/v1/content", tags=["content"])


_courses_cache: dict = {"data": None, "ts": 0}
_COURSES_TTL = 300  # 5 minutes

@router.get("/courses")
async def list_courses(db: AsyncSession = Depends(get_db), user: dict = Depends(get_optional_user)):
    """List all courses with lesson/module counts and metadata.

    Uses a server-side TTL cache (5 min) — course catalog rarely changes.
    Single batch query instead of N+1.
    """
    import time
    now = time.time()
    if _courses_cache["data"] and now - _courses_cache["ts"] < _COURSES_TTL:
        return _courses_cache["data"]

    from sqlalchemy import select, func
    from app.models.course import Course, Module, Lesson
    import re

    # Batch: all courses + aggregated counts in 2 queries total
    courses = (await db.execute(select(Course).order_by(Course.id))).scalars().all()

    # Module counts per course — one query
    mod_counts = dict((await db.execute(
        select(Module.course_id, func.count()).group_by(Module.course_id)
    )).all())

    # Lesson counts + first video URL per course — one query
    lesson_agg = (await db.execute(
        select(
            Module.course_id,
            func.count(Lesson.id),
            func.min(Lesson.video_url),
        )
        .join(Module)
        .group_by(Module.course_id)
    )).all()
    lesson_counts = {row[0]: row[1] for row in lesson_agg}
    first_videos = {row[0]: row[2] for row in lesson_agg}

    result = []
    for c in courses:
        # Derive thumbnail (strip whitespace — some DB entries have leading spaces)
        thumbnail = (c.img_link or "").strip() or None
        if not thumbnail:
            first_video = first_videos.get(c.id)
            if first_video:
                m = re.search(r'(?:embed/|watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', first_video)
                if m:
                    thumbnail = f"https://img.youtube.com/vi/{m[1]}/hqdefault.jpg"

        result.append({
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "lesson_count": lesson_counts.get(c.id, 0),
            "module_count": mod_counts.get(c.id, 0),
            "subject": _guess_subject(c.title),
            "difficulty": c.difficulty.value if c.difficulty else None,
            "thumbnail": thumbnail,
            "tags": c.tags or [],
            "rating": float(c.rating) if c.rating else None,
        })

    _courses_cache["data"] = result
    _courses_cache["ts"] = now
    return result


def _guess_subject(title: str) -> str:
    """Best-effort subject detection from course title."""
    t = (title or "").lower()
    if any(w in t for w in ("calculus", "algebra", "geometry", "math", "trigonometry")):
        return "Mathematics"
    if any(w in t for w in ("quantum", "physics", "mechanic", "electr", "magnet", "thermo")):
        return "Physics"
    if any(w in t for w in ("chemistry", "organic", "inorganic")):
        return "Chemistry"
    if any(w in t for w in ("biology", "cell", "genetics")):
        return "Biology"
    if any(w in t for w in ("computer", "algorithm", "data structure", "programming", "dsa")):
        return "Computer Science"
    return "Course"


@router.get("/resolve-course")
async def resolve_course(q: str = Query(""), db: AsyncSession = Depends(get_db), user: dict = Depends(get_optional_user)):
    """Resolve a free-text intent to matching courses and lessons.

    Returns a content brief: matched courses with relevant lessons,
    primary courseId, and gaps (topics with no matching content).
    """
    from app.services.content_resolver import resolve_content

    brief = await resolve_content(q, db_session=db)
    return {
        "courseId": brief.get("primary_course_id"),
        "brief": brief,
    }


_course_detail_cache: dict = {}  # {course_id: {"data": ..., "ts": ...}}
_COURSE_DETAIL_TTL = 300  # 5 minutes

@router.get("/courses/{course_id}")
async def course_map(course_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_optional_user)):
    import time
    now = time.time()
    cached = _course_detail_cache.get(course_id)
    if cached and now - cached["ts"] < _COURSE_DETAIL_TTL:
        return cached["data"]

    result = await get_course_with_hierarchy(db, course_id)
    if not result:
        raise HTTPException(status_code=404, detail="Course not found")

    _course_detail_cache[course_id] = {"data": result, "ts": now}
    return result


_sections_cache: dict = {}     # {lesson_id: {"data": ..., "ts": ...}}
_concepts_cache: dict = {}     # {course_id: {"data": ..., "ts": ...}}
_CONTENT_CACHE_TTL = 300       # 5 min

@router.get("/lessons/{lesson_id}/sections")
async def lesson_sections(lesson_id: int, user: dict = Depends(get_optional_user)):
    import time
    now = time.time()
    cached = _sections_cache.get(lesson_id)
    if cached and now - cached["ts"] < _CONTENT_CACHE_TTL:
        return cached["data"]
    result = await get_lesson_sections_lightweight(lesson_id)
    _sections_cache[lesson_id] = {"data": result, "ts": now}
    return result


@router.get("/sections/{lesson_id}/{section_index}")
async def section_detail(lesson_id: int, section_index: int, user: dict = Depends(get_optional_user)):
    doc = await get_section_full(lesson_id, section_index)
    if not doc:
        raise HTTPException(status_code=404, detail="Section not found")
    return doc


@router.get("/courses/{course_id}/concepts")
async def course_concepts(course_id: int, user: dict = Depends(get_optional_user)):
    import time
    now = time.time()
    cached = _concepts_cache.get(course_id)
    if cached and now - cached["ts"] < _CONTENT_CACHE_TTL:
        return cached["data"]
    result = await get_course_concepts(course_id)
    _concepts_cache[course_id] = {"data": result, "ts": now}
    return result


@router.get("/search")
async def content_search(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, le=20),
    user: dict = Depends(get_optional_user),
):
    return await search_content(q, limit)


@router.get("/video-stream")
async def video_stream_url(
    url: str = Query(..., description="YouTube video URL"),
    user: dict = Depends(get_optional_user),
):
    """Extract direct stream URL from YouTube video for custom player."""
    import asyncio
    import logging
    import re

    log = logging.getLogger(__name__)

    # Extract video ID
    m = re.search(r'(?:youtu\.be/|v=|/embed/)([A-Za-z0-9_-]{11})', url)
    if not m:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    video_id = m.group(1)
    yt_url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        # Use yt-dlp as Python library (more reliable than subprocess in containers)
        import yt_dlp
        ydl_opts = {
            'format': 'best[height<=720][ext=mp4]/best[height<=720]/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        loop = asyncio.get_event_loop()
        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(yt_url, download=False)
                return info.get('url') or info.get('webpage_url')
        stream_url = await asyncio.wait_for(
            loop.run_in_executor(None, _extract),
            timeout=15,
        )

        if not stream_url or not stream_url.startswith("http"):
            raise HTTPException(status_code=502, detail="Invalid stream URL")

        return {"streamUrl": stream_url, "videoId": video_id}

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Video extraction timed out")
    except HTTPException:
        raise
    except Exception as e:
        log.error("Video stream extraction failed: %s", e)
        raise HTTPException(status_code=500, detail="Video extraction error")
