"""Data models for BYO materials.

Flexible schema — no assumptions about content type.
The processor discovers metadata; the tutor interprets it.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────


class ResourceStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class CollectionStatus(str, Enum):
    PROCESSING = "processing"
    PARTIAL = "partial"  # some resources ready, some still processing
    READY = "ready"


# ── Collection ─────────────────────────────────────────────────────────


class CollectionStats(BaseModel):
    resources: int = 0
    chunks: int = 0
    topics: list[str] = Field(default_factory=list)


class Collection(BaseModel):
    """A student's collection of study materials."""

    collection_id: str
    user_id: str
    title: str
    description: str = ""
    intent: str = ""  # free text: what the student wants to do
    status: CollectionStatus = CollectionStatus.PROCESSING
    stats: CollectionStats = Field(default_factory=CollectionStats)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Resource ───────────────────────────────────────────────────────────


class Resource(BaseModel):
    """One uploaded file or URL in a collection."""

    resource_id: str
    collection_id: str
    user_id: str

    # Source
    source_type: str  # "file", "url", "text"
    mime_type: str = ""  # "application/pdf", "video/mp4", etc.
    original_name: str = ""
    source_url: str | None = None  # YouTube URL, article URL
    storage_path: str | None = None  # local or GCS path
    file_size: int = 0

    # Processing
    status: ResourceStatus = ResourceStatus.QUEUED
    progress: float = 0.0  # 0-1
    error: str | None = None

    # Discovered metadata (flexible — whatever the processor finds)
    meta: dict[str, Any] = Field(default_factory=dict)
    # Examples:
    #   PDF:   {"pages": 45, "has_images": True, "language": "en", "structure": [...]}
    #   Video: {"duration": 1800, "has_transcript": True, "language": "en"}
    #   Image: {"width": 800, "height": 600, "description": "..."}

    chunk_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Chunk ──────────────────────────────────────────────────────────────


class ChunkAnchor(BaseModel):
    """Where this chunk came from in the original resource.
    Flexible — different resource types use different fields.
    """

    page: int | None = None  # PDF page number
    page_end: int | None = None  # PDF page range end
    start_time: float | None = None  # video timestamp (seconds)
    end_time: float | None = None
    section: str | None = None  # heading / chapter name
    paragraph: int | None = None


class ChunkAttachment(BaseModel):
    """Media attached to a chunk (extracted images, diagrams)."""

    type: str  # "image", "audio", "code"
    path: str  # storage path
    description: str = ""
    anchor: ChunkAnchor | None = None


class Chunk(BaseModel):
    """Universal searchable unit of content."""

    chunk_id: str
    collection_id: str
    resource_id: str
    index: int  # order within resource

    # Content
    content: str  # the actual text
    tokens: int = 0  # token count for budget management

    # Where it came from (for citation)
    anchor: ChunkAnchor = Field(default_factory=ChunkAnchor)

    # What the processor discovered (all auto-generated, flexible)
    labels: list[str] = Field(default_factory=list)
    # e.g. ["explanation", "formula", "exercise", "code", "diagram", "theorem", ...]
    topics: list[str] = Field(default_factory=list)
    # e.g. ["rate_law", "kinetics", "binary_tree", ...]

    # Attached media
    attachments: list[ChunkAttachment] = Field(default_factory=list)

    # Search (populated during embedding step)
    embedding: list[float] | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Processing pipeline models ─────────────────────────────────────────


class ProcessResult(BaseModel):
    """Output from a processor's extract step."""

    markdown: str  # extracted text in markdown format
    meta: dict[str, Any] = Field(default_factory=dict)
    images: list[dict[str, Any]] = Field(default_factory=list)
    # [{"path": "...", "description": "...", "anchor": {...}}]


class ChunkClassification(BaseModel):
    """Output from the classifier for one chunk."""

    labels: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


# ── Orchestrator handoff models ────────────────────────────────────────


class SourceRef(BaseModel):
    """Reference to a content source (course lesson or BYO chunk)."""

    type: str  # "course_lesson", "byo_chunk", "web"
    id: str  # lesson_id or chunk_id
    title: str = ""
    anchor: ChunkAnchor | None = None
    snippet: str = ""  # pre-fetched content for tutor context


class MediaRef(BaseModel):
    """Reference to a video segment or image."""

    type: str  # "video_segment", "image", "pdf_page"
    resource_id: str
    title: str = ""
    start_time: float | None = None
    end_time: float | None = None
    page: int | None = None
    path: str = ""
    description: str = ""


class PlanStep(BaseModel):
    """One step in a teaching plan."""

    title: str
    type: str = "teach"  # "teach", "practice", "assess", "watch", "review"
    content_refs: list[SourceRef] = Field(default_factory=list)
    media_refs: list[MediaRef] = Field(default_factory=list)
    snippet: str = ""  # pre-fetched content
    teaching_notes: str = ""  # instructions for the tutor
    estimated_minutes: int = 10


class TutorSessionContext(BaseModel):
    """The enriched context the Orchestrator passes to the Tutor.

    This is the contract between Orchestrator and Tutor.
    """

    # What to do
    skill: str = "free"  # "course_follow", "exam_prep", "homework_help", "watch_along", "free"
    mode: str = "teaching"  # "teaching", "watch_along", "quiz"
    enriched_intent: str = ""  # natural language description for the tutor

    # Plan (if Orchestrator built one — Tutor's planner is optional when this exists)
    plan: list[PlanStep] = Field(default_factory=list)

    # Content sources
    course_id: int | None = None
    collection_id: str | None = None
    sources: list[SourceRef] = Field(default_factory=list)
    preloaded_snippets: dict[str, str] = Field(default_factory=dict)  # ref_id → content

    # Student context
    student_model: dict[str, Any] = Field(default_factory=dict)
    session_history: list[dict[str, Any]] = Field(default_factory=list)
    teaching_notes: str = ""  # from Orchestrator: "Student confuses X with Y"
    prerequisite_gaps: list[str] = Field(default_factory=list)

    # Analysis (if Orchestrator did pre-analysis)
    exam_analysis: dict[str, Any] | None = None

    # Resume state
    resume_state: dict[str, Any] | None = None


# ── Artifact models ────────────────────────────────────────────────────


class Artifact(BaseModel):
    """Something the Orchestrator creates for the student."""

    artifact_id: str
    user_id: str
    type: str  # "flashcards", "revision_notes", "study_plan", "summary", "curriculum"
    title: str
    content: dict[str, Any] = Field(default_factory=dict)
    # type-specific content:
    #   flashcards: {"cards": [{"front": "...", "back": "...", "tags": [...]}]}
    #   revision_notes: {"markdown": "..."}
    #   study_plan: {"sessions": [TutorSessionContext, ...]}
    #   summary: {"text": "..."}
    source: dict[str, Any] = Field(default_factory=dict)
    # {"collection_id": "...", "course_id": 2, "resource_ids": [...]}
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
