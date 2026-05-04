"""Collection synthesis — builds a rich knowledge map after all resources finish processing.

Reads chunk metadata + sampled content across all resources in a collection,
calls Haiku to produce a structured synthesis (overview, resource classification,
topic index, question index, learning path), and stores the result on the
MongoDB collection document.

The tutor uses this synthesis to navigate content intelligently without
needing multiple tool calls on the first turn.

Usage:
    result = await synthesize_collection(collection_id, user_id)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

log = logging.getLogger(__name__)

# Model for synthesis — Haiku for speed and cost
SYNTHESIS_MODEL = "anthropic/claude-haiku-4-5"
MAX_TOKENS = 4096

# Sampling config: how many chunks to sample per resource for context
SAMPLE_FIRST = 2   # first N chunks
SAMPLE_LAST = 1    # last N chunks
SAMPLE_TOP = 2     # chunks with most topics


def _get_db():
    """Get MongoDB database. Import here to avoid circular deps."""
    from app.core.mongodb import get_mongo_db
    return get_mongo_db()


async def synthesize_collection(collection_id: str, user_id: str) -> dict[str, Any]:
    """Build a structured knowledge map for a collection.

    1. Reads all resource docs from MongoDB
    2. Reads chunk TOCs + topics from each resource
    3. Samples a few chunks per resource for context
    4. Calls Haiku to produce a structured synthesis
    5. Stores the result on the collection document
    6. Returns the synthesis dict

    On failure, logs the error and returns an empty dict.
    The old 3-level preload continues to work as fallback.
    """
    db = _get_db()
    start = time.time()

    try:
        # ── 1. Read all resource docs ────────────────────────────────
        resources = []
        async for r in db.byo_resources.find(
            {"collection_id": collection_id, "user_id": user_id, "status": "ready"},
            {"_id": 0, "resource_id": 1, "original_name": 1, "mime_type": 1,
             "chunk_count": 1, "topics": 1, "toc": 1, "meta": 1,
             "source_type": 1, "source_url": 1},
        ):
            resources.append(r)

        if not resources:
            log.warning("Synthesis: no ready resources for collection %s", collection_id[:8])
            return {}

        # ── 2. Read chunk metadata per resource (from Qdrant, not MongoDB) ──
        resource_chunks: dict[str, list[dict]] = {}
        try:
            from byo.shared.store import get_content_store
            store = get_content_store()
            for r in resources:
                rid = r["resource_id"]
                hits = await store.read_resource(rid, user_id=user_id)
                chunks = []
                for h in hits:
                    chunks.append({
                        "chunk_id": h.chunk_id,
                        "index": h.index,
                        "content": h.content[:500],  # truncate for prompt size
                        "anchor": {"page": h.anchor_page, "section": h.anchor_section,
                                   "start_time": h.anchor_start_time, "end_time": h.anchor_end_time},
                        "labels": h.labels,
                        "topics": h.topics,
                        "tokens": len(h.content) // 4,
                        "title": h.title,
                    })
                resource_chunks[rid] = chunks
        except Exception as e:
            log.warning("Synthesis: Qdrant read failed, using TOC only: %s", e)
            # Fallback: use TOC from resource docs (no chunk content)
            for r in resources:
                toc = r.get("toc") or []
                resource_chunks[r["resource_id"]] = [
                    {"chunk_id": t.get("chunk_id", ""), "index": t.get("index", i),
                     "content": "", "anchor": {"page": t.get("page"), "section": t.get("section")},
                     "labels": [], "topics": [], "tokens": 0, "title": t.get("title", "")}
                    for i, t in enumerate(toc)
                ]

        # ── 3. Sample chunks per resource ────────────────────────────
        sampled_content = _sample_chunks(resources, resource_chunks)

        # ── 4. Call Haiku for synthesis ──────────────────────────────
        prompt = _build_synthesis_prompt(resources, resource_chunks, sampled_content)
        synthesis = await _call_llm(prompt)

        if not synthesis:
            log.warning("Synthesis: LLM returned empty result for collection %s", collection_id[:8])
            return {}

        # Add metadata
        synthesis["_meta"] = {
            "created_at": datetime.utcnow().isoformat(),
            "resource_count": len(resources),
            "model": SYNTHESIS_MODEL,
            "elapsed_ms": int((time.time() - start) * 1000),
        }

        # ── 5. Store on collection document ──────────────────────────
        await db.collections.update_one(
            {"collection_id": collection_id},
            {"$set": {
                "synthesis": synthesis,
                "updated_at": datetime.utcnow(),
            }},
        )

        elapsed = int((time.time() - start) * 1000)
        log.info(
            "[BYO] synthesis done collection=%s resources=%d ms=%d",
            collection_id[:8], len(resources), elapsed,
            extra={"event": "BYO_SYNTHESIS_DONE", "collection_id": collection_id,
                   "resources": len(resources), "elapsed_ms": elapsed},
        )

        return synthesis

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        log.error(
            "[BYO] synthesis FAILED collection=%s ms=%d err=%s",
            collection_id[:8], elapsed, repr(e),
            extra={"event": "BYO_SYNTHESIS_FAILED", "collection_id": collection_id,
                   "elapsed_ms": elapsed, "error": repr(e)},
            exc_info=True,
        )
        return {}


def _sample_chunks(
    resources: list[dict],
    resource_chunks: dict[str, list[dict]],
) -> dict[str, list[dict]]:
    """Sample a few chunks per resource: first + last + highest-topic ones."""
    sampled: dict[str, list[dict]] = {}

    for r in resources:
        rid = r["resource_id"]
        chunks = resource_chunks.get(rid, [])
        if not chunks:
            sampled[rid] = []
            continue

        selected: dict[str, dict] = {}  # chunk_id -> chunk (dedup)

        # First N chunks
        for c in chunks[:SAMPLE_FIRST]:
            selected[c["chunk_id"]] = c

        # Last N chunks
        for c in chunks[-SAMPLE_LAST:]:
            selected[c["chunk_id"]] = c

        # Chunks with most topics
        by_topics = sorted(chunks, key=lambda c: len(c.get("topics", [])), reverse=True)
        for c in by_topics[:SAMPLE_TOP]:
            selected[c["chunk_id"]] = c

        # Sort by index for coherent reading
        sampled[rid] = sorted(selected.values(), key=lambda c: c.get("index", 0))

    return sampled


def _build_synthesis_prompt(
    resources: list[dict],
    resource_chunks: dict[str, list[dict]],
    sampled_content: dict[str, list[dict]],
) -> str:
    """Build the LLM prompt for collection synthesis."""
    parts = []

    parts.append(
        "You are analyzing a student's collection of study materials. "
        "Produce a structured JSON synthesis that helps a tutor navigate this content intelligently.\n"
    )

    # Resource catalog
    parts.append("=== RESOURCES ===")
    for i, r in enumerate(resources, 1):
        rid = r["resource_id"]
        name = r.get("original_name", "untitled")
        mime = r.get("mime_type", "unknown")
        pages = (r.get("meta") or {}).get("pages", "?")
        duration = (r.get("meta") or {}).get("duration")
        chunk_count = r.get("chunk_count", 0)
        source_type = r.get("source_type", "file")
        topics = r.get("topics") or []

        info = f"{i}. [{rid[:12]}] {name} (type: {mime}, source: {source_type}"
        if pages and pages != "?":
            info += f", pages: {pages}"
        if duration:
            info += f", duration: {duration}s"
        info += f", chunks: {chunk_count})"

        # Chunk-level topics for this resource
        all_topics: list[str] = list(topics)
        for c in resource_chunks.get(rid, []):
            all_topics.extend(c.get("topics", []))
        unique_topics = list(dict.fromkeys(all_topics))[:20]  # dedup, cap
        if unique_topics:
            info += f"\n   Topics: {', '.join(unique_topics)}"

        # Chunk-level labels
        all_labels: list[str] = []
        for c in resource_chunks.get(rid, []):
            all_labels.extend(c.get("labels", []))
        unique_labels = list(dict.fromkeys(all_labels))[:15]
        if unique_labels:
            info += f"\n   Content types: {', '.join(unique_labels)}"

        # TOC if available
        toc = r.get("toc") or []
        if toc:
            info += "\n   TOC:"
            for entry in toc[:15]:
                title = entry.get("title") or entry.get("section") or ""
                pg = entry.get("page")
                pg_str = f" (p.{pg})" if pg else ""
                info += f"\n     - {title}{pg_str}"

        parts.append(info)

    # Sampled content
    parts.append("\n=== SAMPLED CONTENT (representative excerpts) ===")
    for r in resources:
        rid = r["resource_id"]
        samples = sampled_content.get(rid, [])
        if not samples:
            continue
        parts.append(f"\n--- {r.get('original_name', 'untitled')} ---")
        for c in samples:
            anchor = c.get("anchor", {})
            page = anchor.get("page")
            section = anchor.get("section", "")
            start_time = anchor.get("start_time")
            labels = ", ".join(c.get("labels", []))

            loc_parts = []
            if page:
                loc_parts.append(f"p.{page}")
            if start_time is not None:
                loc_parts.append(f"t={start_time}s")
            if section:
                loc_parts.append(section)
            loc = " | ".join(loc_parts)

            header = f"[chunk {c.get('index', '?')}"
            if loc:
                header += f" | {loc}"
            if labels:
                header += f" | {labels}"
            header += "]"

            # Truncate content to keep prompt manageable
            content = (c.get("content") or "")[:600]
            parts.append(f"{header}\n{content}")

    # Instructions
    parts.append("\n=== INSTRUCTIONS ===")
    parts.append("""Produce a JSON object with these fields:

1. "overview": 1-2 sentence description of what this collection covers.

2. "resources": Array of objects, one per resource:
   {
     "resource_id": "...",
     "name": "...",
     "content_type": one of "lecture" | "textbook" | "slides" | "exam" | "problem_set" | "solutions" | "notes" | "formula_sheet" | "reference" | "video" | "other",
     "role": one of "learning" | "practice" | "reference",
     "smart_toc": [
       {"title": "...", "page": N or null, "start_time": N or null, "topics": ["..."]}
     ],
     "linked_to": "resource_id of related resource (e.g., solutions linked to exam)" or null
   }

   For videos: include topic_timeline entries with start_time in smart_toc.
   For PDFs: include page numbers in smart_toc.
   For exams/problem sets: set role to "practice".
   For answer keys/solutions: set role to "reference" and link to the exam via linked_to.

3. "topic_index": Object mapping topic names to arrays of locations:
   {
     "topic_name": [
       {"resource_id": "...", "resource_name": "...", "page": N, "start_time": N, "context": "brief description"}
     ]
   }
   Merge similar topics (e.g., "binary_tree" and "binary trees" -> "binary_trees").

4. "question_index": Array of questions extracted from exams/problem sets:
   [
     {
       "number": "Q1a",
       "resource_id": "...",
       "resource_name": "...",
       "topic": "...",
       "brief": "short description of what the question asks",
       "page": N or null,
       "marks": N or null,
       "difficulty": "easy" | "medium" | "hard" or null
     }
   ]
   Only include if there are practice materials. Empty array otherwise.

5. "suggested_path": Array of learning steps in recommended order:
   [
     {
       "step": 1,
       "action": "read" | "watch" | "practice" | "review",
       "resource_id": "...",
       "resource_name": "...",
       "focus": "what to focus on",
       "topics": ["..."]
     }
   ]

Output ONLY the JSON object, no other text.""")

    return "\n".join(parts)


async def _call_llm(prompt: str) -> dict[str, Any]:
    """Call Haiku via OpenRouter and parse JSON response."""
    import httpx
    from app.core.config import settings

    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        log.warning("Synthesis: no OPENROUTER_API_KEY — skipping")
        return {}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": SYNTHESIS_MODEL,
                    "max_tokens": MAX_TOKENS,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
            )

            if resp.status_code != 200:
                log.error("Synthesis LLM error: %d %s", resp.status_code, resp.text[:300])
                return {}

            text = resp.json()["choices"][0]["message"]["content"].strip()

            # Handle markdown fences
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3].rstrip()

            result = json.loads(text)

            # Validate expected fields
            expected = {"overview", "resources", "topic_index", "question_index", "suggested_path"}
            missing = expected - set(result.keys())
            if missing:
                log.warning("Synthesis: LLM response missing fields: %s", missing)
                # Fill in missing fields with defaults
                for field in missing:
                    if field == "overview":
                        result[field] = ""
                    elif field in ("resources", "question_index", "suggested_path"):
                        result[field] = []
                    elif field == "topic_index":
                        result[field] = {}

            return result

    except json.JSONDecodeError as e:
        log.error("Synthesis: JSON parse error: %s", e)
        return {}
    except Exception as e:
        log.error("Synthesis: LLM call failed: %s", repr(e))
        return {}


def format_synthesis_for_prompt(synthesis: dict, collection_title: str = "",
                               resource_docs: list[dict] | None = None) -> str:
    """Format a synthesis dict into a text block for the tutor system prompt.

    resource_docs: list of MongoDB resource documents (with resource_id, source_url, etc.)
    Used to build direct media URLs so the tutor never needs to construct them from IDs.
    """
    if not synthesis or not synthesis.get("overview"):
        return ""

    # Build resource_id → direct URL map (keyed by BOTH full ID and prefix)
    _url_map = {}
    _name_map = {}  # resource name → URL (fallback for when IDs are mangled)
    for rd in (resource_docs or []):
        rid = rd.get("resource_id", "")
        name = rd.get("original_name", "")
        source_url = rd.get("source_url", "")
        if source_url and ("youtube" in source_url or "youtu.be" in source_url):
            url = source_url  # YouTube → direct URL
        elif source_url and any(source_url.lower().endswith(ext) for ext in ('.mp4', '.webm', '.ogg', '.mov')):
            url = source_url  # Public video URL → direct
        else:
            url = f"/api/v1/byo/resources/{rid}/file"  # Uploaded → file endpoint
        _url_map[rid] = url
        # Also key by prefix (Haiku truncates IDs)
        if len(rid) >= 8:
            _url_map[rid[:8]] = url
            _url_map[rid[:12]] = url
        if name:
            _name_map[name.lower()] = url

    parts = []

    # Header + overview
    title = collection_title or "Student Collection"
    parts.append(f"[COLLECTION -- {title}]")
    parts.append(synthesis.get("overview", ""))

    # Resources
    resources = synthesis.get("resources", [])
    if resources:
        parts.append("\nRESOURCES:")
        for r in resources:
            name = r.get("name", "untitled")
            ctype = r.get("content_type", "other")
            role = r.get("role", "learning")
            rid = r.get("resource_id", "")
            rname = r.get("name", "")
            # Match by full ID, prefix, or resource name
            media_url = _url_map.get(rid) or _url_map.get(rid[:12]) or _url_map.get(rid[:8]) or _name_map.get(rname.lower(), "")
            line = f"  {name} ({ctype}, {role})"
            if media_url:
                line += f"\n    media: {media_url}"
            linked = r.get("linked_to")
            if linked:
                linked_name = next((rr.get("name", linked[:12]) for rr in resources if rr.get("resource_id") == linked), linked[:12])
                line += f"\n    linked to: {linked_name}"
            parts.append(line)

            # Smart TOC
            toc = r.get("smart_toc", [])
            for entry in toc[:12]:
                title_str = entry.get("title", "")
                pg = entry.get("page")
                ts = entry.get("start_time")
                topics = entry.get("topics", [])
                loc = ""
                if pg:
                    loc = f"p.{pg}"
                elif ts is not None:
                    loc = f"t={ts}s"
                topic_str = f" [{', '.join(topics)}]" if topics else ""
                parts.append(f"    - {title_str} {loc}{topic_str}")

    # Topic map
    topic_index = synthesis.get("topic_index", {})
    if topic_index:
        parts.append("\nTOPIC MAP:")
        for topic, locations in topic_index.items():
            loc_strs = []
            for loc in locations[:5]:
                rname = loc.get("resource_name", "")
                pg = loc.get("page")
                ts = loc.get("start_time")
                ref = rname
                if pg:
                    ref += f" p.{pg}"
                elif ts is not None:
                    ref += f" t={ts}s"
                loc_strs.append(ref)
            parts.append(f"  {topic}: {' | '.join(loc_strs)}")

    # Practice / question index
    questions = synthesis.get("question_index", [])
    if questions:
        parts.append("\nPRACTICE:")
        for q in questions:
            num = q.get("number", "?")
            topic = q.get("topic", "")
            brief = q.get("brief", "")
            marks = q.get("marks")
            rname = q.get("resource_name", "")
            line = f"  {num}. {brief}"
            if topic:
                line += f" [{topic}]"
            if marks:
                line += f" ({marks} marks)"
            if rname:
                line += f" -- {rname}"
            parts.append(line)

    # Suggested path
    path = synthesis.get("suggested_path", [])
    if path:
        parts.append("\nSUGGESTED PATH:")
        for step in path:
            n = step.get("step", "?")
            action = step.get("action", "read")
            rname = step.get("resource_name", "")
            focus = step.get("focus", "")
            parts.append(f"  {n}. {action.upper()}: {rname} -- {focus}")

    return "\n".join(parts)
