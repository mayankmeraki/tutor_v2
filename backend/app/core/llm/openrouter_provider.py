"""OpenRouter (OpenAI SDK) provider — client, message prep, response wrapping, stream."""

from __future__ import annotations

import json
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

_openrouter_client = None


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
                        isinstance(block, dict)
                        and block.get("type") in ("file", "input_audio", "video_url")
                    ):
                        # OpenRouter native formats — pass through as-is
                        # file: PDFs, docs | input_audio: wav/mp3 | video_url: mp4/webm
                        image_parts.append(block)
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


# ── Stream wrapper ───────────────────────────────────────────────────────────


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
        _first_chunk = True
        try:
            async for chunk in self._raw:
                if _first_chunk:
                    _first_chunk = False
                    log.info("LLM stream TTFB", extra={"model": self._model, "ttfb_ms": round((time.monotonic() - self._start_time) * 1000)})

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
        cached_tokens = 0
        if self._usage:
            usage_in = getattr(self._usage, "prompt_tokens", 0) or 0
            usage_out = getattr(self._usage, "completion_tokens", 0) or 0
            cost_usd = getattr(self._usage, "cost", None)
            # Extract cache metrics from prompt_tokens_details
            ptd = getattr(self._usage, "prompt_tokens_details", None)
            if ptd:
                cached_tokens = getattr(ptd, "cached_tokens", 0) or 0

        elapsed = (
            (time.monotonic() - self._start_time) * 1000
            if self._start_time
            else 0
        )
        cache_pct = round(cached_tokens / usage_in * 100) if usage_in > 0 and cached_tokens else 0
        log.info(
            "LLM stream complete",
            extra={
                "model": self._model,
                "tokens_in": usage_in,
                "tokens_out": usage_out,
                "cached_tokens": cached_tokens,
                "cache_hit_pct": cache_pct,
                "duration_ms": round(elapsed),
                "stop_reason": stop_reason,
                "provider": "openrouter",
            },
        )
        if cached_tokens > 0:
            log.info("Prompt cache HIT: %d/%d tokens cached (%d%%)", cached_tokens, usage_in, cache_pct)
        elif usage_in > 1000:
            log.warning("Prompt cache MISS: 0/%d tokens cached — check cache_control setup", usage_in)

        response = LLMResponse(
            content=content,
            stop_reason=stop_reason,
            usage=Usage(input_tokens=usage_in, output_tokens=usage_out, cost_usd=cost_usd),
            model=self._model,
        )
        _notify_usage(response, getattr(self, '_metadata', None))
        return response

