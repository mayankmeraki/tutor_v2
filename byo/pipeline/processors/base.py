"""Base processor — shared utilities."""

from __future__ import annotations

import logging
from typing import Any

from byo.models import ProcessResult

log = logging.getLogger(__name__)


class BaseProcessor:
    """Base class with shared utilities for processors."""

    supported_types: list[str] = []

    async def extract(
        self,
        resource_id: str,
        mime_type: str,
        source_url: str | None,
        storage_path: str | None,
        meta: dict[str, Any],
    ) -> ProcessResult:
        raise NotImplementedError

    def _count_tokens(self, text: str) -> int:
        """Rough token count (4 chars per token)."""
        return len(text) // 4
