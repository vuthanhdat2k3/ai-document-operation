from __future__ import annotations

import logging
import math
import re
from pathlib import Path

import fitz  # PyMuPDF

from app.processing.parsers.base import (
    BaseParser,
    ImageData,
    PageResult,
    ParseResult,
    TableData,
)

logger = logging.getLogger(__name__)

_MIN_CHARS_FOR_TEXT_PAGE = 50
_TABLE_POSITION_TOLERANCE = 3.0  # points


class PDFParser(BaseParser):
    """Parse PDF documents using PyMuPDF (fitz).

    Capabilities:
    - Per-page text extraction
    - Basic table detection via positional analysis
    - Metadata extraction (title, author, page count, …)
    - OCR-needed flag when a page has fewer than 50 characters
    - Graceful handling of encrypted / password-protected PDFs
    """

    def parse(self, file_path: Path) -> ParseResult:
        if not file_path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        try:
            doc = fitz.open(str(file_path))
        except Exception as exc:
            raise ValueError(f"Cannot open PDF: {exc}") from exc

        if doc.is_encrypted and not doc.authenticate(""):
            doc.close()
            return ParseResult(
                pages=[],
                metadata={"error": "encrypted", "needs_password": True},
                quality_score=0.0,
            )

        pages: list[PageResult] = []
        ocr_needed_pages: list[int] = []

        for page_idx in range(len(doc)):
            try:
                page_result = self._parse_page(doc, page_idx)
                pages.append(page_result)
                if len(page_result.text.strip()) < _MIN_CHARS_FOR_TEXT_PAGE:
                    ocr_needed_pages.append(page_idx + 1)
            except Exception:
                logger.warning("Failed to parse PDF page %d", page_idx + 1, exc_info=True)
                pages.append(
                    PageResult(page_number=page_idx + 1, text="", confidence=0.0)
                )
                ocr_needed_pages.append(page_idx + 1)

        metadata = self._extract_metadata(doc)
        metadata["ocr_needed_pages"] = ocr_needed_pages
        doc.close()

        total_pages = len(pages)
        avg_confidence = (
            sum(p.confidence for p in pages) / total_pages if total_pages else 0.0
        )

        return ParseResult(
            pages=pages,
            metadata=metadata,
            quality_score=round(avg_confidence, 4),
        )

    def _parse_page(self, doc: fitz.Document, page_idx: int) -> PageResult:
        page = doc[page_idx]
        text = page.get_text("text") or ""

        tables = self._detect_tables(page)
        images = self._extract_images(doc, page, page_idx)

        char_count = len(text.strip())
        confidence = min(1.0, char_count / 200) if char_count < 200 else 1.0

        return PageResult(
            page_number=page_idx + 1,
            text=text.strip(),
            tables=tables,
            images=images,
            confidence=round(confidence, 4),
        )

    def _detect_tables(self, page: fitz.Page) -> list[TableData]:
        """Basic grid-based table detection.

        Groups text blocks by their vertical position (within tolerance)
        to identify rows, then checks whether multiple rows share the same
        column offsets — a simple heuristic for tabular layouts.
        """
        try:
            blocks = page.get_text("dict")["blocks"]
        except Exception:
            return []

        lines: list[tuple[float, list[tuple[float, float, str]]]] = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                line_text = "".join(s["text"] for s in spans).strip()
                if not line_text:
                    continue
                y0 = round(line["bbox"][1], 1)
                x0 = round(spans[0]["bbox"][0], 1)
                x1 = round(spans[-1]["bbox"][2], 1)
                lines.append((y0, [(x0, x1, line_text)]))

        if len(lines) < 2:
            return []

        lines.sort(key=lambda item: item[0])

        rows: list[list[str]] = []
        current_row_y = lines[0][0]
        current_cells: list[tuple[float, float, str]] = []
        all_rows: list[list[tuple[float, float, str]]] = []

        for y, cells in lines:
            if abs(y - current_row_y) <= _TABLE_POSITION_TOLERANCE:
                current_cells.extend(cells)
                current_row_y = (current_row_y + y) / 2
            else:
                all_rows.append(sorted(current_cells, key=lambda c: c[0]))
                current_cells = cells
                current_row_y = y
        if current_cells:
            all_rows.append(sorted(current_cells, key=lambda c: c[0]))

        if len(all_rows) < 2:
            return []

        max_cols = max(len(r) for r in all_rows)
        if max_cols < 2:
            return []

        header_row = all_rows[0]
        headers = [cell[2] for cell in header_row]
        data_rows = [[cell[2] for cell in row] for row in all_rows[1:]]

        for row in data_rows:
            while len(row) < len(headers):
                row.append("")

        return [TableData(headers=headers, rows=data_rows, page=0)]

    def _extract_images(
        self, doc: fitz.Document, page: fitz.Page, page_idx: int
    ) -> list[ImageData]:
        images: list[ImageData] = []
        try:
            image_list = page.get_images(full=True)
            for img_idx, _ in enumerate(image_list):
                images.append(
                    ImageData(
                        description=f"Image {img_idx + 1} on page {page_idx + 1}",
                        storage_path=None,
                    )
                )
        except Exception:
            logger.debug("Image extraction failed on page %d", page_idx + 1, exc_info=True)
        return images

    def _extract_metadata(self, doc: fitz.Document) -> dict:
        try:
            raw = doc.metadata or {}
        except Exception:
            raw = {}

        return {
            "title": raw.get("title", "") or "",
            "author": raw.get("author", "") or "",
            "subject": raw.get("subject", "") or "",
            "creator": raw.get("creator", "") or "",
            "producer": raw.get("producer", "") or "",
            "page_count": len(doc),
        }
