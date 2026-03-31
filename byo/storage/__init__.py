"""File storage abstraction — local or GCS."""
from byo.storage.local import LocalStorage

# Default to local storage. Switch to GCS in production.
default_storage = LocalStorage()
