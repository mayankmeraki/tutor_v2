#!/usr/bin/env python3
"""Build search index — generates vector embeddings for lessons and courses.

Standalone script that connects to PostgreSQL and MongoDB directly,
builds searchable text for each lesson and course, generates embeddings
via OpenRouter, and upserts to the `capacity.search_index` collection.

Usage:
    # Index a single course
    python -m scripts.build_search_index --course-id 2

    # Index all courses
    python -m scripts.build_search_index --all

    # Preview without writing
    python -m scripts.build_search_index --all --dry-run

    # Force re-index existing entries
    python -m scripts.build_search_index --all --force

Requires (from .env):
    OPENROUTER_API_KEY — for embedding generation
    MONGODB_URI        — MongoDB connection string
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME — PostgreSQL
"""

import argparse
import asyncio
import logging
import math
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env
from pathlib import Path
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

import certifi
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("search-index")

# Embedding config
EMBEDDING_MODEL = "openai/text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
OPENROUTER_URL = "https://openrouter.ai/api/v1/embeddings"
BATCH_SIZE = 20  # embeddings per API call


async def generate_embeddings(texts: list[str]) -> list[list[float] | None]:
    """Generate embeddings for a batch of texts via OpenRouter."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        log.error("No OPENROUTER_API_KEY set")
        return [None] * len(texts)

    clean = [t.strip()[:8000] for t in texts]
    results = []

    for i in range(0, len(clean), BATCH_SIZE):
        batch = clean[i:i + BATCH_SIZE]
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    OPENROUTER_URL,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": EMBEDDING_MODEL, "input": batch},
                )
                if resp.status_code != 200:
                    log.error("Embedding API error %d: %s", resp.status_code, resp.text[:200])
                    results.extend([None] * len(batch))
                    continue
                data = resp.json()
                results.extend([item["embedding"] for item in data["data"]])
        except Exception as e:
            log.error("Embedding batch failed: %s", e)
            results.extend([None] * len(batch))

        if i + BATCH_SIZE < len(clean):
            await asyncio.sleep(0.5)  # rate limit

    return results


def extract_yt_thumbnail(video_url: str) -> str:
    """Extract YouTube thumbnail URL from video URL."""
    if not video_url:
        return ""
    import re
    m = re.search(r'(?:youtu\.be/|v=|/embed/)([A-Za-z0-9_-]{11})', video_url)
    return f"https://img.youtube.com/vi/{m.group(1)}/mqdefault.jpg" if m else ""


async def fetch_courses(pg_pool, course_id: int | None = None):
    """Fetch courses with modules and lessons from PostgreSQL."""
    where = f"WHERE c.id = {course_id}" if course_id else "WHERE c.is_published = true OR c.id IS NOT NULL"

    courses_sql = f"""
        SELECT c.id, c.title, c.description, c.difficulty, c.rating,
               c.img_link, c.preview_video, c.course_summary,
               c.learning_outcomes, c.tags
        FROM course c {where}
        ORDER BY c.id
    """
    courses = await pg_pool.fetch(courses_sql)

    result = []
    for c in courses:
        cid = c["id"]
        if c["title"] == "test-course":
            continue

        modules = await pg_pool.fetch(
            "SELECT id, title, description FROM module WHERE course_id = $1 ORDER BY id", cid
        )
        module_ids = [m["id"] for m in modules]

        lessons = []
        if module_ids:
            lessons = await pg_pool.fetch(
                """SELECT l.id, l.title, l.description, l.module_id, l.duration,
                          l.video_url, l.\"order\", l.lesson_summary, l.lesson_summary_keywords
                   FROM lesson l WHERE l.module_id = ANY($1::int[])
                   ORDER BY l.module_id, l.\"order\"""",
                module_ids,
            )

        result.append({
            "course": dict(c),
            "modules": [dict(m) for m in modules],
            "lessons": [dict(l) for l in lessons],
        })

    return result


async def fetch_sections(mongo_db, lesson_id: int):
    """Fetch section data from MongoDB for a lesson."""
    cursor = mongo_db.sections.find(
        {"lesson_id": lesson_id},
        {"title": 1, "key_points": 1, "concepts": 1, "formulas": 1},
    )
    return [doc async for doc in cursor]


async def build_lesson_search_text(lesson: dict, sections: list[dict], module_title: str) -> str:
    """Build concatenated search text for a lesson."""
    parts = [
        lesson["title"] or "",
        lesson.get("description") or "",
        lesson.get("lesson_summary") or "",
        f"Module: {module_title}" if module_title else "",
    ]

    # Add section data
    for sec in sections:
        parts.append(sec.get("title", ""))
        for kp in sec.get("key_points", []) or []:
            parts.append(kp)
        for concept in sec.get("concepts", []) or []:
            parts.append(concept)
        for formula in sec.get("formulas", []) or []:
            parts.append(formula)

    # Add keywords
    for kw in lesson.get("lesson_summary_keywords") or []:
        parts.append(kw)

    return " ".join(p for p in parts if p).strip()


def build_course_search_text(course_data: dict) -> str:
    """Build concatenated search text for a course."""
    c = course_data["course"]
    parts = [
        c["title"] or "",
        c.get("description") or "",
        c.get("course_summary") or "",
    ]

    for outcome in c.get("learning_outcomes") or []:
        parts.append(outcome)
    for tag in c.get("tags") or []:
        parts.append(tag)

    for mod in course_data["modules"]:
        parts.append(mod["title"] or "")
    for les in course_data["lessons"]:
        parts.append(les["title"] or "")

    return " ".join(p for p in parts if p).strip()


async def main():
    parser = argparse.ArgumentParser(description="Build search index with vector embeddings")
    parser.add_argument("--course-id", type=int, help="Index a specific course")
    parser.add_argument("--all", action="store_true", help="Index all courses")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--force", action="store_true", help="Re-index existing entries")
    args = parser.parse_args()

    if not args.course_id and not args.all:
        parser.error("Specify --course-id N or --all")

    # Connect to PostgreSQL
    pg_pool = await asyncpg.create_pool(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5433")),
        user=os.environ.get("DB_USER", "capacity_service_user"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "capacity"),
        min_size=1, max_size=3,
    )

    # Connect to MongoDB
    mongo_client = AsyncIOMotorClient(
        os.environ.get("MONGODB_URI"),
        tlsCAFile=certifi.where(),
    )
    mongo_db = mongo_client.capacity
    search_col = mongo_db.search_index

    log.info("Connected to PostgreSQL and MongoDB")

    # Fetch courses
    courses = await fetch_courses(pg_pool, args.course_id)
    log.info("Found %d course(s) to index", len(courses))

    docs_to_index = []
    texts_to_embed = []

    for course_data in courses:
        c = course_data["course"]
        cid = c["id"]
        module_map = {m["id"]: m["title"] for m in course_data["modules"]}

        # Build course document
        course_doc_id = f"course:{cid}"
        if not args.force:
            existing = await search_col.find_one({"_id": course_doc_id})
            if existing:
                log.info("  Skipping course %d (already indexed, use --force)", cid)
            else:
                course_text = build_course_search_text(course_data)
                course_thumb = c.get("img_link") or ""
                if not course_thumb and c.get("preview_video"):
                    course_thumb = extract_yt_thumbnail(c["preview_video"])

                docs_to_index.append({
                    "_id": course_doc_id,
                    "type": "course",
                    "courseId": cid,
                    "lessonId": None,
                    "title": c["title"],
                    "description": c.get("description") or "",
                    "searchText": course_text,
                    "metadata": {
                        "difficulty": c.get("difficulty"),
                        "rating": float(c["rating"]) if c.get("rating") else None,
                        "thumbnailUrl": course_thumb,
                        "lessonCount": len(course_data["lessons"]),
                        "moduleCount": len(course_data["modules"]),
                    },
                })
                texts_to_embed.append(course_text)
        else:
            course_text = build_course_search_text(course_data)
            course_thumb = c.get("img_link") or ""
            if not course_thumb and c.get("preview_video"):
                course_thumb = extract_yt_thumbnail(c["preview_video"])

            docs_to_index.append({
                "_id": course_doc_id,
                "type": "course",
                "courseId": cid,
                "lessonId": None,
                "title": c["title"],
                "description": c.get("description") or "",
                "searchText": course_text,
                "metadata": {
                    "difficulty": c.get("difficulty"),
                    "rating": float(c["rating"]) if c.get("rating") else None,
                    "thumbnailUrl": course_thumb,
                    "lessonCount": len(course_data["lessons"]),
                    "moduleCount": len(course_data["modules"]),
                },
            })
            texts_to_embed.append(course_text)

        # Build lesson documents
        for les in course_data["lessons"]:
            lid = les["id"]
            doc_id = f"lesson:{cid}:{lid}"

            if not args.force:
                existing = await search_col.find_one({"_id": doc_id})
                if existing:
                    continue

            sections = await fetch_sections(mongo_db, lid)
            module_title = module_map.get(les["module_id"], "")
            search_text = await build_lesson_search_text(les, sections, module_title)

            thumb = extract_yt_thumbnail(les.get("video_url") or "")
            dur_min = math.floor(les["duration"] / 60) if les.get("duration") else None

            # Collect concepts from sections
            all_concepts = []
            for sec in sections:
                all_concepts.extend(sec.get("concepts") or [])

            docs_to_index.append({
                "_id": doc_id,
                "type": "lesson",
                "courseId": cid,
                "lessonId": lid,
                "title": les["title"],
                "description": les.get("description") or "",
                "searchText": search_text,
                "metadata": {
                    "moduleTitle": module_title,
                    "duration": les.get("duration"),
                    "durationMin": dur_min,
                    "videoUrl": les.get("video_url") or "",
                    "thumbnailUrl": thumb,
                    "order": les.get("order"),
                    "concepts": list(set(all_concepts))[:20],
                    "courseTitle": c["title"],
                },
            })
            texts_to_embed.append(search_text)

        log.info("  Course %d (%s): %d lessons to index", cid, c["title"], len(course_data["lessons"]))

    log.info("Total documents to index: %d", len(docs_to_index))

    if args.dry_run:
        for doc in docs_to_index:
            log.info("  [DRY RUN] %s: %s (text: %d chars)", doc["_id"], doc["title"], len(doc["searchText"]))
        log.info("Dry run complete — no data written")
        await pg_pool.close()
        mongo_client.close()
        return

    if not docs_to_index:
        log.info("Nothing to index")
        await pg_pool.close()
        mongo_client.close()
        return

    # Generate embeddings
    log.info("Generating embeddings for %d texts...", len(texts_to_embed))
    t0 = time.monotonic()
    embeddings = await generate_embeddings(texts_to_embed)
    elapsed = time.monotonic() - t0
    ok_count = sum(1 for e in embeddings if e is not None)
    log.info("Embeddings: %d/%d successful (%.1fs)", ok_count, len(embeddings), elapsed)

    # Upsert to MongoDB
    now = datetime.now(timezone.utc)
    upserted = 0
    for i, doc in enumerate(docs_to_index):
        emb = embeddings[i] if i < len(embeddings) else None
        if emb is None:
            log.warning("  Skipping %s — no embedding", doc["_id"])
            continue

        doc["embedding"] = emb
        doc["embeddingModel"] = EMBEDDING_MODEL
        doc["indexedAt"] = now

        await search_col.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        upserted += 1

    log.info("Upserted %d documents to search_index", upserted)

    # Create text index for fallback search
    try:
        await search_col.create_index([("title", "text"), ("searchText", "text")])
        log.info("Text index created/verified")
    except Exception as e:
        log.warning("Text index creation: %s", e)

    await pg_pool.close()
    mongo_client.close()
    log.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
