"""Google Cloud Storage backend for BYO materials.

Uploads files to gs://capacity-byo-uploads/{user_id}/{collection_id}/{filename}.
Serves files via signed URLs (1-hour expiry) — no public access.

All GCS SDK calls are synchronous — wrapped in run_in_executor to avoid
blocking the async event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import timedelta

from google.cloud import storage as gcs

log = logging.getLogger(__name__)

BUCKET_NAME = os.environ.get("BYO_GCS_BUCKET", "capacity-byo-uploads")
SIGNED_URL_EXPIRY = timedelta(hours=1)


class GCSStorage:
    """Store files in Google Cloud Storage. For production."""

    def __init__(self, bucket_name: str = BUCKET_NAME):
        self.client = gcs.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.bucket_name = bucket_name

    def _blob_path(self, user_id: str, collection_id: str, filename: str) -> str:
        safe_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        return f"{user_id}/{collection_id}/{safe_name}"

    async def save(self, data: bytes, user_id: str, collection_id: str, filename: str) -> str:
        """Upload file to GCS. Returns the gs:// path."""
        import mimetypes
        blob_path = self._blob_path(user_id, collection_id, filename)
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        def _upload():
            blob = self.bucket.blob(blob_path)
            blob.upload_from_string(data, content_type=content_type)

        await asyncio.get_event_loop().run_in_executor(None, _upload)

        gs_path = f"gs://{self.bucket_name}/{blob_path}"
        log.info("Uploaded to GCS: %s (%d bytes)", gs_path, len(data))
        return gs_path

    async def save_from_path(self, source: str, user_id: str, collection_id: str, filename: str) -> str:
        """Upload a local file to GCS."""
        blob_path = self._blob_path(user_id, collection_id, filename)

        def _upload():
            blob = self.bucket.blob(blob_path)
            blob.upload_from_filename(source)

        await asyncio.get_event_loop().run_in_executor(None, _upload)

        gs_path = f"gs://{self.bucket_name}/{blob_path}"
        log.info("Uploaded to GCS from file: %s", gs_path)
        return gs_path

    async def read(self, path: str) -> bytes:
        """Read file bytes from GCS."""
        blob_path = self._strip_gs_prefix(path)

        def _download():
            blob = self.bucket.blob(blob_path)
            return blob.download_as_bytes()

        return await asyncio.get_event_loop().run_in_executor(None, _download)

    async def delete(self, path: str):
        """Delete a file from GCS."""
        blob_path = self._strip_gs_prefix(path)

        def _delete():
            blob = self.bucket.blob(blob_path)
            if blob.exists():
                blob.delete()

        await asyncio.get_event_loop().run_in_executor(None, _delete)

    async def exists(self, path: str) -> bool:
        blob_path = self._strip_gs_prefix(path)

        def _check():
            blob = self.bucket.blob(blob_path)
            return blob.exists()

        return await asyncio.get_event_loop().run_in_executor(None, _check)

    def generate_signed_url(self, path: str, content_type: str | None = None) -> str:
        """Generate a signed URL for browser-direct access (1 hour).

        Used for: PDF viewing, video/audio streaming, image display.
        The URL is temporary and scoped to this specific file.
        """
        blob_path = self._strip_gs_prefix(path)
        blob = self.bucket.blob(blob_path)

        return blob.generate_signed_url(
            version="v4",
            expiration=SIGNED_URL_EXPIRY,
            method="GET",
            response_type=content_type,
        )

    def _strip_gs_prefix(self, path: str) -> str:
        """Convert gs://bucket/path to just path."""
        prefix = f"gs://{self.bucket_name}/"
        if path.startswith(prefix):
            return path[len(prefix):]
        return path
