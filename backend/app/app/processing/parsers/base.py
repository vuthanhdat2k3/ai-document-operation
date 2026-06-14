from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ImageData:
    """Metadata for an image found inside a document."""

    description: str = ""
    storage_path: str | None = None


@dataclass(frozen=True)
class TableData:
    """A table extracted from a document page."""

    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    page: int = 0


@dataclass(frozen=True)
class PageResult:
    """Result of parsing a single page/sheet."""

    page_number: int
    text: str = ""
    tables: list[TableData] = field(default_factory=list)
    images: list[ImageData] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class ParseResult:
    """Aggregated result returned by every parser."""

    pages: list[PageResult] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    quality_score: float = 0.0


class BaseParser(ABC):
    """Abstract base class for all document parsers."""

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """Parse *file_path* and return structured content.

        Args:
            file_path: Absolute path to the document on disk.

        Returns:
            A ``ParseResult`` containing per-page content, metadata, and a
            preliminary quality score (0.0-1.0).

        Raises:
            FileNotFoundError: If *file_path* does not exist.
            ValueError: If the file is corrupt or unreadable.
        """
        ...
