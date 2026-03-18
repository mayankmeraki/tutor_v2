"""Google Cloud Storage helpers for BYO material uploads."""

from __future__ import annotations

import logging
from datetime import timedelta

from app.core.config import settings

log = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        from google.cloud import storage
        _client = storage.Client()
    return _client


def _get_bucket():
    return _get_client().bucket(settings.MATERIALS_BUCKET)


async def upload_bytes(data: bytes, gcs_path: str, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to GCS. Returns the public URL."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _upload_bytes_sync, data, gcs_path, content_type)


def _upload_bytes_sync(data: bytes, gcs_path: str, content_type: str) -> str:
    bucket = _get_bucket()
    blob = bucket.blob(gcs_path)
    blob.upload_from_string(data, content_type=content_type)
    return f"gs://{settings.MATERIALS_BUCKET}/{gcs_path}"


async def upload_file(local_path: str, gcs_path: str, content_type: str | None = None) -> str:
    """Upload a local file to GCS. Returns the gs:// URI."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _upload_file_sync, local_path, gcs_path, content_type)


def _upload_file_sync(local_path: str, gcs_path: str, content_type: str | None) -> str:
    bucket = _get_bucket()
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path, content_type=content_type)
    return f"gs://{settings.MATERIALS_BUCKET}/{gcs_path}"


async def download_bytes(gcs_path: str) -> bytes:
    """Download bytes from GCS."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _download_bytes_sync, gcs_path)


def _download_bytes_sync(gcs_path: str) -> bytes:
    bucket = _get_bucket()
    blob = bucket.blob(gcs_path)
    return blob.download_as_bytes()


async def get_signed_url(gcs_path: str, expiry_minutes: int = 60) -> str:
    """Generate a signed URL for temporary access."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_signed_url_sync, gcs_path, expiry_minutes)


def _get_signed_url_sync(gcs_path: str, expiry_minutes: int) -> str:
    bucket = _get_bucket()
    blob = bucket.blob(gcs_path)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expiry_minutes),
        method="GET",
    )


async def delete_blob(gcs_path: str) -> None:
    """Delete a blob from GCS."""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _delete_blob_sync, gcs_path)


def _delete_blob_sync(gcs_path: str) -> None:
    bucket = _get_bucket()
    blob = bucket.blob(gcs_path)
    blob.delete()
