"""Chunk classifier — batch LLM call for labels + topics.

Uses Haiku for speed and cost. Processes chunks in batches
of 20 to stay within context limits while minimizing API calls.
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

BATCH_SIZE = 20  # chunks per LLM call
MAX_CHUNK_PREVIEW = 200  # chars per chunk sent to classifier


async def classify_chunks_batch(chunks: list[dict]) -> list[dict]:
    """Classify all chunks with labels and topics.

    Processes in batches of BATCH_SIZE. Each batch is one LLM call.
    Returns list of {"labels": [...], "topics": [...]} in same order.

    Cost: ~$0.001 per 20 chunks (Haiku).
    """
    if not chunks:
        return []

    results = []

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        batch_results = await _classify_batch(batch)
        results.extend(batch_results)

    log.info("Classified %d chunks in %d batches",
            len(chunks), (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE)
    return results


async def _classify_batch(chunks: list[dict]) -> list[dict]:
    """Classify a batch of chunks with one LLM call."""
    try:
        import httpx
        from backend.app.core.config import settings

        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            log.warning("No API key for classifier — skipping classification")
            return [{"labels": [], "topics": []} for _ in chunks]

        # Build prompt with chunk previews
        chunk_previews = []
        for j, chunk in enumerate(chunks):
            preview = chunk.get("content", "")[:MAX_CHUNK_PREVIEW]
            heading = chunk.get("anchor", {}).get("section", "")
            heading_str = f" (section: {heading})" if heading else ""
            chunk_previews.append(f"{j}. {preview}...{heading_str}")

        prompt = f"""Classify each chunk. Output a JSON array with one object per chunk.

Each object has:
- "labels": array of content type labels (free-form strings). Examples: "explanation", "exercise", "definition", "example", "proof", "code", "diagram_description", "formula", "summary", "question", "data_table", "biography", "recipe", "theorem", "procedure", "case_study"
- "topics": array of concept/topic names in lowercase_underscore. Examples: "rate_law", "binary_tree", "photosynthesis", "supply_demand"

Use whatever labels and topics fit naturally. Don't force categories.

Chunks:
{chr(10).join(chunk_previews)}

Output ONLY the JSON array, no other text."""

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "anthropic/claude-haiku-4-5-20251001",
                    "max_tokens": 2000,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

            if resp.status_code != 200:
                log.warning("Classifier API error: %d", resp.status_code)
                return [{"labels": [], "topics": []} for _ in chunks]

            text = resp.json()["choices"][0]["message"]["content"].strip()

            # Parse JSON — handle markdown fences
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3].rstrip()

            classifications = json.loads(text)

            # Validate length
            if len(classifications) != len(chunks):
                log.warning("Classifier returned %d results for %d chunks — padding",
                           len(classifications), len(chunks))
                while len(classifications) < len(chunks):
                    classifications.append({"labels": [], "topics": []})

            return classifications

    except json.JSONDecodeError as e:
        log.warning("Classifier JSON parse error: %s", e)
        return [{"labels": [], "topics": []} for _ in chunks]
    except Exception as e:
        log.error("Classifier failed: %s", e)
        return [{"labels": [], "topics": []} for _ in chunks]
