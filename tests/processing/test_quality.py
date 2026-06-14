"""Tests for QualityScorer."""

from __future__ import annotations

import pytest

from app.processing.parsers.base import PageResult, ParseResult, TableData, ImageData
from app.processing.quality import QualityScorer


@pytest.fixture()
def scorer():
    return QualityScorer()


class TestQualityScorerScore:
    """QualityScorer.score() integration tests."""

    def test_empty_pages_returns_zero(self, scorer) -> None:
        result = ParseResult(pages=[])
        assert scorer.score(result, total_pages=10) == 0.0

    def test_perfect_document_scores_high(self, scorer) -> None:
        pages = [
            PageResult(
                page_number=i,
                text="This is a well-formed page with plenty of text content. " * 10,
                tables=[TableData(headers=["A", "B"], rows=[["1", "2"]])],
                confidence=1.0,
            )
            for i in range(1, 6)
        ]
        result = ParseResult(pages=pages)
        score = scorer.score(result, total_pages=5)
        assert score >= 0.7

    def test_all_empty_text_scores_low(self, scorer) -> None:
        pages = [
            PageResult(page_number=i, text="", confidence=0.0)
            for i in range(1, 4)
        ]
        result = ParseResult(pages=pages)
        score = scorer.score(result, total_pages=3)
        # encoding=1.0 (no bad chars in empty text), completeness=1.0, language=0.5
        # 0*0.3 + 0*0.2 + 1.0*0.2 + 1.0*0.2 + 0.5*0.1 = 0.45
        assert score < 0.5
        assert score > 0.0  # not zero because completeness and encoding are perfect

    def test_score_is_clamped_0_to_1(self, scorer) -> None:
        pages = [PageResult(page_number=1, text="x")]
        result = ParseResult(pages=pages)
        score = scorer.score(result, total_pages=1)
        assert 0.0 <= score <= 1.0

    def test_score_with_very_bad_encoding(self, scorer) -> None:
        pages = [
            PageResult(
                page_number=1,
                text="\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd" * 10,
                confidence=1.0,
            )
        ]
        result = ParseResult(pages=pages)
        score = scorer.score(result, total_pages=1)
        assert score < 0.7


class TestTextDensity:
    """_text_density factor tests."""

    def test_all_pages_meaningful(self, scorer) -> None:
        pages = [
            PageResult(page_number=1, text="a" * 50),
            PageResult(page_number=2, text="b" * 100),
        ]
        result = ParseResult(pages=pages)
        density = scorer._text_density(result)
        assert density == 1.0

    def test_no_pages_meaningful(self, scorer) -> None:
        pages = [
            PageResult(page_number=1, text="short"),
            PageResult(page_number=2, text="tiny"),
        ]
        result = ParseResult(pages=pages)
        density = scorer._text_density(result)
        assert density == 0.0

    def test_partial_meaningful(self, scorer) -> None:
        pages = [
            PageResult(page_number=1, text="a" * 50),
            PageResult(page_number=2, text="short"),
        ]
        result = ParseResult(pages=pages)
        density = scorer._text_density(result)
        assert density == 0.5

    def test_empty_pages(self, scorer) -> None:
        result = ParseResult(pages=[])
        assert scorer._text_density(result) == 0.0


class TestStructure:
    """_structure factor tests."""

    def test_page_with_table(self, scorer) -> None:
        pages = [
            PageResult(
                page_number=1,
                text="Some text",
                tables=[TableData(headers=["A"], rows=[["1"]])],
            )
        ]
        result = ParseResult(pages=pages)
        s = scorer._structure(result)
        assert s >= 0.4  # table bonus

    def test_page_with_image(self, scorer) -> None:
        pages = [
            PageResult(
                page_number=1,
                text="Some text",
                images=[ImageData(description="img")],
            )
        ]
        result = ParseResult(pages=pages)
        s = scorer._structure(result)
        assert s >= 0.2  # image bonus

    def test_page_with_heading(self, scorer) -> None:
        pages = [
            PageResult(page_number=1, text="# Heading\nSome content here"),
        ]
        result = ParseResult(pages=pages)
        s = scorer._structure(result)
        assert s >= 0.2  # heading bonus

    def test_empty_text_page(self, scorer) -> None:
        pages = [PageResult(page_number=1, text="")]
        result = ParseResult(pages=pages)
        s = scorer._structure(result)
        assert s == 0.0


class TestEncoding:
    """_encoding factor tests."""

    def test_clean_text_scores_high(self, scorer) -> None:
        pages = [PageResult(page_number=1, text="Normal clean ASCII text.")]
        result = ParseResult(pages=pages)
        enc = scorer._encoding(result)
        assert enc == 1.0

    def test_replacement_chars_penalize(self, scorer) -> None:
        pages = [PageResult(page_number=1, text="\ufffd" * 10 + "abc")]
        result = ParseResult(pages=pages)
        enc = scorer._encoding(result)
        assert enc < 1.0

    def test_mojibake_penalize(self, scorer) -> None:
        pages = [PageResult(page_number=1, text="ÃÃÃÃÃ text")]
        result = ParseResult(pages=pages)
        enc = scorer._encoding(result)
        assert enc < 1.0

    def test_empty_pages(self, scorer) -> None:
        result = ParseResult(pages=[])
        assert scorer._encoding(result) == 0.0


class TestCompleteness:
    """_completeness factor tests."""

    def test_all_pages_parsed(self, scorer) -> None:
        pages = [PageResult(page_number=i) for i in range(1, 6)]
        result = ParseResult(pages=pages)
        assert scorer._completeness(result, total_pages=5) == 1.0

    def test_partial_pages(self, scorer) -> None:
        pages = [PageResult(page_number=i) for i in range(1, 4)]
        result = ParseResult(pages=pages)
        comp = scorer._completeness(result, total_pages=6)
        assert comp == pytest.approx(0.5)

    def test_zero_total_pages(self, scorer) -> None:
        pages = [PageResult(page_number=1)]
        result = ParseResult(pages=pages)
        assert scorer._completeness(result, total_pages=0) == 1.0

    def test_more_pages_than_expected(self, scorer) -> None:
        pages = [PageResult(page_number=i) for i in range(1, 11)]
        result = ParseResult(pages=pages)
        assert scorer._completeness(result, total_pages=5) == 1.0


class TestLanguage:
    """_language factor tests."""

    def test_consistent_latin_text(self, scorer) -> None:
        pages = [PageResult(page_number=1, text="This is consistent English text " * 10)]
        result = ParseResult(pages=pages)
        lang = scorer._language(result)
        assert lang >= 0.8

    def test_no_alpha_chars(self, scorer) -> None:
        pages = [PageResult(page_number=1, text="123 456 789")]
        result = ParseResult(pages=pages)
        lang = scorer._language(result)
        assert lang == 0.5

    def test_empty_pages(self, scorer) -> None:
        result = ParseResult(pages=[])
        assert scorer._language(result) == 0.0


class TestUnicodeBlock:
    """_unicode_block static method tests."""

    def test_basic_latin(self) -> None:
        assert QualityScorer._unicode_block("A") == "basic_latin"

    def test_latin_supplement(self) -> None:
        assert QualityScorer._unicode_block("\u00c0") == "latin_supplement"

    def test_cyrillic(self) -> None:
        assert QualityScorer._unicode_block("\u0410") == "cyrillic"

    def test_cjk_unified(self) -> None:
        assert QualityScorer._unicode_block("\u4e00") == "cjk_unified"
