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

_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_per_M, output_per_M)
    "claude-sonnet-4-6": (3.0, 15.0),
    "anthropic/claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
    "anthropic/claude-haiku-4-5-20251001": (0.80, 4.0),
    "anthropic/claude-haiku-4.5": (0.80, 4.0),
    # Fallback for unknown models
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

    # Fallback: estimate from token counts + pricing table
    pricing = _MODEL_PRICING.get(model)
    if not pricing:
        base = model.rsplit("/", 1)[-1] if "/" in model else model
        pricing = _MODEL_PRICING.get(base, (3.0, 15.0))  # default to sonnet pricing

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

