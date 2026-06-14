"""Tests for BaseParser, ParseResult, PageResult, TableData, ImageData structures."""

from __future__ import annotations

import pytest
from pathlib import Path

from app.processing.parsers.base import (
    BaseParser,
    ImageData,
    PageResult,
    ParseResult,
    TableData,
)


class TestImageData:
    """ImageData frozen dataclass tests."""

    def test_default_values(self) -> None:
        img = ImageData()
        assert img.description == ""
        assert img.storage_path is None

    def test_custom_values(self) -> None:
        img = ImageData(description="logo", storage_path="/tmp/logo.png")
        assert img.description == "logo"
        assert img.storage_path == "/tmp/logo.png"

    def test_frozen(self) -> None:
        img = ImageData(description="test")
        with pytest.raises(AttributeError):
            img.description = "changed"  # type: ignore[misc]


class TestTableData:
    """TableData frozen dataclass tests."""

    def test_default_values(self) -> None:
        t = TableData()
        assert t.headers == []
        assert t.rows == []
        assert t.page == 0

    def test_custom_values(self) -> None:
        t = TableData(
            headers=["Name", "Age"],
            rows=[["Alice", "30"], ["Bob", "25"]],
            page=1,
        )
        assert t.headers == ["Name", "Age"]
        assert len(t.rows) == 2
        assert t.page == 1

    def test_frozen(self) -> None:
        t = TableData(headers=["A"])
        with pytest.raises(AttributeError):
            t.headers = ["B"]  # type: ignore[misc]

    def test_default_factory_independence(self) -> None:
        t1 = TableData()
        t2 = TableData()
        t1.headers.append("X")
        assert t2.headers == []


class TestPageResult:
    """PageResult frozen dataclass tests."""

    def test_required_field(self) -> None:
        p = PageResult(page_number=1)
        assert p.page_number == 1
        assert p.text == ""
        assert p.tables == []
        assert p.images == []
        assert p.confidence == 1.0

    def test_with_content(self) -> None:
        tables = [TableData(headers=["A"], rows=[["1"]])]
        images = [ImageData(description="img1")]
        p = PageResult(
            page_number=5,
            text="Hello world",
            tables=tables,
            images=images,
            confidence=0.85,
        )
        assert p.page_number == 5
        assert p.text == "Hello world"
        assert len(p.tables) == 1
        assert len(p.images) == 1
        assert p.confidence == 0.85

    def test_frozen(self) -> None:
        p = PageResult(page_number=1)
        with pytest.raises(AttributeError):
            p.text = "changed"  # type: ignore[misc]


class TestParseResult:
    """ParseResult mutable dataclass tests."""

    def test_default_values(self) -> None:
        r = ParseResult()
        assert r.pages == []
        assert r.metadata == {}
        assert r.quality_score == 0.0

    def test_is_mutable(self) -> None:
        r = ParseResult()
        r.quality_score = 0.95
        assert r.quality_score == 0.95
        r.pages.append(PageResult(page_number=1))
        assert len(r.pages) == 1

    def test_with_pages_and_metadata(self) -> None:
        pages = [
            PageResult(page_number=1, text="Page 1"),
            PageResult(page_number=2, text="Page 2"),
        ]
        r = ParseResult(
            pages=pages,
            metadata={"title": "Test Doc"},
            quality_score=0.88,
        )
        assert len(r.pages) == 2
        assert r.metadata["title"] == "Test Doc"
        assert r.quality_score == 0.88


class TestBaseParserContract:
    """Verify BaseParser ABC cannot be instantiated and requires parse()."""

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError, match="abstract method"):
            BaseParser()  # type: ignore[abstract]

    def test_concrete_subclass_can_instantiate(self) -> None:
        class DummyParser(BaseParser):
            def parse(self, file_path: Path) -> ParseResult:
                return ParseResult()

        parser = DummyParser()
        result = parser.parse(Path("/fake"))
        assert isinstance(result, ParseResult)
        assert result.pages == []

    def test_subclass_missing_parse_raises(self) -> None:
        class IncompleteParser(BaseParser):
            pass

        with pytest.raises(TypeError):
            IncompleteParser()  # type: ignore[abstract]
