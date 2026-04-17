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


@runtime_checkable
class SupportsContentNearby(Protocol):
    """OPTIONAL capability — deterministic anchor walking around a ref.

    Kept as a separate Protocol so adapters that don't (yet) support
    anchor-walking still satisfy ``ContentProvider``. Callers should
    feature-detect with::

        if isinstance(provider, SupportsContentNearby):
            text = await provider.content_nearby(ref, window=1)

    or simply ``hasattr(provider, "content_nearby")``.

    NOTE: ``content_nearby`` is retrieval by ORDERED POSITION, not by
    semantic similarity — do not confuse it with ``content_search``.
    """

    async def content_nearby(self, ref: str, window: int = 1) -> str:
        """Deterministic anchor walk around a ref (NOT semantic search).

        Behavior (per adapter convention):
          - ``lesson:X:section:Y``: returns section Y together with the
            ``window`` sections on either side of it within the same lesson.
          - ``lesson:X``: returns the lesson overview + first section
            (``window`` is ignored — lesson refs don't have a linear
            neighbour axis beyond "first section").
          - ``sim:X`` / ``simulation:X``: returns the simulation details
            (same output as ``content_peek``; sims have no neighbours).

        Returns a formatted string in the same citation style as
        ``content_read`` / ``content_peek``.
        """
        ...
