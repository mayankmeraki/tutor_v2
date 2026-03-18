"""Anthropic LLM adapter — uses Claude models via the Anthropic SDK."""

from __future__ import annotations

import base64
import json
import logging

import anthropic

from app.core.config import settings

from .base import LLMAdapter

log = logging.getLogger(__name__)

MODEL_MAP = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-5-20250929",
}


class AnthropicLLMAdapter(LLMAdapter):
    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def complete(self, prompt: str, model: str = "haiku", max_tokens: int = 1000) -> str:
        model_id = MODEL_MAP.get(model, model)
        response = await self._client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    async def complete_with_vision(
        self, prompt: str, images: list[bytes], model: str = "haiku", max_tokens: int = 1000,
    ) -> str:
        model_id = MODEL_MAP.get(model, model)
        content: list[dict] = [{"type": "text", "text": prompt}]
        for img in images:
            b64 = base64.standard_b64encode(img).decode("ascii")
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
            })
        response = await self._client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text
