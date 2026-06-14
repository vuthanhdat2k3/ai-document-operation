"""Unit tests for app.utils.file utilities."""

from __future__ import annotations

from app.utils.file import get_file_extension, sanitize_filename


class TestSanitizeFilename:
    """Tests for sanitize_filename."""

    def test_clean_filename_unchanged(self) -> None:
        assert sanitize_filename("document.pdf") == "document.pdf"

    def test_strips_path(self) -> None:
        assert sanitize_filename("/etc/passwd") == "passwd"

        assert sanitize_filename("/tmp/test.txt") == "test.txt"

    def test_strips_path_backslash_windows_style(self) -> None:
        result = sanitize_filename("C:\\Users\\test\\file.txt")
        assert "/" not in result
        assert result.endswith(".txt")

    def test_removes_null_bytes(self) -> None:
        assert sanitize_filename("file\x00.txt") == "file.txt"

    def test_replaces_special_characters(self) -> None:
        result = sanitize_filename("my file (1) @2024!.pdf")
        assert " " not in result
        assert "(" not in result
        assert ")" not in result
        assert "@" not in result
        assert "!" not in result
        assert result.endswith(".pdf")

    def test_collapses_multiple_underscores(self) -> None:
        result = sanitize_filename("a!!!b.txt")
        assert "__" not in result

    def test_strips_leading_trailing_underscores(self) -> None:
        result = sanitize_filename("___test___")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_empty_filename_returns_unnamed(self) -> None:
        assert sanitize_filename("") == "unnamed"

    def test_all_special_characters(self) -> None:
        assert sanitize_filename("!!!") == "unnamed"

    def test_preserves_dots_and_dashes(self) -> None:
        result = sanitize_filename("my-file_v2.0.tar.gz")
        assert "." in result
        assert "-" in result
        assert "_" in result

    def test_nested_path_with_special_chars(self) -> None:
        result = sanitize_filename("/path/to/my file!.pdf")
        assert "/" not in result
        assert result.endswith(".pdf")


class TestGetFileExtension:
    """Tests for get_file_extension."""

    def test_pdf(self) -> None:
        assert get_file_extension("document.pdf") == "pdf"

    def test_docx(self) -> None:
        assert get_file_extension("report.docx") == "docx"

    def test_uppercase_extension_lowercased(self) -> None:
        assert get_file_extension("FILE.PDF") == "pdf"

    def test_no_extension(self) -> None:
        assert get_file_extension("Makefile") == ""

    def test_multiple_dots(self) -> None:
        assert get_file_extension("archive.tar.gz") == "gz"

    def test_hidden_file_no_extension(self) -> None:
        assert get_file_extension(".gitignore") == ""

    def test_hidden_file_with_extension(self) -> None:
        assert get_file_extension(".env.local") == "local"

    def test_dot_only(self) -> None:
        assert get_file_extension(".") == ""

    def test_empty_string(self) -> None:
        assert get_file_extension("") == ""

    def test_xlsx(self) -> None:
        assert get_file_extension("data.xlsx") == "xlsx"

    def test_csv(self) -> None:
        assert get_file_extension("data.CSV") == "csv"
