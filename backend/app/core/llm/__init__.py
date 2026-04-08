"""Unified LLM client — provider-agnostic streaming.

All LLM calls route through llm_call() or llm_stream(). The provider
is selected by settings.LLM_PROVIDER ("anthropic" or "openrouter").
"""

from __future__ import annotations

import logging
import time

from app.core.config import settings

from .types import (
    ContentBlock,
    Usage,
    LLMCallMetadata,
    LLMResponse,
    LLMError,
    LLMBadRequestError,
    LLMAuthError,
    LLMRateLimitError,
    LLMConnectionError,
    LLMOverloadedError,
    compute_cost_cents,
    set_usage_callback,
    _notify_usage,
)
from .anthropic_provider import (
    _get_anthropic_client,
    _wrap_anthropic_response,
    _prepare_messages_anthropic,
    _build_anthropic_system,
    _translate_anthropic_error,
    AnthropicLLMStream,
)
from .openrouter_provider import (
    _get_openrouter_client,
    _wrap_openai_response,
    _convert_messages_openrouter,
    _convert_tools_openrouter,
    _convert_tool_choice_openrouter,
    _prefix_model,
    _translate_openai_error,
    OpenRouterLLMStream,
)
from .retry import is_retryable, extract_retry_after

log = logging.getLogger(__name__)


async def _llm_call_single(
    provider: str,
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int,
    tools: list[dict] | None,
    tool_choice: dict | None,
) -> LLMResponse:
    """Execute a non-streaming LLM call against a specific provider."""
    if provider == "anthropic":
        client = _get_anthropic_client()
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": _build_anthropic_system(system),
            "messages": _prepare_messages_anthropic(messages),
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        try:
            raw = await client.messages.create(**kwargs)
        except Exception as e:
            translated = _translate_anthropic_error(e)
            if translated is not e:
                raise translated from e
            raise
        return _wrap_anthropic_response(raw)

    elif provider == "openrouter":
        client = _get_openrouter_client()
        or_messages = _convert_messages_openrouter(system, messages)
        kwargs = {
            "model": _prefix_model(model),
            "max_tokens": max_tokens,
            "messages": or_messages,
            "extra_body": {
                "provider": {
                    "order": ["Anthropic"],
                    "allow_fallbacks": False,
                },
            },
        }
        if tools:
            kwargs["tools"] = _convert_tools_openrouter(tools)
        tc = _convert_tool_choice_openrouter(tool_choice)
        if tc is not None:
            kwargs["tool_choice"] = tc
        try:
            raw = await client.chat.completions.create(**kwargs)
        except Exception as e:
            translated = _translate_openai_error(e)
            if translated is not e:
                raise translated from e
            raise
        return _wrap_openai_response(raw)

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


async def llm_call(
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int = 4096,
    tools: list[dict] | None = None,
    tool_choice: dict | None = None,
    metadata: LLMCallMetadata | None = None,
) -> LLMResponse:
    """Non-streaming LLM call against the configured provider."""
    provider = settings.LLM_PROVIDER
    start = time.monotonic()

    response = await _llm_call_single(provider, model, system, messages, max_tokens, tools, tool_choice)

    elapsed = (time.monotonic() - start) * 1000
    log.info(
        "LLM call complete",
        extra={
            "model": response.model,
            "tokens_in": response.usage.input_tokens,
            "tokens_out": response.usage.output_tokens,
            "duration_ms": round(elapsed),
            "stop_reason": response.stop_reason,
            "provider": provider,
        },
    )
    _notify_usage(response, metadata)
    return response


def _build_stream(
    provider: str,
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int,
    tools: list[dict] | None,
    tool_choice: dict | None,
) -> AnthropicLLMStream | OpenRouterLLMStream:
    """Build a stream object for a specific provider (does not open it)."""
    if provider == "anthropic":
        client = _get_anthropic_client()
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": _build_anthropic_system(system),
            "messages": _prepare_messages_anthropic(messages),
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        raw = client.messages.stream(**kwargs)
        return AnthropicLLMStream(raw)

    elif provider == "openrouter":
        client = _get_openrouter_client()
        or_messages = _convert_messages_openrouter(system, messages)
        kwargs = {
            "messages": or_messages,
            "max_tokens": max_tokens,
            # Enable Anthropic prompt caching via OpenRouter provider config
            "extra_body": {
                "provider": {
                    "order": ["Anthropic"],
                    "allow_fallbacks": False,
                },
            },
        }
        if tools:
            kwargs["tools"] = _convert_tools_openrouter(tools)
        tc = _convert_tool_choice_openrouter(tool_choice)
        if tc is not None:
            kwargs["tool_choice"] = tc
        return OpenRouterLLMStream(client, _prefix_model(model), **kwargs)

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


async def llm_stream(
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int = 4096,
    tools: list[dict] | None = None,
    tool_choice: dict | None = None,
    metadata: LLMCallMetadata | None = None,
) -> AnthropicLLMStream | OpenRouterLLMStream:
    """Streaming LLM call against the configured provider."""
    provider = settings.LLM_PROVIDER
    stream = _build_stream(provider, model, system, messages, max_tokens, tools, tool_choice)
    stream._metadata = metadata
    return stream



__all__ = [
    "ContentBlock",
    "Usage",
    "LLMCallMetadata",
    "LLMResponse",
    "LLMError",
    "LLMBadRequestError",
    "LLMAuthError",
    "LLMRateLimitError",
    "LLMConnectionError",
    "LLMOverloadedError",
    "compute_cost_cents",
    "set_usage_callback",
    "llm_call",
    "llm_stream",
    "is_retryable",
    "extract_retry_after",
    "AnthropicLLMStream",
    "OpenRouterLLMStream",
]
