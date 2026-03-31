"""Text processor — handles plain text, markdown, and URLs."""

from __future__ import annotations

import logging
from typing import Any

from byo.models import ProcessResult
from byo.pipeline.processors.base import BaseProcessor

log = logging.getLogger(__name__)


class TextProcessor(BaseProcessor):
    supported_types = ["text/*", "application/json", "application/xml"]

    async def extract(
        self,
        resource_id: str,
        mime_type: str,
        source_url: str | None,
        storage_path: str | None,
        meta: dict[str, Any],
    ) -> ProcessResult:
        text = ""

        # URL — fetch the page
        if source_url and not storage_path:
            text = await self._fetch_url(source_url)
        # File
        elif storage_path:
            try:
                with open(storage_path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception as e:
                return ProcessResult(markdown="", meta={"error": str(e)})
        # Inline text (passed in meta)
        elif meta.get("text"):
            text = meta["text"]

        if not text:
            return ProcessResult(markdown="", meta={"error": "No text content"})

        doc_meta = {
            "char_count": len(text),
            "line_count": text.count("\n") + 1,
        }

        log.info("Text extracted: %s — %d chars", resource_id[:8], len(text))
        return ProcessResult(markdown=text, meta=doc_meta)

    async def _fetch_url(self, url: str) -> str:
        """Fetch and extract text from a URL."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Capacity/1.0)"
                })
                if resp.status_code != 200:
                    return ""

                content_type = resp.headers.get("content-type", "")

                # HTML — extract text
                if "html" in content_type:
                    return self._extract_html(resp.text)

                # Plain text
                return resp.text

        except Exception as e:
            log.warning("URL fetch failed for %s: %s", url[:60], e)
            return ""

    @staticmethod
    def _extract_html(html: str) -> str:
        """Extract readable text from HTML. Simple approach — strip tags."""
        import re
        # Remove script, style, nav, header, footer
        html = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        # Remove all tags
        text = re.sub(r"<[^>]+>", " ", html)
        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()
        # Decode HTML entities
        import html as html_mod
        text = html_mod.unescape(text)
        return text
