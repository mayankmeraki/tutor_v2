"""LLM types, errors, cost computation, usage tracking."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)


# ── Response dataclasses ─────────────────────────────────────────────────────


@dataclass
class ContentBlock:
    """Provider-agnostic content block (text or tool_use)."""

    type: str  # "text" or "tool_use"
    text: str | None = None  # for type="text"
    id: str | None = None  # for type="tool_use"
    name: str | None = None  # for type="tool_use"
    input: dict | None = None  # for type="tool_use"

    def to_dict(self) -> dict:
        if self.type == "text":
            return {"type": "text", "text": self.text or ""}
        if self.type == "tool_use":
            return {
                "type": "tool_use",
                "id": self.id,
                "name": self.name,
                "input": self.input or {},
            }
        return {"type": self.type}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None  # Actual cost from provider (OpenRouter returns this)


@dataclass
class LLMCallMetadata:
    """Metadata passed through LLM calls for tracking purposes."""
    session_id: str | None = None
    caller: str = ""          # e.g. "tutor", "planning", "assessment", "delegation", "visual_gen"
    agent_id: str | None = None


@dataclass
class LLMResponse:
    content: list[ContentBlock]
    stop_reason: str  # "end_turn", "tool_use", "max_tokens"
    usage: Usage
    model: str



# ── Cost computation ─────────────────────────────────────────────────────────

def _pricing_table() -> dict[str, tuple[float, float]]:
    """Build model pricing table from env-configured settings.

    Rebuilt on each call so tests/hot-reload pick up env overrides.
    Returns {model_id: (input_per_M, output_per_M)}.
    """
    from app.core.config import settings
    opus = (settings.PRICE_OPUS_INPUT, settings.PRICE_OPUS_OUTPUT)
    sonnet = (settings.PRICE_SONNET_INPUT, settings.PRICE_SONNET_OUTPUT)
    haiku45 = (settings.PRICE_HAIKU_45_INPUT, settings.PRICE_HAIKU_45_OUTPUT)
    haiku35 = (settings.PRICE_HAIKU_35_INPUT, settings.PRICE_HAIKU_35_OUTPUT)
    return {
        # Opus — primary Tutor model
        "claude-opus-4-6": opus,
        "anthropic/claude-opus-4-6": opus,
        "claude-opus-4.7": opus,
        "anthropic/claude-opus-4.7": opus,
        # Sonnet 4.6
        "claude-sonnet-4-6": sonnet,
        "anthropic/claude-sonnet-4-6": sonnet,
        # Haiku 4.5
        "claude-haiku-4-5-20251001": haiku45,
        "anthropic/claude-haiku-4-5-20251001": haiku45,
        "anthropic/claude-haiku-4.5": haiku45,
        "anthropic/claude-haiku-4-5": haiku45,
        # Haiku 3.5 — kept for reference
        "claude-haiku-3-5": haiku35,
        "anthropic/claude-haiku-3.5": haiku35,
    }


def compute_cost_cents(
    model: str,
    input_tokens: int,
    output_tokens: int,
    provider_cost_usd: float | None = None,
) -> float:
    """Compute LLM call cost in cents.

    Prefers the provider-reported cost (e.g. OpenRouter's usage.cost field)
    when available. Falls back to the token-based pricing table estimate.
    """
    # Use provider-reported cost if available (OpenRouter returns this)
    if provider_cost_usd is not None and provider_cost_usd > 0:
        return provider_cost_usd * 100  # USD to cents

    # Fallback: estimate from token counts + pricing table (from env config)
    from app.core.config import settings
    table = _pricing_table()
    pricing = table.get(model)
    if not pricing:
        base = model.rsplit("/", 1)[-1] if "/" in model else model
        pricing = table.get(base, (settings.PRICE_FALLBACK_INPUT, settings.PRICE_FALLBACK_OUTPUT))

    input_cost = (input_tokens / 1_000_000) * pricing[0]
    output_cost = (output_tokens / 1_000_000) * pricing[1]
    return (input_cost + output_cost) * 100  # USD to cents


# ── Usage tracking callback ──────────────────────────────────────────────────

# Global callback: called after every LLM response with (response, metadata).
# Set by the app layer to route usage into session cost tracking.
_usage_callback: Callable[[LLMResponse, LLMCallMetadata], None] | None = None


def set_usage_callback(cb: Callable[[LLMResponse, LLMCallMetadata], None] | None) -> None:
    """Register a global callback invoked after every LLM response."""
    global _usage_callback
    _usage_callback = cb


def _notify_usage(response: LLMResponse, metadata: LLMCallMetadata | None) -> None:
    """Fire the usage callback if registered."""
    if _usage_callback and metadata:
        try:
            _usage_callback(response, metadata)
        except Exception as e:
            log.warning("Usage callback error: %s", e)


# ── Error classes ────────────────────────────────────────────────────────────


class LLMError(Exception):
    """Base for all LLM errors."""


class LLMBadRequestError(LLMError):
    def __init__(self, message: str, body: dict | None = None):
        super().__init__(message)
        self.body = body


class LLMAuthError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMConnectionError(LLMError):
    pass


class LLMOverloadedError(LLMError):
    pass

