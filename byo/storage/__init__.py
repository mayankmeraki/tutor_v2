"""File storage abstraction — auto-selects GCS or local.

GCS is used when BYO_STORAGE=gcs or GOOGLE_APPLICATION_CREDENTIALS is set.
Falls back to local filesystem for development.
"""

import os
import logging

log = logging.getLogger(__name__)

_storage_type = os.environ.get("BYO_STORAGE", "auto")


def _create_storage():
    if _storage_type == "local":
        from byo.storage.local import LocalStorage
        log.info("BYO storage: local filesystem")
        return LocalStorage()

    if _storage_type == "gcs":
        from byo.storage.gcs import GCSStorage
        log.info("BYO storage: Google Cloud Storage")
        return GCSStorage()

    # Auto-detect: use GCS if credentials are available
    if _storage_type == "auto":
        try:
            from google.cloud import storage as gcs
            client = gcs.Client()
            # Quick check — can we reach GCS?
            bucket = client.bucket(os.environ.get("BYO_GCS_BUCKET", "capacity-byo-uploads"))
            if bucket.exists():
                from byo.storage.gcs import GCSStorage
                log.info("BYO storage: auto-detected GCS (bucket exists)")
                return GCSStorage()
        except Exception:
            pass

    from byo.storage.local import LocalStorage
    log.info("BYO storage: falling back to local filesystem")
    return LocalStorage()


default_storage = _create_storage()
