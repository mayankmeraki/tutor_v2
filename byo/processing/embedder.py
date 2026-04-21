"""Segment embedder — multi-representation embedding for BYO.

We embed SEGMENTS (children), not parent chunks. Each segment's embedding
covers `segment.content + "\\n" + "\\n".join(segment.questions)` — the
"hypothetical questions" idea (HyQE): for each segment, Haiku emits 1-3
questions the segment would answer. Embedding the questions alongside
content substantially lifts recall on question-style queries.

Rules:
  - `retrieval_mode == VISUAL_DESCRIPTION` → skip question generation.
    The content is already an LLM description; forcing questions tends
    to paraphrase it back.
  - `retrieval_mode in (SEMANTIC, EXACT_PLUS_SEMANTIC, SYMBOLIC,
    TEMPORAL)` → generate questions with Haiku.
  - Question generation fails gracefully: on error we log a warning and
    embed the raw content.

Uses text-embedding-3-small via OpenRouter. Embedding batch size = 50,
question-gen batch size = 20. Text capped at 2000 chars per embedding.
"""

from __future__ import annotations

import asyncio
import json
import logging

from byo.shared.models import RetrievalMode

log = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 50
EMBED_MODEL = "text-embedding-3-small"
MAX_EMBED_CHARS = 2000

QUESTION_BATCH_SIZE = 20
QUESTION_MODEL = "openai/gpt-5.4-nano"
MAX_QUESTION_PREVIEW_CHARS = 600  # chunk preview sent to Haiku


async def embed_segments_batch(segments: list[dict]) -> None:
    """Generate questions (where applicable) + embeddings for segments.

    Modifies segments in-place. Each segment gets `.questions` (possibly
    empty) and `.embedding` (1536-dim, or `[]` on API failure).
    """
    if not segments:
        return

    # 1) Split segments into "wants questions" vs "visual_description".
    wants_questions = [s for s in segments if _needs_questions(s)]
    if wants_questions:
        await _generate_questions(wants_questions)

    # 2) Embed in batches. Text = content + "\n" + questions.
    for i in range(0, len(segments), EMBED_BATCH_SIZE):
        batch = segments[i:i + EMBED_BATCH_SIZE]
        texts = [_embed_text(s) for s in batch]
        embeddings = await _generate_embeddings(texts)
        for j, emb in enumerate(embeddings):
            batch[j]["embedding"] = emb

    log.info(
        "Embedded %d segments in %d batches (%d w/ questions)",
        len(segments),
        (len(segments) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE,
        sum(1 for s in segments if s.get("questions")),
    )


# ── Text assembly ──────────────────────────────────────────────────────

def _needs_questions(segment: dict) -> bool:
    """Skip HyQE for modes where it hurts (visual descriptions)."""
    mode = segment.get("retrieval_mode", RetrievalMode.SEMANTIC.value)
    return mode != RetrievalMode.VISUAL_DESCRIPTION.value


def _embed_text(segment: dict) -> str:
    """Build the string we actually embed for a segment."""
    content = segment.get("content", "") or ""
    questions = segment.get("questions") or []
    if questions:
        combined = content + "\n" + "\n".join(questions)
    else:
        combined = content
    return combined[:MAX_EMBED_CHARS]


# ── Hypothetical-question generation ───────────────────────────────────

async def _generate_questions(segments: list[dict]) -> None:
    """Populate `segment["questions"]` using Haiku, in batches of 20.

    Graceful on error: if a batch fails, we leave those segments' questions
    as an empty list and the caller embeds content only.
    """
    for i in range(0, len(segments), QUESTION_BATCH_SIZE):
        batch = segments[i:i + QUESTION_BATCH_SIZE]
        try:
            results = await _call_haiku_for_questions(batch)
        except Exception as e:  # noqa: BLE001 — broad by design, graceful
            log.warning("Question generation batch failed: %s", e)
            results = [[] for _ in batch]

        for seg, qs in zip(batch, results):
            # Defensive: cap to 3 and keep only non-empty strings.
            clean = [q.strip() for q in qs if isinstance(q, str) and q.strip()][:3]
            seg["questions"] = clean


async def _call_haiku_for_questions(segments: list[dict]) -> list[list[str]]:
    """One batched LLM call → list of question-lists aligned to input order."""
    import httpx
    from app.core.config import settings

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        log.warning("No OPENROUTER_API_KEY — skipping question generation")
        return [[] for _ in segments]

    # Keep previews short; Haiku is cheap but we batch 20 → ~12k chars max.
    previews = []
    for j, seg in enumerate(segments):
        preview = (seg.get("content", "") or "")[:MAX_QUESTION_PREVIEW_CHARS]
        previews.append(f"{j}. {preview}")

    prompt = (
        "For each chunk below, write 1-3 short questions a student might ask "
        "that THIS chunk directly answers. Questions should be specific to the "
        "content — not generic. Output ONLY a JSON array with one entry per "
        "chunk. Each entry is an array of question strings. No other text.\n\n"
        "Example output: [[\"What is X?\", \"How does Y work?\"], [\"Why Z?\"]]\n\n"
        "Chunks:\n" + "\n\n".join(previews)
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": QUESTION_MODEL,
                "max_tokens": 2000,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            },
        )

        if resp.status_code != 200:
            log.warning("Question API error: %d", resp.status_code)
            return [[] for _ in segments]

        text = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if Haiku wrapped the JSON.
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].rstrip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        log.warning("Question JSON parse failed: %s", e)
        return [[] for _ in segments]

    if not isinstance(parsed, list):
        log.warning("Question output not a list; got %s", type(parsed).__name__)
        return [[] for _ in segments]

    # Pad / truncate to align with input order.
    out: list[list[str]] = []
    for j in range(len(segments)):
        if j < len(parsed) and isinstance(parsed[j], list):
            out.append([q for q in parsed[j] if isinstance(q, str)])
        else:
            out.append([])
    return out


# ── Embedding ──────────────────────────────────────────────────────────

async def _generate_embeddings(texts: list[str], _retries: int = 3) -> list[list[float]]:
    """Call the embeddings endpoint for a batch of texts with retry."""
    import httpx
    from app.core.config import settings

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        log.warning("No API key for embeddings")
        return [[] for _ in texts]

    for attempt in range(1, _retries + 1):
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": EMBED_MODEL, "input": texts},
                )

                if resp.status_code == 429:
                    wait = min(30, 2 ** attempt)
                    log.warning("Embedding API rate limited — retrying in %ds (attempt %d/%d)", wait, attempt, _retries)
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code != 200:
                    log.warning("Embedding API error: %d (attempt %d/%d)", resp.status_code, attempt, _retries)
                    if attempt < _retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return [[] for _ in texts]

                data = resp.json()
                sorted_data = sorted(data["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in sorted_data]

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            wait = min(15, 2 ** attempt)
            log.warning("Embedding request failed (attempt %d/%d, retry in %ds): %s", attempt, _retries, wait, e)
            if attempt < _retries:
                await asyncio.sleep(wait)
            else:
                log.error("Embedding generation failed after %d attempts: %s", _retries, e)
                return [[] for _ in texts]
        except Exception as e:
            log.error("Embedding generation failed: %s", e)
            return [[] for _ in texts]

    return [[] for _ in texts]
