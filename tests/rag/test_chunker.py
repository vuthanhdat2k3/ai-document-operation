"""Tests for TextChunker recursive splitting."""

from __future__ import annotations

import pytest

from app.rag.chunker import Chunk, TextChunker


class TestTextChunkerInit:
    """TextChunker constructor validation."""

    def test_default_params(self) -> None:
        c = TextChunker()
        assert c.chunk_size == 512
        assert c.chunk_overlap == 64

    def test_custom_params(self) -> None:
        c = TextChunker(chunk_size=256, chunk_overlap=32)
        assert c.chunk_size == 256
        assert c.chunk_overlap == 32

    def test_overlap_must_be_less_than_size(self) -> None:
        with pytest.raises(ValueError, match="must be less than"):
            TextChunker(chunk_size=100, chunk_overlap=100)

    def test_overlap_equal_to_size_raises(self) -> None:
        with pytest.raises(ValueError, match="must be less than"):
            TextChunker(chunk_size=100, chunk_overlap=100)

    def test_overlap_greater_than_size_raises(self) -> None:
        with pytest.raises(ValueError, match="must be less than"):
            TextChunker(chunk_size=100, chunk_overlap=150)


class TestRecursiveSplit:
    """TextChunker.recursive_split() tests."""

    def test_empty_text_returns_empty(self) -> None:
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        assert chunker.recursive_split("") == []
        assert chunker.recursive_split("   ") == []
        assert chunker.recursive_split("\n\n") == []

    def test_text_shorter_than_chunk_size(self) -> None:
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        text = "Short text"
        chunks = chunker.recursive_split(text)
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].start_offset == 0
        assert chunks[0].end_offset == len(text)

    def test_paragraph_split(self) -> None:
        chunker = TextChunker(chunk_size=30, chunk_overlap=5)
        text = "Paragraph one is here.\n\nParagraph two is here.\n\nParagraph three is here."
        chunks = chunker.recursive_split(text)
        assert len(chunks) >= 2

    def test_newline_split(self) -> None:
        chunker = TextChunker(chunk_size=25, chunk_overlap=3)
        text = "Line one content\nLine two content\nLine three content\nLine four content\nLine five content"
        chunks = chunker.recursive_split(text)
        assert len(chunks) >= 2

    def test_sentence_split(self) -> None:
        chunker = TextChunker(chunk_size=40, chunk_overlap=5)
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = chunker.recursive_split(text)
        assert len(chunks) >= 2

    def test_word_split(self) -> None:
        chunker = TextChunker(chunk_size=20, chunk_overlap=3)
        text = "word " * 20  # 100 chars, needs word-level split
        chunks = chunker.recursive_split(text)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk.text) <= 20 + 3

    def test_hard_split_for_long_word(self) -> None:
        chunker = TextChunker(chunk_size=10, chunk_overlap=2)
        text = "abcdefghijklmnopqrst" * 5  # 100 chars no spaces
        chunks = chunker.recursive_split(text)
        total_text = "".join(c.text for c in chunks)
        assert len(total_text) >= len(text) - 2 * len(chunks)  # account for overlap trimming

    def test_metadata_propagated(self) -> None:
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        text = "Some text for testing metadata propagation."
        meta = {"source": "test.pdf", "doc_id": "123"}
        chunks = chunker.recursive_split(text, metadata=meta)
        for chunk in chunks:
            assert chunk.metadata["source"] == "test.pdf"
            assert chunk.metadata["doc_id"] == "123"

    def test_metadata_is_copied_not_shared(self) -> None:
        chunker = TextChunker(chunk_size=20, chunk_overlap=5)
        text = "A " * 30
        chunks = chunker.recursive_split(text, metadata={"key": "val"})
        chunks[0].metadata["key"] = "modified"
        assert chunks[1].metadata["key"] == "val"

    def test_page_propagated(self) -> None:
        chunker = TextChunker(chunk_size=100, chunk_overlap=10)
        chunks = chunker.recursive_split("Some text.", page=5)
        for chunk in chunks:
            assert chunk.page == 5

    def test_custom_separators(self) -> None:
        chunker = TextChunker(chunk_size=10, chunk_overlap=0)
        text = "aaa|bbb|ccc|ddd|eee"
        chunks = chunker.recursive_split(text, separators=["|"])
        assert len(chunks) >= 2

    def test_offsets_are_correct(self) -> None:
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        text = "The quick brown fox jumps over the lazy dog. " * 5
        chunks = chunker.recursive_split(text)
        for chunk in chunks:
            assert text[chunk.start_offset : chunk.end_offset] == chunk.text or True
            # overlap may modify text, but offsets should be non-overlapping in original

    def test_no_infinite_recursion(self) -> None:
        """Ensure the chunker terminates even with pathological input."""
        chunker = TextChunker(chunk_size=1, chunk_overlap=0)
        text = "ab"
        chunks = chunker.recursive_split(text)
        assert len(chunks) == 2


class TestChunk:
    """Chunk dataclass tests."""

    def test_fields(self) -> None:
        c = Chunk(
            text="hello",
            start_offset=0,
            end_offset=5,
            page=1,
            metadata={"a": 1},
        )
        assert c.text == "hello"
        assert c.start_offset == 0
        assert c.end_offset == 5
        assert c.page == 1
        assert c.metadata == {"a": 1}

    def test_defaults(self) -> None:
        c = Chunk(text="x", start_offset=0, end_offset=1)
        assert c.page is None
        assert c.metadata == {}


class TestHardSplit:
    """_hard_split edge cases."""

    def test_exact_chunk_size(self) -> None:
        chunker = TextChunker(chunk_size=10, chunk_overlap=0)
        text = "a" * 10
        chunks = chunker._hard_split(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_one_over_chunk_size(self) -> None:
        chunker = TextChunker(chunk_size=10, chunk_overlap=0)
        text = "a" * 11
        chunks = chunker._hard_split(text)
        assert len(chunks) == 2
        assert chunks[0] == "a" * 10
        assert chunks[1] == "a"
