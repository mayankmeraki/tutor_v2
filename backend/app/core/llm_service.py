"""Unified LLM service — EVERY LLM/embed/TTS call in the codebase goes through here.

Usage:
    from app.core.llm_service import euler_llm

    # Non-streaming
    result = await euler_llm.call(
        model="fast",  # tier name or full model ID
        system="You are a tutor.",
        messages=[{"role": "user", "content": "hi"}],
        purpose="intent_classification",
        user_id="user@email.com",
    )
    print(result.text, result.usage)

    # Streaming
    async with await euler_llm.stream(
        model="heavy", system="...", messages=[...],
        purpose="tutor_teaching", user_id="...", session_id="...",
    ) as stream:
        async for delta in stream.text_stream:
            print(delta, end="")
        result = await stream.get_final_message()

    # Embedding
    vectors = await euler_llm.embed(texts=["hello"], user_id="...", resource_id="...")

    # TTS tracking
    await euler_llm.track_tts(char_count=500, user_id="...", session_id="...")

    # STT tracking
    await euler_llm.track_stt(duration_seconds=30, user_id="...", session_id="...")
"""

import logging
import time

from app.core.config import settings
from app.core.llm import (
    llm_call,
    llm_stream,
    LLMCallMetadata,
    LLMResponse,
)
from app.core.usage_tracker import (
    UsageEntry,
    compute_cost_usd,
    compute_tts_cost_usd,
    compute_stt_cost_usd,
    get_model_pricing,
    log_usage,
)

log = logging.getLogger(__name__)


def _resolve_model(model_or_tier: str) -> str:
    """Resolve a tier name ('fast', 'heavy') to a full model ID."""
    tier_map = {
        "heavy": settings.MODEL_HEAVY,
        "mid": settings.MODEL_MID,
        "fast": settings.MODEL_FAST,
        "nano": settings.MODEL_NANO,
        "tutor": settings.tutor_model,
        "planning": settings.planning_model,
        "research": settings.research_model,
        "summarization": settings.summarization_model,
        "embed": getattr(settings, "MODEL_EMBEDDING", "openai/text-embedding-3-small"),
    }
    return tier_map.get(model_or_tier, model_or_tier)


def _resp_text(resp: LLMResponse) -> str:
    """Extract text from LLMResponse content blocks."""
    return "".join(b.text for b in resp.content if b.type == "text" and b.text)


class EulerLLM:
    """Unified LLM service with automatic usage tracking."""

    async def call(
        self,
        model: str,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
        # ── Tracking context ──
        purpose: str = "unknown",
        user_id: str = "",
        session_id: str = "",
        path_id: str = "",
        resource_id: str = "",
        collection_id: str = "",
    ) -> LLMResponse:
        """Non-streaming LLM call with automatic tracking."""
        model_id = _resolve_model(model)
        start = time.monotonic()

        resp = await llm_call(
            model=model_id,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            metadata=LLMCallMetadata(session_id=session_id, caller=purpose),
        )

        elapsed_ms = int((time.monotonic() - start) * 1000)
        cost = compute_cost_usd(
            model_id=resp.model or model_id,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            provider_cost_usd=resp.usage.cost_usd,
        )

        await log_usage(UsageEntry(
            purpose=purpose,
            model=resp.model or model_id,
            call_type="llm",
            user_id=user_id,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            cost_usd=cost,
            duration_ms=elapsed_ms,
            session_id=session_id,
            path_id=path_id,
            resource_id=resource_id,
            collection_id=collection_id,
        ))

        return resp

    async def stream(
        self,
        model: str,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
        tool_choice: dict | None = None,
        # ── Tracking context ──
        purpose: str = "unknown",
        user_id: str = "",
        session_id: str = "",
        path_id: str = "",
        resource_id: str = "",
        collection_id: str = "",
    ):
        """Streaming LLM call. Returns a TrackedStream context manager.

        Usage:
            async with await euler_llm.stream(...) as stream:
                async for delta in stream.text_stream:
                    ...
                result = await stream.get_final_message()
        """
        model_id = _resolve_model(model)
        raw_stream = await llm_stream(
            model=model_id,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            metadata=LLMCallMetadata(session_id=session_id, caller=purpose),
        )
        return _TrackedStream(
            raw_stream, model_id=model_id, purpose=purpose,
            user_id=user_id, session_id=session_id, path_id=path_id,
            resource_id=resource_id, collection_id=collection_id,
        )

    async def call_raw(
        self,
        url: str,
        payload: dict,
        purpose: str = "unknown",
        user_id: str = "",
        resource_id: str = "",
        collection_id: str = "",
        model_id: str = "",
    ) -> dict:
        """Raw HTTP call (for BYO pipeline calls that don't use the unified client).
        Tracks usage from the response.
        """
        import httpx
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Extract usage from response
        usage = data.get("usage", {})
        in_tok = usage.get("prompt_tokens", 0)
        out_tok = usage.get("completion_tokens", 0)
        cached = usage.get("cache_read_input_tokens", 0) or usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
        actual_model = data.get("model", model_id)

        cost = compute_cost_usd(
            model_id=actual_model or model_id,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cached_tokens=cached,
        )

        await log_usage(UsageEntry(
            purpose=purpose,
            model=actual_model or model_id,
            call_type="llm",
            user_id=user_id,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cached_tokens=cached,
            cost_usd=cost,
            duration_ms=elapsed_ms,
            resource_id=resource_id,
            collection_id=collection_id,
        ))

        return data

    async def embed(
        self,
        texts: list[str],
        model: str = "embed",
        purpose: str = "byo_embedding",
        user_id: str = "",
        resource_id: str = "",
        collection_id: str = "",
    ) -> list[list[float]]:
        """Embedding call with tracking."""
        import httpx
        model_id = _resolve_model(model)
        start = time.monotonic()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"model": model_id, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()

        elapsed_ms = int((time.monotonic() - start) * 1000)
        usage = data.get("usage", {})
        in_tok = usage.get("prompt_tokens", 0) or usage.get("total_tokens", 0)

        cost = compute_cost_usd(model_id, in_tok, 0)
        await log_usage(UsageEntry(
            purpose=purpose,
            model=model_id,
            call_type="embed",
            user_id=user_id,
            input_tokens=in_tok,
            cost_usd=cost,
            duration_ms=elapsed_ms,
            resource_id=resource_id,
            collection_id=collection_id,
        ))

        return [item["embedding"] for item in data.get("data", [])]

    async def track_tts(
        self,
        char_count: int,
        user_id: str = "",
        session_id: str = "",
    ):
        """Track TTS usage (call this after TTS audio is generated)."""
        cost = compute_tts_cost_usd(char_count)
        await log_usage(UsageEntry(
            purpose="tts",
            model="elevenlabs/turbo_v2_5",
            call_type="tts",
            user_id=user_id,
            cost_usd=cost,
            session_id=session_id,
            extra={"charCount": char_count},
        ))

    async def track_stt(
        self,
        duration_seconds: float,
        user_id: str = "",
        session_id: str = "",
    ):
        """Track STT usage (call this after speech recognition completes)."""
        cost = compute_stt_cost_usd(duration_seconds)
        await log_usage(UsageEntry(
            purpose="stt",
            model="elevenlabs/scribe_v1",
            call_type="stt",
            user_id=user_id,
            cost_usd=cost,
            session_id=session_id,
            extra={"durationSeconds": round(duration_seconds, 1)},
        ))


class _TrackedStream:
    """Wraps an LLM stream to track usage after completion."""

    def __init__(self, raw_stream, **tracking_kwargs):
        self._raw = raw_stream
        self._tracking = tracking_kwargs
        self._start = time.monotonic()

    async def __aenter__(self):
        self._ctx = await self._raw.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self._raw.__aexit__(*args)

    @property
    def text_stream(self):
        return self._ctx.text_stream

    async def get_final_message(self) -> LLMResponse:
        resp = await self._ctx.get_final_message()
        elapsed_ms = int((time.monotonic() - self._start) * 1000)

        model_id = self._tracking.get("model_id", "")
        cost = compute_cost_usd(
            model_id=resp.model or model_id,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            provider_cost_usd=resp.usage.cost_usd,
        )

        await log_usage(UsageEntry(
            purpose=self._tracking.get("purpose", "unknown"),
            model=resp.model or model_id,
            call_type="llm",
            user_id=self._tracking.get("user_id", ""),
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            cost_usd=cost,
            duration_ms=elapsed_ms,
            session_id=self._tracking.get("session_id", ""),
            path_id=self._tracking.get("path_id", ""),
            resource_id=self._tracking.get("resource_id", ""),
            collection_id=self._tracking.get("collection_id", ""),
        ))

        return resp


# ── Singleton ─────────────────────────────────────────────────────
euler_llm = EulerLLM()
