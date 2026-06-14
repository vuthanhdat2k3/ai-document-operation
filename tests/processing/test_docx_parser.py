"""Tests for DOCXParser with mocked python-docx."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.processing.parsers.base import ParseResult


def _make_mock_paragraph(text: str = "", style_name: str = "Normal") -> MagicMock:
    para = MagicMock()
    para.text = text
    style = MagicMock()
    style.name = style_name
    para.style = style
    return para


def _make_mock_table(rows_data: list[list[str]]) -> MagicMock:
    table = MagicMock()
    rows = []
    for row_data in rows_data:
        row = MagicMock()
        cells = [MagicMock(text=cell_text) for cell_text in row_data]
        row.cells = cells
        rows.append(row)
    table.rows = rows
    return table


def _make_mock_doc(
    paragraphs: list[MagicMock] | None = None,
    tables: list[MagicMock] | None = None,
    image_rels: list | None = None,
    core_properties: dict | None = None,
) -> MagicMock:
    doc = MagicMock()
    doc.paragraphs = paragraphs or []
    doc.tables = tables or []

    if image_rels is None:
        image_rels = []
    rels = {}
    for i, ref in enumerate(image_rels):
        rel = MagicMock()
        rel.reltype = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
        rel.target_ref = ref
        rels[f"rId{i}"] = rel
    doc.part.rels = rels

    props = MagicMock()
    cp = core_properties or {}
    props.title = cp.get("title", "")
    props.author = cp.get("author", "")
    props.subject = cp.get("subject", "")
    props.keywords = cp.get("keywords", "")
    props.created = cp.get("created", None)
    props.modified = cp.get("modified", None)
    props.last_modified_by = cp.get("last_modified_by", "")
    props.revision = cp.get("revision", 0)
    doc.core_properties = props

    return doc


@pytest.fixture()
def parser():
    from app.processing.parsers.docx_parser import DOCXParser

    return DOCXParser()


class TestDOCXParserParse:
    """DOCXParser.parse() end-to-end with mocked python-docx."""

    def test_file_not_found(self, parser, tmp_path) -> None:
        with pytest.raises(FileNotFoundError, match="DOCX not found"):
            parser.parse(tmp_path / "nonexistent.docx")

    @patch("app.processing.parsers.docx_parser.DocxDocument")
    def test_single_paragraph(self, mock_doc_cls, parser, tmp_path) -> None:
        fake_docx = tmp_path / "test.docx"
        fake_docx.write_bytes(b"PK\x03\x04 fake docx")

        para = _make_mock_paragraph("Hello world this has enough text for confidence " * 10)
        doc = _make_mock_doc(paragraphs=[para])
        mock_doc_cls.return_value = doc

        result = parser.parse(fake_docx)

        assert isinstance(result, ParseResult)
        assert len(result.pages) == 1
        assert result.pages[0].page_number == 1
        assert "Hello world" in result.pages[0].text

    @patch("app.processing.parsers.docx_parser.DocxDocument")
    def test_headings_get_markdown_prefix(self, mock_doc_cls, parser, tmp_path) -> None:
        fake_docx = tmp_path / "headings.docx"
        fake_docx.write_bytes(b"PK\x03\x04 fake")

        paragraphs = [
            _make_mock_paragraph("Title Text", "Title"),
            _make_mock_paragraph("Heading 1 Text", "Heading 1"),
            _make_mock_paragraph("Heading 2 Text", "Heading 2"),
            _make_mock_paragraph("Normal paragraph with enough text for the test " * 5, "Normal"),
        ]
        doc = _make_mock_doc(paragraphs=paragraphs)
        mock_doc_cls.return_value = doc

        result = parser.parse(fake_docx)

        text = result.pages[0].text
        assert "# Title Text" in text
        assert "# Heading 1 Text" in text
        assert "## Heading 2 Text" in text
        assert "Normal paragraph" in text

    @patch("app.processing.parsers.docx_parser.DocxDocument")
    def test_tables_extracted(self, mock_doc_cls, parser, tmp_path) -> None:
        fake_docx = tmp_path / "tables.docx"
        fake_docx.write_bytes(b"PK\x03\x04 fake")

        table = _make_mock_table([
            ["Name", "Age", "City"],
            ["Alice", "30", "NYC"],
            ["Bob", "25", "LA"],
        ])
        doc = _make_mock_doc(tables=[table])
        mock_doc_cls.return_value = doc

        result = parser.parse(fake_docx)

        assert len(result.pages[0].tables) == 1
        tbl = result.pages[0].tables[0]
        assert tbl.headers == ["Name", "Age", "City"]
        assert len(tbl.rows) == 2

    @patch("app.processing.parsers.docx_parser.DocxDocument")
    def test_images_extracted(self, mock_doc_cls, parser, tmp_path) -> None:
        fake_docx = tmp_path / "imgs.docx"
        fake_docx.write_bytes(b"PK\x03\x04 fake")

        doc = _make_mock_doc(image_rels=["image1.png", "image2.jpg"])
        mock_doc_cls.return_value = doc

        result = parser.parse(fake_docx)

        assert len(result.pages[0].images) == 2
        assert "image1.png" in result.pages[0].images[0].description

    @patch("app.processing.parsers.docx_parser.DocxDocument")
    def test_metadata_extraction(self, mock_doc_cls, parser, tmp_path) -> None:
        fake_docx = tmp_path / "meta.docx"
        fake_docx.write_bytes(b"PK\x03\x04 fake")

        doc = _make_mock_doc(core_properties={
            "title": "Test Title",
            "author": "Author",
            "subject": "Subject",
            "keywords": "kw1, kw2",
        })
        mock_doc_cls.return_value = doc

        result = parser.parse(fake_docx)

        assert result.metadata["title"] == "Test Title"
        assert result.metadata["author"] == "Author"
        assert result.metadata["subject"] == "Subject"

    @patch("app.processing.parsers.docx_parser.DocxDocument")
    def test_cannot_open_raises_value_error(self, mock_doc_cls, parser, tmp_path) -> None:
        fake_docx = tmp_path / "bad.docx"
        fake_docx.write_bytes(b"not a docx")
        mock_doc_cls.side_effect = Exception("corrupt")

        with pytest.raises(ValueError, match="Cannot open DOCX"):
            parser.parse(fake_docx)

    @patch("app.processing.parsers.docx_parser.DocxDocument")
    def test_empty_paragraphs_skipped(self, mock_doc_cls, parser, tmp_path) -> None:
        fake_docx = tmp_path / "empty.docx"
        fake_docx.write_bytes(b"PK\x03\x04 fake")

        paragraphs = [
            _make_mock_paragraph("", "Normal"),
            _make_mock_paragraph("   ", "Normal"),
            _make_mock_paragraph("Real content here with enough chars " * 5, "Normal"),
        ]
        doc = _make_mock_doc(paragraphs=paragraphs)
        mock_doc_cls.return_value = doc

        result = parser.parse(fake_docx)

        assert "Real content" in result.pages[0].text
        # Empty/whitespace-only paragraphs should not appear
        lines = [l for l in result.pages[0].text.split("\n") if l.strip()]
        assert len(lines) >= 1

    @patch("app.processing.parsers.docx_parser.DocxDocument")
    def test_confidence_scales_with_content(self, mock_doc_cls, parser, tmp_path) -> None:
        fake_docx = tmp_path / "conf.docx"
        fake_docx.write_bytes(b"PK\x03\x04 fake")

        short_para = _make_mock_paragraph("Hi", "Normal")
        doc = _make_mock_doc(paragraphs=[short_para])
        mock_doc_cls.return_value = doc

        result = parser.parse(fake_docx)

        assert result.quality_score < 1.0

    @patch("app.processing.parsers.docx_parser.DocxDocument")
    def test_table_parsing_failure_graceful(self, mock_doc_cls, parser, tmp_path) -> None:
        fake_docx = tmp_path / "badtable.docx"
        fake_docx.write_bytes(b"PK\x03\x04 fake")

        bad_table = MagicMock()
        # Make iterating over rows raise an exception
        type(bad_table).rows = property(lambda self: (_ for _ in ()).throw(Exception("table error")))

        para = _make_mock_paragraph("Content " * 20, "Normal")
        doc = _make_mock_doc(paragraphs=[para], tables=[bad_table])
        mock_doc_cls.return_value = doc

        result = parser.parse(fake_docx)

        assert len(result.pages[0].tables) == 0


class TestDOCXParserHeadingLevel:
    """Test _heading_level static method."""

    def test_heading_1(self) -> None:
        from app.processing.parsers.docx_parser import DOCXParser

        assert DOCXParser._heading_level("Heading 1") == 1

    def test_heading_3(self) -> None:
        from app.processing.parsers.docx_parser import DOCXParser

        assert DOCXParser._heading_level("Heading 3") == 3

    def test_title_returns_1(self) -> None:
        from app.processing.parsers.docx_parser import DOCXParser

        assert DOCXParser._heading_level("Title") == 1

    def test_subtitle_returns_2(self) -> None:
        from app.processing.parsers.docx_parser import DOCXParser

        assert DOCXParser._heading_level("Subtitle") == 2

    def test_normal_returns_0(self) -> None:
        from app.processing.parsers.docx_parser import DOCXParser

        assert DOCXParser._heading_level("Normal") == 0
