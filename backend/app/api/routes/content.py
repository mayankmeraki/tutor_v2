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


@router.get("/courses")
async def list_courses(db: AsyncSession = Depends(get_db), user: dict = Depends(get_optional_user)):
    """List all courses with lesson/module counts and metadata."""
    from sqlalchemy import select, func
    from app.models.course import Course, Module, Lesson
    import re

    courses = (await db.execute(select(Course).order_by(Course.id))).scalars().all()
    result = []
    for c in courses:
        modules = (await db.execute(
            select(func.count()).select_from(Module).where(Module.course_id == c.id)
        )).scalar()
        lesson_rows = (await db.execute(
            select(Lesson.video_url).join(Module).where(Module.course_id == c.id).order_by(Lesson.order).limit(1)
        )).scalars().all()

        # Derive thumbnail from first lesson's video URL or course img_link
        thumbnail = c.img_link
        if not thumbnail and lesson_rows:
            first_video = lesson_rows[0]
            if first_video:
                m = re.search(r'(?:embed/|watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', first_video)
                if m:
                    thumbnail = f"https://img.youtube.com/vi/{m[1]}/hqdefault.jpg"

        # Derive subject from title (tags are topic-level, not subject-level)
        tags = c.tags or []
        subject = _guess_subject(c.title)

        total_lessons = (await db.execute(
            select(func.count()).select_from(Lesson).join(Module).where(Module.course_id == c.id)
        )).scalar()

        result.append({
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "lesson_count": total_lessons,
            "module_count": modules,
            "subject": subject,
            "difficulty": c.difficulty.value if c.difficulty else None,
            "thumbnail": thumbnail,
            "tags": tags,
            "rating": float(c.rating) if c.rating else None,
        })
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


@router.get("/courses/{course_id}")
async def course_map(course_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_optional_user)):
    result = await get_course_with_hierarchy(db, course_id)
    if not result:
        raise HTTPException(status_code=404, detail="Course not found")
    return result


@router.get("/lessons/{lesson_id}/sections")
async def lesson_sections(lesson_id: int, user: dict = Depends(get_optional_user)):
    return await get_lesson_sections_lightweight(lesson_id)


@router.get("/sections/{lesson_id}/{section_index}")
async def section_detail(lesson_id: int, section_index: int, user: dict = Depends(get_optional_user)):
    doc = await get_section_full(lesson_id, section_index)
    if not doc:
        raise HTTPException(status_code=404, detail="Section not found")
    return doc


@router.get("/courses/{course_id}/concepts")
async def course_concepts(course_id: int, user: dict = Depends(get_optional_user)):
    return await get_course_concepts(course_id)


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
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "-f", "best[height<=720][ext=mp4]/best[height<=720]/best",
            "--get-url", "--no-warnings", yt_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)

        if proc.returncode != 0:
            log.warning("yt-dlp failed: %s", stderr.decode()[:200])
            raise HTTPException(status_code=502, detail="Could not extract video stream")

        stream_url = stdout.decode().strip().split("\n")[0]
        if not stream_url.startswith("http"):
            raise HTTPException(status_code=502, detail="Invalid stream URL")

        return {"streamUrl": stream_url, "videoId": video_id}

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Video extraction timed out")
    except HTTPException:
        raise
    except Exception as e:
        log.error("Video stream extraction failed: %s", e)
        raise HTTPException(status_code=500, detail="Video extraction error")
