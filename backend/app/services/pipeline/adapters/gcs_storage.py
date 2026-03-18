"""GCS blob storage adapter."""

from __future__ import annotations

from app.services.gcs import delete_blob, download_bytes, get_signed_url, upload_bytes

from .base import BlobStorageAdapter


class GCSStorageAdapter(BlobStorageAdapter):
    async def upload(self, data: bytes, path: str, content_type: str = "application/octet-stream") -> str:
        return await upload_bytes(data, path, content_type)

    async def download(self, path: str) -> bytes:
        return await download_bytes(path)

    async def get_signed_url(self, path: str, expiry_minutes: int = 60) -> str:
        return await get_signed_url(path, expiry_minutes)
