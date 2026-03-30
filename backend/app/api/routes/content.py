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
