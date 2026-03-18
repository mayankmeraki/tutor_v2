"""Keyframe extraction from video using ffmpeg."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class FramePath:
    path: str
    timestamp: float  # seconds into video
    image_bytes: bytes | None = None


async def extract_frames_ffmpeg(
    video_url: str,
    material_id: str,
    interval: int = 10,
    scene_threshold: float = 0.3,
    max_frames: int = 200,
) -> list[FramePath]:
    """Extract frames from video using ffmpeg.

    For YouTube URLs, we need to get a direct stream URL first via yt-dlp.
    """
    output_dir = tempfile.mkdtemp(prefix=f"frames_{material_id}_")

    try:
        # Get stream URL if it's a YouTube URL
        stream_url = await _get_stream_url(video_url)

        # Extract at regular intervals
        interval_dir = os.path.join(output_dir, "interval")
        os.makedirs(interval_dir, exist_ok=True)

        cmd_interval = [
            "ffmpeg", "-i", stream_url,
            "-vf", f"fps=1/{interval}",
            "-q:v", "2",
            "-y",
            os.path.join(interval_dir, "frame_%06d.jpg"),
        ]

        await _run_ffmpeg(cmd_interval)

        # Collect all frames with timestamps
        frames: list[FramePath] = []
        for f in sorted(os.listdir(interval_dir)):
            if not f.endswith(".jpg"):
                continue
            # ffmpeg names files sequentially starting at 1
            try:
                frame_num = int(f.replace("frame_", "").replace(".jpg", ""))
                timestamp = (frame_num - 1) * interval
            except ValueError:
                continue

            full_path = os.path.join(interval_dir, f)
            with open(full_path, "rb") as fh:
                img_bytes = fh.read()

            frames.append(FramePath(
                path=full_path,
                timestamp=float(timestamp),
                image_bytes=img_bytes,
            ))

        # Cap at max_frames
        if len(frames) > max_frames:
            step = len(frames) / max_frames
            frames = [frames[int(i * step)] for i in range(max_frames)]

        log.info("Extracted %d frames from %s", len(frames), material_id)
        return frames

    except Exception as e:
        log.error("Frame extraction failed for %s: %s", material_id, e)
        return []
    finally:
        # Clean up temp directory
        shutil.rmtree(output_dir, ignore_errors=True)


async def _get_stream_url(url: str) -> str:
    """Get direct video stream URL. For YouTube, use yt-dlp."""
    if "youtube.com" in url or "youtu.be" in url:
        loop = asyncio.get_event_loop()

        def _sync():
            import yt_dlp
            opts = {
                "quiet": True,
                "no_warnings": True,
                "format": "bestvideo[height<=720]",
                "skip_download": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get("url", url)

        return await loop.run_in_executor(None, _sync)

    return url  # Already a direct URL


async def _run_ffmpeg(cmd: list[str], timeout: int = 300) -> None:
    """Run an ffmpeg command asynchronously."""
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        if process.returncode != 0:
            log.warning("ffmpeg stderr: %s", stderr.decode()[-500:] if stderr else "")
    except asyncio.TimeoutError:
        process.kill()
        raise TimeoutError(f"ffmpeg timed out after {timeout}s")
