from __future__ import annotations

from app.processing.parsers.base import BaseParser
from app.processing.parsers.pdf_parser import PDFParser
from app.processing.parsers.docx_parser import DOCXParser
from app.processing.parsers.xlsx_parser import XLSXParser

_MIME_TO_PARSER: dict[str, type[BaseParser]] = {
    "application/pdf": PDFParser,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DOCXParser,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": XLSXParser,
}

_PARSER_INSTANCES: dict[str, BaseParser] = {}


def get_parser(mime_type: str) -> BaseParser | None:
    """Return a parser instance for the given MIME type, or None if unsupported."""
    if mime_type in _PARSER_INSTANCES:
        return _PARSER_INSTANCES[mime_type]
    parser_cls = _MIME_TO_PARSER.get(mime_type)
    if parser_cls is None:
        return None
    instance = parser_cls()
    _PARSER_INSTANCES[mime_type] = instance
    return instance


__all__ = [
    "get_parser",
    "BaseParser",
    "PDFParser",
    "DOCXParser",
    "XLSXParser",
]
