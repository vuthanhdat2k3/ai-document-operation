"""Shared conftest for processing tests — mocks unavailable third-party modules."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


class _MockMergedCell:
    """Stand-in for openpyxl.cell.cell.MergedCell so isinstance() works."""
    pass


class _MockCell:
    """Stand-in for openpyxl.cell.cell.Cell."""
    def __init__(self, row: int = 1, column: int = 1, value=None):
        self.row = row
        self.column = column
        self.value = value


class _MockReadOnlyCell:
    """Stand-in for openpyxl.cell.read_only.ReadOnlyCell."""
    def __init__(self, row: int = 1, column: int = 1, value=None):
        self.row = row
        self.column = column
        self.value = value


# Build openpyxl mock hierarchy with real classes for isinstance checks
openpyxl_mock = MagicMock()
openpyxl_mock.cell.cell.Cell = _MockCell
openpyxl_mock.cell.cell.MergedCell = _MockMergedCell
openpyxl_mock.cell.read_only.ReadOnlyCell = _MockReadOnlyCell

_MOCK_MODULES: dict[str, object] = {
    "fitz": MagicMock(),
    "docx": MagicMock(),
    "docx.table": MagicMock(),
    "docx.text": MagicMock(),
    "docx.text.paragraph": MagicMock(),
    "openpyxl": openpyxl_mock,
    "openpyxl.cell": openpyxl_mock.cell,
    "openpyxl.cell.cell": openpyxl_mock.cell.cell,
    "openpyxl.cell.read_only": openpyxl_mock.cell.read_only,
    "openpyxl.worksheet": openpyxl_mock.worksheet,
    "openpyxl.worksheet.worksheet": openpyxl_mock.worksheet.worksheet,
}

for mod_name, mod_obj in _MOCK_MODULES.items():
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mod_obj
