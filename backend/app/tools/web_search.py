"""Web search tool — DuckDuckGo instant answers + HTML search fallback.

Provides the tutor and sub-agents with general web search capability
for supplementary information not found in course materials.
"""

import re

import httpx

_TAG_RE = re.compile(r"<[^>]+>")


async def web_search(query: str, limit: int = 5) -> str:
    """Search the web for educational content.

    Uses DuckDuckGo instant answer API first (fast, structured).
    Falls back to DuckDuckGo HTML search for broader results.
    Returns a concise summary of top results.
    """
    limit = max(1, min(limit, 8))

    results: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            # ── Phase 1: DuckDuckGo Instant Answer API ──
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            data = resp.json()

            # Abstract (Wikipedia-style summary)
            abstract = data.get("AbstractText", "").strip()
            if abstract:
                source = data.get("AbstractSource", "")
                url = data.get("AbstractURL", "")
                results.append(
                    f"**Summary** ({source}):\n{abstract[:600]}"
                    + (f"\nSource: {url}" if url else "")
                )

            # Related topics
            for topic in (data.get("RelatedTopics") or [])[:4]:
                text = topic.get("Text", "").strip()
                url = topic.get("FirstURL", "")
                if text and len(results) < limit:
                    results.append(f"- {text[:250]}" + (f"\n  URL: {url}" if url else ""))

            # If instant answer gave enough, return early
            if len(results) >= 2:
                return f"Web search results for \"{query}\":\n\n" + "\n\n".join(results)

            # ── Phase 2: DuckDuckGo HTML search fallback ──
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; EducationalBot/1.0)"},
            )
            html = resp.text

            # Parse result snippets from HTML
            # DuckDuckGo HTML results are in <a class="result__a"> and <a class="result__snippet">
            snippet_pattern = re.compile(
                r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
                r'class="result__snippet"[^>]*>(.*?)</(?:a|td)',
                re.DOTALL,
            )
            for match in snippet_pattern.finditer(html):
                if len(results) >= limit:
                    break
                url = match.group(1).strip()
                title = _TAG_RE.sub("", match.group(2)).strip()
                snippet = _TAG_RE.sub("", match.group(3)).strip()
                if title and snippet:
                    # DuckDuckGo HTML wraps URLs in a redirect — extract the real URL
                    if "uddg=" in url:
                        real_url_match = re.search(r"uddg=([^&]+)", url)
                        if real_url_match:
                            from urllib.parse import unquote
                            url = unquote(real_url_match.group(1))
                    results.append(f"**{title}**\n{snippet[:300]}\nURL: {url}")

    except Exception as e:
        if not results:
            return f"Web search failed: {e}. Try a different query or use course materials."

    if results:
        return f"Web search results for \"{query}\":\n\n" + "\n\n".join(results)
    return f"No web results found for \"{query}\". Try rephrasing or using course materials."
