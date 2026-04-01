"""Video processor — YouTube captions + ElevenLabs STT fallback.

Chain of transcription attempts:
1. YouTube captions API (free, fast, no download needed)
2. ElevenLabs Speech-to-Text (high quality, handles audio files)
3. Return error with clear message if all fail

For uploaded videos: uses ElevenLabs STT directly.
"""

from __future__ import annotations

import logging
import re
import tempfile
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

        # Uploaded video file — transcribe with ElevenLabs
        if storage_path:
            return await self._extract_elevenlabs(storage_path, resource_id)

        return ProcessResult(markdown="", meta={"error": "No video source"})

    async def _extract_youtube(self, url: str, resource_id: str) -> ProcessResult:
        """Extract transcript from YouTube — try captions API first, then ElevenLabs."""
        video_id = self._parse_youtube_id(url)
        if not video_id:
            return ProcessResult(markdown="", meta={"error": f"Could not parse YouTube ID from {url}"})

        # Attempt 1: YouTube captions API (free, fast)
        result = await self._try_youtube_captions(video_id, resource_id)
        if result:
            return result

        # Attempt 2: Download audio + ElevenLabs STT
        log.info("YouTube captions unavailable for %s — trying ElevenLabs STT", resource_id[:8])
        result = await self._try_youtube_elevenlabs(url, video_id, resource_id)
        if result:
            return result

        return ProcessResult(markdown="", meta={
            "error": "Could not get transcript — YouTube captions unavailable and audio transcription failed.",
            "video_id": video_id,
            "source_url": url,
        })

    async def _try_youtube_captions(self, video_id: str, resource_id: str) -> ProcessResult | None:
        """Try YouTube captions API (updated API for v1.x)."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            import asyncio

            ytt_api = YouTubeTranscriptApi()
            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(None, ytt_api.fetch, video_id)

            # Build timestamped markdown from transcript snippets
            segments = []
            for snippet in transcript:
                start = snippet.start
                text = snippet.text.strip()
                if text:
                    minutes = int(start // 60)
                    seconds = int(start % 60)
                    segments.append({
                        "timestamp": start,
                        "text": text,
                        "time_str": f"{minutes}:{seconds:02d}",
                    })

            if not segments:
                return None

            markdown = "\n".join(f"[{s['time_str']}] {s['text']}" for s in segments)
            duration = segments[-1]["timestamp"] + 10 if segments else 0

            log.info("YouTube captions extracted: %s — %d segments, %.0f min",
                    resource_id[:8], len(segments), duration / 60)

            return ProcessResult(markdown=markdown, meta={
                "duration": duration,
                "has_transcript": True,
                "language": "en",
                "video_id": video_id,
                "segment_count": len(segments),
                "source": "youtube_captions",
            })

        except ImportError:
            log.warning("youtube-transcript-api not installed")
            return None
        except Exception as e:
            log.warning("YouTube captions failed for %s: %s", resource_id[:8], e)
            return None

    async def _try_youtube_elevenlabs(self, url: str, video_id: str, resource_id: str) -> ProcessResult | None:
        """Download YouTube audio and transcribe with ElevenLabs STT."""
        import asyncio

        # Download audio with yt-dlp
        audio_path = await self._download_youtube_audio(url, video_id)
        if not audio_path:
            return None

        try:
            result = await self._extract_elevenlabs(audio_path, resource_id, video_id=video_id, source_url=url)
            return result if result.markdown else None
        finally:
            # Clean up temp audio file
            import os
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)

    async def _download_youtube_audio(self, url: str, video_id: str) -> str | None:
        """Download audio from YouTube using yt-dlp."""
        import asyncio
        import os

        try:
            import yt_dlp
        except ImportError:
            log.warning("yt-dlp not installed — cannot download YouTube audio")
            return None

        tmp_dir = tempfile.mkdtemp()
        output_path = os.path.join(tmp_dir, f"{video_id}.mp3")

        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(tmp_dir, f"{video_id}.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            loop = asyncio.get_event_loop()
            def _download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])

            await loop.run_in_executor(None, _download)

            if os.path.exists(output_path):
                log.info("YouTube audio downloaded: %s (%.1f MB)", video_id, os.path.getsize(output_path) / 1e6)
                return output_path

            # yt-dlp might use different extension
            for f in os.listdir(tmp_dir):
                if f.startswith(video_id):
                    return os.path.join(tmp_dir, f)

            return None
        except Exception as e:
            log.warning("YouTube audio download failed: %s", e)
            return None

    async def _extract_elevenlabs(
        self,
        file_path: str,
        resource_id: str,
        video_id: str | None = None,
        source_url: str | None = None,
    ) -> ProcessResult:
        """Transcribe audio/video file using ElevenLabs Speech-to-Text."""
        try:
            from elevenlabs import ElevenLabs
            from app.core.config import settings
            import asyncio

            api_key = settings.ELEVENLABS_API_KEY
            if not api_key:
                log.warning("No ElevenLabs API key — cannot transcribe")
                return ProcessResult(markdown="", meta={"error": "No ElevenLabs API key for transcription"})

            client = ElevenLabs(api_key=api_key)

            loop = asyncio.get_event_loop()
            def _transcribe():
                with open(file_path, "rb") as f:
                    return client.speech_to_text.convert(
                        model_id="scribe_v1",
                        file=f,
                        timestamps_granularity="word",
                        language_code="en",
                    )

            result = await loop.run_in_executor(None, _transcribe)

            # Build timestamped markdown from result
            text = result.text if hasattr(result, "text") else ""
            words = result.words if hasattr(result, "words") else []

            if not text:
                return ProcessResult(markdown="", meta={"error": "ElevenLabs returned empty transcript"})

            # Group words into ~30-second segments for timestamped output
            segments = []
            current_segment = {"text": [], "start": 0}
            segment_duration = 30  # seconds per segment

            for word in words:
                word_start = word.start if hasattr(word, "start") else 0
                word_text = word.text if hasattr(word, "text") else str(word)

                if not current_segment["text"]:
                    current_segment["start"] = word_start

                current_segment["text"].append(word_text)

                # Start new segment every ~30 seconds
                if word_start - current_segment["start"] >= segment_duration:
                    start = current_segment["start"]
                    minutes = int(start // 60)
                    seconds = int(start % 60)
                    segments.append(f"[{minutes}:{seconds:02d}] {' '.join(current_segment['text'])}")
                    current_segment = {"text": [], "start": word_start}

            # Flush remaining
            if current_segment["text"]:
                start = current_segment["start"]
                minutes = int(start // 60)
                seconds = int(start % 60)
                segments.append(f"[{minutes}:{seconds:02d}] {' '.join(current_segment['text'])}")

            markdown = "\n".join(segments) if segments else text

            duration = words[-1].end if words and hasattr(words[-1], "end") else 0

            log.info("ElevenLabs STT complete: %s — %d segments, %.0f min",
                    resource_id[:8], len(segments), duration / 60)

            meta = {
                "duration": duration,
                "has_transcript": True,
                "language": result.language_code if hasattr(result, "language_code") else "en",
                "segment_count": len(segments),
                "source": "elevenlabs_stt",
            }
            if video_id:
                meta["video_id"] = video_id
            if source_url:
                meta["source_url"] = source_url

            return ProcessResult(markdown=markdown, meta=meta)

        except ImportError:
            log.error("elevenlabs SDK not installed")
            return ProcessResult(markdown="", meta={"error": "elevenlabs SDK not installed"})
        except Exception as e:
            log.error("ElevenLabs STT failed for %s: %s", resource_id[:8], e)
            return ProcessResult(markdown="", meta={"error": f"ElevenLabs transcription failed: {e}"})

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
