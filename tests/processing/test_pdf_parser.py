"""Tests for PDFParser with mocked fitz (PyMuPDF)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.processing.parsers.base import PageResult, ParseResult


def _make_mock_page(
    text: str = "Sample page text content for testing.",
    images: list | None = None,
    text_dict: dict | None = None,
) -> MagicMock:
    page = MagicMock()
    page.get_text.return_value = text
    page.get_images.return_value = images or []
    if text_dict is None:
        text_dict = {"blocks": []}
    page.get_text_dict = text_dict

    def get_text_side_effect(mode: str = "text"):
        if mode == "dict":
            return text_dict
        return text

    page.get_text.side_effect = get_text_side_effect
    return page


def _make_mock_doc(
    pages: list[MagicMock] | None = None,
    encrypted: bool = False,
    authenticated: bool = True,
    metadata: dict | None = None,
) -> MagicMock:
    doc = MagicMock()
    pages = pages or [_make_mock_page()]
    doc.__len__ = MagicMock(return_value=len(pages))
    doc.__getitem__ = MagicMock(side_effect=lambda idx: pages[idx])
    doc.is_encrypted = encrypted
    doc.authenticate.return_value = authenticated
    doc.metadata = metadata or {
        "title": "Test PDF",
        "author": "Test Author",
        "subject": "Testing",
        "creator": "pytest",
        "producer": "test-producer",
    }
    doc.close = MagicMock()
    return doc


@pytest.fixture()
def parser():
    from app.processing.parsers.pdf_parser import PDFParser

    return PDFParser()


class TestPDFParserParse:
    """PDFParser.parse() end-to-end with mocked fitz."""

    def test_file_not_found(self, parser, tmp_path) -> None:
        with pytest.raises(FileNotFoundError, match="PDF not found"):
            parser.parse(tmp_path / "nonexistent.pdf")

    @patch("app.processing.parsers.pdf_parser.fitz")
    def test_single_page_document(self, mock_fitz, parser, tmp_path) -> None:
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")

        page = _make_mock_page(text="Hello world this is a test document with enough chars " * 5)
        doc = _make_mock_doc(pages=[page])
        mock_fitz.open.return_value = doc

        result = parser.parse(fake_pdf)

        assert isinstance(result, ParseResult)
        assert len(result.pages) == 1
        assert result.pages[0].page_number == 1
        assert "Hello world" in result.pages[0].text
        assert result.pages[0].confidence > 0.0
        doc.close.assert_called_once()

    @patch("app.processing.parsers.pdf_parser.fitz")
    def test_multi_page_document(self, mock_fitz, parser, tmp_path) -> None:
        fake_pdf = tmp_path / "multi.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")

        pages = [
            _make_mock_page(text=f"Content of page {i} with enough text " * 10)
            for i in range(3)
        ]
        doc = _make_mock_doc(pages=pages)
        mock_fitz.open.return_value = doc

        result = parser.parse(fake_pdf)

        assert len(result.pages) == 3
        for i, page in enumerate(result.pages):
            assert page.page_number == i + 1

    @patch("app.processing.parsers.pdf_parser.fitz")
    def test_encrypted_pdf_returns_empty(self, mock_fitz, parser, tmp_path) -> None:
        fake_pdf = tmp_path / "encrypted.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")

        doc = _make_mock_doc(encrypted=True, authenticated=False)
        mock_fitz.open.return_value = doc

        result = parser.parse(fake_pdf)

        assert result.pages == []
        assert result.metadata.get("error") == "encrypted"
        assert result.metadata.get("needs_password") is True
        assert result.quality_score == 0.0

    @patch("app.processing.parsers.pdf_parser.fitz")
    def test_encrypted_pdf_authenticated(self, mock_fitz, parser, tmp_path) -> None:
        fake_pdf = tmp_path / "auth.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")

        page = _make_mock_page(text="Decrypted content with enough characters " * 5)
        doc = _make_mock_doc(pages=[page], encrypted=True, authenticated=True)
        mock_fitz.open.return_value = doc

        result = parser.parse(fake_pdf)

        assert len(result.pages) == 1

    @patch("app.processing.parsers.pdf_parser.fitz")
    def test_cannot_open_pdf_raises_value_error(self, mock_fitz, parser, tmp_path) -> None:
        fake_pdf = tmp_path / "corrupt.pdf"
        fake_pdf.write_bytes(b"not a pdf")
        mock_fitz.open.side_effect = Exception("corrupt file")

        with pytest.raises(ValueError, match="Cannot open PDF"):
            parser.parse(fake_pdf)

    @patch("app.processing.parsers.pdf_parser.fitz")
    def test_metadata_extraction(self, mock_fitz, parser, tmp_path) -> None:
        fake_pdf = tmp_path / "meta.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")

        page = _make_mock_page(text="x " * 100)
        doc = _make_mock_doc(
            pages=[page],
            metadata={
                "title": "My Title",
                "author": "Author Name",
                "subject": "Subject",
                "creator": "Creator",
                "producer": "Producer",
            },
        )
        mock_fitz.open.return_value = doc

        result = parser.parse(fake_pdf)

        assert result.metadata["title"] == "My Title"
        assert result.metadata["author"] == "Author Name"
        assert result.metadata["page_count"] == 1

    @patch("app.processing.parsers.pdf_parser.fitz")
    def test_ocr_needed_pages_flagged(self, mock_fitz, parser, tmp_path) -> None:
        fake_pdf = tmp_path / "scan.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")

        empty_page = _make_mock_page(text="x")  # < 50 chars
        good_page = _make_mock_page(text="This is a page with enough text content " * 10)
        doc = _make_mock_doc(pages=[empty_page, good_page])
        mock_fitz.open.return_value = doc

        result = parser.parse(fake_pdf)

        assert 1 in result.metadata.get("ocr_needed_pages", [])
        assert 2 not in result.metadata.get("ocr_needed_pages", [])

    @patch("app.processing.parsers.pdf_parser.fitz")
    def test_page_exception_produces_zero_confidence(self, mock_fitz, parser, tmp_path) -> None:
        fake_pdf = tmp_path / "bad.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")

        bad_page = MagicMock()
        bad_page.get_text.side_effect = Exception("page error")
        bad_page.get_images.side_effect = Exception("page error")

        def get_text_dict_side_effect(mode: str = "text"):
            if mode == "dict":
                raise Exception("page error")
            raise Exception("page error")

        bad_page.get_text.side_effect = get_text_dict_side_effect

        doc = _make_mock_doc(pages=[bad_page])
        mock_fitz.open.return_value = doc

        result = parser.parse(fake_pdf)

        assert len(result.pages) == 1
        assert result.pages[0].confidence == 0.0
        assert result.pages[0].text == ""

    @patch("app.processing.parsers.pdf_parser.fitz")
    def test_quality_score_is_average_confidence(self, mock_fitz, parser, tmp_path) -> None:
        fake_pdf = tmp_path / "avg.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")

        page1 = _make_mock_page(text="Short")  # low confidence
        page2 = _make_mock_page(text="Long text content " * 50)  # high confidence
        doc = _make_mock_doc(pages=[page1, page2])
        mock_fitz.open.return_value = doc

        result = parser.parse(fake_pdf)

        assert 0.0 < result.quality_score <= 1.0

    @patch("app.processing.parsers.pdf_parser.fitz")
    def test_empty_document(self, mock_fitz, parser, tmp_path) -> None:
        fake_pdf = tmp_path / "empty.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")

        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=0)
        doc.__getitem__ = MagicMock(side_effect=IndexError("out of range"))
        doc.is_encrypted = False
        doc.metadata = {"title": "", "author": "", "subject": "", "creator": "", "producer": ""}
        doc.close = MagicMock()
        mock_fitz.open.return_value = doc

        result = parser.parse(fake_pdf)

        assert result.pages == []
        assert result.quality_score == 0.0


class TestPDFParserImages:
    """Image extraction tests."""

    @patch("app.processing.parsers.pdf_parser.fitz")
    def test_images_extracted(self, mock_fitz, parser, tmp_path) -> None:
        fake_pdf = tmp_path / "imgs.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")

        page = _make_mock_page(
            text="Text with images " * 10,
            images=[("img1",), ("img2",)],
        )
        doc = _make_mock_doc(pages=[page])
        mock_fitz.open.return_value = doc

        result = parser.parse(fake_pdf)

        assert len(result.pages[0].images) == 2
        assert "Image 1" in result.pages[0].images[0].description

    @patch("app.processing.parsers.pdf_parser.fitz")
    def test_image_extraction_failure_graceful(self, mock_fitz, parser, tmp_path) -> None:
        fake_pdf = tmp_path / "noimg.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")

        page = _make_mock_page(text="Text content " * 10)
        page.get_images.side_effect = Exception("image error")
        doc = _make_mock_doc(pages=[page])
        mock_fitz.open.return_value = doc

        result = parser.parse(fake_pdf)

        assert result.pages[0].images == []
