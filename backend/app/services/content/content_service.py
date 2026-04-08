from bson import ObjectId
from bson.errors import InvalidId
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mongodb import get_mongo_db
from app.models.course import Course, Lesson, Module


def _serialize_mongo(doc: dict) -> dict:
    """Convert MongoDB document for JSON serialization.

    Also adds an ``id`` alias for ``_id`` at the top level so the frontend
    can look up documents by ``doc.id``.
    """
    if doc is None:
        return None
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, dict):
            out[k] = _serialize_mongo(v)
        elif isinstance(v, list):
            out[k] = [_serialize_mongo(i) if isinstance(i, dict) else (str(i) if isinstance(i, ObjectId) else i) for i in v]
        else:
            out[k] = v
    # Provide 'id' alias for '_id' so frontend can use doc.id
    if "_id" in out and "id" not in out:
        out["id"] = out["_id"]
    return out


# ── Lightweight cached course title lookup ──
_course_title_cache: dict[int, str] = {}

async def get_course_title_cached(course_id: int) -> str:
    """Get just the course title — cached in memory, single lightweight query."""
    if course_id in _course_title_cache:
        return _course_title_cache[course_id]
    try:
        from app.core.database import get_db
        db_gen = get_db()
        db_session = await db_gen.__anext__()
        try:
            result = await db_session.execute(
                select(Course.title).where(Course.id == course_id)
            )
            title = result.scalar_one_or_none()
            if title:
                _course_title_cache[course_id] = title
                return title
        finally:
            await db_gen.aclose()
    except Exception:
        pass
    return ""


async def get_course_with_hierarchy(db: AsyncSession, course_id: int) -> dict | None:
    course = (await db.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
    if not course:
        return None

    modules = (await db.execute(
        select(Module).where(Module.course_id == course_id).order_by(Module.id)
    )).scalars().all()

    module_ids = [m.id for m in modules]
    lessons = (await db.execute(
        select(Lesson).where(Lesson.module_id.in_(module_ids)).order_by(Lesson.order)
    )).scalars().all() if module_ids else []

    lessons_by_module: dict[int, list] = {}
    for lesson in lessons:
        lessons_by_module.setdefault(lesson.module_id, []).append({
            "id": lesson.id,
            "title": lesson.title,
            "description": lesson.description,
            "module_id": lesson.module_id,
            "duration": lesson.duration,
            "video_url": lesson.video_url,
            "order": lesson.order,
            "lesson_summary": lesson.lesson_summary,
        })

    # Derive thumbnail from first lesson video if no img_link
    import re as _re
    thumbnail = (course.img_link or "").strip() or None
    if not thumbnail and lessons:
        for l in lessons:
            if l.video_url:
                m = _re.search(r'(?:embed/|watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', l.video_url)
                if m:
                    thumbnail = f"https://img.youtube.com/vi/{m[1]}/hqdefault.jpg"
                    break

    return {
        "course": {
            "id": course.id,
            "title": course.title,
            "description": course.description,
            "difficulty": course.difficulty.value if course.difficulty else None,
            "tags": course.tags or [],
            "thumbnail": thumbnail,
            "rating": float(course.rating) if course.rating else None,
        },
        "modules": [
            {
                "id": m.id,
                "title": m.title,
                "description": m.description,
                "course_id": m.course_id,
                "lesson_ids": [l["id"] for l in lessons_by_module.get(m.id, [])],
            }
            for m in modules
        ],
        "lessons": [
            {
                "id": l.id,
                "lesson_id": l.id,
                "title": l.title,
                "description": l.description,
                "module_id": l.module_id,
                "duration": l.duration,
                "video_url": l.video_url,
                "order": l.order,
                "lesson_summary": l.lesson_summary,
            }
            for l in lessons
        ],
    }


async def get_lesson_sections_lightweight(lesson_id: int) -> list[dict]:
    db = get_mongo_db()
    cursor = db.sections.find(
        {"lesson_id": lesson_id},
        {"title": 1, "lesson_id": 1, "index": 1, "start_seconds": 1, "end_seconds": 1},
    ).sort("index", 1)
    return [_serialize_mongo(doc) async for doc in cursor]


async def get_sections_for_lesson(lesson_id: int) -> list[dict]:
    """Alias for get_lesson_sections_lightweight."""
    return await get_lesson_sections_lightweight(lesson_id)


async def get_enriched_section(lesson_id: int, section_index: int) -> dict | None:
    """Return enriched teaching data for a section, if available."""
    db = get_mongo_db()
    doc = await db.enriched_sections.find_one(
        {"lesson_id": lesson_id, "section_index": section_index}
    )
    return _serialize_mongo(doc) if doc else None


async def get_section_full(lesson_id: int, section_index: int) -> dict | None:
    db = get_mongo_db()
    doc = await db.sections.find_one({"lesson_id": lesson_id, "index": section_index})
    return _serialize_mongo(doc) if doc else None


async def get_course_concepts(course_id: int) -> list[dict]:
    db = get_mongo_db()
    cursor = db.concepts.find({"course_id": course_id})
    return [_serialize_mongo(doc) async for doc in cursor]


async def get_learning_tools_for_course(course_id: int) -> list[dict]:
    db = get_mongo_db()
    cursor = db.learning_tools.find({"course_id": course_id})
    return [_serialize_mongo(doc) async for doc in cursor]


async def search_content(query: str, limit: int = 10) -> list[dict]:
    """Semantic + text search across lessons and courses.

    Uses MongoDB Atlas Vector Search if available, falls back to text regex.
    Returns a merged, deduplicated list of results.
    """
    import logging
    log = logging.getLogger(__name__)
    db = get_mongo_db()
    col = db.search_index
    results = []

    # Try vector search first
    try:
        from app.services.content.embedding_service import generate_embedding
        embedding = await generate_embedding(query)

        if embedding:
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "content_search_vector",
                        "path": "embedding",
                        "queryVector": embedding,
                        "numCandidates": limit * 5,
                        "limit": limit,
                    }
                },
                {
                    "$project": {
                        "_id": 1, "type": 1, "courseId": 1, "lessonId": 1,
                        "title": 1, "description": 1, "metadata": 1,
                        "score": {"$meta": "vectorSearchScore"},
                    }
                },
            ]
            async for doc in col.aggregate(pipeline):
                results.append(_serialize_mongo(doc))

            if results:
                log.info("Vector search for '%s': %d results", query[:40], len(results))
                # Re-rank with LLM to filter irrelevant results
                if len(results) > 1:
                    results = await _rerank_with_haiku(query, results)
                return results

    except Exception as e:
        log.warning("Vector search failed (falling back to text): %s", e)

    # Fallback: text regex search (match any word in the query)
    import re
    words = [w for w in query.strip().split() if len(w) >= 2]
    if not words:
        return []
    word_patterns = [{"$or": [
        {"title": {"$regex": re.escape(w), "$options": "i"}},
        {"searchText": {"$regex": re.escape(w), "$options": "i"}},
    ]} for w in words[:5]]  # limit to 5 words

    # Use $or — match any word for broader results
    all_conditions = []
    for wp in word_patterns:
        all_conditions.extend(wp["$or"])
    cursor = col.find(
        {"$or": all_conditions},
        {"embedding": 0, "searchText": 0},
    ).limit(limit)

    async for doc in cursor:
        results.append(_serialize_mongo(doc))

    log.info("Text search for '%s': %d results", query[:40], len(results))

    # Re-rank with Haiku for relevance
    if results and len(results) > 1:
        results = await _rerank_with_haiku(query, results)

    return results


async def _rerank_with_haiku(query: str, results: list[dict]) -> list[dict]:
    """Use Haiku to re-rank search results by relevance to the query."""
    import json
    import logging
    log = logging.getLogger(__name__)

    try:
        from app.core.config import settings
        import httpx

        # Build candidate list for Haiku
        candidates = []
        for i, r in enumerate(results):
            candidates.append(f"{i}. [{r['type']}] {r['title']}" + (f" — {r.get('description', '')[:100]}" if r.get('description') else ""))

        prompt = f"""Search query: "{query}"

TASK: Filter and rank these results. BE STRICT:
- ONLY include results that genuinely match what the user is looking for
- DROP anything that just happens to share a word but isn't about the topic
- If the query is about a topic we don't have courses for (e.g. "cooking", "basketball", "machine learning"), return NONE
- A result about "wave functions" is NOT relevant to "machine learning" even if it contains the word "learning"
- Rank the remaining results by how directly they address the query

Results:
{chr(10).join(candidates)}

Return ONLY comma-separated numbers of relevant results (most relevant first).
If NOTHING is relevant, return "NONE".
Response:"""

        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            return results

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": settings.MODEL_NANO,
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

            if resp.status_code != 200:
                log.warning("Haiku rerank failed: %d", resp.status_code)
                return results

            text = resp.json()["choices"][0]["message"]["content"].strip()

            # Handle "NONE" — no relevant results
            if text.upper().startswith("NONE"):
                log.info("Reranker filtered ALL results for '%s'", query[:30])
                return []

            # Parse indices
            indices = []
            for part in text.replace(" ", "").split(","):
                try:
                    idx = int(part.strip())
                    if 0 <= idx < len(results):
                        indices.append(idx)
                except ValueError:
                    continue

            if indices:
                reranked = [results[i] for i in indices if i < len(results)]
                log.info("Haiku reranked '%s': %d → %d results", query[:30], len(results), len(reranked))
                return reranked

    except Exception as e:
        log.warning("Haiku rerank error: %s", e)

    return results


async def get_learning_tool_by_id(tool_id: str) -> dict | None:
    db = get_mongo_db()
    try:
        doc = await db.learning_tools.find_one({"_id": ObjectId(tool_id)})
    except (InvalidId, TypeError):
        doc = await db.learning_tools.find_one({"id": tool_id})
    return _serialize_mongo(doc) if doc else None
