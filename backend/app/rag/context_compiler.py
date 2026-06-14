"""Context compilation: assemble retrieved chunks into a structured ContextPack."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_APPROX_CHARS_PER_TOKEN = 4


@dataclass
class Citation:
    """A reference to a specific chunk in a source document.

    Attributes:
        chunk_id: Unique identifier for the chunk.
        document_id: UUID of the parent document.
        page: Page number (0 if unknown).
        text_excerpt: A short excerpt from the chunk.
        relevance_score: Relevance score from retrieval (higher is better).
    """

    chunk_id: str
    document_id: str
    page: int = 0
    text_excerpt: str = ""
    relevance_score: float = 0.0


@dataclass
class ContextPack:
    """The assembled context passed to the answer generator.

    Attributes:
        system_prompt: The system-level prompt guiding the LLM.
        context_text: The formatted context block (numbered sources).
        citations: Ordered list of citations referenced in the context.
        token_count: Approximate total token count of the full prompt.
    """

    system_prompt: str = ""
    context_text: str = ""
    citations: list[Citation] = field(default_factory=list)
    token_count: int = 0


_SYSTEM_PROMPT = (
    "You are a precise document analysis assistant. Answer the user's question "
    "using ONLY the information provided in the <context> section below. "
    "When referencing information, cite the source using [source:N] notation "
    "where N is the source number.\n\n"
    "Rules:\n"
    "- If the context does not contain enough information, say so clearly.\n"
    "- Do NOT fabricate information not present in the context.\n"
    "- Be concise and factual.\n"
    "- Preserve exact numbers, dates, and names from the source.\n"
    "- If the question is in Vietnamese, answer in Vietnamese.\n"
    "- If the question is in English, answer in English.\n"
)


def _estimate_tokens(text: str) -> int:
    """Estimate token count using character-based heuristic."""
    return max(1, len(text) // _APPROX_CHARS_PER_TOKEN)


def _truncate_excerpt(text: str, max_chars: int = 200) -> str:
    """Create a short excerpt from chunk text."""
    text = text.strip().replace("\n", " ")
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


class ContextCompiler:
    """Compile retrieved chunks into a structured ``ContextPack``.

    Manages token budgets, formats citations, and assembles the system prompt.

    Args:
        max_context_tokens: Maximum token budget for the context block.
    """

    def __init__(self, max_context_tokens: int = 4000) -> None:
        self._max_context_tokens = max_context_tokens

    def compile(
        self,
        query: str,
        chunks: list,
        max_tokens: int = 4000,
    ) -> ContextPack:
        """Build a ``ContextPack`` from retrieved chunks.

        Chunks are included in score-descending order until the token budget
        is exhausted. Each included chunk receives a numbered citation.

        Args:
            query: The (possibly rewritten) user query.
            chunks: A list of ``SearchResult`` objects (must have ``text``,
                ``chunk_id``, ``document_id``, ``page``, ``score`` attributes).
            max_tokens: Maximum token budget for the context block.

        Returns:
            A fully populated ``ContextPack``.
        """
        budget = min(max_tokens, self._max_context_tokens)

        sorted_chunks = sorted(chunks, key=lambda c: c.score, reverse=True)

        context_parts: list[str] = []
        citations: list[Citation] = []
        used_tokens = 0

        system_prompt = _SYSTEM_PROMPT
        system_tokens = _estimate_tokens(system_prompt)

        available = budget - system_tokens - _estimate_tokens(f"\n\n<question>\n{query}\n</question>")

        for i, chunk in enumerate(sorted_chunks):
            source_num = i + 1
            header = f"[source:{source_num}]"
            block = f"{header}\n{chunk.text}\n"
            block_tokens = _estimate_tokens(block)

            if used_tokens + block_tokens > available and citations:
                break

            context_parts.append(block)
            used_tokens += block_tokens

            citations.append(
                Citation(
                    chunk_id=str(chunk.chunk_id),
                    document_id=str(chunk.document_id),
                    page=getattr(chunk, "page", 0),
                    text_excerpt=_truncate_excerpt(chunk.text),
                    relevance_score=chunk.score,
                )
            )

        context_text = "\n".join(context_parts)
        total_tokens = system_tokens + _estimate_tokens(context_text) + _estimate_tokens(query)

        logger.debug(
            "Compiled context: %d sources, ~%d tokens (budget=%d)",
            len(citations),
            total_tokens,
            budget,
        )

        return ContextPack(
            system_prompt=system_prompt,
            context_text=context_text,
            citations=citations,
            token_count=total_tokens,
        )
