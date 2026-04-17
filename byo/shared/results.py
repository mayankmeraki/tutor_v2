"""Shared result types used across retrieval + processing.

Kept as plain dataclasses (not pydantic) — these are hot-path objects
and don't need validation on construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from byo.shared.models import ChunkAnchor, Modality, RetrievalMode


@dataclass
class RetrievedChunk:
    """One retrieval hit. Always carries the parent chunk content + anchor
    so the tutor can cite without a second lookup.
    """

    chunk_id: str  # parent chunk_id — the unit the LLM consumes
    segment_id: str  # child segment that matched
    resource_id: str
    collection_id: str

    content: str  # parent content (~800 tokens)
    anchor: ChunkAnchor
    score: float

    modality: Modality | None = None
    retrieval_mode: RetrievalMode | None = None
    topics: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)

    # Per-ranker score contributions (populated when hybrid+rerank used)
    dense_score: float | None = None
    sparse_score: float | None = None
    rerank_score: float | None = None

    # Provenance for debugging / eval
    source: str = "byo"  # "byo" | "course"
    resource_name: str = ""  # original_name for citation display


@dataclass
class RetrievedRef:
    """Lightweight hit — ref + snippet only. Used by list/peek paths."""

    ref: str  # "chunk:<id>" | "segment:<id>" | "resource:<id>"
    title: str
    snippet: str
    anchor: ChunkAnchor | None = None
    score: float = 0.0
    source: str = "byo"


@dataclass
class SearchFilters:
    """Filters applied at every ranker. user_id is MANDATORY for security."""

    user_id: str
    collection_id: str | None = None
    resource_id: str | None = None
    modality: list[Modality] | None = None
    retrieval_mode: list[RetrievalMode] | None = None
    topics: list[str] | None = None
    # Anchor filters (for nearby / time-local / page-local queries)
    page: int | None = None
    page_range: tuple[int, int] | None = None
    time_range: tuple[float, float] | None = None

    def to_mongo(self) -> dict[str, Any]:
        """Render as a MongoDB filter dict. Always includes user_id."""
        q: dict[str, Any] = {"user_id": self.user_id}
        if self.collection_id:
            q["collection_id"] = self.collection_id
        if self.resource_id:
            q["resource_id"] = self.resource_id
        if self.modality:
            q["modality"] = {"$in": [m.value for m in self.modality]}
        if self.retrieval_mode:
            q["retrieval_mode"] = {"$in": [m.value for m in self.retrieval_mode]}
        if self.topics:
            q["topics"] = {"$in": self.topics}
        if self.page is not None:
            q["anchor.page"] = self.page
        elif self.page_range:
            q["anchor.page"] = {"$gte": self.page_range[0], "$lte": self.page_range[1]}
        if self.time_range:
            lo, hi = self.time_range
            q["$or"] = [
                {"anchor.start_time": {"$gte": lo, "$lte": hi}},
                {"anchor.end_time": {"$gte": lo, "$lte": hi}},
                {"$and": [
                    {"anchor.start_time": {"$lte": lo}},
                    {"anchor.end_time": {"$gte": hi}},
                ]},
            ]
        return q
