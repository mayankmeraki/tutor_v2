"""Security regression tests: BYO data from user A must NEVER surface
on a user B query.

The `user_id` on every byo_chunk / byo_segment / byo_resource is the
single security boundary. These tests seed two users with overlapping
content (same words, different users) and assert that every retrieval
API path is correctly scoped.

If any of these tests ever start failing, stop the world: user data is
leaking across accounts.
"""

from __future__ import annotations

import pytest

from byo.processing.chunker import chunk_markdown
from byo.processing.embedder import embed_segments_batch
from byo.processing.indexer import index_chunks_and_segments
from byo.retrieval import service as svc


pytestmark = pytest.mark.asyncio


SAME_CONTENT = """# Photosynthesis

Photosynthesis is how plants turn light into chemical energy. It happens
in the chloroplasts. Chlorophyll absorbs light.

## Calvin cycle

The Calvin cycle fixes CO2 into sugar using ATP and NADPH. Rubisco is
the main enzyme.
"""


async def _seed_user(db, *, user_id: str, collection_id: str, resource_id: str):
    await db.byo_resources.insert_one({
        "resource_id": resource_id,
        "collection_id": collection_id,
        "user_id": user_id,
        "original_name": f"{user_id}-notes.md",
        "mime_type": "text/markdown",
        "status": "ready",
        "chunk_count": 0,
    })
    parents, segments = await chunk_markdown(
        SAME_CONTENT,
        resource_id=resource_id,
        collection_id=collection_id,
        user_id=user_id,
        mime_type="text/markdown",
    )
    await embed_segments_batch(segments)
    await index_chunks_and_segments(
        resource_id=resource_id,
        collection_id=collection_id,
        user_id=user_id,
        parents=parents,
        segments=segments,
    )
    return parents, segments


@pytest.fixture
async def two_users(fake_db):
    """Seed both users with the SAME content so only user_id can separate them."""
    a_parents, a_segments = await _seed_user(
        fake_db,
        user_id="user-A",
        collection_id="col-A",
        resource_id="res-A",
    )
    b_parents, b_segments = await _seed_user(
        fake_db,
        user_id="user-B",
        collection_id="col-B",
        resource_id="res-B",
    )
    return {
        "A": {"parents": a_parents, "segments": a_segments},
        "B": {"parents": b_parents, "segments": b_segments},
    }


# ── search ────────────────────────────────────────────────────────────────


async def test_search_isolates_by_user_id(fake_db, two_users):
    """User A querying their own collection cannot see B's chunks."""
    hits_A = await svc.search(
        "photosynthesis Calvin",
        user_id="user-A",
        scope="collection",
        collection_id="col-A",
        k=5,
    )
    assert hits_A, "expected A to find their own content"
    for h in hits_A:
        assert h.resource_id == "res-A", (
            f"LEAK: user-A search surfaced resource {h.resource_id}"
        )

    hits_B = await svc.search(
        "photosynthesis Calvin",
        user_id="user-B",
        scope="collection",
        collection_id="col-B",
        k=5,
    )
    assert hits_B
    for h in hits_B:
        assert h.resource_id == "res-B", (
            f"LEAK: user-B search surfaced resource {h.resource_id}"
        )


async def test_search_blocked_when_cross_user_collection_id(fake_db, two_users):
    """User A passing B's collection_id gets nothing (user_id filter wins)."""
    hits = await svc.search(
        "photosynthesis",
        user_id="user-A",
        scope="collection",
        collection_id="col-B",  # try to sneak in
        k=5,
    )
    for h in hits:
        assert h.resource_id != "res-B", (
            f"LEAK: cross-collection query returned {h.resource_id}"
        )
    # With user-A's filter applied, col-B yields no user-A docs → []
    assert hits == []


async def test_user_corpus_scope_scoped_to_user(fake_db, two_users):
    """scope='user_corpus' crosses collections but NEVER users."""
    hits_A = await svc.search(
        "photosynthesis",
        user_id="user-A",
        scope="user_corpus",
        k=10,
    )
    for h in hits_A:
        assert h.resource_id == "res-A", (
            f"LEAK: user_corpus search crossed user boundary → {h.resource_id}"
        )


# ── fetch ─────────────────────────────────────────────────────────────────


async def test_fetch_blocks_other_users_chunk(fake_db, two_users):
    """User A trying to fetch a chunk ID that belongs to user B returns None."""
    # Get one of user-B's real chunk_ids
    b_chunk = await fake_db.byo_chunks.find_one({"user_id": "user-B"})
    assert b_chunk, "seeding failed to write B's chunks"

    hit = await svc.fetch(f"chunk:{b_chunk['chunk_id']}", user_id="user-A")
    assert hit is None, f"LEAK: user-A fetched user-B's chunk {b_chunk['chunk_id']}"


async def test_fetch_blocks_other_users_segment(fake_db, two_users):
    """Same protection at the segment level."""
    b_seg = await fake_db.byo_segments.find_one({"user_id": "user-B"})
    assert b_seg

    hit = await svc.fetch(f"segment:{b_seg['segment_id']}", user_id="user-A")
    assert hit is None, "LEAK: user-A fetched user-B's segment"


async def test_fetch_blocks_other_users_resource(fake_db, two_users):
    """resource:<id> resolves to the resource's first chunk — user-scoped."""
    hit = await svc.fetch("resource:res-B", user_id="user-A")
    assert hit is None, "LEAK: user-A resolved user-B's resource"


# ── nearby ────────────────────────────────────────────────────────────────


async def test_nearby_blocks_other_users_chunk(fake_db, two_users):
    """Even if the ref is legit, the user must own it."""
    b_chunk = await fake_db.byo_chunks.find_one({"user_id": "user-B"})
    hits = await svc.nearby(
        f"chunk:{b_chunk['chunk_id']}", user_id="user-A", window=2,
    )
    assert hits == [], (
        f"LEAK: user-A walked user-B's chunk → {[h.chunk_id for h in hits]}"
    )


async def test_nearby_within_user_returns_own_chunks(fake_db, two_users):
    """Sanity: within-user nearby still works."""
    a_chunk = await fake_db.byo_chunks.find_one({
        "user_id": "user-A", "index": 0,
    })
    hits = await svc.nearby(
        f"chunk:{a_chunk['chunk_id']}", user_id="user-A", window=1,
    )
    for h in hits:
        assert h.resource_id == "res-A"


# ── list_contents ─────────────────────────────────────────────────────────


async def test_list_contents_scoped_to_user(fake_db, two_users):
    """list_contents must show only the requesting user's resources."""
    refs_A = await svc.list_contents("col-A", user_id="user-A", group_by="resource")
    # Exactly one resource, and it's A's.
    assert len(refs_A) == 1
    assert refs_A[0].ref == "resource:res-A"

    # User A passing B's collection sees nothing.
    refs_A_on_B = await svc.list_contents("col-B", user_id="user-A", group_by="resource")
    assert refs_A_on_B == [], (
        "LEAK: user-A listed contents of user-B's collection"
    )


# ── Defence in depth: filters helper ──────────────────────────────────────


async def test_segment_to_parent_chunk_id_scoped(fake_db, two_users):
    """filters.segment_to_parent_chunk_id respects user_id."""
    from byo.retrieval.filters import segment_to_parent_chunk_id

    b_seg = await fake_db.byo_segments.find_one({"user_id": "user-B"})
    # B can resolve their own segment
    parent_id = await segment_to_parent_chunk_id(b_seg["segment_id"], "user-B")
    assert parent_id == b_seg["parent_chunk_id"]
    # A cannot
    parent_id_leak = await segment_to_parent_chunk_id(b_seg["segment_id"], "user-A")
    assert parent_id_leak is None, "LEAK: segment resolution ignored user_id"
