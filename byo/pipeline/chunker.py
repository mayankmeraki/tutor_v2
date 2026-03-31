"""Structure-aware chunker — splits markdown into chunks.

Strategy:
1. Split by headers (h1 = chapter, h2 = section, h3 = subsection)
2. If a section > 800 tokens, split at paragraph breaks
3. If a section < 100 tokens, merge with next
4. Preserve page references and timestamps per chunk
5. Keep code blocks and tables atomic (don't split mid-block)
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

log = logging.getLogger(__name__)

# Target chunk size in tokens (~4 chars per token)
TARGET_TOKENS = 600
MAX_TOKENS = 1000
MIN_TOKENS = 80


async def chunk_markdown(
    markdown: str,
    resource_id: str,
    collection_id: str,
    resource_meta: dict[str, Any] | None = None,
) -> list[dict]:
    """Split markdown into chunks. Returns list of chunk dicts.

    Each chunk has: chunk_id, content, tokens, anchor, index.
    Labels and topics are added later by the classifier.
    """
    if not markdown.strip():
        return []

    resource_meta = resource_meta or {}
    sections = _split_by_headers(markdown)
    chunks = []

    for sec in sections:
        sec_chunks = _split_section(sec)
        for sc in sec_chunks:
            if sc["tokens"] < MIN_TOKENS and chunks:
                # Merge tiny chunks with previous
                chunks[-1]["content"] += "\n\n" + sc["content"]
                chunks[-1]["tokens"] += sc["tokens"]
            else:
                chunks.append(sc)

    # Assign IDs, indexes, and anchors
    result = []
    for i, chunk in enumerate(chunks):
        # Detect page references from markdown comments
        page = _detect_page(chunk["content"])
        # Detect timestamps from [MM:SS] patterns
        timestamp = _detect_timestamp(chunk["content"])

        result.append({
            "chunk_id": str(uuid.uuid4()),
            "collection_id": collection_id,
            "resource_id": resource_id,
            "index": i,
            "content": chunk["content"].strip(),
            "tokens": chunk["tokens"],
            "anchor": {
                "page": page,
                "start_time": timestamp[0] if timestamp else None,
                "end_time": timestamp[1] if timestamp else None,
                "section": chunk.get("heading"),
            },
            "labels": [],
            "topics": [],
            "attachments": [],
            "embedding": None,
        })

    log.info("Chunked %s: %d chunks from %d chars",
            resource_id[:8], len(result), len(markdown))
    return result


def _split_by_headers(markdown: str) -> list[dict]:
    """Split markdown by header boundaries."""
    lines = markdown.split("\n")
    sections = []
    current = {"heading": None, "lines": []}

    for line in lines:
        header_match = re.match(r"^(#{1,3})\s+(.+)", line)
        if header_match:
            # Save previous section
            if current["lines"]:
                sections.append(current)
            current = {
                "heading": header_match.group(2).strip(),
                "level": len(header_match.group(1)),
                "lines": [line],
            }
        else:
            current["lines"].append(line)

    if current["lines"]:
        sections.append(current)

    return sections


def _split_section(section: dict) -> list[dict]:
    """Split a section into chunks if it's too long."""
    content = "\n".join(section["lines"])
    tokens = len(content) // 4

    if tokens <= MAX_TOKENS:
        return [{"content": content, "tokens": tokens, "heading": section.get("heading")}]

    # Split at paragraph breaks (double newline)
    paragraphs = re.split(r"\n\n+", content)
    chunks = []
    current_chunk = {"content": "", "tokens": 0, "heading": section.get("heading")}

    for para in paragraphs:
        para_tokens = len(para) // 4

        # Keep code blocks and tables atomic
        if para.startswith("```") or para.startswith("|"):
            if current_chunk["tokens"] + para_tokens > MAX_TOKENS and current_chunk["tokens"] > MIN_TOKENS:
                chunks.append(current_chunk)
                current_chunk = {"content": "", "tokens": 0, "heading": section.get("heading")}
            current_chunk["content"] += ("\n\n" if current_chunk["content"] else "") + para
            current_chunk["tokens"] += para_tokens
            continue

        if current_chunk["tokens"] + para_tokens > TARGET_TOKENS and current_chunk["tokens"] > MIN_TOKENS:
            chunks.append(current_chunk)
            current_chunk = {"content": para, "tokens": para_tokens, "heading": section.get("heading")}
        else:
            current_chunk["content"] += ("\n\n" if current_chunk["content"] else "") + para
            current_chunk["tokens"] += para_tokens

    if current_chunk["content"]:
        chunks.append(current_chunk)

    return chunks


def _detect_page(content: str) -> int | None:
    """Detect page number from markdown comments like <!-- page 5 -->."""
    m = re.search(r"<!--\s*page\s+(\d+)\s*-->", content)
    if m:
        return int(m.group(1))
    return None


def _detect_timestamp(content: str) -> tuple[float, float] | None:
    """Detect timestamp range from [MM:SS] patterns."""
    timestamps = re.findall(r"\[(\d+):(\d{2})\]", content)
    if len(timestamps) >= 2:
        first = int(timestamps[0][0]) * 60 + int(timestamps[0][1])
        last = int(timestamps[-1][0]) * 60 + int(timestamps[-1][1])
        return (first, last)
    elif len(timestamps) == 1:
        t = int(timestamps[0][0]) * 60 + int(timestamps[0][1])
        return (t, t + 30)  # assume ~30s window
    return None
