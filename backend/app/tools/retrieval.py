"""Unified retrieval tool handlers — search / fetch / peek / nearby / list_contents.

These replace the old split-brain surface (byo_read, byo_list,
byo_transcript_context, content_read, content_peek, content_search,
get_section_content, get_simulation_details) with a single ref-based API
that works across BOTH course content AND BYO (student-uploaded) materials.

Routing is explicit on the caller side:
  - `search` takes a `scope` arg ("course" | "collection" | "resource" |
    "user_corpus" | "both") and fans out to the right backend.
  - `fetch`/`peek`/`nearby` inspect the ref prefix:
      lesson:.. / sim:.. / simulation:..   → course adapter
      chunk:.. / segment:.. / resource:..  → BYO retrieval service
  - `list_contents` takes a `scope` arg.

Every BYO-side call needs `user_id` — enforced at the service layer, we
pull it from the session context here (studentProfile.userEmail). No
silent fallback: missing user_id on a BYO scope returns an error string
so the tutor can course-correct.

All handlers return strings formatted for direct LLM consumption
(truncated, with citations). Errors come back as informative strings,
never raised — the tutor handles them gracefully.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

log = logging.getLogger(__name__)


# ── Context helpers ───────────────────────────────────────────────────────────


def _get_user_id(context_data: dict | None) -> str:
    """Resolve user_id (the security boundary for BYO) from session context.

    Pattern matches `_extract_user_email` in services/teaching/pipeline.py.
    """
    if not context_data:
        return ""
    profile_str = context_data.get("studentProfile", "")
    if not profile_str:
        return ""
    try:
        profile = (
            json.loads(profile_str) if isinstance(profile_str, str) else profile_str
        )
        return (
            profile.get("userEmail")
            or profile.get("userId")
            or profile.get("user_id")
            or ""
        )
    except (json.JSONDecodeError, TypeError):
        return ""


def _get_course_id(context_data: dict | None) -> int | None:
    if not context_data:
        return None
    profile_str = context_data.get("studentProfile", "")
    if profile_str:
        try:
            profile = (
                json.loads(profile_str)
                if isinstance(profile_str, str)
                else profile_str
            )
            cid = profile.get("courseId") or profile.get("course_id")
            if cid:
                return int(cid)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    cid = context_data.get("courseId") or context_data.get("course_id")
    if cid:
        try:
            return int(cid)
        except (TypeError, ValueError):
            return None
    return None


def _get_collection_id(context_data: dict | None) -> str:
    """Fallback collection_id from sessionContext.collection_id."""
    if not context_data:
        return ""
    sc = context_data.get("sessionContext", "")
    if not sc:
        return ""
    try:
        ctx = json.loads(sc) if isinstance(sc, str) else sc
        return ctx.get("collection_id") or ctx.get("collectionId") or ""
    except (json.JSONDecodeError, TypeError, AttributeError):
        return ""


def _classify_ref(ref: str) -> str:
    """Return the coarse ref kind: 'course' | 'byo' | 'unknown'.

    lesson:.. / sim:.. / simulation:..  → course
    chunk:.. / segment:.. / resource:.. → byo
    """
    if not ref or ":" not in ref:
        return "unknown"
    prefix = ref.split(":", 1)[0].strip().lower()
    if prefix in ("lesson", "sim", "simulation"):
        return "course"
    if prefix in ("chunk", "segment", "resource"):
        return "byo"
    return "unknown"


async def _get_course_adapter(context_data: dict | None):
    """Create a CapacityCourseAdapter from context. Returns None if unavailable."""
    course_id = _get_course_id(context_data)
    if not course_id:
        return None
    try:
        from app.core.database import get_db
        from app.services.content.providers import create_adapter
        db_gen = get_db()
        db_session = await db_gen.__anext__()
        return create_adapter(course_id, db_session)
    except Exception as e:
        log.warning("Failed to build course adapter: %s", e)
        return None


# ── Formatters ────────────────────────────────────────────────────────────────


def _fmt_anchor(anchor) -> str:
    if anchor is None:
        return ""
    parts: list[str] = []
    page = getattr(anchor, "page", None)
    section = getattr(anchor, "section", None)
    start = getattr(anchor, "start_time", None)
    if page is not None:
        parts.append(f"p. {page}")
    if section:
        parts.append(str(section))
    if start is not None:
        m = int(start // 60)
        s = int(start % 60)
        parts.append(f"{m}:{s:02d}")
    return " · ".join(parts)


def _truncate(text: str, n: int = 500) -> str:
    if not text:
        return ""
    return text if len(text) <= n else text[:n].rstrip() + "…"


def _fmt_byo_hit(h, *, snippet_chars: int = 500) -> str:
    ref = f"chunk:{h.chunk_id}"
    # Show segment match (what matched the query) + parent context
    segment = getattr(h, "segment_content", "") or ""
    parent = (h.content or "").replace("\n", " ")
    title = getattr(h, "title", "") or ""
    labels = ", ".join(h.labels) if h.labels else ""
    tag = f"[{labels}] " if labels else ""
    cite_bits: list[str] = []
    if getattr(h, "resource_name", ""):
        cite_bits.append(h.resource_name)
    anchor_str = _fmt_anchor(h.anchor)
    if anchor_str:
        cite_bits.append(anchor_str)
    cite = f" — {' · '.join(cite_bits)}" if cite_bits else ""
    # Title + matched segment + parent preview
    lines = [f"  {ref}  {tag}{title}{cite}" if title else f"  {ref}  {tag}{cite}"]
    if segment and segment != parent:
        lines.append(f"    [match] {_truncate(segment.replace(chr(10), ' '), 200)}")
        lines.append(f"    [context] {_truncate(parent, snippet_chars)}")
    else:
        lines.append(f"    {_truncate(parent, snippet_chars)}")
    # Append image references if present
    images = getattr(h, 'image_refs', []) or []
    if images:
        for img in images[:3]:
            lines.append(f"    [image] {img.get('url', '')} — {img.get('description', '')[:80]}")
    return "\n".join(lines)


def _fmt_course_hit(r: dict) -> str:
    """Format one search_content row into the unified shape."""
    ref = f"lesson:{r['lessonId']}" if r.get("lessonId") else ""
    title = r.get("title", "?") or "?"
    desc = _truncate((r.get("description") or "").replace("\n", " "), 250)
    lines = [f"  {ref}  [{r.get('type', '?')}] {title}"]
    if desc:
        lines.append(f"         {desc}")
    return "\n".join(lines)


# ── search_tool ──────────────────────────────────────────────────────────────


async def search_tool(
    tool_input: dict, *, context_data: dict | None = None
) -> str:
    """Unified search across course + BYO."""
    query = (tool_input.get("query") or "").strip()
    if not query:
        return "Error: query is required"

    scope = (tool_input.get("scope") or "").strip() or None
    collection_id = (tool_input.get("collection_id") or "").strip() or None
    resource_id = (tool_input.get("resource_id") or "").strip() or None
    k = int(tool_input.get("k") or 5)
    modality_filter = tool_input.get("modality_filter") or None

    # Default scope: if caller has a BYO collection in session context AND a course,
    # use "both"; else whichever is available.
    has_byo = bool(collection_id or _get_collection_id(context_data))
    has_course = _get_course_id(context_data) is not None
    if scope is None:
        if has_byo and has_course:
            scope = "both"
        elif has_byo:
            scope = "collection"
        else:
            scope = "course"

    # Fallback collection_id from session context when relevant
    if scope in ("collection", "both") and not collection_id:
        collection_id = _get_collection_id(context_data) or None

    user_id = _get_user_id(context_data)

    # Convert modality strings to Modality enums
    modality_enums = None
    if modality_filter:
        try:
            from byo.shared.models import Modality
            modality_enums = []
            for m in modality_filter:
                try:
                    modality_enums.append(Modality(m))
                except (ValueError, TypeError):
                    log.debug("Unknown modality filter: %s", m)
            if not modality_enums:
                modality_enums = None
        except ImportError:
            modality_enums = None

    async def _byo_search(byo_scope: str) -> list:
        if not user_id:
            return []
        try:
            from byo.retrieval import service as retrieval_service
            return await retrieval_service.search(
                query,
                user_id=user_id,
                scope=byo_scope,  # type: ignore[arg-type]
                collection_id=collection_id,
                resource_id=resource_id,
                modality_filter=modality_enums,
                k=k,
            )
        except Exception as e:
            log.warning("BYO search failed (scope=%s): %s", byo_scope, e)
            return []

    async def _course_search() -> list[dict]:
        try:
            from app.services.content.content_service import search_content
            return await search_content(query, limit=k)
        except Exception as e:
            log.warning("Course search failed: %s", e)
            return []

    # Dispatch
    if scope == "course":
        rows = await _course_search()
        if not rows:
            return f'No course results for "{query}".'
        return f'Search results for "{query}" (course):\n' + "\n".join(
            _fmt_course_hit(r) for r in rows[:k]
        )

    if scope in ("collection", "resource", "user_corpus"):
        if scope == "collection" and not collection_id:
            return (
                "Error: scope='collection' requires collection_id "
                "(from session context or your input)."
            )
        if scope == "resource" and not resource_id:
            return "Error: scope='resource' requires resource_id."
        if not user_id:
            return (
                "Error: missing user_id for BYO search. "
                "Session context did not carry a student identifier."
            )
        hits = await _byo_search(scope)
        if not hits:
            return f'No results for "{query}" in {scope}.'
        lines = [f'Search results for "{query}" ({scope}):']
        lines.extend(_fmt_byo_hit(h) for h in hits)
        return "\n".join(lines)

    if scope == "both":
        # Run both in parallel. Course results are dict-shaped; BYO are RetrievedChunk.
        # Merge sorted by score (course uses the re-ranker's relevance order already —
        # we assign a pseudo-score by rank; BYO carries .score).
        byo_scope = "collection" if collection_id else "user_corpus"
        if byo_scope == "collection" and not collection_id:
            byo_scope = "user_corpus"
        if byo_scope == "user_corpus" and not user_id:
            # Can only do course side
            rows = await _course_search()
            if not rows:
                return f'No results for "{query}".'
            return f'Search results for "{query}" (course — BYO unavailable):\n' + (
                "\n".join(_fmt_course_hit(r) for r in rows[:k])
            )

        course_task = _course_search()
        byo_task = _byo_search(byo_scope)
        course_rows, byo_hits = await asyncio.gather(course_task, byo_task)

        # Produce unified output — BYO block first (student's own material wins on
        # equal relevance), then course. Cap total at k hits combined is too strict —
        # show up to k per side to give the tutor real choice.
        if not course_rows and not byo_hits:
            return f'No results for "{query}".'

        lines = [f'Search results for "{query}" (course + BYO):']
        if byo_hits:
            lines.append("\n-- From your uploaded materials --")
            lines.extend(_fmt_byo_hit(h) for h in byo_hits[:k])
        if course_rows:
            lines.append("\n-- From course --")
            lines.extend(_fmt_course_hit(r) for r in course_rows[:k])
        return "\n".join(lines)

    return f"Error: unknown scope '{scope}'."


# ── fetch_tool ──────────────────────────────────────────────────────────────


async def fetch_tool(
    tool_input: dict, *, context_data: dict | None = None
) -> str:
    ref = (tool_input.get("ref") or "").strip()
    if not ref:
        return "Error: ref is required"

    kind = _classify_ref(ref)

    if kind == "course":
        adapter = await _get_course_adapter(context_data)
        if adapter is None:
            return "Error: no course in this session — cannot fetch course refs."
        try:
            return await adapter.content_read(ref)
        except Exception as e:
            log.warning("fetch (course) failed for %s: %s", ref, e)
            return f"Error fetching {ref}: {str(e)[:200]}"

    if kind == "byo":
        user_id = _get_user_id(context_data)
        if not user_id:
            return "Error: missing user_id for BYO fetch."
        try:
            from byo.retrieval import service as retrieval_service
            hit = await retrieval_service.fetch(ref, user_id=user_id)
        except Exception as e:
            log.warning("fetch (BYO) failed for %s: %s", ref, e)
            return f"Error fetching {ref}: {str(e)[:200]}"
        if not hit:
            return f"{ref} not found."
        cite_parts: list[str] = []
        if hit.resource_name:
            cite_parts.append(hit.resource_name)
        anchor_str = _fmt_anchor(hit.anchor)
        if anchor_str:
            cite_parts.append(anchor_str)
        citation = " — ".join(cite_parts) if cite_parts else hit.chunk_id
        parts = []
        if hit.title:
            parts.append(f"[{hit.title}]")
        parts.append(hit.content or "")
        if hit.labels:
            parts.append(f"\nType: {', '.join(hit.labels)}")
        if hit.topics:
            parts.append(f"Topics: {', '.join(hit.topics)}")
        # Include image references from the chunk
        images = getattr(hit, 'image_refs', []) or []
        if images:
            parts.append("Images:")
            for img in images[:5]:
                parts.append(f"  [image] {img.get('url', '')} — {img.get('description', '')[:120]}")
        parts.append(f"Source: {citation}")
        return "\n".join(parts)

    return (
        f"Error: unknown ref format '{ref}'. "
        "Use lesson:ID, lesson:ID:section:IDX, sim:ID, chunk:ID, segment:ID, or resource:ID."
    )


# ── peek_tool ──────────────────────────────────────────────────────────────


async def peek_tool(
    tool_input: dict, *, context_data: dict | None = None
) -> str:
    ref = (tool_input.get("ref") or "").strip()
    if not ref:
        return "Error: ref is required"

    kind = _classify_ref(ref)

    if kind == "course":
        adapter = await _get_course_adapter(context_data)
        if adapter is None:
            return "Error: no course in this session — cannot peek course refs."
        try:
            return await adapter.content_peek(ref)
        except Exception as e:
            log.warning("peek (course) failed for %s: %s", ref, e)
            return f"Error peeking {ref}: {str(e)[:200]}"

    if kind == "byo":
        user_id = _get_user_id(context_data)
        if not user_id:
            return "Error: missing user_id for BYO peek."
        try:
            from byo.retrieval import service as retrieval_service
            summary = await retrieval_service.peek(ref, user_id=user_id)
        except Exception as e:
            log.warning("peek (BYO) failed for %s: %s", ref, e)
            return f"Error peeking {ref}: {str(e)[:200]}"
        if not summary:
            return f"{ref} not found."
        lines: list[str] = []
        # peek returns a dict for BYO, an object for course
        if isinstance(summary, dict):
            resource = summary.get("resource_name", "")
            snippet = summary.get("snippet", "")
            page = summary.get("page")
            section = summary.get("section", "")
            topics = summary.get("topics", [])
            header = f"[{resource}]" if resource else ""
            if page:
                header += f" p.{page}"
            if section:
                header += f" {section}"
            lines.append(f"{header} {snippet}" if header else snippet)
            if topics:
                lines.append(f"Topics: {', '.join(topics[:5])}")
        else:
            if getattr(summary, "title", ""):
                lines.append(f"[{summary.title}] {summary.snippet}")
            else:
                lines.append(getattr(summary, "snippet", "") or "")
            anchor_str = _fmt_anchor(getattr(summary, "anchor", None))
            if anchor_str:
                lines.append(f"At: {anchor_str}")
        return "\n".join(lines)

    return (
        f"Error: unknown ref format '{ref}'. "
        "Use lesson:ID, lesson:ID:section:IDX, sim:ID, chunk:ID, segment:ID, or resource:ID."
    )


# ── nearby_tool ──────────────────────────────────────────────────────────────


async def nearby_tool(
    tool_input: dict, *, context_data: dict | None = None
) -> str:
    ref = (tool_input.get("ref") or "").strip()
    if not ref:
        return "Error: ref is required"
    window = int(tool_input.get("window") or 1)

    kind = _classify_ref(ref)

    if kind == "course":
        adapter = await _get_course_adapter(context_data)
        if adapter is None:
            return "Error: no course in this session — cannot walk course refs."
        try:
            return await adapter.content_nearby(ref, window=window)
        except Exception as e:
            log.warning("nearby (course) failed for %s: %s", ref, e)
            return f"Error walking {ref}: {str(e)[:200]}"

    if kind == "byo":
        user_id = _get_user_id(context_data)
        if not user_id:
            return "Error: missing user_id for BYO nearby."
        try:
            from byo.retrieval import service as retrieval_service
            hits = await retrieval_service.nearby(
                ref, user_id=user_id, window=window,
            )
        except Exception as e:
            log.warning("nearby (BYO) failed for %s: %s", ref, e)
            return f"Error walking {ref}: {str(e)[:200]}"
        if not hits:
            return f"No nearby content for {ref}."
        lines: list[str] = []
        for h in hits:
            header = f"chunk:{h.chunk_id}"
            anchor_str = _fmt_anchor(h.anchor)
            if anchor_str:
                header = f"{header} ({anchor_str})"
            lines.append(header)
            lines.append(_truncate(h.content or "", 800))
            lines.append("")
        return "\n".join(lines).rstrip()

    return (
        f"Error: unknown ref format '{ref}'. "
        "Use lesson:ID:section:IDX for course, or chunk:ID / segment:ID / resource:ID for BYO."
    )


# ── list_contents_tool ───────────────────────────────────────────────────────


async def list_contents_tool(
    tool_input: dict, *, context_data: dict | None = None
) -> str:
    scope = (tool_input.get("scope") or "").strip()
    if not scope:
        return "Error: scope is required"

    if scope == "course":
        adapter = await _get_course_adapter(context_data)
        if adapter is None:
            return "Error: no course in this session."
        try:
            return await adapter.content_map()
        except Exception as e:
            log.warning("list_contents (course) failed: %s", e)
            return f"Error listing course: {str(e)[:200]}"

    if scope in ("collection", "user_corpus"):
        user_id = _get_user_id(context_data)
        if not user_id:
            return "Error: missing user_id for BYO list_contents."

        collection_id = (
            (tool_input.get("collection_id") or "").strip()
            or _get_collection_id(context_data)
        )
        if scope == "collection" and not collection_id:
            return (
                "Error: scope='collection' requires collection_id "
                "(from session context or your input)."
            )

        group_by = tool_input.get("group_by") or "resource"

        try:
            from byo.retrieval import service as retrieval_service
            if scope == "user_corpus":
                # Aggregate across all collections by listing the user's collections first.
                from app.core.mongodb import get_mongo_db
                db = get_mongo_db()
                cursor = db.collections.find(
                    {"user_id": user_id},
                    {"_id": 0, "collection_id": 1, "title": 1, "stats": 1},
                )
                collections = [c async for c in cursor]
                if not collections:
                    return "You have no BYO collections."
                lines = ["Your collections:"]
                for c in collections:
                    cid = c.get("collection_id", "")
                    title = c.get("title", "(untitled)")
                    stats = c.get("stats") or {}
                    res = stats.get("resources", 0)
                    chunks = stats.get("chunks", 0)
                    lines.append(f"  collection:{cid}  {title} — {res} resources, {chunks} chunks")
                return "\n".join(lines)

            refs = await retrieval_service.list_contents(
                collection_id,
                user_id=user_id,
                group_by=group_by,  # type: ignore[arg-type]
            )
        except Exception as e:
            log.warning("list_contents (BYO) failed: %s", e)
            return f"Error listing collection: {str(e)[:200]}"

        if not refs:
            return f"Collection {collection_id} is empty or has no extractable content."
        lines = [f"Contents of collection {collection_id}:"]
        for r in refs:
            # list_contents returns dicts grouped by resource
            if isinstance(r, dict):
                resource = r.get("resource", "?")
                chunks = r.get("chunks", [])
                lines.append(f"\n  {resource} ({len(chunks)} sections)")
                for c in chunks[:5]:
                    ref = c.get("ref", "")
                    page = c.get("page")
                    snippet = (c.get("snippet") or "")[:80]
                    page_str = f" p.{page}" if page else ""
                    lines.append(f"    {ref}{page_str}  {snippet}")
                if len(chunks) > 5:
                    lines.append(f"    ... and {len(chunks) - 5} more")
            else:
                lines.append(f"  {getattr(r, 'ref', '?')}  {getattr(r, 'title', '?')} — {getattr(r, 'snippet', '')}")
        return "\n".join(lines)

    return f"Error: unknown scope '{scope}'. Use 'course', 'collection', or 'user_corpus'."
