"""Unified LLM client — single-provider streaming via OpenRouter.

All LLM calls route through llm_call() or llm_stream(). The provider
is selected by settings.LLM_PROVIDER ("anthropic" or "openrouter").
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.core.config import settings

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

# Pricing per million tokens (USD) — update when models change
# Source: https://openrouter.ai/models
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


# ── Client singletons ───────────────────────────────────────────────────────

_anthropic_client = None
_openrouter_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic

        _anthropic_client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
    return _anthropic_client


def _get_openrouter_client():
    global _openrouter_client
    if _openrouter_client is None:
        import openai

        _openrouter_client = openai.AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            default_headers={
                "HTTP-Referer": "https://capacity.app",
                "X-Title": "Capacity Tutor",
            },
        )
    return _openrouter_client


# ── Response wrapping ────────────────────────────────────────────────────────


def _wrap_anthropic_response(response) -> LLMResponse:
    content = []
    for block in response.content:
        if block.type == "text":
            content.append(ContentBlock(type="text", text=block.text))
        elif block.type == "tool_use":
            content.append(
                ContentBlock(
                    type="tool_use",
                    id=block.id,
                    name=block.name,
                    input=block.input,
                )
            )
    return LLMResponse(
        content=content,
        stop_reason=response.stop_reason,
        usage=Usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        ),
        model=response.model,
    )


def _wrap_openai_response(response) -> LLMResponse:
    choice = response.choices[0]
    message = choice.message

    content: list[ContentBlock] = []
    if message.content:
        content.append(ContentBlock(type="text", text=message.content))
    if message.tool_calls:
        for tc in message.tool_calls:
            try:
                tool_input = (
                    json.loads(tc.function.arguments)
                    if tc.function.arguments
                    else {}
                )
            except json.JSONDecodeError:
                log.warning(
                    "Failed to parse tool arguments: %s",
                    tc.function.arguments[:200],
                )
                tool_input = {}
            content.append(
                ContentBlock(
                    type="tool_use",
                    id=tc.id,
                    name=tc.function.name,
                    input=tool_input,
                )
            )

    # Extract cost from OpenRouter's usage.cost field (USD)
    cost_usd = None
    if response.usage:
        # OpenRouter returns cost in usage object
        cost_usd = getattr(response.usage, 'cost', None)

    return LLMResponse(
        content=content,
        stop_reason=_convert_finish_reason(choice.finish_reason),
        usage=Usage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=(
                response.usage.completion_tokens if response.usage else 0
            ),
            cost_usd=cost_usd,
        ),
        model=response.model,
    )


def _convert_finish_reason(reason: str | None) -> str:
    return {
        "stop": "end_turn",
        "tool_calls": "tool_use",
        "length": "max_tokens",
        "content_filter": "end_turn",
    }.get(reason or "stop", "end_turn")


# ── Message / tool conversion ────────────────────────────────────────────────


def _prepare_messages_anthropic(messages: list[dict]) -> list[dict]:
    """Convert ContentBlock objects in messages to dicts for the Anthropic SDK."""
    result = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            new_content = []
            for block in content:
                if isinstance(block, ContentBlock):
                    new_content.append(block.to_dict())
                elif isinstance(block, dict):
                    new_content.append(block)
                elif hasattr(block, "type"):
                    # Legacy SDK objects — convert to dict
                    d: dict = {"type": block.type}
                    if block.type == "text" and hasattr(block, "text"):
                        d["text"] = block.text
                    elif block.type == "tool_use":
                        d["id"] = block.id
                        d["name"] = block.name
                        d["input"] = block.input
                    new_content.append(d)
                else:
                    new_content.append(block)
            result.append({**msg, "content": new_content})
        else:
            result.append(msg)
    return result


def _convert_messages_openrouter(
    system: str | tuple, messages: list[dict]
) -> list[dict]:
    """Convert Anthropic-format messages to OpenAI/OpenRouter format.

    system can be:
      - str: single system message (entire prompt cached as one block)
      - tuple (static, dynamic): two content blocks — static is cached, dynamic is not
    """
    result: list[dict] = []
    if system:
        if isinstance(system, tuple) and len(system) == 2:
            # Split prompt: static (cached) + dynamic (not cached)
            static_part, dynamic_part = system
            content_blocks = [
                {
                    "type": "text",
                    "text": static_part,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
            if dynamic_part and dynamic_part.strip():
                content_blocks.append({
                    "type": "text",
                    "text": dynamic_part,
                })
            result.append({"role": "system", "content": content_blocks})
        else:
            # Single string — cache the whole thing
            system_text = system if isinstance(system, str) else str(system)
            result.append({
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": system_text,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            })

    for msg in messages:
        role = msg["role"]
        content = msg.get("content")

        if role == "user":
            if isinstance(content, str):
                result.append({"role": "user", "content": content})
            elif isinstance(content, list):
                tool_results = []
                text_parts = []
                image_parts = []
                for block in content:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "tool_result"
                    ):
                        tool_results.append(block)
                    elif (
                        isinstance(block, dict)
                        and block.get("type") == "text"
                    ):
                        text_parts.append(block.get("text", ""))
                    elif (
                        isinstance(block, dict)
                        and block.get("type") == "image"
                    ):
                        # Convert Anthropic image format to OpenAI/OpenRouter format
                        source = block.get("source", {})
                        if source.get("type") == "base64":
                            media = source.get("media_type", "image/png")
                            data = source.get("data", "")
                            image_parts.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{media};base64,{data}"},
                            })
                        elif source.get("type") == "url":
                            image_parts.append({
                                "type": "image_url",
                                "image_url": {"url": source.get("url", "")},
                            })
                    elif (
                        isinstance(block, ContentBlock)
                        and block.type == "text"
                    ):
                        text_parts.append(block.text or "")

                if tool_results:
                    for tr in tool_results:
                        tc_content = tr.get("content", "")
                        if isinstance(tc_content, list):
                            parts = []
                            for p in tc_content:
                                if (
                                    isinstance(p, dict)
                                    and p.get("type") == "text"
                                ):
                                    parts.append(p.get("text", ""))
                            tc_content = "\n".join(parts) or "(no output)"
                        result.append(
                            {
                                "role": "tool",
                                "tool_call_id": tr.get("tool_use_id", ""),
                                "content": (
                                    tc_content
                                    if isinstance(tc_content, str)
                                    else str(tc_content)
                                ),
                            }
                        )
                    # Also include any text parts as a user message
                    if text_parts:
                        result.append(
                            {"role": "user", "content": "\n".join(text_parts)}
                        )

                # Build multipart content if we have images
                if image_parts:
                    multipart = []
                    for ip in image_parts:
                        multipart.append(ip)
                    if text_parts:
                        multipart.append({"type": "text", "text": "\n".join(text_parts)})
                    elif not tool_results:
                        multipart.append({"type": "text", "text": "[Image sent by student]"})
                    if not tool_results:
                        result.append({"role": "user", "content": multipart})
                    else:
                        # Images after tool results — add as separate user message
                        result.append({"role": "user", "content": multipart})
                elif text_parts and not tool_results:
                    result.append(
                        {"role": "user", "content": "\n".join(text_parts)}
                    )
                elif not tool_results:
                    result.append({"role": "user", "content": "."})
            else:
                result.append(
                    {
                        "role": "user",
                        "content": str(content) if content else ".",
                    }
                )

        elif role == "assistant":
            if isinstance(content, str):
                result.append({"role": "assistant", "content": content})
            elif isinstance(content, list):
                text_parts = []
                tool_calls = []
                for block in content:
                    btype = None
                    if isinstance(block, ContentBlock):
                        btype = block.type
                        if btype == "text" and block.text:
                            text_parts.append(block.text)
                        elif btype == "tool_use":
                            tool_calls.append(
                                {
                                    "id": block.id,
                                    "type": "function",
                                    "function": {
                                        "name": block.name,
                                        "arguments": json.dumps(
                                            block.input or {}
                                        ),
                                    },
                                }
                            )
                    elif isinstance(block, dict):
                        btype = block.get("type")
                        if btype == "text" and block.get("text"):
                            text_parts.append(block["text"])
                        elif btype == "tool_use":
                            tool_calls.append(
                                {
                                    "id": block.get("id", ""),
                                    "type": "function",
                                    "function": {
                                        "name": block.get("name", ""),
                                        "arguments": json.dumps(
                                            block.get("input", {})
                                        ),
                                    },
                                }
                            )
                    elif hasattr(block, "type"):
                        # Legacy SDK objects
                        btype = block.type
                        if (
                            btype == "text"
                            and hasattr(block, "text")
                            and block.text
                        ):
                            text_parts.append(block.text)
                        elif btype == "tool_use":
                            tool_calls.append(
                                {
                                    "id": block.id,
                                    "type": "function",
                                    "function": {
                                        "name": block.name,
                                        "arguments": json.dumps(
                                            block.input or {}
                                        ),
                                    },
                                }
                            )

                msg_dict: dict = {"role": "assistant"}
                text = "\n".join(text_parts) if text_parts else None
                msg_dict["content"] = text
                if tool_calls:
                    msg_dict["tool_calls"] = tool_calls
                result.append(msg_dict)
            else:
                result.append(
                    {
                        "role": "assistant",
                        "content": str(content) if content else None,
                    }
                )

    return result


def _convert_tools_openrouter(tools: list[dict]) -> list[dict]:
    """Convert Anthropic tool format to OpenAI function format."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            },
        }
        for tool in tools
    ]


def _convert_tool_choice_openrouter(choice: dict | None) -> dict | str | None:
    """Convert Anthropic tool_choice to OpenAI format."""
    if choice is None:
        return None
    tc_type = choice.get("type", "auto")
    if tc_type == "tool":
        return {"type": "function", "function": {"name": choice["name"]}}
    if tc_type == "any":
        return "required"
    return "auto"


def _prefix_model(model: str) -> str:
    """Add anthropic/ prefix for OpenRouter if not already present."""
    if "/" not in model:
        return f"anthropic/{model}"
    return model


# ── Error translation ────────────────────────────────────────────────────────


def _translate_anthropic_error(e: Exception) -> Exception:
    import anthropic

    if isinstance(e, anthropic.BadRequestError):
        return LLMBadRequestError(str(e), body=getattr(e, "body", None))
    if isinstance(e, anthropic.AuthenticationError):
        return LLMAuthError(str(e))
    if isinstance(e, anthropic.RateLimitError):
        return LLMRateLimitError(str(e))
    if isinstance(e, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return LLMConnectionError(str(e))
    if isinstance(e, anthropic.InternalServerError):
        return LLMOverloadedError(str(e))
    return e


def _translate_openai_error(e: Exception) -> Exception:
    import openai

    if isinstance(e, openai.BadRequestError):
        return LLMBadRequestError(str(e), body=getattr(e, "body", None))
    if isinstance(e, openai.AuthenticationError):
        return LLMAuthError(str(e))
    if isinstance(e, openai.RateLimitError):
        return LLMRateLimitError(str(e))
    if isinstance(e, (openai.APIConnectionError, openai.APITimeoutError)):
        return LLMConnectionError(str(e))
    if isinstance(e, openai.InternalServerError):
        return LLMOverloadedError(str(e))
    return e


def _translate_error(e: Exception) -> Exception:
    """Route to the appropriate provider error translator."""
    if settings.LLM_PROVIDER == "openrouter":
        return _translate_openai_error(e)
    return _translate_anthropic_error(e)


# ── Stream wrappers ──────────────────────────────────────────────────────────


class AnthropicLLMStream:
    """Wraps anthropic.AsyncMessageStream to return LLMResponse."""

    def __init__(self, raw_context_manager):
        self._raw = raw_context_manager
        self._stream = None
        self._start_time: float | None = None

    async def __aenter__(self):
        self._start_time = time.monotonic()
        try:
            self._stream = await self._raw.__aenter__()
        except Exception as e:
            translated = _translate_anthropic_error(e)
            if translated is not e:
                raise translated from e
            raise
        return self

    async def __aexit__(self, *args):
        await self._raw.__aexit__(*args)

    @property
    def text_stream(self):
        return self._text_stream_gen()

    async def _text_stream_gen(self):
        try:
            async for text in self._stream.text_stream:
                yield text
        except GeneratorExit:
            return
        except Exception as e:
            translated = _translate_anthropic_error(e)
            if translated is not e:
                raise translated from e
            raise

    async def get_final_message(self) -> LLMResponse:
        raw_msg = await self._stream.get_final_message()
        response = _wrap_anthropic_response(raw_msg)
        elapsed = (
            (time.monotonic() - self._start_time) * 1000
            if self._start_time
            else 0
        )
        log.info(
            "LLM %s stream — %din/%dout, %.0fms, stop=%s",
            response.model,
            response.usage.input_tokens,
            response.usage.output_tokens,
            elapsed,
            response.stop_reason,
        )
        _notify_usage(response, getattr(self, '_metadata', None))
        return response


class OpenRouterLLMStream:
    """Wraps OpenAI streaming to match the Anthropic stream interface."""

    def __init__(self, client, model: str, **kwargs):
        self._client = client
        self._model = model
        self._kwargs = kwargs
        self._raw = None
        self._start_time: float | None = None
        self._accumulated_text = ""
        self._tool_calls: dict[int, dict] = {}
        self._finish_reason: str | None = None
        self._usage = None

    async def __aenter__(self):
        self._start_time = time.monotonic()
        try:
            self._raw = await self._client.chat.completions.create(
                model=self._model,
                stream=True,
                stream_options={"include_usage": True},
                **self._kwargs,
            )
        except Exception as e:
            translated = _translate_openai_error(e)
            if translated is not e:
                raise translated from e
            raise
        return self

    async def __aexit__(self, *args):
        if self._raw and hasattr(self._raw, "close"):
            await self._raw.close()

    @property
    def text_stream(self):
        return self._text_stream_gen()

    async def _text_stream_gen(self):
        try:
            async for chunk in self._raw:
                # Usage-only chunk (no choices)
                if not chunk.choices:
                    if chunk.usage:
                        self._usage = chunk.usage
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                # Text content
                if delta and delta.content:
                    self._accumulated_text += delta.content
                    yield delta.content

                # Tool call deltas
                if delta and delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in self._tool_calls:
                            self._tool_calls[idx] = {
                                "id": "",
                                "name": "",
                                "arguments": "",
                            }
                        if tc.id:
                            self._tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                self._tool_calls[idx]["name"] = (
                                    tc.function.name
                                )
                            if tc.function.arguments:
                                self._tool_calls[idx]["arguments"] += (
                                    tc.function.arguments
                                )

                # Finish reason
                if choice.finish_reason:
                    self._finish_reason = choice.finish_reason

                # Usage
                if hasattr(chunk, "usage") and chunk.usage:
                    self._usage = chunk.usage
        except GeneratorExit:
            return
        except Exception as e:
            translated = _translate_openai_error(e)
            if translated is not e:
                raise translated from e
            raise

    async def get_final_message(self) -> LLMResponse:
        content: list[ContentBlock] = []
        if self._accumulated_text:
            content.append(
                ContentBlock(type="text", text=self._accumulated_text)
            )
        for idx in sorted(self._tool_calls.keys()):
            tc = self._tool_calls[idx]
            try:
                tool_input = (
                    json.loads(tc["arguments"]) if tc["arguments"] else {}
                )
            except json.JSONDecodeError:
                log.warning(
                    "Failed to parse tool arguments: %s",
                    tc["arguments"][:200],
                )
                tool_input = {}
            content.append(
                ContentBlock(
                    type="tool_use",
                    id=tc["id"],
                    name=tc["name"],
                    input=tool_input,
                )
            )

        stop_reason = _convert_finish_reason(self._finish_reason)

        usage_in = 0
        usage_out = 0
        cost_usd = None
        if self._usage:
            usage_in = getattr(self._usage, "prompt_tokens", 0) or 0
            usage_out = getattr(self._usage, "completion_tokens", 0) or 0
            cost_usd = getattr(self._usage, "cost", None)

        elapsed = (
            (time.monotonic() - self._start_time) * 1000
            if self._start_time
            else 0
        )
        log.info(
            "LLM %s stream — %din/%dout, %.0fms, stop=%s",
            self._model,
            usage_in,
            usage_out,
            elapsed,
            stop_reason,
        )

        response = LLMResponse(
            content=content,
            stop_reason=stop_reason,
            usage=Usage(input_tokens=usage_in, output_tokens=usage_out, cost_usd=cost_usd),
            model=self._model,
        )
        _notify_usage(response, getattr(self, '_metadata', None))
        return response


# ── Public API ───────────────────────────────────────────────────────────────


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
            "system": "\n\n".join(system) if isinstance(system, tuple) else system,
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
        "LLM %s call — %din/%dout, %.0fms, stop=%s",
        response.model,
        response.usage.input_tokens,
        response.usage.output_tokens,
        elapsed,
        response.stop_reason,
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
            "system": "\n\n".join(system) if isinstance(system, tuple) else system,
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


# ── Retry helpers ────────────────────────────────────────────────────────────


def is_retryable(exc: Exception) -> bool:
    """Check if an error is transient and worth retrying.

    Handles both generic LLM error types and provider-specific errors
    (for cases where errors bypass translation, e.g. during streaming).
    """
    import asyncio

    # Generic LLM errors
    if isinstance(
        exc, (LLMRateLimitError, LLMConnectionError, LLMOverloadedError)
    ):
        return True

    # Standard Python errors
    if isinstance(exc, (asyncio.TimeoutError, ConnectionError, TimeoutError)):
        return True

    # httpx transport errors (connection drops mid-stream)
    try:
        import httpx
        import httpcore
        if isinstance(exc, (httpx.ReadError, httpx.RemoteProtocolError, httpx.ConnectError)):
            return True
        if isinstance(exc, (httpcore.ReadError, httpcore.RemoteProtocolError, httpcore.ConnectError)):
            return True
    except ImportError:
        pass

    # Provider-specific (fallback for untranslated errors)
    try:
        import anthropic

        if isinstance(exc, anthropic.RateLimitError):
            return True
        if (
            isinstance(exc, anthropic.APIStatusError)
            and exc.status_code in (429, 529)
        ):
            return True
        if isinstance(
            exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)
        ):
            return True
        if isinstance(exc, anthropic.InternalServerError):
            return True
    except ImportError:
        pass

    try:
        import openai

        if isinstance(exc, openai.RateLimitError):
            return True
        if (
            isinstance(exc, openai.APIStatusError)
            and exc.status_code in (429, 529)
        ):
            return True
        if isinstance(
            exc, (openai.APIConnectionError, openai.APITimeoutError)
        ):
            return True
        if isinstance(exc, openai.InternalServerError):
            return True
    except ImportError:
        pass

    return False


def extract_retry_after(exc: Exception) -> float | None:
    """Extract Retry-After header from API errors.

    Checks the error itself and __cause__ (for wrapped LLM errors).
    """
    for err in (exc, getattr(exc, "__cause__", None)):
        if err is None:
            continue
        response = getattr(err, "response", None)
        if response is not None:
            headers = getattr(response, "headers", None)
            if headers:
                val = headers.get("retry-after")
                if val:
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        pass
    return None
