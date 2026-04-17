"""Tool dispatch contract tests.

Covers execute_tutor_tool for each unified retrieval tool:
  search / fetch / peek / nearby / list_contents

Every scenario verifies the OUTPUT is always a string (contract: the
tutor never sees an exception; bad inputs come back as informative
strings it can course-correct on).

Routing:
  - lesson:/sim: refs go to the course adapter
  - chunk:/segment:/resource: refs go to BYO service
"""

from __future__ import annotations

import json

import pytest

from app.tools import execute_tutor_tool
from byo.processing.chunker import chunk_markdown
from byo.processing.embedder import embed_segments_batch
from byo.processing.indexer import index_chunks_and_segments


pytestmark = pytest.mark.asyncio


SEED_MD = """# Wave Functions

The wave function is a complex-valued function. Its modulus squared is
a probability density.

## Schrodinger equation

The Schrodinger equation governs time evolution.
"""


async def _seed_byo(db, user_id="u-1", collection_id="col-1", resource_id="res-1"):
    """Ingest one short resource so BYO calls have something to hit."""
    await db.byo_resources.insert_one({
        "resource_id": resource_id,
        "collection_id": collection_id,
        "user_id": user_id,
        "original_name": "Study Notes.md",
        "mime_type": "text/markdown",
        "status": "ready",
        "chunk_count": 0,
    })
    parents, segments = await chunk_markdown(
        SEED_MD,
        resource_id=resource_id,
        collection_id=collection_id,
        user_id=user_id,
        mime_type="text/markdown",
    )
    for p in parents:
        if "schrodinger" in (p.get("content") or "").lower():
            p["topics"] = ["schrodinger"]
        else:
            p["topics"] = ["wave function"]
    await embed_segments_batch(segments)
    await index_chunks_and_segments(
        resource_id=resource_id,
        collection_id=collection_id,
        user_id=user_id,
        parents=parents,
        segments=segments,
    )
    return parents, segments


def _ctx(user_email="u-1", collection_id="col-1"):
    return {
        "studentProfile": json.dumps({"userEmail": user_email}),
        "sessionContext": json.dumps({"collection_id": collection_id}),
    }


# ── search ────────────────────────────────────────────────────────────────


async def test_search_returns_string_with_valid_input(fake_db):
    await _seed_byo(fake_db)
    out = await execute_tutor_tool(
        "search",
        {"query": "Schrodinger", "scope": "collection", "collection_id": "col-1", "k": 3},
        context_data=_ctx(),
    )
    assert isinstance(out, str)
    assert out.strip(), "search output must not be empty"
    # Must include at least one chunk ref the tutor can pass to fetch
    assert "chunk:" in out


async def test_search_missing_query_returns_error_string(fake_db):
    out = await execute_tutor_tool(
        "search",
        {"scope": "collection", "collection_id": "col-1"},  # no query
        context_data=_ctx(),
    )
    assert isinstance(out, str)
    assert "query" in out.lower() and "requir" in out.lower(), (
        f"missing-query error should be informative, got: {out!r}"
    )


async def test_search_missing_user_id_returns_error_string(fake_db):
    """BYO scope requires user_id — without it, return a string error."""
    out = await execute_tutor_tool(
        "search",
        {"query": "anything", "scope": "collection", "collection_id": "col-1"},
        context_data={},  # no studentProfile → no user_id
    )
    assert isinstance(out, str)
    assert "user" in out.lower(), f"expected user_id error, got: {out!r}"


async def test_search_routes_course_scope_without_crashing(fake_db):
    """scope='course' without a course should degrade gracefully."""
    out = await execute_tutor_tool(
        "search",
        {"query": "entanglement", "scope": "course", "k": 2},
        context_data={},
    )
    assert isinstance(out, str)
    # Either "no results" style or error — just must not raise.


# ── fetch ─────────────────────────────────────────────────────────────────


async def test_fetch_byo_ref_returns_string(fake_db):
    parents, _ = await _seed_byo(fake_db)
    ref = f"chunk:{parents[0]['chunk_id']}"
    out = await execute_tutor_tool("fetch", {"ref": ref}, context_data=_ctx())
    assert isinstance(out, str)
    assert "Source:" in out, f"fetch output must include citation, got: {out!r}"


async def test_fetch_missing_ref_returns_error_string(fake_db):
    out = await execute_tutor_tool("fetch", {}, context_data=_ctx())
    assert isinstance(out, str)
    assert "ref" in out.lower()


async def test_fetch_unknown_ref_format_returns_error_string(fake_db):
    out = await execute_tutor_tool(
        "fetch", {"ref": "banana:123"}, context_data=_ctx(),
    )
    assert isinstance(out, str)
    assert "unknown ref" in out.lower() or "error" in out.lower()


async def test_fetch_byo_missing_user_id_returns_error_string(fake_db):
    """chunk: ref with no user_id → string error, not an exception."""
    out = await execute_tutor_tool(
        "fetch", {"ref": "chunk:nonexistent"}, context_data={},
    )
    assert isinstance(out, str)
    assert "user" in out.lower()


async def test_fetch_routes_course_refs_to_adapter(fake_db, monkeypatch):
    """lesson:<id>:section:<idx> must go to the course adapter, not BYO."""
    calls: list[str] = []

    class StubAdapter:
        async def content_read(self, ref):
            calls.append(ref)
            return f"COURSE:{ref}"

    async def _stub_get_adapter(context_data=None):
        return StubAdapter()

    import app.tools.retrieval as retrieval_mod
    monkeypatch.setattr(retrieval_mod, "_get_course_adapter", _stub_get_adapter)

    out = await execute_tutor_tool(
        "fetch",
        {"ref": "lesson:3:section:2"},
        context_data={"studentProfile": json.dumps({"courseId": 1, "userEmail": "u"})},
    )
    assert isinstance(out, str)
    assert calls == ["lesson:3:section:2"], (
        "lesson: ref was not routed to the course adapter"
    )


# ── peek ──────────────────────────────────────────────────────────────────


async def test_peek_byo_ref_returns_string(fake_db):
    parents, _ = await _seed_byo(fake_db)
    out = await execute_tutor_tool(
        "peek", {"ref": f"chunk:{parents[0]['chunk_id']}"}, context_data=_ctx(),
    )
    assert isinstance(out, str)
    assert out.strip()


async def test_peek_missing_ref_returns_error_string(fake_db):
    out = await execute_tutor_tool("peek", {}, context_data=_ctx())
    assert isinstance(out, str)
    assert "ref" in out.lower()


# ── nearby ────────────────────────────────────────────────────────────────


async def test_nearby_byo_ref_returns_string(fake_db):
    parents, _ = await _seed_byo(fake_db)
    out = await execute_tutor_tool(
        "nearby",
        {"ref": f"chunk:{parents[0]['chunk_id']}", "window": 1},
        context_data=_ctx(),
    )
    assert isinstance(out, str)
    assert out.strip()


async def test_nearby_missing_user_id_returns_error_string(fake_db):
    out = await execute_tutor_tool(
        "nearby", {"ref": "chunk:anything"}, context_data={},
    )
    assert isinstance(out, str)
    assert "user" in out.lower()


# ── list_contents ─────────────────────────────────────────────────────────


async def test_list_contents_returns_string(fake_db):
    await _seed_byo(fake_db)
    out = await execute_tutor_tool(
        "list_contents",
        {"scope": "collection", "collection_id": "col-1", "group_by": "resource"},
        context_data=_ctx(),
    )
    assert isinstance(out, str)
    assert "resource:" in out or "Contents of" in out


async def test_list_contents_missing_scope_returns_error(fake_db):
    out = await execute_tutor_tool("list_contents", {}, context_data=_ctx())
    assert isinstance(out, str)
    assert "scope" in out.lower()


async def test_list_contents_unknown_scope_returns_error(fake_db):
    out = await execute_tutor_tool(
        "list_contents", {"scope": "garbage"}, context_data=_ctx(),
    )
    assert isinstance(out, str)
    assert "unknown" in out.lower() or "scope" in out.lower()


async def test_list_contents_missing_user_id_returns_error(fake_db):
    out = await execute_tutor_tool(
        "list_contents",
        {"scope": "collection", "collection_id": "col-1"},
        context_data={},  # no studentProfile
    )
    assert isinstance(out, str)
    assert "user" in out.lower()


# ── Unknown tool name ─────────────────────────────────────────────────────


async def test_unknown_tool_returns_string(fake_db):
    """The dispatcher must not raise on an unknown tool name."""
    out = await execute_tutor_tool("does_not_exist", {}, context_data={})
    assert isinstance(out, str)
    assert "unknown" in out.lower()


# ── Dispatch exception safety ─────────────────────────────────────────────


async def test_exceptions_in_handlers_return_string(fake_db, monkeypatch):
    """If a handler somehow raises unexpectedly, the dispatcher catches it."""
    async def _boom(*a, **k):
        raise RuntimeError("synthetic failure")

    import app.tools as tools_pkg
    monkeypatch.setattr(tools_pkg, "search_tool", _boom)

    out = await execute_tutor_tool(
        "search",
        {"query": "x"},
        context_data=_ctx(),
    )
    assert isinstance(out, str)
    assert "error" in out.lower() or "try" in out.lower()
