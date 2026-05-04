"""Test collection synthesis pipeline.

Connects to MongoDB (myprofessor database), picks a collection with resources,
runs synthesize_collection(), and verifies the result.

Usage:
    # From backend/ directory:
    python -m pytest tests/test_synthesis.py -v -s

    # Or directly:
    python tests/test_synthesis.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

# Ensure repo root is on path so `byo` package resolves
_here = os.path.dirname(os.path.abspath(__file__))
_backend = os.path.dirname(_here)
_repo_root = os.path.dirname(_backend)
for p in (_backend, _repo_root):
    if p not in sys.path:
        sys.path.insert(0, p)

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_backend, ".env"), override=False)
except ImportError:
    pass


EXPECTED_FIELDS = {"overview", "resources", "topic_index", "question_index", "suggested_path"}


async def _find_test_collection():
    """Find a collection with ready resources to test against."""
    from app.core.mongodb import get_mongo_db
    db = get_mongo_db()

    # Find collections with ready resources
    async for col in db.collections.find(
        {"status": {"$in": ["ready", "partial"]}},
        {"collection_id": 1, "user_id": 1, "title": 1, "status": 1,
         "stats": 1, "synthesis": 1},
    ).sort("updated_at", -1).limit(10):
        cid = col["collection_id"]
        uid = col["user_id"]

        # Count ready resources
        ready = await db.byo_resources.count_documents(
            {"collection_id": cid, "user_id": uid, "status": "ready"}
        )
        if ready > 0:
            return {
                "collection_id": cid,
                "user_id": uid,
                "title": col.get("title", "untitled"),
                "ready_resources": ready,
                "has_existing_synthesis": bool(col.get("synthesis")),
            }

    return None


async def _run_synthesis_test():
    """Main test runner."""
    print("=" * 60)
    print("Collection Synthesis Pipeline Test")
    print("=" * 60)

    # Step 1: Find a test collection
    print("\n[1] Looking for a test collection...")
    info = await _find_test_collection()
    if not info:
        print("   No collection with ready resources found. Skipping.")
        return False

    print(f"   Collection: {info['title']}")
    print(f"   ID: {info['collection_id']}")
    print(f"   User: {info['user_id']}")
    print(f"   Ready resources: {info['ready_resources']}")
    print(f"   Has existing synthesis: {info['has_existing_synthesis']}")

    # Step 2: Clear existing synthesis if present (so we can test fresh)
    if info["has_existing_synthesis"]:
        print("\n[2] Clearing existing synthesis for fresh test...")
        from app.core.mongodb import get_mongo_db
        db = get_mongo_db()
        await db.collections.update_one(
            {"collection_id": info["collection_id"]},
            {"$unset": {"synthesis": 1}},
        )
        print("   Cleared.")
    else:
        print("\n[2] No existing synthesis — running fresh.")

    # Step 3: Run synthesis
    print("\n[3] Running synthesize_collection()...")
    from byo.processing.synthesis import synthesize_collection
    result = await synthesize_collection(info["collection_id"], info["user_id"])

    if not result:
        print("   FAILED: synthesize_collection returned empty dict")
        return False

    # Step 4: Print the result
    print("\n[4] Synthesis result:")
    print("-" * 40)
    print(json.dumps(result, indent=2, default=str)[:3000])
    if len(json.dumps(result, default=str)) > 3000:
        print("   ... (truncated)")
    print("-" * 40)

    # Step 5: Verify all expected fields
    print("\n[5] Verifying fields...")
    missing = EXPECTED_FIELDS - set(result.keys())
    if missing:
        print(f"   MISSING fields: {missing}")
        return False

    checks = {
        "overview": isinstance(result.get("overview"), str) and len(result["overview"]) > 0,
        "resources": isinstance(result.get("resources"), list),
        "topic_index": isinstance(result.get("topic_index"), dict),
        "question_index": isinstance(result.get("question_index"), list),
        "suggested_path": isinstance(result.get("suggested_path"), list),
        "_meta": isinstance(result.get("_meta"), dict),
    }

    all_pass = True
    for field, ok in checks.items():
        status = "PASS" if ok else "FAIL"
        print(f"   {field}: {status}")
        if not ok:
            all_pass = False

    # Step 6: Verify it was stored in MongoDB
    print("\n[6] Verifying MongoDB storage...")
    from app.core.mongodb import get_mongo_db
    db = get_mongo_db()
    stored = await db.collections.find_one(
        {"collection_id": info["collection_id"]},
        {"synthesis": 1},
    )
    has_stored = bool((stored or {}).get("synthesis"))
    print(f"   Stored in MongoDB: {'PASS' if has_stored else 'FAIL'}")
    if not has_stored:
        all_pass = False

    # Step 7: Test format_synthesis_for_prompt
    print("\n[7] Testing format_synthesis_for_prompt()...")
    from byo.processing.synthesis import format_synthesis_for_prompt
    formatted = format_synthesis_for_prompt(result, info["title"])
    if formatted and "[COLLECTION --" in formatted:
        print(f"   Formatted output: {len(formatted)} chars")
        print(f"   Starts with: {formatted[:100]}...")
        print("   PASS")
    else:
        print("   FAIL: format_synthesis_for_prompt returned empty or wrong format")
        all_pass = False

    print("\n" + "=" * 60)
    print(f"RESULT: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
    print("=" * 60)
    return all_pass


# ── pytest entry point ────────────────────────────────────────────────

def test_synthesis_pipeline():
    """pytest-compatible test. Requires live MongoDB + OpenRouter."""
    import pytest
    if not os.environ.get("OPENROUTER_API_KEY") and not os.environ.get("RUN_LIVE_TESTS"):
        pytest.skip("Set OPENROUTER_API_KEY or RUN_LIVE_TESTS=1 to run live synthesis test")
    result = asyncio.get_event_loop().run_until_complete(_run_synthesis_test())
    assert result, "Synthesis pipeline test failed"


# ── Direct run ────────────────────────────────────────────────────────

if __name__ == "__main__":
    ok = asyncio.run(_run_synthesis_test())
    sys.exit(0 if ok else 1)
