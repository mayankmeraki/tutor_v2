"""Live grounding tests — test every tool against real student intents.

Run: cd backend && python tests/test_grounding_live.py
Output: tests/output_grounding_results.txt

Tests each tool with multiple natural language queries to see
what grounding content the tutor actually gets.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "output_grounding_results.txt")
output_lines = []

def log(text=""):
    output_lines.append(text)
    print(text)

def section(title):
    log(f"\n{'='*80}")
    log(f"  {title}")
    log(f"{'='*80}")

def subsection(title):
    log(f"\n  {'─'*60}")
    log(f"  {title}")
    log(f"  {'─'*60}")

def result(tool, query, output, elapsed_ms=0):
    log(f"\n  [{tool}] query: \"{query}\" ({elapsed_ms}ms)")
    if output is None:
        log("    → (None)")
    elif isinstance(output, str):
        for line in output[:2000].split('\n'):
            log(f"    {line}")
        if len(output) > 2000:
            log(f"    ... ({len(output)} total chars)")
    elif isinstance(output, list):
        log(f"    → {len(output)} results:")
        for item in output[:5]:
            if isinstance(item, dict):
                log(f"    - {item.get('title', item.get('_id', '?'))} (score={item.get('score', '?')})")
            else:
                log(f"    - {str(item)[:200]}")
    else:
        log(f"    → {str(output)[:2000]}")

async def timed_call(fn, *args, **kwargs):
    t0 = time.time()
    try:
        r = await fn(*args, **kwargs)
        return r, round((time.time() - t0) * 1000)
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}", round((time.time() - t0) * 1000)


# ═══════════════════════════════════════════════════════════════

STUDENT_INTENTS = [
    "teach me quantum entanglement",
    "I want to understand superposition",
    "explain the double slit experiment",
    "what is Schrodinger's equation",
    "how does quantum teleportation work",
    "Bell's theorem and hidden variables",
]

async def main():
    log(f"Grounding Tool Test Results — {datetime.now().isoformat()}")
    log(f"Testing {len(STUDENT_INTENTS)} student intents against all grounding tools\n")

    # ── 1. content_search ─────────────────────────────────────
    section("1. CONTENT SEARCH (content_service.search_content)")
    log("  How: MongoDB text/vector search across course content index")
    log("  Returns: matching courses/lessons with scores")

    try:
        from app.services.content.content_service import search_content
        for intent in STUDENT_INTENTS:
            r, ms = await timed_call(search_content, intent, limit=5)
            result("content_search", intent, r, ms)
    except Exception as e:
        log(f"  IMPORT ERROR: {e}")

    # ── 2. resolve_content ────────────────────────────────────
    section("2. CONTENT RESOLVER (content_resolver.resolve_content)")
    log("  How: Maps student intent → course/lesson matches via vector search")
    log("  Returns: matched courses, lessons, gaps")

    try:
        from app.services.content.content_resolver import resolve_content, format_content_brief
        for intent in STUDENT_INTENTS:
            r, ms = await timed_call(resolve_content, intent)
            result("resolve_content", intent, json.dumps(r, indent=2, default=str) if isinstance(r, dict) else r, ms)
            if isinstance(r, dict):
                brief = format_content_brief(r)
                log(f"\n    Formatted brief:")
                for line in brief.split('\n'):
                    log(f"      {line}")
    except Exception as e:
        log(f"  IMPORT ERROR: {e}")

    # ── 3. content_map ────────────────────────────────────────
    section("3. CONTENT MAP (course_adapter.content_map)")
    log("  How: Returns full course hierarchy — what the tutor sees as structure")

    try:
        from app.services.content.providers import create_adapter
        # Try course IDs 1, 2
        for cid in [1, 2]:
            try:
                adapter = create_adapter(cid, db_session=None)
                r, ms = await timed_call(adapter.content_map)
                result("content_map", f"course_id={cid}", r, ms)
            except Exception as e:
                result("content_map", f"course_id={cid}", f"ERROR: {e}", 0)
    except Exception as e:
        log(f"  IMPORT ERROR: {e}")

    # ── 4. get_section_content ────────────────────────────────
    section("4. GET SECTION CONTENT (handlers.get_section_content)")
    log("  How: Fetches full section with transcript, key points, concepts")
    log("  Needs: lesson_id (int) + section_index (int)")

    try:
        from app.tools.handlers import get_section_content
        # Try various lesson/section combos
        test_sections = [(1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (5, 0), (10, 0)]
        for lid, sidx in test_sections:
            r, ms = await timed_call(get_section_content, lid, sidx)
            result("get_section_content", f"lesson={lid}, section={sidx}", r, ms)
    except Exception as e:
        log(f"  IMPORT ERROR: {e}")

    # ── 5. get_section_brief ──────────────────────────────────
    section("5. GET SECTION BRIEF (handlers.get_section_brief)")
    log("  How: Compact brief — title, summary, key pedagogical points")

    try:
        from app.tools.handlers import get_section_brief
        for lid, sidx in [(1, 0), (2, 0), (3, 0), (5, 0)]:
            r, ms = await timed_call(get_section_brief, lid, sidx)
            result("get_section_brief", f"lesson={lid}, section={sidx}", r, ms)
    except Exception as e:
        log(f"  IMPORT ERROR: {e}")

    # ── 6. get_simulation_details ─────────────────────────────
    section("6. SIMULATION DETAILS")
    log("  How: Fetches interactive simulation metadata from MongoDB learning_tools")

    try:
        from app.core.mongodb import get_mongo_db
        from app.tools.handlers import get_simulation_details
        db = get_mongo_db()
        cursor = db.learning_tools.find({}).limit(5)
        sims = await cursor.to_list(length=5)
        if sims:
            for sim in sims:
                sid = str(sim['_id'])
                r, ms = await timed_call(get_simulation_details, sid)
                result("get_simulation_details", f"id={sid}", r, ms)
        else:
            log("  (no simulations in DB)")
    except Exception as e:
        log(f"  ERROR: {e}")

    # ── 7. search_images ──────────────────────────────────────
    section("7. SEARCH IMAGES (Wikimedia Commons)")
    log("  How: Searches Wikimedia Commons API for educational images")

    try:
        from app.tools.search_images import search_images
        image_queries = [
            "quantum entanglement diagram",
            "double slit experiment interference pattern",
            "Schrodinger equation wave function",
            "Bell inequality CHSH",
        ]
        for q in image_queries:
            r, ms = await timed_call(search_images, q, limit=2)
            result("search_images", q, r, ms)
    except Exception as e:
        log(f"  IMPORT ERROR: {e}")

    # ── 8. web_search ─────────────────────────────────────────
    section("8. WEB SEARCH (DuckDuckGo)")
    log("  How: DuckDuckGo instant answer API + HTML fallback")

    try:
        from app.tools.web_search import web_search
        web_queries = [
            "quantum entanglement simple explanation",
            "Bell theorem experiment results",
            "quantum teleportation how it works",
            "EPR paradox Einstein",
        ]
        for q in web_queries:
            r, ms = await timed_call(web_search, q, limit=3)
            result("web_search", q, r, ms)
    except Exception as e:
        log(f"  IMPORT ERROR: {e}")

    # ── 9. query_knowledge ────────────────────────────────────
    section("9. QUERY KNOWLEDGE (student concept notes)")
    log("  How: Vector/text search on student_concept_mastery collection")

    try:
        from app.services.knowledge.knowledge_state import hybrid_search_notes
        knowledge_queries = [
            "superposition understanding",
            "entanglement concepts",
            "measurement collapse",
            "wave function",
        ]
        for q in knowledge_queries:
            r, ms = await timed_call(hybrid_search_notes, 2, "ishita@ishita.com", q, limit=3)
            result("query_knowledge", f"user=ishita, query={q}", r, ms)
    except Exception as e:
        log(f"  IMPORT ERROR: {e}")

    # ── 10. BYO tools ─────────────────────────────────────────
    section("10. BYO TOOLS (student uploaded content)")

    try:
        from app.core.mongodb import get_mongo_db
        from app.tools import execute_tutor_tool
        db = get_mongo_db()
        col = await db.collections.find_one({"status": "complete"})
        if col:
            cid = str(col.get("collection_id", col.get("_id", "")))
            log(f"  Found BYO collection: {cid} — {col.get('title', '?')}")

            r, ms = await timed_call(execute_tutor_tool, "byo_list", {"collection_id": cid})
            result("byo_list", f"collection={cid}", r, ms)

            r, ms = await timed_call(execute_tutor_tool, "byo_read", {"collection_id": cid, "query": "quantum"})
            result("byo_read", f"collection={cid}, query=quantum", r, ms)

            r, ms = await timed_call(execute_tutor_tool, "byo_read", {"collection_id": cid, "chunk_index": 0})
            result("byo_read", f"collection={cid}, chunk_index=0", r, ms)
        else:
            log("  (no BYO collections in DB)")
    except Exception as e:
        log(f"  ERROR: {e}")

    # ── 11. content_read / content_peek via adapter ───────────
    section("11. CONTENT READ/PEEK (via adapter)")
    log("  How: Fetches full content or brief for a given ref")

    try:
        from app.services.content.providers import create_adapter
        adapter = create_adapter(2, db_session=None)  # course 2 = MIT QM

        refs_to_test = ["lesson:1", "lesson:2", "lesson:1:section:0", "lesson:2:section:0"]
        for ref in refs_to_test:
            r, ms = await timed_call(adapter.content_read, ref)
            result("content_read", f"ref={ref}", r, ms)

        for ref in ["lesson:1", "lesson:2"]:
            r, ms = await timed_call(adapter.content_peek, ref)
            result("content_peek", f"ref={ref}", r, ms)
    except Exception as e:
        log(f"  ERROR: {e}")

    # ── 12. DB inventory ──────────────────────────────────────
    section("12. DATABASE INVENTORY")
    log("  What content exists in MongoDB?")

    try:
        from app.core.mongodb import get_mongo_db
        db = get_mongo_db()
        for col_name in ["sections", "enriched_sections", "lessons", "learning_tools", "search_index", "collections", "byo_chunks", "student_concept_mastery"]:
            try:
                count = await db[col_name].count_documents({})
                sample = await db[col_name].find_one({})
                fields = list(sample.keys()) if sample else []
                log(f"  {col_name}: {count} docs, fields: {fields[:10]}")
            except Exception as e:
                log(f"  {col_name}: ERROR — {e}")
    except Exception as e:
        log(f"  DB ERROR: {e}")

    # ── Write output ──────────────────────────────────────────
    section("SUMMARY")
    log(f"  Tests completed at {datetime.now().isoformat()}")
    log(f"  Total intents tested: {len(STUDENT_INTENTS)}")

    with open(OUTPUT_FILE, "w") as f:
        f.write("\n".join(output_lines))
    log(f"\n  Output written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
