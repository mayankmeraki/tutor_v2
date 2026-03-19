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

    return {
        "course": {
            "id": course.id,
            "title": course.title,
            "description": course.description,
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


async def get_learning_tool_by_id(tool_id: str) -> dict | None:
    db = get_mongo_db()
    try:
        doc = await db.learning_tools.find_one({"_id": ObjectId(tool_id)})
    except (InvalidId, TypeError):
        doc = await db.learning_tools.find_one({"id": tool_id})
    return _serialize_mongo(doc) if doc else None
