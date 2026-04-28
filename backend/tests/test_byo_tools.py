"""End-to-end BYO tool chain tests.

Tests: Qdrant connectivity, content store ops, retrieval service,
tool handlers, prefetch system, and 3-level preload.

Usage: python -m tests.test_byo_tools
"""

import asyncio
import json
import logging
import os
import sys

# Setup
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.chdir(os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv(".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("test_byo_tools")

PASS = 0
FAIL = 0


def ok(label, detail=""):
    global PASS
    PASS += 1
    print(f"  OK  {label}" + (f" — {detail}" if detail else ""))


def fail(label, detail=""):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))


# ─────────────────────────────────────────────────────────────────────
# 1. Qdrant Connectivity
# ─────────────────────────────────────────────────────────────────────

def test_qdrant_connectivity():
    print("\n═══ 1. Qdrant Connectivity ═══")

    url = os.environ.get("QDRANT_URL", "")
    if not url:
        fail("QDRANT_URL", "not set in env")
        return False

    ok("QDRANT_URL", url[:60])

    try:
        from byo.shared.qdrant import get_qdrant_client
        client = get_qdrant_client()
        if client is None:
            fail("get_qdrant_client()", "returned None")
            return False
        ok("get_qdrant_client()", "connected")
    except Exception as e:
        fail("get_qdrant_client()", str(e))
        return False

    # Check collections
    try:
        collections = [c.name for c in client.get_collections().collections]
        ok("get_collections()", f"found {len(collections)}: {collections}")
    except Exception as e:
        fail("get_collections()", str(e))
        return False

    # Check byo_content collection
    if "byo_content" in collections:
        info = client.get_collection("byo_content")
        count = info.points_count
        ok("byo_content collection", f"{count} points")
    else:
        fail("byo_content collection", "does not exist")

    # Check byo_segments (old) — should be deprecated
    if "byo_segments" in collections:
        info = client.get_collection("byo_segments")
        count = info.points_count
        print(f"  WARN byo_segments (OLD) — {count} points (should migrate to byo_content)")

    return True


# ─────────────────────────────────────────────────────────────────────
# 2. Content Store Operations
# ─────────────────────────────────────────────────────────────────────

async def test_content_store():
    print("\n═══ 2. Content Store Operations ═══")

    from byo.shared.store import get_content_store

    store = get_content_store()
    ok("get_content_store()", type(store).__name__)

    # List what's in the store for any user
    from byo.shared.qdrant import get_qdrant_client
    client = get_qdrant_client()
    if not client:
        fail("client", "None")
        return

    # Scroll a few points to see what data exists
    try:
        points = client.scroll(
            collection_name="byo_content",
            limit=5,
            with_payload=True,
            with_vectors=False,
        )[0]

        if not points:
            fail("scroll byo_content", "0 points — collection is empty")
            return

        ok("scroll byo_content", f"{len(points)} sample points")

        # Show user_ids and collection_ids — paired correctly
        combos = {}
        for p in points:
            uid = p.payload.get("user_id", "?")
            cid = p.payload.get("collection_id", "?")
            rname = p.payload.get("resource_name", "?")
            key = (uid, cid)
            if key not in combos:
                combos[key] = set()
            combos[key].add(rname)

        for (uid, cid), resources in combos.items():
            print(f"       user={uid} collection={cid} resources={resources}")

        # Pick the first valid user/collection PAIR
        sample_user, sample_cid = list(combos.keys())[0]
        print(f"       selected: user={sample_user}, collection={sample_cid}")
        return sample_user, sample_cid

    except Exception as e:
        fail("scroll byo_content", str(e))
        return None


# ─────────────────────────────────────────────────────────────────────
# 3. Embedding Service
# ─────────────────────────────────────────────────────────────────────

async def test_embedding():
    print("\n═══ 3. Embedding Service ═══")

    from app.services.content.embedding_service import generate_embedding

    embedding = await generate_embedding("Lorentz transformation special relativity")
    if embedding is None:
        fail("generate_embedding()", "returned None — check OPENROUTER_API_KEY")
        return None

    if len(embedding) != 1536:
        fail("embedding dimensions", f"got {len(embedding)}, expected 1536")
        return None

    ok("generate_embedding()", f"{len(embedding)}d vector, norm={sum(x*x for x in embedding):.3f}")
    return embedding


# ─────────────────────────────────────────────────────────────────────
# 4. Retrieval Service (search, fetch, nearby)
# ─────────────────────────────────────────────────────────────────────

async def test_retrieval_service(user_id: str, collection_id: str):
    print("\n═══ 4. Retrieval Service ═══")

    from byo.retrieval import service as svc

    # Search
    try:
        results = await svc.search(
            "Lorentz transformation special relativity",
            user_id=user_id,
            scope="collection",
            collection_id=collection_id,
            k=3,
            rerank=False,
        )
        if results:
            ok("search()", f"{len(results)} results")
            for r in results[:2]:
                print(f"       score={r.score:.3f} resource={r.resource_name[:40]} content={r.content[:80]}...")
        else:
            fail("search()", "0 results — content not found in Qdrant")
            return
    except Exception as e:
        fail("search()", str(e))
        return

    # Fetch
    chunk_id = results[0].chunk_id
    try:
        hit = await svc.fetch(f"chunk:{chunk_id}", user_id=user_id)
        if hit:
            ok("fetch()", f"chunk_id={chunk_id[:20]} content={len(hit.content)} chars")
        else:
            fail("fetch()", f"chunk:{chunk_id} not found")
    except Exception as e:
        fail("fetch()", str(e))

    # Nearby
    try:
        nearby = await svc.nearby(f"chunk:{chunk_id}", user_id=user_id, window=1)
        ok("nearby()", f"{len(nearby)} chunks around index")
    except Exception as e:
        fail("nearby()", str(e))

    # List contents
    try:
        contents = await svc.list_contents(collection_id, user_id=user_id)
        if contents:
            ok("list_contents()", f"{len(contents)} refs")
        else:
            fail("list_contents()", "0 refs")
    except Exception as e:
        fail("list_contents()", str(e))


# ─────────────────────────────────────────────────────────────────────
# 5. Tool Handlers (the tutor-facing API)
# ─────────────────────────────────────────────────────────────────────

async def test_tool_handlers(user_id: str, collection_id: str):
    print("\n═══ 5. Tool Handlers ═══")

    from app.tools.retrieval import search_tool, fetch_tool, peek_tool, nearby_tool, list_contents_tool

    # Build context_data like the pipeline does
    context_data = {
        "studentProfile": json.dumps({"userEmail": user_id}),
        "sessionContext": json.dumps({"collection_id": collection_id}),
    }

    # search_tool
    result = await search_tool(
        {"query": "reference frames and velocity", "scope": "collection", "k": 3},
        context_data=context_data,
    )
    if "Error" in result or "No results" in result:
        fail("search_tool", result[:200])
    else:
        ok("search_tool", f"{len(result)} chars output")
        # Extract a chunk ref from the result
        import re
        refs = re.findall(r"chunk:(\S+)", result)
        if refs:
            print(f"       found refs: {refs[:3]}")

            # fetch_tool
            result2 = await fetch_tool(
                {"ref": f"chunk:{refs[0]}"},
                context_data=context_data,
            )
            if "Error" in result2:
                fail("fetch_tool", result2[:200])
            else:
                ok("fetch_tool", f"{len(result2)} chars")

            # peek_tool
            result3 = await peek_tool(
                {"ref": f"chunk:{refs[0]}"},
                context_data=context_data,
            )
            if "Error" in result3:
                fail("peek_tool", result3[:200])
            else:
                ok("peek_tool", f"{len(result3)} chars")

            # nearby_tool
            result4 = await nearby_tool(
                {"ref": f"chunk:{refs[0]}", "window": 1},
                context_data=context_data,
            )
            if "Error" in result4:
                fail("nearby_tool", result4[:200])
            else:
                ok("nearby_tool", f"{len(result4)} chars")
        else:
            fail("search_tool refs", "no chunk: refs in search output")

    # list_contents_tool
    result5 = await list_contents_tool(
        {"scope": "collection"},
        context_data=context_data,
    )
    if "Error" in result5:
        fail("list_contents_tool", result5[:200])
    else:
        ok("list_contents_tool", f"{len(result5)} chars")


# ─────────────────────────────────────────────────────────────────────
# 6. execute_tutor_tool dispatcher
# ─────────────────────────────────────────────────────────────────────

async def test_dispatcher(user_id: str, collection_id: str):
    print("\n═══ 6. execute_tutor_tool Dispatcher ═══")

    from app.tools import execute_tutor_tool

    context_data = {
        "studentProfile": json.dumps({"userEmail": user_id}),
        "sessionContext": json.dumps({"collection_id": collection_id}),
    }

    # search
    result = await execute_tutor_tool("search", {"query": "spacetime invariance", "scope": "collection", "k": 2}, context_data=context_data)
    if "Error" not in (result or ""):
        ok("dispatch search", f"{len(result)} chars")
    else:
        fail("dispatch search", str(result)[:200])

    # query_knowledge (should not error anymore)
    result = await execute_tutor_tool("query_knowledge", {"query": "physics understanding"}, context_data=context_data)
    if "Unknown tool" in (result or ""):
        fail("dispatch query_knowledge", "still returns Unknown tool!")
    else:
        ok("dispatch query_knowledge", result[:100] if result else "(empty)")

    # update_student_model (should not error)
    result = await execute_tutor_tool("update_student_model", {"notes": [{"concepts": ["test"], "note": "test"}]}, context_data=context_data)
    if "Unknown tool" in (result or ""):
        fail("dispatch update_student_model", "still returns Unknown tool!")
    else:
        ok("dispatch update_student_model", result[:100] if result else "(empty)")


# ─────────────────────────────────────────────────────────────────────
# 7. MongoDB BYO Resources Check
# ─────────────────────────────────────────────────────────────────────

async def test_mongodb_byo():
    print("\n═══ 7. MongoDB BYO Resources ═══")

    from app.core.mongodb import get_mongo_db
    db = get_mongo_db()

    # Check byo_resources
    count = await db.byo_resources.count_documents({})
    ok("byo_resources", f"{count} documents")

    if count > 0:
        sample = await db.byo_resources.find_one({}, {"original_name": 1, "collection_id": 1, "user_id": 1, "status": 1, "chunk_count": 1, "topics": 1, "toc": 1})
        if sample:
            print(f"       sample: name={sample.get('original_name')}, chunks={sample.get('chunk_count')}, status={sample.get('status')}")
            has_toc = bool(sample.get("toc"))
            has_topics = bool(sample.get("topics"))
            if has_toc:
                ok("toc field", f"{len(sample['toc'])} entries")
            else:
                fail("toc field", "missing — Level 2 preload won't work")
            if has_topics:
                ok("topics field", f"{len(sample['topics'])} topics")
            else:
                fail("topics field", "missing — topic-based search won't work")

    # Check byo_jobs
    job_count = await db.byo_jobs.count_documents({})
    ok("byo_jobs", f"{job_count} jobs")

    # Check collections
    col_count = await db.collections.count_documents({})
    ok("collections", f"{col_count} collections")


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

async def main():
    print("BYO Tool Chain Test Suite")
    print("=" * 60)

    # 1. Qdrant
    qdrant_ok = test_qdrant_connectivity()
    if not qdrant_ok:
        print("\nQdrant failed — skipping remaining tests")
        return

    # 2. Content store
    store_result = await test_content_store()
    if not store_result:
        print("\nContent store empty — skipping retrieval tests")
        # Still run MongoDB + dispatcher tests
        await test_mongodb_byo()
        embedding = await test_embedding()
        if embedding:
            await test_dispatcher("test@test.com", "test-collection")
        return

    user_id, collection_id = store_result

    # 3. Embedding
    embedding = await test_embedding()

    # 4. Retrieval service
    await test_retrieval_service(user_id, collection_id)

    # 5. Tool handlers
    await test_tool_handlers(user_id, collection_id)

    # 6. Dispatcher
    await test_dispatcher(user_id, collection_id)

    # 7. MongoDB
    await test_mongodb_byo()

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL > 0:
        print("FIX THE FAILURES ABOVE")
    else:
        print("All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
