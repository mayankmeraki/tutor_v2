"""Remove garbage image segments from Qdrant (placeholder descriptions)."""
import os
from dotenv import load_dotenv
load_dotenv('backend/.env', override=True)

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

COLLECTION = os.environ.get("QDRANT_COLLECTION", "byo_v1")
url = os.environ.get("QDRANT_URL", "http://localhost:6333")

client = QdrantClient(url=url)

# Find segments with garbage content
scroll_result = client.scroll(
    collection_name=COLLECTION,
    scroll_filter=Filter(must=[
        FieldCondition(key="modality", match=MatchValue(value="image")),
    ]),
    limit=500,
    with_payload=True,
)

points_to_delete = []
for point in scroll_result[0]:
    content = point.payload.get("segment_content", "")
    if not content or len(content) < 20 or "description unavailable" in content or "[Image —" in content:
        points_to_delete.append(point.id)

if points_to_delete:
    client.delete(collection_name=COLLECTION, points_selector=points_to_delete)
    print(f"Deleted {len(points_to_delete)} garbage image segments")
else:
    print("No garbage segments found")
