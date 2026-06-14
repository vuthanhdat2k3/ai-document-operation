"""Grounded answer generation with citation extraction."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.llm.base import LLMProvider, Message
from app.rag.context_compiler import Citation, ContextPack

logger = logging.getLogger(__name__)


@dataclass
class Answer:
    """A generated answer with citations and confidence."""

    text: str
    citations: list[Citation] = field(default_factory=list)
    confidence: float = 0.0
    thinking: str | None = None


_SOURCE_PATTERN = re.compile(r"\[source:(\d+)\]")


def _build_system_prompt() -> str:
    return (
        "You are a document analysis assistant. Answer questions using ONLY "
        "the provided context. Cite sources using [source:N] notation. "
        "If the context does not contain enough information, say so clearly. "
        "Respond in the same language as the question."
    )


def _build_prompt(query: str, context: ContextPack) -> str:
    parts: list[str] = []
    if context.context_text:
        parts.append(f"<context>\n{context.context_text}\n</context>")
    parts.append(f"<question>\n{query}\n</question>")
    return "\n\n".join(parts)


def _extract_citations(
    answer_text: str,
    available_citations: list[Citation],
) -> list[Citation]:
    found_indices: set[int] = set()
    for m in _SOURCE_PATTERN.finditer(answer_text):
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(available_citations):
            found_indices.add(idx)
    if not found_indices and available_citations:
        return [available_citations[0]]
    return [available_citations[i] for i in sorted(found_indices)]


def _estimate_confidence(answer_text: str, citations: list[Citation], total_sources: int) -> float:
    if total_sources == 0:
        return 0.0
    citation_count = len(re.findall(r"\[source:\d+\]", answer_text))
    citation_ratio = min(citation_count / max(total_sources, 1), 1.0)
    hedging_phrases = [
        "i cannot", "not enough information", "unclear", "not specified",
        "i'm not sure", "it seems", "possibly", "might be",
        "không đủ thông tin", "không rõ", "có thể", "không xác định",
    ]
    lower = answer_text.lower()
    hedge_count = sum(1 for h in hedging_phrases if h in lower)
    hedge_penalty = min(hedge_count * 0.15, 0.5)
    base = 0.5 + (citation_ratio * 0.4)
    return round(max(0.0, min(1.0, base - hedge_penalty)), 3)


class AnswerGenerator:
    """Generate grounded answers from a compiled context pack.

    Args:
        llm_provider: LLM provider from app.llm module.
    """

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self._llm = llm_provider

    async def generate(
        self,
        query: str,
        context: ContextPack,
        llm_provider: LLMProvider | None = None,
    ) -> Answer:
        provider = llm_provider or self._llm
        system = _build_system_prompt()
        prompt = _build_prompt(query, context)

        if provider is None:
            logger.warning("No LLM provider available, returning fallback answer")
            return Answer(
                text="No LLM provider configured. Please set LLM_PROVIDER in .env",
                citations=context.citations[:1],
                confidence=0.0,
            )

        try:
            messages = [Message(role="user", content=prompt)]
            response = await provider.chat(
                messages=messages,
                system=system,
                max_tokens=1024,
                temperature=0.1,
            )
            answer_text = response.content.strip()
            thinking = response.thinking
        except Exception:
            logger.warning("LLM generation failed", exc_info=True)
            answer_text = (
                "Unable to generate an answer at this time. "
                "Please try again or refer to the source documents directly."
            )
            thinking = None

        citations = _extract_citations(answer_text, context.citations)
        confidence = _estimate_confidence(answer_text, citations, len(context.citations))

        return Answer(
            text=answer_text,
            citations=citations,
            confidence=confidence,
            thinking=thinking,
        )
