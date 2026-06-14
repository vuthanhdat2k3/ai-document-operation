"""Tests for FileValidator."""

from __future__ import annotations

import pytest

from app.services.validation import ALLOWED_MIME_TYPES, FileValidator, ValidationResult


@pytest.fixture()
def validator() -> FileValidator:
    return FileValidator(max_file_size_bytes=10 * 1024 * 1024)


class TestValidateFile:
    def test_valid_pdf(self, validator: FileValidator) -> None:
        result = validator.validate_file(
            filename="report.pdf",
            content_type="application/pdf",
            file_size=1024,
            file_header=b"%PDF-1.4",
        )
        assert result.is_valid is True
        assert result.errors == []
        assert result.detected_mime_type == "application/pdf"

    def test_valid_docx(self, validator: FileValidator) -> None:
        result = validator.validate_file(
            filename="report.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_size=2048,
            file_header=b"PK\x03\x04",
        )
        assert result.is_valid is True
        assert result.detected_mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_valid_xlsx(self, validator: FileValidator) -> None:
        result = validator.validate_file(
            filename="data.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            file_size=4096,
            file_header=b"PK\x03\x04",
        )
        assert result.is_valid is True

    def test_valid_png(self, validator: FileValidator) -> None:
        result = validator.validate_file(
            filename="scan.png",
            content_type="image/png",
            file_size=512,
            file_header=b"\x89PNG\r\n\x1a\n",
        )
        assert result.is_valid is True
        assert result.detected_mime_type == "image/png"

    def test_valid_jpeg(self, validator: FileValidator) -> None:
        result = validator.validate_file(
            filename="photo.jpg",
            content_type="image/jpeg",
            file_size=1024,
            file_header=b"\xff\xd8\xff\xe0",
        )
        assert result.is_valid is True
        assert result.detected_mime_type == "image/jpeg"

    def test_invalid_mime_type(self, validator: FileValidator) -> None:
        result = validator.validate_file(
            filename="script.exe",
            content_type="application/x-msdownload",
            file_size=1024,
            file_header=b"MZ",
        )
        assert result.is_valid is False
        assert any("not allowed" in e for e in result.errors)

    def test_oversized_file(self, validator: FileValidator) -> None:
        result = validator.validate_file(
            filename="huge.pdf",
            content_type="application/pdf",
            file_size=100 * 1024 * 1024,
            file_header=b"%PDF-1.4",
        )
        assert result.is_valid is False
        assert any("exceeds" in e for e in result.errors)

    def test_empty_file(self, validator: FileValidator) -> None:
        result = validator.validate_file(
            filename="empty.pdf",
            content_type="application/pdf",
            file_size=0,
            file_header=b"",
        )
        assert result.is_valid is False
        assert any("empty" in e.lower() for e in result.errors)

    def test_magic_byte_mismatch(self, validator: FileValidator) -> None:
        result = validator.validate_file(
            filename="fake.pdf",
            content_type="application/pdf",
            file_size=1024,
            file_header=b"NOT_PDF",
        )
        assert result.is_valid is False

    def test_empty_filename(self, validator: FileValidator) -> None:
        result = validator.validate_file(
            filename="",
            content_type="application/pdf",
            file_size=1024,
            file_header=b"%PDF-1.4",
        )
        assert result.is_valid is False
        assert any("filename" in e.lower() for e in result.errors)


class TestSanitizeFilename:
    def test_normal_filename(self) -> None:
        assert FileValidator._sanitize_filename("report.pdf") == "report.pdf"

    def test_path_traversal(self) -> None:
        assert FileValidator._sanitize_filename("../../etc/passwd") == "passwd"

    def test_special_characters(self) -> None:
        result = FileValidator._sanitize_filename("file name@#$.pdf")
        assert result == "file name__.pdf"

    def test_double_dots(self) -> None:
        result = FileValidator._sanitize_filename("file..name..pdf")
        assert result == "file.name.pdf"


class TestAllowedMimeTypes:
    def test_all_types_have_extensions(self) -> None:
        for mime, exts in ALLOWED_MIME_TYPES.items():
            assert len(exts) > 0, f"No extensions for {mime}"

    def test_pdf_in_allowed(self) -> None:
        assert "application/pdf" in ALLOWED_MIME_TYPES

    def test_docx_in_allowed(self) -> None:
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in ALLOWED_MIME_TYPES

    def test_xlsx_in_allowed(self) -> None:
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in ALLOWED_MIME_TYPES
