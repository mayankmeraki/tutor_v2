"""Local filesystem storage for BYO materials."""

from __future__ import annotations

import os
import shutil
import uuid
import logging

log = logging.getLogger(__name__)

UPLOAD_DIR = os.environ.get("BYO_UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "byo"))


class LocalStorage:
    """Store files on local filesystem. For development and single-server deployments."""

    def __init__(self, base_dir: str = UPLOAD_DIR):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _path(self, user_id: str, collection_id: str, filename: str) -> str:
        dir_path = os.path.join(self.base_dir, user_id, collection_id)
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, filename)

    async def save(self, data: bytes, user_id: str, collection_id: str, filename: str) -> str:
        """Save file bytes. Returns the storage path."""
        # Add UUID prefix to avoid collisions
        safe_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        path = self._path(user_id, collection_id, safe_name)
        with open(path, "wb") as f:
            f.write(data)
        log.info("Saved file: %s (%d bytes)", path, len(data))
        return path

    async def save_from_path(self, source: str, user_id: str, collection_id: str, filename: str) -> str:
        """Copy a file from a temp location to permanent storage."""
        safe_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        dest = self._path(user_id, collection_id, safe_name)
        shutil.copy2(source, dest)
        return dest

    async def read(self, path: str) -> bytes:
        """Read file bytes."""
        with open(path, "rb") as f:
            return f.read()

    async def delete(self, path: str):
        """Delete a file."""
        if os.path.exists(path):
            os.remove(path)

    async def exists(self, path: str) -> bool:
        return os.path.exists(path)
