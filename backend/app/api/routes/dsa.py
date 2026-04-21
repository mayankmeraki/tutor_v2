"""DSA & System Design problem API — gracefully degrades when MongoDB is unavailable."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import os
import logging

router = APIRouter(prefix="/api/v1", tags=["dsa"])
log = logging.getLogger("dsa.api")

_db_cache = None


def _get_db():
    global _db_cache
    if _db_cache is not None:
        return _db_cache
    try:
        from app.core.config import settings
        uri = getattr(settings, 'MONGODB_URI', None) or os.environ.get('MONGODB_URI', '')
        if not uri:
            return None
        from pymongo import MongoClient
        import certifi
        client = MongoClient(
            uri,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
        )
        client.admin.command("ping")
        _db_cache = client["tutor_v2"]
        return _db_cache
    except Exception as e:
        log.warning("MongoDB unavailable for DSA API: %s", e)
        return None


def _safe_find(coll_name, query=None, sort=None, skip=0, limit=50):
    db = _get_db()
    if db is None:
        return [], 0
    try:
        coll = db[coll_name]
        cursor = coll.find(query or {}, {"_id": 0})
        if sort:
            cursor = cursor.sort(*sort)
        cursor = cursor.skip(skip).limit(limit)
        items = list(cursor)
        total = coll.count_documents(query or {})
        return items, total
    except Exception as e:
        log.warning("Query %s failed: %s", coll_name, e)
        return [], 0


def _safe_find_one(coll_name, query):
    db = _get_db()
    if db is None:
        return None
    try:
        return db[coll_name].find_one(query, {"_id": 0})
    except Exception as e:
        log.warning("Find one %s failed: %s", coll_name, e)
        return None


def _safe_aggregate(coll_name, pipeline):
    db = _get_db()
    if db is None:
        return []
    try:
        return list(db[coll_name].aggregate(pipeline))
    except Exception as e:
        log.warning("Aggregate %s failed: %s", coll_name, e)
        return []


@router.get("/dsa/problems")
def list_dsa_problems(
    difficulty: Optional[str] = None,
    topic: Optional[str] = None,
    list_name: Optional[str] = Query(None, alias="list"),
    company: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
):
    query = {}
    if difficulty:
        query["difficulty"] = difficulty.lower()
    if topic:
        query["topics"] = {"$in": [topic.lower()]}
    if list_name:
        query["lists"] = {"$in": [list_name.lower()]}
    if company:
        query["companies"] = {"$in": [company.lower()]}
    problems, total = _safe_find("dsa_problems", query, sort=("num", 1), skip=skip, limit=limit)
    return {"problems": problems, "total": total}


@router.get("/dsa/problems/{slug}")
def get_dsa_problem(slug: str):
    problem = _safe_find_one("dsa_problems", {"slug": slug})
    if not problem:
        raise HTTPException(status_code=404, detail=f"Problem '{slug}' not found")
    return problem


@router.get("/dsa/topics")
def list_topics():
    results = _safe_aggregate("dsa_problems", [
        {"$unwind": "$topics"},
        {"$group": {"_id": "$topics", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ])
    return [{"topic": t["_id"], "count": t["count"]} for t in results]


@router.get("/dsa/lists")
def list_curated_lists():
    results = _safe_aggregate("dsa_problems", [
        {"$unwind": "$lists"},
        {"$group": {"_id": "$lists", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ])
    return [{"name": l["_id"], "count": l["count"]} for l in results]


@router.get("/sd/problems")
def list_sd_problems(
    difficulty: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
):
    query = {}
    if difficulty:
        query["difficulty"] = difficulty.lower()
    problems, total = _safe_find("sd_problems", query, sort=("name", 1), skip=skip, limit=limit)
    return {"problems": problems, "total": total}


@router.get("/sd/problems/{slug}")
def get_sd_problem(slug: str):
    problem = _safe_find_one("sd_problems", {"slug": slug})
    if not problem:
        raise HTTPException(status_code=404, detail=f"SD problem '{slug}' not found")
    return problem


@router.get("/dsa/random")
def get_random_problem(
    difficulty: Optional[str] = None,
    topic: Optional[str] = None,
    type: str = "dsa",
):
    import random
    coll = "sd_problems" if type == "sd" else "dsa_problems"
    query = {}
    if difficulty:
        query["difficulty"] = difficulty.lower()
    if topic:
        key = "concepts" if type == "sd" else "topics"
        query[key] = {"$in": [topic.lower()]}
    candidates, _ = _safe_find(coll, query, limit=200)
    if not candidates:
        raise HTTPException(status_code=404, detail="No problems match filters")
    return random.choice(candidates)


@router.post("/mock/start")
def start_mock_session(
    company: str = "generic",
    difficulty: str = "medium",
    type: str = "dsa",
    slug: Optional[str] = None,
    timer_minutes: int = 45,
):
    import random
    coll = "sd_problems" if type == "sd" else "dsa_problems"

    if slug:
        problem = _safe_find_one(coll, {"slug": slug})
        if not problem:
            raise HTTPException(status_code=404, detail=f"Problem '{slug}' not found")
    else:
        query = {"difficulty": difficulty.lower()} if difficulty else {}
        candidates, _ = _safe_find(coll, query, limit=200)
        if not candidates:
            raise HTTPException(status_code=404, detail="No problems match difficulty")
        problem = random.choice(candidates)

    return {
        "problem": problem,
        "config": {
            "company": company,
            "type": type,
            "timer_minutes": timer_minutes,
            "difficulty": difficulty,
        },
    }


@router.get("/dsa/teaching-plan/{topic}")
def get_teaching_plan(topic: str):
    """Get the teaching plan for a DSA topic or SD concept."""
    # Try MongoDB first
    plan = _safe_find_one("teaching_plans", {"slug": topic})
    if plan:
        return plan
    # Fallback to Python file if MongoDB empty
    try:
        from byo.scripts.teaching_plans import DSA_TEACHING_PLANS, SD_TEACHING_PLANS
        plan = DSA_TEACHING_PLANS.get(topic) or SD_TEACHING_PLANS.get(topic)
        if plan:
            return plan
    except ImportError:
        pass
    raise HTTPException(status_code=404, detail=f"No teaching plan for '{topic}'")


@router.get("/dsa/progress")
def get_dsa_progress(user_id: str = Query(...)):
    db = _get_db()
    if db is None:
        return {"solved_count": 0, "solved_slugs": [], "topic_stats": {}, "total_notes": 0}
    try:
        from app.core.config import settings
        from pymongo import MongoClient
        import certifi
        tutor_db = MongoClient(
            settings.MONGODB_URI,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=3000,
        )["tutor_v2"]
        notes = list(tutor_db.knowledge_notes.find(
            {"user_id": user_id, "tags": {"$in": [
                "mock_interview", "arrays", "trees", "graphs", "dynamic_programming",
                "hash_map_lookup", "sliding_window", "two_pointers", "binary_search",
                "stack", "linked_list", "backtracking", "greedy",
            ]}},
            {"_id": 0}
        ))
    except Exception:
        return {"solved_count": 0, "solved_slugs": [], "topic_stats": {}, "total_notes": 0}

    topic_stats = {}
    solved_slugs = set()
    for note in notes:
        for tag in note.get("tags", []):
            if tag not in topic_stats:
                topic_stats[tag] = {"seen": 0, "mastered": 0, "struggling": 0}
            topic_stats[tag]["seen"] += 1
            blooms = note.get("blooms", "")
            if blooms in ("apply", "analyze", "evaluate", "create"):
                topic_stats[tag]["mastered"] += 1
            elif blooms in ("remember", "understand"):
                topic_stats[tag]["struggling"] += 1
        for tag in note.get("tags", []):
            if "_" in tag and tag not in (
                "mock_interview", "hash_map_lookup", "dynamic_programming",
                "sliding_window", "two_pointers", "binary_search",
            ):
                solved_slugs.add(tag)

    return {
        "solved_count": len(solved_slugs),
        "solved_slugs": list(solved_slugs),
        "topic_stats": topic_stats,
        "total_notes": len(notes),
    }


@router.post("/classify")
async def classify_session_intent(body: dict):
    """Classify student intent and return a session blueprint."""
    from app.agents.blueprint import classify_intent
    text = body.get("text", "")
    bp = await classify_intent(
        text=text,
        explicit_mode=body.get("mode"),
        explicit_interaction=body.get("interaction"),
        explicit_slug=body.get("slug"),
        explicit_company=body.get("company"),
    )
    return bp.to_dict()
