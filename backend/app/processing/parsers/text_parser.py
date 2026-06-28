"""Plain-text parser for .txt files."""

from __future__ import annotations

import logging
from pathlib import Path

from app.processing.parsers.base import BaseParser, PageResult, ParseResult

logger = logging.getLogger(__name__)


class TextParser(BaseParser):
    """Parse plain-text (.txt) files.

    Reads the entire text file and returns it as a single page.
    """

    def parse(self, file_path: Path) -> ParseResult:
        """Read *file_path* and return its content as one page.

        Args:
            file_path: Absolute path to the .txt file on disk.

        Returns:
            A ``ParseResult`` with a single page containing the full text.

        Raises:
            FileNotFoundError: If *file_path* does not exist.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Text file not found: {file_path}")

        try:
            text = file_path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = file_path.read_text(encoding="latin-1")
            except Exception as exc:
                raise ValueError(f"Cannot read text file: {exc}") from exc

        char_count = len(text)
        confidence = min(1.0, char_count / 200) if char_count < 200 else 1.0

        return ParseResult(
            pages=[
                PageResult(
                    page_number=1,
                    text=text,
                    confidence=round(confidence, 4),
                )
            ],
            metadata={"encoding": "utf-8-sig", "line_count": text.count("\n") + 1},
            quality_score=round(confidence, 4),
        )
