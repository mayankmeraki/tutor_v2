"""Session attachment storage — uploads to GCS, caches for re-injection.

Files go to gs://capacity-session-attachments/{session_id}/{uuid}_{filename}.
Metadata (GCS path, mime_type, filename) stored on session for persistence.
On subsequent turns, files are fetched from GCS and injected into messages.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import uuid

from google.cloud import storage as gcs

log = logging.getLogger(__name__)

BUCKET_NAME = os.environ.get("SESSION_ATTACHMENTS_BUCKET", "capacity-session-attachments")

_client = None
_bucket = None


def _get_bucket():
    global _client, _bucket
    if _bucket is None:
        _client = gcs.Client()
        _bucket = _client.bucket(BUCKET_NAME)
    return _bucket


async def upload_attachments(session_id: str, attachments: list[dict]) -> list[dict]:
    """Upload base64 attachments to GCS. Returns metadata list for session storage.

    Input:  [{"filename": "photo.jpg", "mime_type": "image/jpeg", "data": "<base64>"}]
    Output: [{"filename": "photo.jpg", "mime_type": "image/jpeg", "gcs_path": "gs://..."}]
    """
    bucket = _get_bucket()
    results = []

    for att in attachments:
        mime = att.get("mime_type", "")
        data_b64 = att.get("data", "")
        fname = att.get("filename", "file")
        if not data_b64 or not mime:
            continue

        raw_bytes = base64.b64decode(data_b64)
        blob_name = f"{session_id}/{uuid.uuid4().hex[:8]}_{fname}"

        def _upload(blob_name=blob_name, raw_bytes=raw_bytes, content_type=mime):
            blob = bucket.blob(blob_name)
            blob.upload_from_string(raw_bytes, content_type=content_type)

        await asyncio.get_event_loop().run_in_executor(None, _upload)

        gcs_path = f"gs://{BUCKET_NAME}/{blob_name}"
        results.append({
            "filename": fname,
            "mime_type": mime,
            "gcs_path": gcs_path,
        })
        log.info("Uploaded attachment: %s (%d bytes)", gcs_path, len(raw_bytes))

    return results


async def fetch_attachments(attachment_meta: list[dict]) -> list[dict]:
    """Fetch attachments from GCS and return with base64 data for LLM injection.

    Input:  [{"filename": "photo.jpg", "mime_type": "image/jpeg", "gcs_path": "gs://..."}]
    Output: [{"filename": "photo.jpg", "mime_type": "image/jpeg", "data": "<base64>"}]
    """
    bucket = _get_bucket()
    results = []

    for meta in attachment_meta:
        gcs_path = meta.get("gcs_path", "")
        if not gcs_path:
            continue

        blob_name = gcs_path.replace(f"gs://{BUCKET_NAME}/", "")

        def _download(blob_name=blob_name):
            blob = bucket.blob(blob_name)
            return blob.download_as_bytes()

        try:
            raw_bytes = await asyncio.get_event_loop().run_in_executor(None, _download)
            results.append({
                "filename": meta["filename"],
                "mime_type": meta["mime_type"],
                "data": base64.b64encode(raw_bytes).decode("ascii"),
            })
        except Exception as e:
            log.warning("Failed to fetch attachment %s: %s", gcs_path, e)

    return results
