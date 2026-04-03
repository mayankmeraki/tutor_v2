"""Image search via SearchAPI (Google Images Light).

Returns image titles + URLs that the tutor can embed on the board
using <teaching-image src="..." caption="..." />.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SEARCHAPI_URL = "https://www.searchapi.io/api/v1/search"


async def search_images(query: str, limit: int = 3) -> str:
    """Search Google Images via SearchAPI. Returns titles + URLs for board embedding."""
    limit = max(1, min(limit, 5))
    logger.info("search_images query=%r limit=%d", query, limit)

    api_key = settings.SEARCHAPI_KEY
    if not api_key:
        return "Image search not configured (missing SEARCHAPI_KEY)."

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                SEARCHAPI_URL,
                params={
                    "engine": "google_images_light",
                    "q": query,
                    "num": str(limit + 2),  # fetch a few extra in case some are unusable
                    "api_key": api_key,
                },
            )
            if resp.status_code != 200:
                logger.warning("SearchAPI returned %d: %s", resp.status_code, resp.text[:200])
                return f"Image search failed (HTTP {resp.status_code}). Try a different query."

            data = resp.json()

        images = data.get("images", [])
        if not images:
            return "No images found. Try a different or more specific query."

        results = []
        for img in images[:limit]:
            title = img.get("title", "Image")
            original = img.get("original", {})
            url = original.get("link", "")
            thumb = img.get("thumbnail", "")
            # Prefer original, fall back to thumbnail
            display_url = url or thumb
            if not display_url:
                continue

            safe_title = title.replace('"', "'")[:100]
            results.append(
                f'- "{safe_title}"\n'
                f'  URL: {display_url}\n'
                f'  Embed: <teaching-image src="{display_url}" caption="{safe_title}" />'
            )

        if results:
            logger.info("search_images query=%r returned %d image(s)", query, len(results))
            return (
                f"Found {len(results)} image(s) for \"{query}\":\n\n"
                + "\n\n".join(results)
                + "\n\nUse the <teaching-image> tag to embed any of these on the board."
            )

        return "No usable images found. Try a different query."

    except Exception as e:
        logger.error("search_images failed: %s", e, exc_info=True)
        return f"Image search failed: {e}"
