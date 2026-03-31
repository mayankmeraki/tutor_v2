"""Image processor — uses Vision LLM to describe images."""

from __future__ import annotations

import base64
import logging
from typing import Any

from byo.models import ProcessResult
from byo.pipeline.processors.base import BaseProcessor

log = logging.getLogger(__name__)


class ImageProcessor(BaseProcessor):
    supported_types = ["image/*"]

    async def extract(
        self,
        resource_id: str,
        mime_type: str,
        source_url: str | None,
        storage_path: str | None,
        meta: dict[str, Any],
    ) -> ProcessResult:
        if not storage_path:
            return ProcessResult(markdown="", meta={"error": "No image file"})

        try:
            # Read image as base64
            with open(storage_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")

            # Use Vision LLM to describe the image
            description = await self._describe_image(img_data, mime_type)

            doc_meta = {
                "description": description,
                "mime_type": mime_type,
            }

            markdown = f"# Image\n\n{description}"

            log.info("Image described: %s — %d chars", resource_id[:8], len(description))

            return ProcessResult(
                markdown=markdown,
                meta=doc_meta,
                images=[{"path": storage_path, "description": description}],
            )

        except Exception as e:
            log.error("Image processing failed for %s: %s", resource_id[:8], e)
            return ProcessResult(markdown="", meta={"error": str(e)})

    async def _describe_image(self, img_base64: str, mime_type: str) -> str:
        """Use Haiku Vision to describe an image."""
        try:
            import httpx
            from backend.app.core.config import settings

            api_key = settings.OPENROUTER_API_KEY
            if not api_key:
                return "[Image — no API key for description]"

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "anthropic/claude-haiku-4-5-20251001",
                        "max_tokens": 500,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{img_base64}"}},
                                {"type": "text", "text": (
                                    "Describe this image for a student studying from it. "
                                    "Include: what it shows, any text/equations visible, "
                                    "key concepts illustrated, and any data/values shown. "
                                    "Be concise but thorough."
                                )},
                            ],
                        }],
                    },
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]

            return "[Image description unavailable]"

        except Exception as e:
            log.warning("Image description failed: %s", e)
            return f"[Image — description failed: {str(e)[:50]}]"
