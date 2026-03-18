"""Transcription adapters — YouTube captions and Deepgram fallback."""

from __future__ import annotations

import logging
import re

from app.core.config import settings

from .base import Segment, TranscriptionAdapter

log = logging.getLogger(__name__)


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


class YouTubeCaptionsAdapter(TranscriptionAdapter):
    """Free transcription via YouTube's built-in captions."""

    async def transcribe(self, audio_source: str) -> list[Segment]:
        from youtube_transcript_api import YouTubeTranscriptApi

        video_id = _extract_video_id(audio_source)
        if not video_id:
            raise ValueError(f"Cannot extract video ID from: {audio_source}")

        import asyncio
        loop = asyncio.get_event_loop()
        raw_segments = await loop.run_in_executor(
            None, lambda: YouTubeTranscriptApi.get_transcript(video_id),
        )

        return [
            Segment(
                text=seg["text"],
                start=seg["start"],
                end=seg["start"] + seg["duration"],
            )
            for seg in raw_segments
        ]


class DeepgramAdapter(TranscriptionAdapter):
    """Paid transcription via Deepgram Nova-2 model."""

    async def transcribe(self, audio_source: str) -> list[Segment]:
        from deepgram import DeepgramClient, PrerecordedOptions

        client = DeepgramClient(settings.DEEPGRAM_API_KEY)

        options = PrerecordedOptions(
            model="nova-2",
            language="en",
            punctuate=True,
            paragraphs=True,
            diarize=True,
            smart_format=True,
            utterances=True,
        )

        response = await client.listen.asyncprerecorded.v("1").transcribe_url(
            {"url": audio_source}, options,
        )

        segments = []
        for utterance in response.results.utterances:
            segments.append(Segment(
                text=utterance.transcript,
                start=utterance.start,
                end=utterance.end,
                speaker=utterance.speaker,
                confidence=utterance.confidence,
            ))

        return segments
