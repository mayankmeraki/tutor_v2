"""LLM-driven document structure analysis for chunking.

Replaces format-specific regex with a model call. Two cheap LLM calls
per document decide how to chunk it:

  1. classify_structure(sample) — 1 call at ingest, returns a label
     describing the document's structural shape (prose / discrete_items /
     mixed) + a natural-language unit hint. No regex, no format guess.

  2. detect_boundaries(window) — N calls (one per parent-sized window)
     for documents classified as discrete_items / mixed. Returns
     character offsets where semantic units begin. The chunker splits
     at those offsets; no pattern matching required.

Model: `openai/gpt-5.4-nano` via OpenRouter (fast, cheap).
Graceful degradation: every LLM call has a try/except wrapper; on any
failure callers fall back to paragraph-granular chunking.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

log = logging.getLogger(__name__)

STRUCTURE_MODEL = "openai/gpt-5.4-nano"
_FALLBACK_MODEL = "openai/gpt-5.4-nano"  # same model; rely on retry alone

SAMPLE_START = 3000   # chars sampled from document start
SAMPLE_MID = 3000     # chars sampled from middle
SAMPLE_END = 3000     # chars sampled from end

BOUNDARY_WINDOW = 5000  # chars per boundary-detection call
BOUNDARY_OVERLAP = 300  # char overlap so a split never lands inside a unit

StructureType = Literal["prose", "discrete_items", "mixed", "unknown"]


# ── Classification ──────────────────────────────────────────────────────

async def classify_structure(markdown: str) -> dict[str, Any]:
    """Sample the document, ask the LLM to classify its structure.

    Returns a dict with:
      - structure: "prose" | "discrete_items" | "mixed" | "unknown"
      - unit_hint: short natural-language description of what one unit
        looks like (used as context for the boundary detector)
      - recommended_granularity: "fine" | "medium" | "coarse"
      - confidence: 0.0-1.0

    On LLM failure: returns structure="unknown" so caller falls back.
    """
    if not markdown or len(markdown) < 500:
        return {
            "structure": "prose",
            "unit_hint": "short document — treat as prose",
            "recommended_granularity": "medium",
            "confidence": 1.0,
        }

    sample = _make_sample(markdown)
    prompt = _classification_prompt(sample)

    result = await _call_llm_json(
        prompt,
        model=STRUCTURE_MODEL,
        max_tokens=300,
        fallback_model=_FALLBACK_MODEL,
    )
    if result is None:
        return {
            "structure": "unknown",
            "unit_hint": "",
            "recommended_granularity": "medium",
            "confidence": 0.0,
        }

    structure = result.get("structure", "unknown")
    if structure not in ("prose", "discrete_items", "mixed"):
        structure = "unknown"

    return {
        "structure": structure,
        "unit_hint": result.get("unit_hint", "")[:400],
        "recommended_granularity": result.get("recommended_granularity", "medium"),
        "confidence": float(result.get("confidence") or 0.5),
    }


def _make_sample(markdown: str) -> str:
    """Sample start + middle + end so the classifier sees the whole shape."""
    if len(markdown) <= SAMPLE_START + SAMPLE_MID + SAMPLE_END:
        return markdown
    n = len(markdown)
    mid_start = (n - SAMPLE_MID) // 2
    end_start = n - SAMPLE_END
    return "\n\n---[SAMPLE BREAK]---\n\n".join([
        markdown[:SAMPLE_START],
        markdown[mid_start:mid_start + SAMPLE_MID],
        markdown[end_start:],
    ])


def _classification_prompt(sample: str) -> str:
    return (
        "You're analyzing a document's structural shape for a retrieval pipeline. "
        "Read the sample below (which may include [SAMPLE BREAK] markers between "
        "excerpts from start/middle/end of the document). Classify its structure.\n\n"
        "Decide:\n"
        "  structure:\n"
        '    - "prose":         long-form text. Paragraphs build on each other. '
        "Examples: textbook chapters, articles, lecture notes, tutorials.\n"
        '    - "discrete_items": a collection of independent short units. Each '
        "unit is self-contained. Examples: exam questions, FAQs, flashcards, "
        "problem sets, glossaries, recipe books, reference lists.\n"
        '    - "mixed":          contains BOTH substantial prose AND discrete '
        "items. Examples: textbook chapter with end-of-chapter exercises, "
        "tutorial with exercises mixed in.\n\n"
        "  unit_hint:   a short natural-language description of what ONE "
        "semantic unit looks like in this document (1-2 sentences). This "
        "will be fed to a boundary detector.\n\n"
        "  recommended_granularity:\n"
        '    - "fine":    units are small (~20-80 words each)\n'
        '    - "medium":  units are medium (~80-400 words each)\n'
        '    - "coarse":  units are large (~400+ words each)\n\n'
        "  confidence:  0.0 - 1.0, how sure you are about the classification.\n\n"
        "Output STRICTLY a JSON object. No prose. No markdown. Keys: "
        '"structure", "unit_hint", "recommended_granularity", "confidence".\n\n'
        "SAMPLE:\n" + sample
    )


# ── Boundary detection ─────────────────────────────────────────────────

async def detect_boundaries(
    text: str,
    *,
    unit_hint: str = "",
) -> list[int]:
    """Return character offsets where semantic units begin, within `text`.

    The caller is expected to have segmented the document into roughly
    BOUNDARY_WINDOW-sized windows. We send one window per LLM call.

    Contract:
      - Offset 0 is always included (the window's first character starts a unit).
      - Returned offsets are strictly ascending, within [0, len(text)].
      - If the LLM fails or returns junk, returns [0] so the caller
        falls back to a single-chunk behavior for that window.
    """
    if not text.strip():
        return []

    prompt = _boundary_prompt(text, unit_hint=unit_hint)
    result = await _call_llm_json(
        prompt,
        model=STRUCTURE_MODEL,
        max_tokens=800,
        fallback_model=_FALLBACK_MODEL,
    )
    if not isinstance(result, dict) or "boundaries" not in result:
        log.info("boundary detector returned no usable output; falling back")
        return [0]

    raw_offsets: list[int] = []
    for o in result.get("boundaries") or []:
        try:
            raw_offsets.append(int(o))
        except (TypeError, ValueError):
            continue

    # Normalize — ensure 0 is present, dedupe, sort, clamp to text bounds.
    offsets = {0}
    for o in raw_offsets:
        if 0 <= o < len(text):
            offsets.add(o)
    return sorted(offsets)


def _boundary_prompt(text: str, unit_hint: str) -> str:
    hint_line = (
        f'A "semantic unit" in this document: {unit_hint}\n\n'
        if unit_hint else ""
    )
    return (
        "You are identifying boundaries between semantic units in a document. "
        "Given the text below, return the CHARACTER OFFSETS (0-indexed) where "
        "each new semantic unit begins.\n\n"
        f"{hint_line}"
        "Rules:\n"
        '  - Offset 0 is always the start of a unit — include it.\n'
        "  - Offsets must be positions in the text where a new unit clearly "
        "starts (new topic, new question, new example, new theorem, new "
        "problem, etc.).\n"
        "  - Do NOT split mid-unit. Err on the side of fewer, cleaner "
        "boundaries rather than many.\n"
        "  - Do NOT include the end of the text (use start-of-unit offsets "
        "only).\n"
        "  - Respect atomic blocks — if a block of code or a proof spans "
        "several paragraphs, keep it as one unit.\n\n"
        "Output STRICTLY a JSON object: "
        '{"boundaries": [0, <int>, <int>, ...]}\n\n'
        "TEXT:\n" + text
    )


# ── LLM wrapper ─────────────────────────────────────────────────────────

async def _call_llm_json(
    prompt: str,
    *,
    model: str,
    max_tokens: int,
    fallback_model: str | None = None,
    timeout: float = 30.0,
) -> dict | None:
    """POST to OpenRouter chat/completions, expect JSON in the response.

    Strips markdown fences, parses JSON, returns the dict. On any error
    (network, non-200, parse failure), returns None. If a fallback_model
    is given and the primary fails, retries once with the fallback.
    """
    for candidate in [model, fallback_model] if fallback_model else [model]:
        if candidate is None:
            continue
        try:
            return await _one_llm_call(prompt, candidate, max_tokens, timeout)
        except Exception as e:  # noqa: BLE001
            log.warning("structure LLM (%s) failed: %s", candidate, e)
            continue
    return None


async def _one_llm_call(
    prompt: str, model: str, max_tokens: int, timeout: float
) -> dict | None:
    import httpx
    from app.core.config import settings

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        log.warning("No OPENROUTER_API_KEY — structure classifier disabled")
        return None

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        if resp.status_code != 200:
            log.warning("structure LLM %s returned %d", model, resp.status_code)
            return None
        text = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if the model wrapped the JSON.
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].rstrip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log.warning("structure LLM JSON parse failed: %s", e)
        return None
