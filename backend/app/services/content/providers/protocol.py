"""ContentProvider protocol — the contract all content adapters implement.

Four methods, all return formatted strings ready for the LLM context.
Adapters parse opaque ref strings (e.g. "lesson:3:section:2") and resolve
them against their backing store.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ContentProvider(Protocol):

    async def content_map(self) -> str:
        """Course/content structure overview. Called once at session start.

        Returns modules, lessons (with refs), timestamps, available resources.
        ~200-400 tokens.
        """
        ...

    async def content_read(self, ref: str) -> str:
        """Full content for a ref — transcript, key points, formulas.

        Use when grounding teaching in actual lecture content.
        ~500-800 tokens per section.
        """
        ...

    async def content_peek(self, ref: str) -> str:
        """Brief summary for a ref — title, concepts, teaching points.

        For lesson refs: returns section listing with refs.
        For section refs: returns compact teaching brief.
        ~50-150 tokens.
        """
        ...

    async def content_search(self, query: str, limit: int = 5) -> str:
        """Search across all content. Returns matches with refs for follow-up."""
        ...
