"""Tests for context compilation, citation formatting, and token budgets."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.rag.context_compiler import (
    Citation,
    ContextCompiler,
    ContextPack,
    _estimate_tokens,
    _truncate_excerpt,
)


@dataclass
class FakeChunk:
    """Minimal chunk stub for testing."""

    chunk_id: str
    document_id: str
    text: str
    page: int = 0
    score: float = 0.5


class TestEstimateTokens:
    """Token estimation heuristic."""

    def test_empty_string(self) -> None:
        assert _estimate_tokens("") == 1

    def test_short_string(self) -> None:
        result = _estimate_tokens("hello")
        assert result == 1  # 5 chars // 4 = 1

    def test_longer_string(self) -> None:
        text = "a" * 100
        assert _estimate_tokens(text) == 25

    def test_approximate_ratio(self) -> None:
        text = "x" * 400
        assert _estimate_tokens(text) == 100


class TestTruncateExcerpt:
    """Excerpt truncation."""

    def test_short_text_unchanged(self) -> None:
        assert _truncate_excerpt("short text") == "short text"

    def test_exact_limit_unchanged(self) -> None:
        text = "a" * 200
        assert _truncate_excerpt(text) == text

    def test_long_text_truncated(self) -> None:
        text = "word " * 100  # 500 chars
        result = _truncate_excerpt(text, max_chars=200)
        assert len(result) <= 204  # 200 + "..."
        assert result.endswith("...")

    def test_newlines_replaced(self) -> None:
        assert _truncate_excerpt("line1\nline2") == "line1 line2"

    def test_whitespace_stripped(self) -> None:
        assert _truncate_excerpt("  padded  ") == "padded"


class TestCitation:
    """Citation dataclass."""

    def test_defaults(self) -> None:
        c = Citation(chunk_id="c1", document_id="d1")
        assert c.page == 0
        assert c.text_excerpt == ""
        assert c.relevance_score == 0.0

    def test_full_fields(self) -> None:
        c = Citation(
            chunk_id="c1",
            document_id="d1",
            page=5,
            text_excerpt="some text",
            relevance_score=0.95,
        )
        assert c.chunk_id == "c1"
        assert c.document_id == "d1"
        assert c.page == 5
        assert c.text_excerpt == "some text"
        assert c.relevance_score == 0.95


class TestContextPack:
    """ContextPack dataclass."""

    def test_defaults(self) -> None:
        cp = ContextPack()
        assert cp.system_prompt == ""
        assert cp.context_text == ""
        assert cp.citations == []
        assert cp.token_count == 0


class TestContextCompiler:
    """ContextCompiler.compile tests."""

    def test_empty_chunks(self) -> None:
        compiler = ContextCompiler()
        pack = compiler.compile("test query", [])
        assert pack.citations == []
        assert "[source:" not in pack.context_text
        assert pack.token_count > 0

    def test_single_chunk(self) -> None:
        compiler = ContextCompiler()
        chunks = [FakeChunk(chunk_id="c1", document_id="d1", text="Hello world", score=0.9)]
        pack = compiler.compile("query", chunks)
        assert len(pack.citations) == 1
        assert pack.citations[0].chunk_id == "c1"
        assert "[source:1]" in pack.context_text

    def test_multiple_chunks_sorted_by_score(self) -> None:
        compiler = ContextCompiler()
        chunks = [
            FakeChunk(chunk_id="c_low", document_id="d1", text="Low score", score=0.1),
            FakeChunk(chunk_id="c_high", document_id="d1", text="High score", score=0.9),
            FakeChunk(chunk_id="c_mid", document_id="d1", text="Mid score", score=0.5),
        ]
        pack = compiler.compile("query", chunks)
        assert pack.citations[0].chunk_id == "c_high"
        assert pack.citations[1].chunk_id == "c_mid"
        assert pack.citations[2].chunk_id == "c_low"

    def test_citation_numbering(self) -> None:
        compiler = ContextCompiler()
        chunks = [
            FakeChunk(chunk_id=f"c{i}", document_id="d1", text=f"Chunk {i}", score=0.9 - i * 0.1)
            for i in range(3)
        ]
        pack = compiler.compile("query", chunks)
        for i, cit in enumerate(pack.citations):
            assert cit.chunk_id == f"c{i}"

    def test_token_budget_enforced(self) -> None:
        compiler = ContextCompiler(max_context_tokens=100)
        chunks = [
            FakeChunk(
                chunk_id=f"c{i}",
                document_id="d1",
                text=f"This is a reasonably long chunk number {i} with enough text to consume tokens.",
                score=0.9 - i * 0.05,
            )
            for i in range(20)
        ]
        pack = compiler.compile("query", chunks, max_tokens=100)
        assert len(pack.citations) < 20

    def test_max_tokens_param_overrides(self) -> None:
        compiler = ContextCompiler(max_context_tokens=10000)
        chunks = [
            FakeChunk(chunk_id=f"c{i}", document_id="d1", text=f"Chunk {i} content here", score=0.9 - i * 0.01)
            for i in range(5)
        ]
        pack = compiler.compile("query", chunks, max_tokens=50)
        assert len(pack.citations) < 5

    def test_system_prompt_present(self) -> None:
        compiler = ContextCompiler()
        pack = compiler.compile("query", [])
        assert "document analysis assistant" in pack.system_prompt.lower()

    def test_system_prompt_contains_citation_instruction(self) -> None:
        compiler = ContextCompiler()
        pack = compiler.compile("query", [])
        assert "[source:N]" in pack.system_prompt

    def test_citation_page_preserved(self) -> None:
        compiler = ContextCompiler()
        chunks = [FakeChunk(chunk_id="c1", document_id="d1", text="text", page=7, score=0.9)]
        pack = compiler.compile("query", chunks)
        assert pack.citations[0].page == 7

    def test_citation_text_excerpt(self) -> None:
        compiler = ContextCompiler()
        long_text = "word " * 100
        chunks = [FakeChunk(chunk_id="c1", document_id="d1", text=long_text, score=0.9)]
        pack = compiler.compile("query", chunks)
        assert len(pack.citations[0].text_excerpt) <= 204

    def test_context_contains_source_blocks(self) -> None:
        compiler = ContextCompiler()
        chunks = [
            FakeChunk(chunk_id="c1", document_id="d1", text="Alpha content", score=0.9),
            FakeChunk(chunk_id="c2", document_id="d2", text="Beta content", score=0.8),
        ]
        pack = compiler.compile("query", chunks)
        assert "[source:1]" in pack.context_text
        assert "[source:2]" in pack.context_text
        assert "Alpha content" in pack.context_text
        assert "Beta content" in pack.context_text

    def test_first_chunk_included_even_if_large(self) -> None:
        compiler = ContextCompiler(max_context_tokens=50)
        big_text = "x " * 500
        chunks = [FakeChunk(chunk_id="c1", document_id="d1", text=big_text, score=0.9)]
        pack = compiler.compile("query", chunks, max_tokens=50)
        assert len(pack.citations) == 1
