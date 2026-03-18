"""Text extractor — normalization and structure detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TextExtractResult:
    title: str
    text: str
    char_count: int
    structure_hints: dict = field(default_factory=dict)


def normalize_text(content: str) -> str:
    """Normalize whitespace, encoding, and line endings."""
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse multiple blank lines into max 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Normalize unicode whitespace
    text = text.replace("\u00a0", " ")  # non-breaking space
    text = text.replace("\u200b", "")   # zero-width space
    return text.strip()


def detect_structure(text: str) -> dict:
    """Detect structural elements in text."""
    hints: dict = {
        "has_headings": False,
        "has_numbered_list": False,
        "has_bullet_list": False,
        "has_code_blocks": False,
        "has_equations": False,
        "heading_count": 0,
    }

    # Markdown headings
    headings = re.findall(r"^#{1,6}\s+.+", text, re.MULTILINE)
    if headings:
        hints["has_headings"] = True
        hints["heading_count"] = len(headings)

    # Numbered lists
    if re.search(r"^\s*\d+[.)]\s+", text, re.MULTILINE):
        hints["has_numbered_list"] = True

    # Bullet lists
    if re.search(r"^\s*[-*•]\s+", text, re.MULTILINE):
        hints["has_bullet_list"] = True

    # Code blocks
    if "```" in text:
        hints["has_code_blocks"] = True

    # Math/equations (LaTeX-style)
    if re.search(r"\$\$.+?\$\$|\\\[.+?\\\]|\\frac|\\int|\\sum", text, re.DOTALL):
        hints["has_equations"] = True

    return hints


async def extract_text(content: str, title: str = "Untitled") -> TextExtractResult:
    """Extract and normalize text content."""
    normalized = normalize_text(content)
    structure = detect_structure(normalized)

    return TextExtractResult(
        title=title,
        text=normalized,
        char_count=len(normalized),
        structure_hints=structure,
    )
