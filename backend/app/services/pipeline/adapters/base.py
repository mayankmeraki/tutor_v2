"""Abstract adapter interfaces for swappable pipeline providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Segment:
    text: str
    start: float
    end: float
    speaker: int | None = None
    confidence: float = 1.0


@dataclass
class OcrElement:
    type: str  # "equation", "text", "label", "diagram_desc"
    text: str
    confidence: float = 1.0


@dataclass
class OcrResult:
    text: str
    elements: list[OcrElement] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class FrameClassification:
    frame_index: int
    classification: str  # board, equation, diagram, slide, chart, table, talking_head, transition, other
    content_description: str = ""
    has_text: bool = False
    has_math: bool = False
    has_diagram: bool = False


class TranscriptionAdapter(ABC):
    @abstractmethod
    async def transcribe(self, audio_source: str) -> list[Segment]:
        ...


class OCRAdapter(ABC):
    @abstractmethod
    async def extract_text(self, image_bytes: bytes) -> OcrResult:
        ...


class VisionClassifierAdapter(ABC):
    @abstractmethod
    async def classify_frames(self, frames: list[bytes]) -> list[FrameClassification]:
        ...


class BlobStorageAdapter(ABC):
    @abstractmethod
    async def upload(self, data: bytes, path: str, content_type: str = "application/octet-stream") -> str:
        ...

    @abstractmethod
    async def download(self, path: str) -> bytes:
        ...

    @abstractmethod
    async def get_signed_url(self, path: str, expiry_minutes: int = 60) -> str:
        ...


class LLMAdapter(ABC):
    @abstractmethod
    async def complete(self, prompt: str, model: str = "haiku", max_tokens: int = 1000) -> str:
        ...

    @abstractmethod
    async def complete_with_vision(
        self, prompt: str, images: list[bytes], model: str = "haiku", max_tokens: int = 1000,
    ) -> str:
        ...


@dataclass
class PipelineAdapters:
    """Container for all adapter instances used by the pipeline."""
    llm: LLMAdapter
    vision: VisionClassifierAdapter
    ocr: OCRAdapter
    storage: BlobStorageAdapter
    transcription: TranscriptionAdapter
