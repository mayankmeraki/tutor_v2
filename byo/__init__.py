"""BYO (Bring Your Own) Materials Service.

Handles upload, processing, storage, and retrieval of student-uploaded
study materials (PDFs, videos, text, images). Designed as a separate
service that can be deployed independently.

Key components:
  - pipeline/: Processing pipeline (extract → chunk → classify → embed)
  - storage/: File storage abstraction (local, GCS)
  - api/: REST endpoints for collections and resources
  - adapter.py: BYOCollectionAdapter (implements ContentProvider protocol)
  - models.py: Pydantic models for Collection, Resource, Chunk
"""
