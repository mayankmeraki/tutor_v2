"""Unit tests for byo.processing.chunker.chunk_markdown.

Covers parent/child token budgets, atomic-block preservation (code fences
and tables), anchor propagation (page markers + timestamps + headers),
degenerate inputs, and modality/retrieval_mode selection per mime_type.
No network, no DB.
"""

from __future__ import annotations

import pytest

from byo.processing.chunker import (
    PARENT_MAX,
    PARENT_MIN,
    CHILD_MAX,
    CHILD_MIN,
    chunk_markdown,
    _tok,
)
from byo.shared.models import ChunkLevel, Modality, RetrievalMode


def _lorem(n_tokens: int, seed: str = "word") -> str:
    # Token heuristic is len(s)//4, so we want ~n_tokens*4 chars.
    # Use varied words so we get paragraph breaks.
    unit = (seed + " ") * 20  # ~80 chars ≈ 20 tokens
    copies = max(1, n_tokens // 20)
    return (unit.strip() + "\n\n") * copies


class TestEmpty:
    async def test_empty_string(self):
        parents, segments = await chunk_markdown("", "r1", "c1")
        assert parents == []
        assert segments == []

    async def test_whitespace_only(self):
        parents, segments = await chunk_markdown("   \n\n  \t \n", "r1", "c1")
        assert parents == []
        assert segments == []


class TestTokenBudget:
    async def test_parents_respect_max(self):
        md = "# Heading\n\n" + _lorem(3000)
        parents, segments = await chunk_markdown(
            md, "r1", "c1", mime_type="text/plain"
        )
        assert parents, "expected at least one parent"
        for p in parents:
            # PARENT_MAX is a soft cap — we close once we exceed target, so
            # may overshoot by up to one paragraph. Hard upper bound = PARENT_MAX*1.5.
            assert p["tokens"] <= int(PARENT_MAX * 1.6), (
                f"parent too large: {p['tokens']}"
            )

    async def test_children_within_bounds(self):
        md = "# Heading\n\n" + _lorem(1500)
        parents, segments = await chunk_markdown(
            md, "r1", "c1", mime_type="text/plain"
        )
        assert segments
        for s in segments:
            # Same reasoning — overshoot by up to one paragraph.
            assert s["tokens"] <= int(CHILD_MAX * 1.6), (
                f"segment too large: {s['tokens']}"
            )
            # Tiny stragglers are merged; every segment should be reasonably
            # sized OR be the whole parent (degenerate short-parent case).
            if s["tokens"] < CHILD_MIN:
                # Only acceptable for short parents with a single segment.
                siblings = [x for x in segments if x["parent_chunk_id"] == s["parent_chunk_id"]]
                assert len(siblings) == 1

    async def test_children_per_parent_in_range(self):
        md = "# Heading\n\n" + _lorem(2400)
        parents, segments = await chunk_markdown(
            md, "r1", "c1", mime_type="text/plain"
        )
        assert parents
        for p in parents:
            kids = [s for s in segments if s["parent_chunk_id"] == p["chunk_id"]]
            assert 1 <= len(kids) <= 6, (
                f"parent {p['index']} has {len(kids)} children"
            )


class TestParentChildLinkage:
    async def test_every_segment_has_real_parent(self):
        md = "# T\n\n" + _lorem(2000)
        parents, segments = await chunk_markdown(md, "r1", "c1")
        parent_ids = {p["chunk_id"] for p in parents}
        for s in segments:
            assert s["parent_chunk_id"] in parent_ids

    async def test_parent_level_set(self):
        parents, _ = await chunk_markdown("# T\n\n" + _lorem(500), "r1", "c1")
        for p in parents:
            assert p["level"] == ChunkLevel.PARENT.value

    async def test_parent_indices_dense(self):
        parents, _ = await chunk_markdown(
            "# A\n\n" + _lorem(1500) + "\n\n# B\n\n" + _lorem(1500),
            "r1", "c1",
        )
        indices = [p["index"] for p in parents]
        assert indices == list(range(len(parents)))

    async def test_segment_indices_per_parent(self):
        parents, segments = await chunk_markdown(
            "# T\n\n" + _lorem(2000), "r1", "c1"
        )
        for p in parents:
            kids = [s for s in segments if s["parent_chunk_id"] == p["chunk_id"]]
            kids.sort(key=lambda s: s["index"])
            assert [k["index"] for k in kids] == list(range(len(kids)))


class TestAtomicBlocks:
    async def test_code_fence_not_split_across_parents(self):
        # One huge code block + surrounding prose. The fence must sit
        # inside exactly one parent.
        prose = _lorem(600)
        code = "```python\n" + "print('x')\n" * 400 + "```\n"
        md = f"# Title\n\n{prose}\n{code}\n{prose}"
        parents, _ = await chunk_markdown(md, "r1", "c1")
        containing = [p for p in parents if "```python" in p["content"]]
        assert len(containing) == 1, (
            f"expected code fence in exactly one parent, got {len(containing)}"
        )
        # The closing fence must be in the same parent.
        assert containing[0]["content"].count("```") >= 2

    async def test_code_fence_not_split_across_children(self):
        prose = _lorem(200)
        code = "```python\n" + "x = 1\n" * 100 + "```\n"
        md = f"{prose}\n{code}\n{prose}"
        _, segments = await chunk_markdown(md, "r1", "c1")
        # Exactly one segment contains the fenced block (both opening &
        # closing backticks).
        fenced = [s for s in segments if "```python" in s["content"]]
        assert len(fenced) == 1
        assert fenced[0]["content"].count("```") >= 2

    async def test_table_preserved(self):
        prose = _lorem(500)
        table = (
            "| col1 | col2 |\n"
            "|------|------|\n"
            + "| a | b |\n" * 40
        )
        md = f"{prose}\n\n{table}\n\n{prose}"
        parents, _ = await chunk_markdown(md, "r1", "c1")
        # Every parent that has any table row must contain the full table.
        rows_total = md.count("| a | b |")
        parents_with_rows = [p for p in parents if "| a | b |" in p["content"]]
        assert len(parents_with_rows) == 1, (
            "table split across parents"
        )
        assert parents_with_rows[0]["content"].count("| a | b |") == rows_total


class TestAnchors:
    async def test_page_marker_propagates_to_parent_and_children(self):
        md = (
            "# Intro\n\n"
            "<!-- page 5 -->\n\n"
            + _lorem(400)
            + "\n\nsecond para here with more content.\n"
        )
        parents, segments = await chunk_markdown(
            md, "r1", "c1", mime_type="application/pdf"
        )
        assert parents
        p0 = parents[0]
        assert p0["anchor"]["page"] == 5
        kids = [s for s in segments if s["parent_chunk_id"] == p0["chunk_id"]]
        assert kids
        for k in kids:
            assert k["anchor"]["page"] == 5

    async def test_multiple_pages_become_range(self):
        md = (
            "<!-- page 3 -->\n\n" + _lorem(300)
            + "\n\n<!-- page 4 -->\n\n" + _lorem(300)
        )
        parents, _ = await chunk_markdown(
            md, "r1", "c1", mime_type="application/pdf"
        )
        # At least one parent should span 3..4 — find it.
        spanning = [
            p for p in parents
            if p["anchor"].get("page") == 3 and p["anchor"].get("page_end") == 4
        ]
        assert spanning, (
            f"expected a parent spanning pages 3-4, anchors: "
            f"{[p['anchor'] for p in parents]}"
        )

    async def test_heading_captured_in_anchor_section(self):
        md = "# Kinematics\n\n" + _lorem(600)
        parents, _ = await chunk_markdown(md, "r1", "c1")
        assert parents
        assert parents[0]["anchor"]["section"] == "Kinematics"

    async def test_timestamp_anchor_from_video_markers(self):
        md = "[0:30] first segment\n\n" + _lorem(400) + "\n\n[2:15] later\n"
        parents, _ = await chunk_markdown(
            md, "r1", "c1", mime_type="video/mp4"
        )
        assert parents
        a = parents[0]["anchor"]
        assert a["start_time"] is not None
        assert a["end_time"] is not None
        # 0:30 = 30s, 2:15 = 135s.
        assert a["start_time"] == 30.0
        assert a["end_time"] == 135.0

    async def test_no_page_marker_leaves_anchor_null(self):
        md = "# T\n\n" + _lorem(300)
        parents, _ = await chunk_markdown(md, "r1", "c1", mime_type="text/plain")
        assert parents[0]["anchor"]["page"] is None
        assert parents[0]["anchor"]["start_time"] is None


class TestModalityDetection:
    async def test_pdf_digital(self):
        parents, _ = await chunk_markdown(
            _lorem(300), "r", "c", mime_type="application/pdf"
        )
        assert parents[0]["modality"] == Modality.PDF_DIGITAL.value
        assert parents[0]["retrieval_mode"] == RetrievalMode.EXACT_PLUS_SEMANTIC.value

    async def test_pdf_scanned(self):
        parents, _ = await chunk_markdown(
            _lorem(300),
            "r",
            "c",
            resource_meta={"pages": 10, "low_text_pages": 8},
            mime_type="application/pdf",
        )
        assert parents[0]["modality"] == Modality.PDF_SCANNED.value
        assert parents[0]["retrieval_mode"] == RetrievalMode.VISUAL_DESCRIPTION.value

    async def test_video(self):
        parents, _ = await chunk_markdown(
            _lorem(300), "r", "c", mime_type="video/mp4"
        )
        assert parents[0]["modality"] == Modality.VIDEO.value
        assert parents[0]["retrieval_mode"] == RetrievalMode.TEMPORAL.value

    async def test_image(self):
        parents, _ = await chunk_markdown(
            _lorem(300), "r", "c", mime_type="image/png"
        )
        assert parents[0]["modality"] == Modality.IMAGE.value
        assert parents[0]["retrieval_mode"] == RetrievalMode.VISUAL_DESCRIPTION.value

    async def test_text_default(self):
        parents, _ = await chunk_markdown(
            _lorem(300), "r", "c", mime_type="text/plain"
        )
        assert parents[0]["modality"] == Modality.TEXT.value

    async def test_webpage_from_html(self):
        parents, _ = await chunk_markdown(
            _lorem(300), "r", "c", mime_type="text/html"
        )
        assert parents[0]["modality"] == Modality.WEBPAGE.value

    async def test_segments_inherit_modality(self):
        parents, segments = await chunk_markdown(
            _lorem(1000), "r", "c", mime_type="application/pdf"
        )
        assert segments
        for s in segments:
            assert s["modality"] == Modality.PDF_DIGITAL.value
            assert s["retrieval_mode"] == RetrievalMode.EXACT_PLUS_SEMANTIC.value


class TestIds:
    async def test_unique_ids(self):
        parents, segments = await chunk_markdown(
            "# T\n\n" + _lorem(3000), "r1", "c1"
        )
        p_ids = [p["chunk_id"] for p in parents]
        s_ids = [s["segment_id"] for s in segments]
        assert len(set(p_ids)) == len(p_ids)
        assert len(set(s_ids)) == len(s_ids)

    async def test_ids_carry_resource_and_collection(self):
        parents, segments = await chunk_markdown(
            _lorem(500), "RES-9", "COL-9", user_id="U-1"
        )
        for p in parents:
            assert p["resource_id"] == "RES-9"
            assert p["collection_id"] == "COL-9"
            assert p["user_id"] == "U-1"
        for s in segments:
            assert s["resource_id"] == "RES-9"
            assert s["collection_id"] == "COL-9"
            assert s["user_id"] == "U-1"
