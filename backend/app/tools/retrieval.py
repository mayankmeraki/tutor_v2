"""Unified retrieval tool handlers — search / fetch / peek / nearby / list_contents.

Course content has been retired — these handlers operate on BYO
(student-uploaded) materials only. Refs use the BYO format:
  chunk:.. / segment:.. / resource:..

Every BYO call needs `user_id` — pulled from session context
(studentProfile.userEmail). Missing user_id returns an error string
so the tutor can course-correct.

All handlers return strings formatted for direct LLM consumption
(truncated, with citations). Errors come back as informative strings,
never raised — the tutor handles them gracefully.
"""

from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)


# ── Context helpers ───────────────────────────────────────────────────────────


def _get_user_id(context_data: dict | None) -> str:
    """Resolve user_id (the security boundary for BYO) from session context."""
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
    """Return the coarse ref kind: 'byo' | 'unknown'."""
    if not ref or ":" not in ref:
        return "unknown"
    prefix = ref.split(":", 1)[0].strip().lower()
    if prefix in ("chunk", "segment", "resource"):
        return "byo"
    return "unknown"


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
    lines = [f"  {ref}  {tag}{title}{cite}" if title else f"  {ref}  {tag}{cite}"]
    if segment and segment != parent:
        lines.append(f"    [match] {_truncate(segment.replace(chr(10), ' '), 200)}")
        lines.append(f"    [context] {_truncate(parent, snippet_chars)}")
    else:
        lines.append(f"    {_truncate(parent, snippet_chars)}")
    images = getattr(h, 'image_refs', []) or []
    if images:
        for img in images[:3]:
            lines.append(f"    [image] {img.get('url', '')} — {img.get('description', '')[:80]}")
    return "\n".join(lines)


# ── search_tool ──────────────────────────────────────────────────────────────


async def search_tool(
    tool_input: dict, *, context_data: dict | None = None
) -> str:
    """Semantic search across student-uploaded (BYO) content."""
    query = (tool_input.get("query") or "").strip()
    if not query:
        return "Error: query is required"

    scope = (tool_input.get("scope") or "").strip() or None
    collection_id = (tool_input.get("collection_id") or "").strip() or None
    resource_id = (tool_input.get("resource_id") or "").strip() or None
    k = int(tool_input.get("k") or 5)
    modality_filter = tool_input.get("modality_filter") or None

    if scope is None:
        scope = "collection" if (collection_id or _get_collection_id(context_data)) else "user_corpus"

    if scope in ("collection", "both") and not collection_id:
        collection_id = _get_collection_id(context_data) or None

    user_id = _get_user_id(context_data)

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

    if scope not in ("collection", "resource", "user_corpus"):
        return f"Error: unknown scope '{scope}'. Use 'collection', 'resource', or 'user_corpus'."

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

    try:
        from byo.retrieval import service as retrieval_service
        hits = await retrieval_service.search(
            query,
            user_id=user_id,
            scope=scope,  # type: ignore[arg-type]
            collection_id=collection_id,
            resource_id=resource_id,
            modality_filter=modality_enums,
            k=k,
        )
    except Exception as e:
        log.warning("BYO search failed (scope=%s): %s", scope, e)
        return f"Error: BYO search failed: {str(e)[:200]}"

    if not hits:
        return f'No results for "{query}" in {scope}.'
    lines = [f'Search results for "{query}" ({scope}):']
    lines.extend(_fmt_byo_hit(h) for h in hits)
    return "\n".join(lines)


# ── fetch_tool ──────────────────────────────────────────────────────────────


async def fetch_tool(
    tool_input: dict, *, context_data: dict | None = None
) -> str:
    ref = (tool_input.get("ref") or "").strip()
    if not ref:
        return "Error: ref is required"

    if _classify_ref(ref) != "byo":
        return (
            f"Error: unknown ref format '{ref}'. "
            "Use chunk:ID, segment:ID, or resource:ID."
        )

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
    images = getattr(hit, 'image_refs', []) or []
    if images:
        parts.append("Images:")
        for img in images[:5]:
            parts.append(f"  [image] {img.get('url', '')} — {img.get('description', '')[:120]}")
    parts.append(f"Source: {citation}")
    return "\n".join(parts)


# ── peek_tool ──────────────────────────────────────────────────────────────


async def peek_tool(
    tool_input: dict, *, context_data: dict | None = None
) -> str:
    ref = (tool_input.get("ref") or "").strip()
    if not ref:
        return "Error: ref is required"

    if _classify_ref(ref) != "byo":
        return (
            f"Error: unknown ref format '{ref}'. "
            "Use chunk:ID, segment:ID, or resource:ID."
        )

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


# ── nearby_tool ──────────────────────────────────────────────────────────────


async def nearby_tool(
    tool_input: dict, *, context_data: dict | None = None
) -> str:
    ref = (tool_input.get("ref") or "").strip()
    if not ref:
        return "Error: ref is required"
    window = int(tool_input.get("window") or 1)

    if _classify_ref(ref) != "byo":
        return (
            f"Error: unknown ref format '{ref}'. "
            "Use chunk:ID, segment:ID, or resource:ID."
        )

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


# ── list_contents_tool ───────────────────────────────────────────────────────


async def list_contents_tool(
    tool_input: dict, *, context_data: dict | None = None
) -> str:
    scope = (tool_input.get("scope") or "").strip()
    if not scope:
        return "Error: scope is required"

    if scope not in ("collection", "user_corpus"):
        return f"Error: unknown scope '{scope}'. Use 'collection' or 'user_corpus'."

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
