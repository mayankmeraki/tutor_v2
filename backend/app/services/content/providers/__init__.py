"""Content provider abstraction layer.

ContentProvider protocol defines 4 methods: content_map, content_read,
content_search, content_peek. Adapters implement this for different backends.

Usage:
    from app.services.content.providers import create_adapter

    adapter = create_adapter(course_id, db_session)
    structure = await adapter.content_map()
    content = await adapter.content_read("lesson:3:section:2")
"""

from .factory import create_adapter
from .protocol import ContentProvider

__all__ = ["ContentProvider", "create_adapter"]
