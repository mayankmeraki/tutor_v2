import re

import httpx

_NON_LATIN_RE = re.compile(r"[^\u0000-\u024F\u1E00-\u1EFF\s.,;:!?()\-\d%°±×÷=<>+\/'\"\$€£#&@^~*]")


async def search_images(query: str, limit: int = 3) -> str:
    limit = max(1, min(limit, 5))
    fetch_limit = min(limit * 3, 15)

    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": str(fetch_limit),
        "gsrnamespace": "6",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": "800",
        "iiextmetadatalanguage": "en",
        "format": "json",
        "uselang": "en",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://commons.wikimedia.org/w/api.php", params=params)
            data = resp.json()

        pages = (data.get("query") or {}).get("pages") or {}
        if not pages:
            return "No images found. Try a different search query."

        results: list[str] = []
        for page in pages.values():
            if len(results) >= limit:
                break
            info = (page.get("imageinfo") or [{}])[0]
            thumb = info.get("thumburl", "")
            if not thumb:
                continue

            desc_raw = (info.get("extmetadata") or {}).get("ImageDescription", {}).get("value", "")
            desc = re.sub(r"<[^>]+>", "", desc_raw)[:200].strip()
            title = (page.get("title") or "").replace("File:", "")
            label = desc or title

            if label and _NON_LATIN_RE.search(label):
                continue

            safe_label = label.replace('"', "'")
            results.append(
                f'- URL: {thumb}\n  Caption: {label}\n  Use: <teaching-image src="{thumb}" caption="{safe_label}" />'
            )

        if results:
            return f"Found {len(results)} image(s):\n" + "\n".join(results)
        return 'No images found. Try a different search query or add "english" to your query.'
    except Exception as e:
        return f"Image search failed: {e}"
