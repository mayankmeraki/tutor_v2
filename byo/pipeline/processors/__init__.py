"""Processor registry — maps MIME types to processing implementations.

Each processor extracts content from a specific file type and returns
a ProcessResult (markdown + metadata + images).

Adding a new file type = writing one processor class. Nothing else changes.
"""

from __future__ import annotations

import fnmatch
import logging
from typing import Protocol, Any

from byo.models import ProcessResult

log = logging.getLogger(__name__)


class Processor(Protocol):
    """Protocol for file processors."""

    supported_types: list[str]

    async def extract(
        self,
        resource_id: str,
        mime_type: str,
        source_url: str | None,
        storage_path: str | None,
        meta: dict[str, Any],
    ) -> ProcessResult:
        """Extract content from a resource.

        Returns ProcessResult with:
          - markdown: extracted text in markdown format
          - meta: discovered metadata (flexible dict)
          - images: extracted images with descriptions
        """
        ...


# ── Registry ──────────────────────────────────────────────────────────

_PROCESSOR_MAP: dict[str, type] = {}


def register_processor(patterns: list[str], cls: type):
    """Register a processor class for MIME type patterns."""
    for pattern in patterns:
        _PROCESSOR_MAP[pattern] = cls


def get_processor(mime_type: str) -> Processor:
    """Get the appropriate processor for a MIME type."""
    for pattern, cls in _PROCESSOR_MAP.items():
        if fnmatch.fnmatch(mime_type, pattern):
            return cls()

    # Fallback: try as text
    from byo.pipeline.processors.text import TextProcessor
    log.warning("No processor for %s, falling back to TextProcessor", mime_type)
    return TextProcessor()


# ── Register built-in processors ──────────────────────────────────────

def _register_builtins():
    from byo.pipeline.processors.pdf import PDFProcessor
    from byo.pipeline.processors.video import VideoProcessor
    from byo.pipeline.processors.text import TextProcessor
    from byo.pipeline.processors.image import ImageProcessor

    register_processor(["application/pdf"], PDFProcessor)
    register_processor(["video/*", "application/x-youtube"], VideoProcessor)
    register_processor(["text/*", "application/json", "application/xml"], TextProcessor)
    register_processor(["image/*"], ImageProcessor)


_register_builtins()
