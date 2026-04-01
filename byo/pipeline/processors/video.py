"""Video processor — YouTube captions + Whisper fallback.

For YouTube URLs: uses youtube-transcript-api (free, fast, no download).
For uploaded videos: uses Whisper API for transcription.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from byo.models import ProcessResult
from byo.pipeline.processors.base import BaseProcessor

log = logging.getLogger(__name__)


class VideoProcessor(BaseProcessor):
    supported_types = ["video/*", "application/x-youtube"]

    async def extract(
        self,
        resource_id: str,
        mime_type: str,
        source_url: str | None,
        storage_path: str | None,
        meta: dict[str, Any],
    ) -> ProcessResult:
        # YouTube URL
        if source_url and ("youtube.com" in source_url or "youtu.be" in source_url):
            return await self._extract_youtube(source_url, resource_id)

        # Uploaded video file
        if storage_path:
            return await self._extract_whisper(storage_path, resource_id)

        return ProcessResult(markdown="", meta={"error": "No video source"})

    async def _extract_youtube(self, url: str, resource_id: str) -> ProcessResult:
        """Extract transcript from YouTube using captions API."""
        video_id = self._parse_youtube_id(url)
        if not video_id:
            return ProcessResult(markdown="", meta={"error": f"Could not parse YouTube ID from {url}"})

        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            import asyncio

            loop = asyncio.get_event_loop()
            transcript_list = await loop.run_in_executor(
                None, YouTubeTranscriptApi.get_transcript, video_id
            )

            # Build timestamped markdown
            segments = []
            for entry in transcript_list:
                start = entry["start"]
                text = entry["text"].strip()
                if text:
                    minutes = int(start // 60)
                    seconds = int(start % 60)
                    segments.append({
                        "timestamp": start,
                        "text": text,
                        "time_str": f"{minutes}:{seconds:02d}",
                    })

            # Build markdown with timestamp markers
            markdown_parts = []
            for seg in segments:
                markdown_parts.append(f"[{seg['time_str']}] {seg['text']}")

            markdown = "\n".join(markdown_parts)
            duration = segments[-1]["timestamp"] + 10 if segments else 0

            doc_meta = {
                "duration": duration,
                "has_transcript": True,
                "language": "en",
                "video_id": video_id,
                "source_url": url,
                "segment_count": len(segments),
                "segments": segments,  # keep raw segments for chunking
            }

            log.info("YouTube extracted: %s — %d segments, %.0f min",
                    resource_id[:8], len(segments), duration / 60)

            return ProcessResult(markdown=markdown, meta=doc_meta)

        except ImportError:
            log.error("youtube-transcript-api not installed")
            return ProcessResult(markdown="", meta={"error": "youtube-transcript-api not installed"})
        except Exception as e:
            log.error("YouTube extraction failed for %s: %s", resource_id[:8], e)
            return ProcessResult(markdown="", meta={"error": str(e)})

    async def _extract_whisper(self, file_path: str, resource_id: str) -> ProcessResult:
        """Transcribe uploaded video using Whisper API."""
        try:
            import httpx

            # Use OpenAI Whisper API via OpenRouter
            from app.core.config import settings
            api_key = settings.OPENROUTER_API_KEY or settings.ANTHROPIC_API_KEY

            if not api_key:
                return ProcessResult(markdown="", meta={"error": "No API key for Whisper"})

            async with httpx.AsyncClient(timeout=120.0) as client:
                with open(file_path, "rb") as f:
                    resp = await client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        files={"file": (file_path, f, "audio/mp4")},
                        data={"model": "whisper-1", "response_format": "verbose_json"},
                    )

                if resp.status_code != 200:
                    return ProcessResult(markdown="", meta={"error": f"Whisper API {resp.status_code}"})

                data = resp.json()
                segments = data.get("segments", [])

                markdown_parts = []
                for seg in segments:
                    start = seg.get("start", 0)
                    text = seg.get("text", "").strip()
                    minutes = int(start // 60)
                    seconds = int(start % 60)
                    markdown_parts.append(f"[{minutes}:{seconds:02d}] {text}")

                markdown = "\n".join(markdown_parts)

                doc_meta = {
                    "duration": data.get("duration", 0),
                    "has_transcript": True,
                    "language": data.get("language", "en"),
                    "segment_count": len(segments),
                }

                log.info("Whisper extracted: %s — %d segments", resource_id[:8], len(segments))
                return ProcessResult(markdown=markdown, meta=doc_meta)

        except Exception as e:
            log.error("Whisper extraction failed for %s: %s", resource_id[:8], e)
            return ProcessResult(markdown="", meta={"error": str(e)})

    @staticmethod
    def _parse_youtube_id(url: str) -> str | None:
        """Extract video ID from various YouTube URL formats."""
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
            r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        return None
