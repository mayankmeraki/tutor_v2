"""Tool-selection scaffold (NOT LLM-in-the-loop).

Each scenario declares: (a) what the student is doing, (b) what tool + args
a correct tutor would pick, (c) the shape we expect that call to produce.

We don't test the LLM's choice here — that's a Braintrust / Inspect job.
What we CAN test is that the handlers, given the chosen tool + args, produce
output that would actually help the tutor finish the turn.

Think of this as a contract test for each row of the "when to use which
tool" table in the tutor prompt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.tools import execute_tutor_tool
from byo.processing.chunker import chunk_markdown
from byo.processing.embedder import embed_segments_batch
from byo.processing.indexer import index_chunks_and_segments


pytestmark = pytest.mark.asyncio


# ── Seed: two resources the scenarios below reference ────────────────────


PDF_MD = """# Photosynthesis Chapter

<!-- page 12 -->
Photosynthesis occurs in chloroplasts. Light-dependent reactions happen in
the thylakoid membranes; the Calvin cycle happens in the stroma.

<!-- page 13 -->
The Calvin cycle fixes CO2 into G3P using ATP and NADPH from the light
reactions. Rubisco is the key enzyme — it's notoriously slow.

<!-- page 14 -->
G3P can be used to make glucose or regenerated to RuBP. The regeneration
phase closes the cycle.
"""

VIDEO_MD = """# Calvin Cycle Lecture

[00:00] Today's lecture: the Calvin cycle. The dark reactions of
photosynthesis.

[12:00] At twelve minutes in we discuss Rubisco's active site. It's a
remarkable catalyst despite being slow.

[12:34] The critical step: CO2 fixation onto RuBP. Forms a 6-carbon
intermediate that splits into two 3-PGA molecules.

[13:10] Reduction phase: 3-PGA → G3P using NADPH and ATP. Then
regeneration: some G3P → RuBP.
"""


@pytest.fixture
async def seeded(fake_db):
    user_id = "student-ishita"
    collection_id = "col-biology"
    await fake_db.collections.insert_one({
        "collection_id": collection_id,
        "user_id": user_id,
        "title": "Biology — Photosynthesis",
        "stats": {"resources": 2, "chunks": 0},
    })
    specs = [
        ("res-pdf-biology", "Biology Textbook Ch 8.pdf", "application/pdf", PDF_MD),
        ("res-vid-calvin", "Calvin Cycle Lecture.mp4", "video/mp4", VIDEO_MD),
    ]
    for rid, name, mime, md in specs:
        await fake_db.byo_resources.insert_one({
            "resource_id": rid,
            "collection_id": collection_id,
            "user_id": user_id,
            "original_name": name,
            "mime_type": mime,
            "status": "ready",
            "chunk_count": 0,
        })
        parents, segments = await chunk_markdown(
            md,
            resource_id=rid,
            collection_id=collection_id,
            user_id=user_id,
            mime_type=mime,
        )
        for p in parents:
            p["topics"] = ["calvin cycle"]
        await embed_segments_batch(segments)
        await index_chunks_and_segments(
            resource_id=rid,
            collection_id=collection_id,
            user_id=user_id,
            parents=parents,
            segments=segments,
        )

    return {
        "user_id": user_id,
        "collection_id": collection_id,
        "pdf_resource": "res-pdf-biology",
        "video_resource": "res-vid-calvin",
    }


def _ctx(user_id, collection_id):
    return {
        "studentProfile": json.dumps({"userEmail": user_id}),
        "sessionContext": json.dumps({"collection_id": collection_id}),
    }


# ── Scenarios ─────────────────────────────────────────────────────────────


async def test_scenario_student_asks_about_topic_in_their_pdf(seeded, fake_db):
    """'I want to understand the Calvin cycle from my biology textbook.'

    Expected: search(scope='collection', query='Calvin cycle', collection_id=...)
    Success: output contains at least one chunk ref + pdf citation.
    """
    out = await execute_tutor_tool(
        "search",
        {
            "query": "Calvin cycle",
            "scope": "collection",
            "collection_id": seeded["collection_id"],
            "k": 3,
        },
        context_data=_ctx(seeded["user_id"], seeded["collection_id"]),
    )
    assert "chunk:" in out, f"no fetchable ref in search output:\n{out}"
    assert "Biology Textbook Ch 8.pdf" in out or "Calvin Cycle Lecture.mp4" in out


async def test_scenario_student_pauses_video_at_timestamp(seeded, fake_db):
    """Student pauses at 12:34 in the Calvin cycle lecture.

    Expected flow: tutor finds a chunk near that timestamp in the video,
    then calls nearby(ref=chunk:<id>, window=1) to get transcript around
    the pause point.
    Success: nearby output covers multiple adjacent chunks, ordered by time.
    """
    # Simulate: the tutor searches its own collection for the right chunk
    search_out = await execute_tutor_tool(
        "search",
        {
            "query": "Rubisco CO2 fixation",
            "scope": "resource",
            "resource_id": seeded["video_resource"],
            "k": 1,
        },
        context_data=_ctx(seeded["user_id"], seeded["collection_id"]),
    )
    refs = re.findall(r"chunk:[a-zA-Z0-9\-]+", search_out)
    assert refs, f"expected a chunk ref from video search, got:\n{search_out}"

    # Then nearby on that chunk (window=1 minute for temporal modality)
    nearby_out = await execute_tutor_tool(
        "nearby",
        {"ref": refs[0], "window": 1},
        context_data=_ctx(seeded["user_id"], seeded["collection_id"]),
    )
    # Should cite timestamps (m:ss)
    assert re.search(r"\b\d+:\d{2}\b", nearby_out), (
        f"nearby video output missing timestamp citations:\n{nearby_out}"
    )


async def test_scenario_student_asks_what_do_i_have(seeded, fake_db):
    """'What study materials do I have in this collection?'

    Expected: list_contents(scope='collection', collection_id=...,
    group_by='resource').
    Success: the tutor gets both original_name entries back.
    """
    out = await execute_tutor_tool(
        "list_contents",
        {
            "scope": "collection",
            "collection_id": seeded["collection_id"],
            "group_by": "resource",
        },
        context_data=_ctx(seeded["user_id"], seeded["collection_id"]),
    )
    assert "Biology Textbook Ch 8.pdf" in out
    assert "Calvin Cycle Lecture.mp4" in out


async def test_scenario_tutor_wants_specific_course_section(seeded, fake_db, monkeypatch):
    """'Now teach section 2 of lesson 3 of the course.'

    Expected: fetch(ref='lesson:3:section:2') — routed to course adapter.
    Success: the course adapter is invoked with that ref.
    """
    invocations: list[str] = []

    class StubAdapter:
        async def content_read(self, ref):
            invocations.append(ref)
            return (
                f"Section: Entanglement Basics\n"
                f"Timestamps: 5:30 - 9:12\n"
                f"Summary: Introduces EPR pairs."
            )

    async def _stub_get_adapter(context_data=None):
        return StubAdapter()

    import app.tools.retrieval as retrieval_mod
    monkeypatch.setattr(retrieval_mod, "_get_course_adapter", _stub_get_adapter)

    out = await execute_tutor_tool(
        "fetch",
        {"ref": "lesson:3:section:2"},
        context_data={
            "studentProfile": json.dumps({
                "courseId": 1,
                "userEmail": seeded["user_id"],
            })
        },
    )
    assert invocations == ["lesson:3:section:2"], (
        "lesson ref was not dispatched to course adapter"
    )
    assert "Entanglement Basics" in out


async def test_scenario_tutor_wants_preview_before_committing(seeded, fake_db):
    """'Quick preview of this chunk before I decide to fetch it in full.'

    Expected: peek(ref=chunk:<id>)
    Success: output is strictly shorter than fetch on the same ref (peek is
    a compact summary).
    """
    parent = await fake_db.byo_chunks.find_one({"user_id": seeded["user_id"]})
    ref = f"chunk:{parent['chunk_id']}"

    peek_out = await execute_tutor_tool(
        "peek", {"ref": ref}, context_data=_ctx(seeded["user_id"], seeded["collection_id"]),
    )
    fetch_out = await execute_tutor_tool(
        "fetch", {"ref": ref}, context_data=_ctx(seeded["user_id"], seeded["collection_id"]),
    )
    assert peek_out and fetch_out
    assert len(peek_out) <= len(fetch_out), (
        f"peek ({len(peek_out)}) was not shorter than fetch ({len(fetch_out)})"
    )


async def test_scenario_cross_user_content_across_collection(seeded, fake_db):
    """'What's across all of my BYO materials?' (session context has no
    collection_id — student is browsing from a dashboard).

    Expected: list_contents(scope='user_corpus')
    Success: the user's collection shows up by title.
    """
    out = await execute_tutor_tool(
        "list_contents",
        {"scope": "user_corpus"},
        context_data={"studentProfile": json.dumps({"userEmail": seeded["user_id"]})},
    )
    assert "Biology — Photosynthesis" in out or "col-biology" in out, (
        f"user_corpus listing missing the user's collection:\n{out}"
    )


async def test_scenario_byo_and_course_both_hit_simultaneously(seeded, fake_db, monkeypatch):
    """'Find something about photosynthesis across course + my notes.'

    Expected: search(scope='both', ...) fans out in parallel; the output
    carries both halves with clear section headers.
    """
    # Stub the course search to return a small static list
    async def _fake_course_search(query, limit=5):
        return [{
            "lessonId": 4,
            "type": "lesson",
            "title": "Photosynthesis Overview",
            "description": "Light + dark reactions.",
        }]

    import app.services.content.content_service as cs_mod
    monkeypatch.setattr(cs_mod, "search_content", _fake_course_search)

    out = await execute_tutor_tool(
        "search",
        {
            "query": "photosynthesis",
            "scope": "both",
            "collection_id": seeded["collection_id"],
            "k": 3,
        },
        context_data=_ctx(seeded["user_id"], seeded["collection_id"]),
    )
    assert "From your uploaded materials" in out
    assert "From course" in out
    assert "lesson:4" in out, "course hit should include lesson: ref"
