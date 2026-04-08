"""Anthropic SDK provider — client, message prep, response wrapping, stream."""

from __future__ import annotations

import logging
import time

from app.core.config import settings
from .types import (
    ContentBlock, Usage, LLMResponse,
    LLMBadRequestError, LLMAuthError, LLMRateLimitError,
    LLMConnectionError, LLMOverloadedError,
    _notify_usage,
)

log = logging.getLogger(__name__)

_anthropic_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic

        _anthropic_client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
    return _anthropic_client


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


# ── Message prep ─────────────────────────────────────────────────────────────


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


def _build_anthropic_system(system) -> str | list[dict]:
    """Convert system prompt to Anthropic format with cache_control.

    If system is a tuple (static, dynamic), returns a list of content blocks
    with cache_control on the static part. Otherwise returns the string as-is.
    """
    if isinstance(system, tuple) and len(system) == 2:
        static_part, dynamic_part = system
        blocks = [
            {"type": "text", "text": static_part, "cache_control": {"type": "ephemeral"}},
        ]
        if dynamic_part and dynamic_part.strip():
            blocks.append({"type": "text", "text": dynamic_part})
        return blocks
    return system if isinstance(system, str) else str(system)


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


# ── Stream wrapper ───────────────────────────────────────────────────────────


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
            "LLM stream complete",
            extra={
                "model": response.model,
                "tokens_in": response.usage.input_tokens,
                "tokens_out": response.usage.output_tokens,
                "duration_ms": round(elapsed),
                "stop_reason": response.stop_reason,
                "provider": "anthropic",
            },
        )
        _notify_usage(response, getattr(self, '_metadata', None))
        return response

