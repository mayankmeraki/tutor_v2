"""Tests for SearchFilters.to_mongo() and byo.retrieval.filters helpers."""

from __future__ import annotations

import pytest

from byo.retrieval.filters import parse_ref
from byo.shared.models import Modality, RetrievalMode
from byo.shared.results import SearchFilters


# ── SearchFilters.to_mongo ──────────────────────────────────────────────


class TestSearchFiltersToMongo:
    def test_user_id_always_present(self):
        q = SearchFilters(user_id="u-123").to_mongo()
        assert q["user_id"] == "u-123"

    def test_empty_filters_only_user_id(self):
        q = SearchFilters(user_id="u-1").to_mongo()
        assert q == {"user_id": "u-1"}

    def test_collection_id_present(self):
        q = SearchFilters(user_id="u", collection_id="c1").to_mongo()
        assert q["collection_id"] == "c1"
        assert q["user_id"] == "u"

    def test_resource_id_present(self):
        q = SearchFilters(user_id="u", resource_id="r1").to_mongo()
        assert q["resource_id"] == "r1"

    def test_modality_in_clause(self):
        q = SearchFilters(
            user_id="u",
            modality=[Modality.PDF_DIGITAL, Modality.VIDEO],
        ).to_mongo()
        assert q["modality"] == {"$in": ["pdf_digital", "video"]}

    def test_retrieval_mode_in_clause(self):
        q = SearchFilters(
            user_id="u",
            retrieval_mode=[RetrievalMode.SEMANTIC, RetrievalMode.TEMPORAL],
        ).to_mongo()
        assert q["retrieval_mode"] == {"$in": ["semantic", "temporal"]}

    def test_topics_in_clause(self):
        q = SearchFilters(user_id="u", topics=["calculus", "algebra"]).to_mongo()
        assert q["topics"] == {"$in": ["calculus", "algebra"]}

    def test_page_single_value(self):
        q = SearchFilters(user_id="u", page=5).to_mongo()
        assert q["anchor.page"] == 5

    def test_page_range(self):
        q = SearchFilters(user_id="u", page_range=(3, 10)).to_mongo()
        assert q["anchor.page"] == {"$gte": 3, "$lte": 10}

    def test_page_single_overrides_page_range(self):
        """If both `page` and `page_range` are set, page wins."""
        q = SearchFilters(user_id="u", page=7, page_range=(1, 20)).to_mongo()
        # The implementation uses if/elif — single page wins.
        assert q["anchor.page"] == 7

    def test_time_range_produces_or_clause(self):
        q = SearchFilters(user_id="u", time_range=(10.0, 30.0)).to_mongo()
        assert "$or" in q
        ors = q["$or"]
        # Three clauses: start overlaps, end overlaps, or fully spans.
        assert len(ors) == 3
        assert {"anchor.start_time": {"$gte": 10.0, "$lte": 30.0}} in ors
        assert {"anchor.end_time": {"$gte": 10.0, "$lte": 30.0}} in ors
        spans = {
            "$and": [
                {"anchor.start_time": {"$lte": 10.0}},
                {"anchor.end_time": {"$gte": 30.0}},
            ]
        }
        assert spans in ors

    def test_all_filters_together(self):
        q = SearchFilters(
            user_id="u",
            collection_id="c",
            resource_id="r",
            modality=[Modality.PDF_DIGITAL],
            retrieval_mode=[RetrievalMode.SEMANTIC],
            topics=["t1"],
            page_range=(1, 5),
            time_range=(0.0, 60.0),
        ).to_mongo()
        assert q["user_id"] == "u"
        assert q["collection_id"] == "c"
        assert q["resource_id"] == "r"
        assert q["modality"] == {"$in": ["pdf_digital"]}
        assert q["retrieval_mode"] == {"$in": ["semantic"]}
        assert q["topics"] == {"$in": ["t1"]}
        assert q["anchor.page"] == {"$gte": 1, "$lte": 5}
        assert "$or" in q


# ── Security: user_id construction ──────────────────────────────────────


class TestSecurity:
    def test_search_empty_user_id_raises(self):
        """`service.search(user_id="")` must raise ValueError — even though
        SearchFilters itself accepts empty strings (dataclass w/o validator)."""
        import asyncio

        from byo.retrieval.service import search

        async def _call():
            return await search("query", user_id="")

        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(ValueError):
                loop.run_until_complete(_call())
        finally:
            loop.close()

    def test_build_filters_empty_user_id_passes_through(self):
        """build_filters doesn't validate user_id — search() does that
        at the API boundary. build_filters is an internal helper."""
        from byo.retrieval.service import build_filters
        result = build_filters(user_id="", scope="collection", collection_id="c")
        assert result["user_id"] == ""

    def test_scoped_filters_empty_user_id_raises(self):
        from byo.retrieval.filters import scoped_filters

        with pytest.raises(ValueError):
            scoped_filters(user_id="")

    def test_require_user_filter_empty_raises(self):
        from byo.retrieval.filters import require_user_filter

        with pytest.raises(ValueError):
            require_user_filter("")

    def test_searchfilters_accepts_empty_user_id_note(self):
        """NOTE/BUG-hint: SearchFilters is a plain dataclass and does NOT
        validate on construction. The security boundary is enforced by
        the service/ranker entrypoints, not the dataclass itself."""
        # Not a bug per se — documents current behaviour.
        f = SearchFilters(user_id="")
        assert f.to_mongo() == {"user_id": ""}


# ── parse_ref ───────────────────────────────────────────────────────────


class TestParseRef:
    def test_chunk_prefix(self):
        assert parse_ref("chunk:abc") == ("chunk", "abc")

    def test_segment_prefix(self):
        assert parse_ref("segment:xy") == ("segment", "xy")

    def test_resource_prefix(self):
        assert parse_ref("resource:r1") == ("resource", "r1")

    def test_bare_ref_defaults_to_chunk(self):
        assert parse_ref("abc123") == ("chunk", "abc123")

    def test_bare_ref_strips_whitespace(self):
        assert parse_ref("  abc123  ") == ("chunk", "abc123")

    def test_unknown_prefix_treated_as_bare(self):
        assert parse_ref("topic:foo") == ("chunk", "topic:foo")

    def test_empty_ref_raises(self):
        with pytest.raises(ValueError):
            parse_ref("")

    def test_empty_id_after_known_prefix_raises(self):
        with pytest.raises(ValueError):
            parse_ref("chunk:")

    def test_case_insensitive_prefix(self):
        assert parse_ref("CHUNK:abc") == ("chunk", "abc")
