"""PDF processor — uses marker-pdf for high-quality extraction.

marker converts PDF → markdown preserving:
- Headers and document structure
- Equations (as LaTeX)
- Tables
- Image references
- Multi-column layouts
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

from byo.models import ProcessResult
from byo.pipeline.processors.base import BaseProcessor

log = logging.getLogger(__name__)


class PDFProcessor(BaseProcessor):
    supported_types = ["application/pdf"]

    async def extract(
        self,
        resource_id: str,
        mime_type: str,
        source_url: str | None,
        storage_path: str | None,
        meta: dict[str, Any],
    ) -> ProcessResult:
        if not storage_path:
            return ProcessResult(markdown="", meta={"error": "No file path provided"})

        import asyncio

        # Run marker in thread pool (it's CPU-bound)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._extract_sync, storage_path, resource_id)
        return result

    def _extract_sync(self, file_path: str, resource_id: str) -> ProcessResult:
        """Synchronous extraction using marker-pdf."""
        try:
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict

            # Initialize marker models (cached after first call)
            model_dict = create_model_dict()
            converter = PdfConverter(artifact_dict=model_dict)

            # Convert PDF to markdown
            rendered = converter(file_path)
            markdown = rendered.markdown

            # Extract metadata
            doc_meta = {
                "pages": rendered.metadata.get("pages", 0) if hasattr(rendered, "metadata") else 0,
                "has_images": "![" in markdown,
                "language": "en",  # TODO: detect language
            }

            # Extract images if any
            images = []
            if hasattr(rendered, "images") and rendered.images:
                for img_name, img_data in rendered.images.items():
                    images.append({
                        "path": img_name,
                        "data": img_data,  # base64 or bytes
                        "description": "",  # will be described by classifier
                    })

            log.info("PDF extracted: %s — %d chars, %d images",
                    resource_id[:8], len(markdown), len(images))

            return ProcessResult(markdown=markdown, meta=doc_meta, images=images)

        except ImportError:
            # marker-pdf not installed — fall back to PyMuPDF
            log.warning("marker-pdf not available, falling back to PyMuPDF")
            return self._extract_pymupdf(file_path, resource_id)

        except Exception as e:
            log.error("PDF extraction failed for %s: %s", resource_id[:8], e)
            # Try PyMuPDF as fallback
            try:
                return self._extract_pymupdf(file_path, resource_id)
            except Exception as e2:
                return ProcessResult(markdown="", meta={"error": str(e2)})

    def _extract_pymupdf(self, file_path: str, resource_id: str) -> ProcessResult:
        """Fallback PDF extraction using PyMuPDF.

        Two strategies:
        1. Text extraction (fast) — works for digital PDFs
        2. Page-as-image rendering — for pages with little/no text (scanned docs, diagrams)
           These get described by the vision LLM in the pipeline's image description step.
        """
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        pages = []
        images = []
        low_text_pages = []  # pages with < 50 chars of text (likely scanned/image-heavy)

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")

            if text.strip():
                pages.append(f"<!-- page {page_num + 1} -->\n{text}")

            # Track pages with very little text — need vision fallback
            if len(text.strip()) < 50:
                low_text_pages.append(page_num)

            # Extract embedded images
            for img_index, img in enumerate(page.get_images(full=True)):
                try:
                    xref = img[0]
                    base_img = doc.extract_image(xref)
                    if base_img:
                        img_name = f"page{page_num + 1}_img{img_index}.{base_img['ext']}"
                        images.append({
                            "path": img_name,
                            "data": base_img["image"],
                            "description": "",
                            "anchor": {"page": page_num + 1},
                        })
                except Exception:
                    pass

        # For pages with little/no text, render the page as an image for vision LLM
        # This handles scanned PDFs, handwritten notes, diagram-heavy pages
        if low_text_pages:
            log.info("PDF has %d low-text pages — rendering as images for vision", len(low_text_pages))
            for page_num in low_text_pages[:20]:  # cap at 20 pages to avoid cost explosion
                try:
                    page = doc[page_num]
                    # Render at 150 DPI — good enough for vision, not too large
                    pix = page.get_pixmap(dpi=150)
                    img_data = pix.tobytes("png")
                    images.append({
                        "path": f"page{page_num + 1}_render.png",
                        "data": img_data,
                        "description": "",
                        "anchor": {"page": page_num + 1},
                        "_is_page_render": True,
                    })
                    # Ensure a page marker exists for this page
                    marker = f"<!-- page {page_num + 1} -->"
                    if marker not in "\n".join(pages):
                        pages.append(f"{marker}\n[Page {page_num + 1}: image/scanned content]")
                except Exception as e:
                    log.warning("Failed to render page %d as image: %s", page_num + 1, e)

        doc.close()

        markdown = "\n\n".join(pages)
        doc_meta = {
            "pages": len(doc) if hasattr(doc, '__len__') else len(pages),
            "has_images": len(images) > 0,
            "low_text_pages": len(low_text_pages),
            "extractor": "pymupdf",
        }

        log.info("PDF extracted (PyMuPDF): %s — %d pages, %d images, %d low-text pages",
                resource_id[:8], len(pages), len(images), len(low_text_pages))

        return ProcessResult(markdown=markdown, meta=doc_meta, images=images)
