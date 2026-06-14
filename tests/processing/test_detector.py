"""Tests for detect_file_type."""

from __future__ import annotations

import pytest
from pathlib import Path

from app.processing.detector import detect_file_type


class TestDetectFileType:
    """Test MIME type detection via magic bytes and extension fallback."""

    def test_file_not_found(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError, match="File not found"):
            detect_file_type(tmp_path / "missing.pdf")

    def test_pdf_magic_bytes(self, tmp_path) -> None:
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4 some content")
        assert detect_file_type(f) == "application/pdf"

    def test_docx_magic_bytes(self, tmp_path) -> None:
        f = tmp_path / "doc.docx"
        f.write_bytes(b"PK\x03\x04 rest of zip content")
        mime = detect_file_type(f)
        assert mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_xlsx_magic_bytes(self, tmp_path) -> None:
        f = tmp_path / "sheet.xlsx"
        f.write_bytes(b"PK\x03\x04 rest of zip content")
        mime = detect_file_type(f)
        assert mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def test_pptx_magic_bytes(self, tmp_path) -> None:
        f = tmp_path / "deck.pptx"
        f.write_bytes(b"PK\x03\x04 rest of zip content")
        mime = detect_file_type(f)
        assert mime == "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    def test_ole2_magic_bytes(self, tmp_path) -> None:
        f = tmp_path / "old.xls"
        f.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1 rest")
        mime = detect_file_type(f)
        assert mime == "application/vnd.ms-excel"

    def test_extension_fallback_pdf(self, tmp_path) -> None:
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"\x00\x00\x00\x00 not magic")
        mime = detect_file_type(f)
        assert mime == "application/pdf"

    def test_extension_fallback_docx(self, tmp_path) -> None:
        f = tmp_path / "doc.docx"
        f.write_bytes(b"\x00\x00\x00\x00 not magic")
        mime = detect_file_type(f)
        assert mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_extension_fallback_csv(self, tmp_path) -> None:
        f = tmp_path / "data.csv"
        f.write_bytes(b"col1,col2\n1,2\n")
        mime = detect_file_type(f)
        assert mime == "text/csv"

    def test_extension_fallback_txt(self, tmp_path) -> None:
        f = tmp_path / "readme.txt"
        f.write_bytes(b"hello world")
        mime = detect_file_type(f)
        assert mime == "text/plain"

    def test_unknown_extension_returns_octet_stream(self, tmp_path) -> None:
        f = tmp_path / "file.xyz"
        f.write_bytes(b"\x00\x00\x00\x00")
        mime = detect_file_type(f)
        assert mime == "application/octet-stream"

    def test_case_insensitive_extension(self, tmp_path) -> None:
        f = tmp_path / "DOC.PDF"
        f.write_bytes(b"%PDF-1.4 content")
        mime = detect_file_type(f)
        assert mime == "application/pdf"

    def test_zip_with_unknown_extension_returns_none_falls_back(self, tmp_path) -> None:
        f = tmp_path / "archive.zip"
        f.write_bytes(b"PK\x03\x04 zip content")
        mime = detect_file_type(f)
        # ZIP is not in _ZIP_EXTENSION_MAP or _EXTENSION_MAP,
        # so it falls back to extension-based detection
        assert mime == "application/octet-stream"

    def test_empty_file_falls_back_to_extension(self, tmp_path) -> None:
        f = tmp_path / "empty.pdf"
        f.write_bytes(b"")
        mime = detect_file_type(f)
        assert mime == "application/pdf"
