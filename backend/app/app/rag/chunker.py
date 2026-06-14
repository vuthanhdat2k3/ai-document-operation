"""Recursive text chunking with overlap for document indexing."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Chunk:
    """A text chunk produced by the chunker.

    Attributes:
        text: The chunk text content.
        start_offset: Character offset where this chunk starts in the original text.
        end_offset: Character offset where this chunk ends in the original text.
        page: Optional page number this chunk originated from.
        metadata: Arbitrary metadata attached to this chunk.
    """

    text: str
    start_offset: int
    end_offset: int
    page: int | None = None
    metadata: dict = field(default_factory=dict)


class TextChunker:
    """Splits text into chunks using a recursive separator strategy.

    The splitter tries separators in priority order (paragraph → newline →
    sentence → word → character) and recursively splits pieces that still
    exceed ``chunk_size``.  Adjacent chunks share ``chunk_overlap`` characters
    of context.

    Args:
        chunk_size: Maximum character length of each chunk.
        chunk_overlap: Number of overlapping characters between consecutive chunks.
    """

    DEFAULT_SEPARATORS: list[str] = ["\n\n", "\n", ". ", " ", ""]

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be less than chunk_size ({chunk_size})"
            )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def recursive_split(
        self,
        text: str,
        metadata: dict | None = None,
        page: int | None = None,
        separators: list[str] | None = None,
    ) -> list[Chunk]:
        """Split *text* into chunks respecting size and overlap constraints.

        Args:
            text: The full text to split.
            metadata: Optional metadata propagated to every resulting ``Chunk``.
            page: Optional page number propagated to every resulting ``Chunk``.
            separators: Override the default separator priority list.

        Returns:
            Ordered list of ``Chunk`` objects.
        """
        if not text or not text.strip():
            return []

        sep_list = separators if separators is not None else self.DEFAULT_SEPARATORS
        raw_pieces = self._split_text_recursive(text, sep_list)
        return self._merge_pieces(raw_pieces, text, metadata or {}, page)

    def _split_text_recursive(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split *text* using the given *separators* in order.

        Returns pieces that are each ≤ ``chunk_size`` characters.
        """
        if len(text) <= self.chunk_size:
            return [text]

        if not separators:
            return self._hard_split(text)

        sep = separators[0]
        remaining_seps = separators[1:]

        if sep == "":
            return self._hard_split(text)

        parts = text.split(sep)
        pieces: list[str] = []
        current = ""

        for part in parts:
            candidate = (current + sep + part) if current else part

            if len(candidate) > self.chunk_size:
                if current:
                    pieces.append(current)
                    current = ""

                if len(part) > self.chunk_size:
                    pieces.extend(self._split_text_recursive(part, remaining_seps))
                else:
                    current = part
            else:
                current = candidate

        if current:
            pieces.append(current)

        final: list[str] = []
        for piece in pieces:
            if len(piece) > self.chunk_size:
                final.extend(self._split_text_recursive(piece, remaining_seps))
            else:
                final.append(piece)

        return final

    def _hard_split(self, text: str) -> list[str]:
        """Last-resort fixed-size character split."""
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunks.append(text[start:end])
            start = end
        return chunks

    def _merge_pieces(
        self,
        pieces: list[str],
        original: str,
        metadata: dict,
        page: int | None,
    ) -> list[Chunk]:
        """Convert raw text pieces into ``Chunk`` objects with offsets and overlap."""
        chunks: list[Chunk] = []
        search_start = 0

        for piece in pieces:
            idx = original.find(piece, search_start)
            if idx == -1:
                idx = search_start
            start = idx
            end = idx + len(piece)

            chunks.append(
                Chunk(
                    text=piece,
                    start_offset=start,
                    end_offset=end,
                    page=page,
                    metadata=dict(metadata),
                )
            )
            search_start = max(end - self.chunk_overlap, start)

        if self.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._apply_overlap(chunks, original)

        return chunks

    def _apply_overlap(self, chunks: list[Chunk], original: str) -> list[Chunk]:
        """Extend each chunk (except the first) with overlapping context from the previous chunk."""
        overlapped: list[Chunk] = [chunks[0]]

        for i in range(1, len(chunks)):
            prev = chunks[i - 1]
            curr = chunks[i]

            overlap_start = max(curr.start_offset - self.chunk_overlap, 0)
            overlap_text = original[overlap_start : curr.start_offset]

            new_text = overlap_text + curr.text
            if len(new_text) > self.chunk_size:
                new_text = new_text[: self.chunk_size]

            overlapped.append(
                Chunk(
                    text=new_text,
                    start_offset=overlap_start,
                    end_offset=curr.end_offset,
                    page=curr.page,
                    metadata=dict(curr.metadata),
                )
            )

        return overlapped
