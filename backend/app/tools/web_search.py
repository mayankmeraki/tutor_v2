"""Web search via OpenRouter's ``openrouter:web_search`` server tool.

The tutor and sub-agents already get web search for free at the
chat-completion layer: ``_convert_tools_openrouter`` rewrites a
``web_search`` tool entry into the ``openrouter:web_search`` server
tool, so when the model decides to call it the search runs server-side
(Exa-backed by default) and never round-trips through us.

This module exists for the few backend code paths that want to perform
a search *outside* of a tutor/agent loop (e.g. ``prefetch_context`` in
the teaching pipeline). It issues a small chat-completion to a cheap
model with the same server tool enabled and returns the model's cited
summary. No DuckDuckGo HTML scraping anywhere.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "You are a research assistant. The user gives you a query — call the "
    "openrouter:web_search tool, then return a concise factual summary of "
    "what you found. Include 2-5 inline source URLs in markdown link form. "
    "Never invent facts; only report what the search returned. Keep the "
    "answer under ~250 words."
)


async def web_search(query, limit: int = 5) -> str:
    """Search the web for educational / factual content.

    Args:
        query: Search query string. Also accepts a ``{"query": ..., "limit": ...}``
            dict for backwards compatibility with one legacy call site.
        limit: Max results per search call (1-10).

    Returns:
        Cited summary, or a short error string on failure.
    """
    # Backwards-compat: legacy call site passes a dict positionally.
    if isinstance(query, dict):
        limit = int(query.get("limit", limit) or limit)
        query = query.get("query", "")

    query = (query or "").strip()
    if not query:
        return "Web search: empty query."

    limit = max(1, min(int(limit), 10))
    logger.debug("web_search query=%r limit=%d", query, limit)

    api_key = getattr(settings, "OPENROUTER_API_KEY", "") or ""
    if not api_key:
        return "Web search unavailable: OPENROUTER_API_KEY not configured."

    try:
        import openai

        client = openai.AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://capacity.app",
                "X-Title": "Capacity Tutor",
            },
        )
        # MODEL_FAST is cheap + fast (Haiku via OpenRouter). Any model that
        # supports tool calling works — the actual searching is done by
        # OpenRouter, the model just orchestrates and summarises.
        model = getattr(settings, "MODEL_FAST", "anthropic/claude-haiku-4.5")
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            tools=[
                {
                    "type": "openrouter:web_search",
                    "parameters": {
                        "max_results": limit,
                        "search_context_size": "medium",
                    },
                }
            ],
            max_tokens=900,
            timeout=20,
        )
        text = (resp.choices[0].message.content or "").strip()
        usage = getattr(resp, "usage", None)
        searches = 0
        if usage is not None:
            stu = getattr(usage, "server_tool_use", None)
            if stu is not None:
                searches = getattr(stu, "web_search_requests", 0) or 0
        if not text:
            logger.warning("web_search query=%r returned empty body", query)
            return f'No web results found for "{query}".'
        logger.info(
            "web_search query=%r returned %d chars, %d underlying searches",
            query, len(text), searches,
        )
        return f'Web search results for "{query}":\n\n{text[:4000]}'
    except Exception as e:
        logger.warning("web_search failed query=%r: %s", query, e, exc_info=True)
        return f"Web search failed: {e}"
