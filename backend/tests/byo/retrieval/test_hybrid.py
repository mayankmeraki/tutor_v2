"""Tests for byo.retrieval.rankers.hybrid.hybrid_fuse (pure-function, no Mongo)."""

from __future__ import annotations

import pytest

from byo.retrieval.rankers.hybrid import (
    DEFAULT_FALLBACK_WEIGHT,
    DEFAULT_MODALITY_WEIGHTS,
    RRF_K,
    hybrid_fuse,
)
from byo.shared.models import Modality


def _rrf(weight: float, rank: int) -> float:
    return weight / (RRF_K + rank)


class TestRRFMath:
    def test_single_hit_dense_only_default_weight(self):
        out = hybrid_fuse(
            [("s1", "p1", 0.9)],
            [],
            k=5,
        )
        # No modality → fallback (0.5, 0.5); rank 1 → 0.5 / 61
        assert len(out) == 1
        sid, pid, sc = out[0]
        assert sid == "s1" and pid == "p1"
        assert sc == pytest.approx(_rrf(DEFAULT_FALLBACK_WEIGHT[0], 1))

    def test_single_hit_sparse_only_default_weight(self):
        out = hybrid_fuse([], [("s1", "p1", 0.5)], k=5)
        sid, pid, sc = out[0]
        assert sc == pytest.approx(_rrf(DEFAULT_FALLBACK_WEIGHT[1], 1))

    def test_hit_in_both_rankers_sums(self):
        out = hybrid_fuse(
            [("s1", "p1", 0.9)],
            [("s1", "p1", 0.8)],
            k=5,
        )
        assert len(out) == 1
        _, _, sc = out[0]
        expected = _rrf(0.5, 1) + _rrf(0.5, 1)
        assert sc == pytest.approx(expected)

    def test_hit_in_both_scores_higher_than_single(self):
        both = hybrid_fuse(
            [("s1", "p1", 0.9)],
            [("s1", "p1", 0.8)],
            k=5,
        )
        only_dense = hybrid_fuse([("s1", "p1", 0.9)], [], k=5)
        only_sparse = hybrid_fuse([], [("s1", "p1", 0.8)], k=5)
        assert both[0][2] > only_dense[0][2]
        assert both[0][2] > only_sparse[0][2]


class TestModalityWeights:
    def test_per_hit_weight_applied(self):
        # CODE: (0.2, 0.8) → a dense hit on code contributes less than a
        # sparse hit at the same rank.
        modality_map = {"s1": Modality.CODE}
        dense_out = hybrid_fuse(
            [("s1", "p1", 0.9)], [], k=5, modality_map=modality_map
        )
        sparse_out = hybrid_fuse(
            [], [("s1", "p1", 0.5)], k=5, modality_map=modality_map
        )
        assert dense_out[0][2] == pytest.approx(_rrf(0.2, 1))
        assert sparse_out[0][2] == pytest.approx(_rrf(0.8, 1))
        assert sparse_out[0][2] > dense_out[0][2]

    def test_video_favors_dense(self):
        modality_map = {"s1": Modality.VIDEO}  # (0.7, 0.3)
        dense_out = hybrid_fuse(
            [("s1", "p1", 0.9)], [], k=5, modality_map=modality_map
        )
        sparse_out = hybrid_fuse(
            [], [("s1", "p1", 0.9)], k=5, modality_map=modality_map
        )
        assert dense_out[0][2] > sparse_out[0][2]

    def test_override_weights(self):
        overrides = {Modality.TEXT: (0.1, 0.9)}
        out = hybrid_fuse(
            [("s1", "p1", 0.9)],
            [],
            k=5,
            modality_map={"s1": Modality.TEXT},
            modality_weights=overrides,
        )
        assert out[0][2] == pytest.approx(_rrf(0.1, 1))

    def test_default_modality_weights_used_when_no_override(self):
        # PDF_DIGITAL default is (0.6, 0.4)
        out = hybrid_fuse(
            [("s1", "p1", 0.9)],
            [],
            k=5,
            modality_map={"s1": Modality.PDF_DIGITAL},
        )
        assert out[0][2] == pytest.approx(
            _rrf(DEFAULT_MODALITY_WEIGHTS[Modality.PDF_DIGITAL][0], 1)
        )


class TestOrderingAndTruncation:
    def test_sorted_descending(self):
        out = hybrid_fuse(
            [("s1", "p1", 0.9), ("s2", "p2", 0.8), ("s3", "p3", 0.7)],
            [],
            k=5,
        )
        scores = [s[2] for s in out]
        assert scores == sorted(scores, reverse=True)

    def test_truncates_to_k(self):
        dense = [(f"s{i}", f"p{i}", 1.0 / (i + 1)) for i in range(10)]
        out = hybrid_fuse(dense, [], k=3)
        assert len(out) == 3

    def test_empty_inputs(self):
        assert hybrid_fuse([], [], k=5) == []

    def test_k_zero_returns_empty(self):
        out = hybrid_fuse([("s1", "p1", 0.5)], [], k=0)
        assert out == []

    def test_hit_in_only_one_ranker_still_scored(self):
        out = hybrid_fuse(
            [("s_only_dense", "p", 0.5)],
            [("s_only_sparse", "p", 0.5)],
            k=5,
        )
        ids = [x[0] for x in out]
        assert "s_only_dense" in ids
        assert "s_only_sparse" in ids

    def test_parent_id_preserved_from_first_seen(self):
        out = hybrid_fuse(
            [("s1", "parent_a", 0.9)],
            [("s1", "parent_b", 0.8)],  # different parent (shouldn't happen in real life)
            k=5,
        )
        # Keeps the first-seen parent
        assert out[0][1] == "parent_a"


class TestMixedModalityQuery:
    def test_different_modalities_weighted_independently(self):
        """A mixed-modality query where CODE and PDF hits tie in rank but
        the hybrid weight pushes them to different fused scores."""
        modality_map = {
            "s_code": Modality.CODE,  # (0.2, 0.8)
            "s_pdf": Modality.PDF_DIGITAL,  # (0.6, 0.4)
        }
        # Both at rank 1 in dense
        out = hybrid_fuse(
            [("s_code", "pc", 0.9), ("s_pdf", "pp", 0.8)],
            [],
            k=5,
            modality_map=modality_map,
        )
        score_by_sid = {sid: sc for sid, _, sc in out}
        # s_pdf (dense weight 0.6) should beat s_code (dense weight 0.2)
        assert score_by_sid["s_pdf"] > score_by_sid["s_code"]
