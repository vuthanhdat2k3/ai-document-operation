"""Tests for XLSXParser with mocked openpyxl."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.processing.parsers.base import ParseResult


def _make_mock_cell(row: int, column: int, value: str | int | float | None = None) -> MagicMock:
    cell = MagicMock()
    cell.row = row
    cell.column = column
    cell.value = value
    return cell


def _make_mock_worksheet(
    rows: list[list[str | int | float | None]] | None = None,
    sheet_name: str = "Sheet1",
    merged_ranges: list | None = None,
) -> MagicMock:
    ws = MagicMock()
    ws.title = sheet_name

    if rows is None:
        rows = []

    mock_rows = []
    for r_idx, row_data in enumerate(rows, start=1):
        row_cells = []
        for c_idx, val in enumerate(row_data, start=1):
            row_cells.append(_make_mock_cell(r_idx, c_idx, val))
        mock_rows.append(row_cells)

    ws.iter_rows.return_value = mock_rows

    merged = MagicMock()
    merged.ranges = merged_ranges or []
    ws.merged_cells = merged

    def cell_side_effect(row: int, column: int):
        if row <= len(rows) and column <= len(rows[row - 1]) if row > 0 else False:
            return _make_mock_cell(row, column, rows[row - 1][column - 1])
        return _make_mock_cell(row, column, None)

    ws.cell.side_effect = cell_side_effect

    return ws


def _make_mock_workbook(
    sheets: dict[str, list[list[str | int | float | None]]] | None = None,
    properties: dict | None = None,
) -> MagicMock:
    wb = MagicMock()

    if sheets is None:
        sheets = {"Sheet1": [["A", "B"], ["1", "2"]]}

    wb.sheetnames = list(sheets.keys())

    ws_map = {}
    for name, data in sheets.items():
        ws_map[name] = _make_mock_worksheet(rows=data, sheet_name=name)
    wb.__getitem__ = MagicMock(side_effect=lambda key: ws_map[key])

    props = MagicMock()
    p = properties or {}
    props.title = p.get("title", "")
    props.creator = p.get("creator", "")
    props.subject = p.get("subject", "")
    props.description = p.get("description", "")
    props.created = p.get("created", None)
    props.modified = p.get("modified", None)
    wb.properties = props

    wb.close = MagicMock()
    return wb


@pytest.fixture()
def parser():
    from app.processing.parsers.xlsx_parser import XLSXParser

    return XLSXParser()


class TestXLSXParserParse:
    """XLSXParser.parse() end-to-end with mocked openpyxl."""

    def test_file_not_found(self, parser, tmp_path) -> None:
        with pytest.raises(FileNotFoundError, match="XLSX not found"):
            parser.parse(tmp_path / "nonexistent.xlsx")

    @patch("app.processing.parsers.xlsx_parser.load_workbook")
    def test_single_sheet(self, mock_load, parser, tmp_path) -> None:
        fake_xlsx = tmp_path / "test.xlsx"
        fake_xlsx.write_bytes(b"PK\x03\x04 fake")

        wb = _make_mock_workbook(sheets={
            "Sheet1": [
                ["Name", "Age"],
                ["Alice", 30],
                ["Bob", 25],
            ]
        })
        mock_load.return_value = wb

        result = parser.parse(fake_xlsx)

        assert isinstance(result, ParseResult)
        assert len(result.pages) == 1
        assert result.pages[0].page_number == 1
        assert len(result.pages[0].tables) == 1

    @patch("app.processing.parsers.xlsx_parser.load_workbook")
    def test_multiple_sheets(self, mock_load, parser, tmp_path) -> None:
        fake_xlsx = tmp_path / "multi.xlsx"
        fake_xlsx.write_bytes(b"PK\x03\x04 fake")

        wb = _make_mock_workbook(sheets={
            "Sheet1": [["A", "B"], ["1", "2"]],
            "Sheet2": [["X", "Y"], ["3", "4"]],
            "Sheet3": [["P"], ["Q"]],
        })
        mock_load.return_value = wb

        result = parser.parse(fake_xlsx)

        assert len(result.pages) == 3
        assert result.pages[0].page_number == 1
        assert result.pages[1].page_number == 2
        assert result.pages[2].page_number == 3

    @patch("app.processing.parsers.xlsx_parser.load_workbook")
    def test_table_headers_and_rows(self, mock_load, parser, tmp_path) -> None:
        fake_xlsx = tmp_path / "table.xlsx"
        fake_xlsx.write_bytes(b"PK\x03\x04 fake")

        wb = _make_mock_workbook(sheets={
            "Data": [
                ["ID", "Name", "Score"],
                [1, "Alice", 95],
                [2, "Bob", 87],
            ]
        })
        mock_load.return_value = wb

        result = parser.parse(fake_xlsx)

        table = result.pages[0].tables[0]
        assert table.headers == ["ID", "Name", "Score"]
        assert len(table.rows) == 2

    @patch("app.processing.parsers.xlsx_parser.load_workbook")
    def test_metadata_extraction(self, mock_load, parser, tmp_path) -> None:
        fake_xlsx = tmp_path / "meta.xlsx"
        fake_xlsx.write_bytes(b"PK\x03\x04 fake")

        wb = _make_mock_workbook(
            sheets={"S1": [["A"]]},
            properties={"title": "My Sheet", "creator": "Test User"},
        )
        mock_load.return_value = wb

        result = parser.parse(fake_xlsx)

        assert result.metadata["title"] == "My Sheet"
        assert result.metadata["creator"] == "Test User"
        assert result.metadata["sheet_count"] == 1

    @patch("app.processing.parsers.xlsx_parser.load_workbook")
    def test_cannot_open_raises_value_error(self, mock_load, parser, tmp_path) -> None:
        fake_xlsx = tmp_path / "bad.xlsx"
        fake_xlsx.write_bytes(b"not xlsx")
        mock_load.side_effect = Exception("corrupt")

        with pytest.raises(ValueError, match="Cannot open XLSX"):
            parser.parse(fake_xlsx)

    @patch("app.processing.parsers.xlsx_parser.load_workbook")
    def test_empty_sheet(self, mock_load, parser, tmp_path) -> None:
        fake_xlsx = tmp_path / "empty.xlsx"
        fake_xlsx.write_bytes(b"PK\x03\x04 fake")

        wb = _make_mock_workbook(sheets={"Empty": []})
        mock_load.return_value = wb

        result = parser.parse(fake_xlsx)

        assert len(result.pages) == 1
        assert "empty" in result.pages[0].text.lower()

    @patch("app.processing.parsers.xlsx_parser.load_workbook")
    def test_formula_preserved_as_text(self, mock_load, parser, tmp_path) -> None:
        fake_xlsx = tmp_path / "formula.xlsx"
        fake_xlsx.write_bytes(b"PK\x03\x04 fake")

        wb = _make_mock_workbook(sheets={
            "Sheet1": [
                ["A", "B"],
                [1, "=SUM(A1:A10)"],
            ]
        })
        mock_load.return_value = wb

        result = parser.parse(fake_xlsx)

        all_text = result.pages[0].text
        assert "=SUM(A1:A10)" in all_text

    @patch("app.processing.parsers.xlsx_parser.load_workbook")
    def test_sheet_parse_failure_graceful(self, mock_load, parser, tmp_path) -> None:
        fake_xlsx = tmp_path / "bad_sheet.xlsx"
        fake_xlsx.write_bytes(b"PK\x03\x04 fake")

        wb = MagicMock()
        wb.sheetnames = ["BadSheet"]

        bad_ws = MagicMock()
        bad_ws.iter_rows.side_effect = Exception("sheet error")
        wb.__getitem__ = MagicMock(return_value=bad_ws)

        props = MagicMock()
        props.title = ""
        props.creator = ""
        props.subject = ""
        props.description = ""
        props.created = None
        props.modified = None
        wb.properties = props
        wb.close = MagicMock()

        mock_load.return_value = wb

        result = parser.parse(fake_xlsx)

        assert len(result.pages) == 1
        assert result.pages[0].confidence == 0.0
        assert "Error" in result.pages[0].text


class TestXLSXParserCellToString:
    """Test _cell_to_string static method."""

    def test_none_value_returns_empty(self) -> None:
        from app.processing.parsers.xlsx_parser import XLSXParser

        cell = _make_mock_cell(1, 1, None)
        # Ensure the mock cell is not an instance of MergedCell
        assert not isinstance(cell, type(None))
        result = XLSXParser._cell_to_string(cell, {})
        assert result == ""

    def test_string_value(self) -> None:
        from app.processing.parsers.xlsx_parser import XLSXParser

        cell = _make_mock_cell(1, 1, "hello")
        result = XLSXParser._cell_to_string(cell, {})
        assert result == "hello"

    def test_numeric_value(self) -> None:
        from app.processing.parsers.xlsx_parser import XLSXParser

        cell = _make_mock_cell(1, 1, 42)
        result = XLSXParser._cell_to_string(cell, {})
        assert result == "42"

    def test_formula_preserved(self) -> None:
        from app.processing.parsers.xlsx_parser import XLSXParser

        cell = _make_mock_cell(1, 1, "=SUM(A1:A10)")
        result = XLSXParser._cell_to_string(cell, {})
        assert result == "=SUM(A1:A10)"

    def test_merged_cell_from_map(self) -> None:
        from app.processing.parsers.xlsx_parser import XLSXParser
        from tests.processing.conftest import _MockMergedCell

        cell = _MockMergedCell()
        cell.row = 2
        cell.column = 1
        merged_map = {(2, 1): "merged_value"}

        result = XLSXParser._cell_to_string(cell, merged_map)
        assert result == "merged_value"

    def test_none_with_merged_map_fallback(self) -> None:
        from app.processing.parsers.xlsx_parser import XLSXParser

        cell = _make_mock_cell(1, 1, None)
        merged_map = {(1, 1): "fallback"}
        result = XLSXParser._cell_to_string(cell, merged_map)
        assert result == "fallback"


class TestXLSXParserTextSummary:
    """Test _build_text_summary static method."""

    def test_basic_summary(self) -> None:
        from app.processing.parsers.xlsx_parser import XLSXParser

        rows = [["A", "B"], ["1", "2"]]
        summary = XLSXParser._build_text_summary("TestSheet", rows)

        assert "[Sheet: TestSheet]" in summary
        assert "A | B" in summary
        assert "1 | 2" in summary

    def test_large_sheet_truncated(self) -> None:
        from app.processing.parsers.xlsx_parser import XLSXParser

        rows = [["row", str(i)] for i in range(100)]
        summary = XLSXParser._build_text_summary("BigSheet", rows)

        assert "50 more rows" in summary
