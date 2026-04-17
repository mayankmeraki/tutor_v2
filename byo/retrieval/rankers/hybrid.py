"""Hybrid fusion — RRF (Reciprocal Rank Fusion) of dense + sparse results.

RRF formula (per hit): score = sum over rankers of weight / (k_rrf + rank),
where rank is 1-indexed and k_rrf=60 is the usual constant.

Modality weights: different content types benefit from different
dense/sparse mixes (code is mostly symbolic; digital PDFs benefit from
semantics; OCR'd / handwritten lean on exact terms extracted by OCR).

Mixed-modality handling: a single query spans many modalities in the
user's corpus. Rather than computing one global weight, we apply the
weight *per hit* based on that hit's modality (`modality_map`, a
pre-fetched {segment_id: modality} dict). Hits without a known modality
fall back to the default (0.5, 0.5).
"""

from __future__ import annotations

from typing import Iterable

from byo.shared.models import Modality


RRF_K = 60

# (dense_weight, sparse_weight) per modality
DEFAULT_MODALITY_WEIGHTS: dict[Modality, tuple[float, float]] = {
    Modality.PDF_DIGITAL: (0.6, 0.4),
    Modality.PDF_SCANNED: (0.3, 0.7),
    Modality.HANDWRITTEN: (0.3, 0.7),
    Modality.SLIDES: (0.5, 0.5),
    Modality.VIDEO: (0.7, 0.3),
    Modality.AUDIO: (0.7, 0.3),
    Modality.IMAGE: (0.4, 0.6),
    Modality.TEXT: (0.6, 0.4),
    Modality.WEBPAGE: (0.6, 0.4),
    Modality.CODE: (0.2, 0.8),
}
DEFAULT_FALLBACK_WEIGHT: tuple[float, float] = (0.5, 0.5)


def _weights_for(
    modality: Modality | None,
    overrides: dict[Modality, tuple[float, float]] | None,
) -> tuple[float, float]:
    if modality is None:
        return DEFAULT_FALLBACK_WEIGHT
    if overrides and modality in overrides:
        return overrides[modality]
    return DEFAULT_MODALITY_WEIGHTS.get(modality, DEFAULT_FALLBACK_WEIGHT)


def hybrid_fuse(
    dense_results: list[tuple[str, str, float]],
    sparse_results: list[tuple[str, str, float]],
    *,
    k: int,
    modality_map: dict[str, Modality | None] | None = None,
    modality_weights: dict[Modality, tuple[float, float]] | None = None,
) -> list[tuple[str, str, float]]:
    """Fuse dense + sparse rankings with per-modality weighted RRF.

    Args:
      dense_results:  [(segment_id, parent_chunk_id, score)]
      sparse_results: same shape
      k:              desired output size
      modality_map:   {segment_id: Modality | None} — used to weight each hit.
                      If omitted, uses the fallback weight for every hit.
      modality_weights: override table {Modality: (dense_w, sparse_w)}.

    Returns: [(segment_id, parent_chunk_id, fused_score)] sorted desc,
    truncated to `k`.
    """
    modality_map = modality_map or {}

    # seg_id -> (parent_id, fused_score)
    scores: dict[str, tuple[str, float]] = {}

    def _accumulate(
        hits: Iterable[tuple[str, str, float]],
        channel: str,
    ) -> None:
        for rank, (seg_id, parent_id, _score) in enumerate(hits, start=1):
            modality = modality_map.get(seg_id)
            dense_w, sparse_w = _weights_for(modality, modality_weights)
            weight = dense_w if channel == "dense" else sparse_w
            contribution = weight / (RRF_K + rank)
            prev_parent, prev_score = scores.get(seg_id, (parent_id, 0.0))
            # Keep first-seen parent_id — both rankers must agree anyway
            scores[seg_id] = (prev_parent or parent_id, prev_score + contribution)

    _accumulate(dense_results, "dense")
    _accumulate(sparse_results, "sparse")

    fused = [(sid, pid, sc) for sid, (pid, sc) in scores.items()]
    fused.sort(key=lambda t: t[2], reverse=True)
    return fused[:k]
