"""YouTube extractor — metadata and playlist expansion via yt-dlp."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    title: str
    duration: int  # seconds
    thumbnail_url: str | None = None
    description: str = ""
    uploader: str = ""
    url: str = ""


@dataclass
class PlaylistResult:
    videos: list[dict]  # [{url, title, duration}]


def _extract_video_id(url: str) -> str | None:
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _is_playlist(url: str) -> bool:
    return "list=" in url and "v=" not in url


async def extract_youtube(url: str) -> VideoMetadata | PlaylistResult:
    """Extract metadata from a YouTube URL. Handles playlists and single videos."""

    if _is_playlist(url):
        return await _expand_playlist(url)

    return await _fetch_video_metadata(url)


async def _fetch_video_metadata(url: str) -> VideoMetadata:
    """Fetch metadata for a single YouTube video using yt-dlp."""
    loop = asyncio.get_event_loop()

    def _sync():
        import yt_dlp
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return VideoMetadata(
                title=info.get("title", "Untitled"),
                duration=info.get("duration", 0),
                thumbnail_url=info.get("thumbnail"),
                description=(info.get("description") or "")[:500],
                uploader=info.get("uploader", ""),
                url=url,
            )

    return await loop.run_in_executor(None, _sync)


async def _expand_playlist(url: str) -> PlaylistResult:
    """Expand a YouTube playlist into individual video URLs."""
    loop = asyncio.get_event_loop()

    def _sync():
        import yt_dlp
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            entries = info.get("entries", [])
            videos = []
            for entry in entries:
                video_url = entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id', '')}"
                videos.append({
                    "url": video_url,
                    "title": entry.get("title", "Untitled"),
                    "duration": entry.get("duration", 0),
                })
            return PlaylistResult(videos=videos)

    return await loop.run_in_executor(None, _sync)


async def get_audio_stream_url(url: str) -> str:
    """Get direct audio stream URL for transcription services."""
    loop = asyncio.get_event_loop()

    def _sync():
        import yt_dlp
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio",
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("url", "")

    return await loop.run_in_executor(None, _sync)
