"""PDF extractor — text + image extraction via PyMuPDF."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.pipeline.adapters.base import BlobStorageAdapter

log = logging.getLogger(__name__)


@dataclass
class PageData:
    page_num: int
    text: str
    images: list[dict] = field(default_factory=list)  # [{page, index, gcs_path, url}]
    is_scanned: bool = False


@dataclass
class PdfExtractResult:
    title: str
    page_count: int
    pages: list[PageData]
    needs_ocr: list[int]  # page numbers that need OCR
    full_text: str = ""


async def extract_pdf(
    file_bytes: bytes,
    material_id: str,
    collection_id: str,
    storage: BlobStorageAdapter,
    original_filename: str = "document.pdf",
) -> PdfExtractResult:
    """Extract text and images from a PDF file."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages: list[PageData] = []
    full_text_parts: list[str] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        full_text_parts.append(text)

        # Extract embedded images
        images: list[dict] = []
        for img_index, img in enumerate(page.get_images(full=True)):
            try:
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                if pix.n > 4:  # CMYK → RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                img_bytes = pix.tobytes("jpeg")

                gcs_path = f"{collection_id}/frames/{material_id}/page_{page_num:03d}_img_{img_index}.jpg"
                url = await storage.upload(img_bytes, gcs_path, "image/jpeg")

                images.append({
                    "page": page_num,
                    "index": img_index,
                    "gcs_path": gcs_path,
                    "url": url,
                })
            except Exception as e:
                log.warning("Failed to extract image %d from page %d: %s", img_index, page_num, e)

        is_scanned = len(text.strip()) < 50 and len(images) > 0

        pages.append(PageData(
            page_num=page_num,
            text=text,
            images=images,
            is_scanned=is_scanned,
        ))

    doc.close()

    title = original_filename.rsplit(".", 1)[0] if original_filename else "Untitled"

    return PdfExtractResult(
        title=title,
        page_count=len(pages),
        pages=pages,
        needs_ocr=[p.page_num for p in pages if p.is_scanned],
        full_text="\n\n".join(full_text_parts),
    )
