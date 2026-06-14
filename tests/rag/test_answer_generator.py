"""Tests for answer generation, citation extraction, and confidence scoring."""

from __future__ import annotations

import pytest

from app.rag.answer_generator import (
    Answer,
    AnswerGenerator,
    _build_prompt,
    _estimate_confidence,
    _extract_citations,
)
from app.rag.context_compiler import Citation, ContextPack


def _make_citations(n: int) -> list[Citation]:
    return [
        Citation(
            chunk_id=f"c{i}",
            document_id=f"d{i}",
            page=i,
            text_excerpt=f"excerpt {i}",
            relevance_score=1.0 - i * 0.1,
        )
        for i in range(n)
    ]


def _make_context(citations: list[Citation] | None = None) -> ContextPack:
    return ContextPack(
        system_prompt="You are a helpful assistant.",
        context_text="[source:1]\nSome context.\n[source:2]\nMore context.",
        citations=citations or _make_citations(2),
    )


class MockLLM:
    """Mock LLM that returns a preset response."""

    def __init__(self, response: str = "Default answer. [source:1]") -> None:
        self._response = response
        self.last_prompt: str | None = None

    async def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.1) -> str:
        self.last_prompt = prompt
        return self._response


class FailingLLM:
    """Mock LLM that always raises."""

    async def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.1) -> str:
        raise RuntimeError("LLM unavailable")


class TestBuildPrompt:
    """Prompt assembly."""

    def test_contains_system_prompt(self) -> None:
        ctx = _make_context()
        prompt = _build_prompt("What is X?", ctx)
        assert "helpful assistant" in prompt

    def test_contains_context(self) -> None:
        ctx = _make_context()
        prompt = _build_prompt("query", ctx)
        assert "<context>" in prompt
        assert "Some context." in prompt

    def test_contains_question(self) -> None:
        ctx = _make_context()
        prompt = _build_prompt("What is the penalty?", ctx)
        assert "What is the penalty?" in prompt
        assert "<question>" in prompt

    def test_contains_citation_instruction(self) -> None:
        ctx = _make_context()
        prompt = _build_prompt("query", ctx)
        assert "[source:N]" in prompt

    def test_empty_context(self) -> None:
        ctx = ContextPack(system_prompt="sys", context_text="", citations=[])
        prompt = _build_prompt("query", ctx)
        assert "query" in prompt
        assert "sys" in prompt


class TestExtractCitations:
    """Citation extraction from answer text."""

    def test_single_citation(self) -> None:
        cits = _make_citations(3)
        result = _extract_citations("Answer here. [source:1]", cits)
        assert len(result) == 1
        assert result[0].chunk_id == "c0"

    def test_multiple_citations(self) -> None:
        cits = _make_citations(3)
        result = _extract_citations("Answer. [source:1] and [source:3]", cits)
        assert len(result) == 2
        assert result[0].chunk_id == "c0"
        assert result[1].chunk_id == "c2"

    def test_duplicate_citations_deduped(self) -> None:
        cits = _make_citations(3)
        result = _extract_citations("[source:1] text [source:1] more", cits)
        assert len(result) == 1

    def test_no_citations_returns_first_available(self) -> None:
        cits = _make_citations(3)
        result = _extract_citations("No citations here.", cits)
        assert len(result) == 1
        assert result[0].chunk_id == "c0"

    def test_no_citations_empty_available(self) -> None:
        result = _extract_citations("No citations.", [])
        assert result == []

    def test_out_of_range_citation_ignored(self) -> None:
        cits = _make_citations(2)
        result = _extract_citations("[source:5] text", cits)
        assert len(result) == 1
        assert result[0].chunk_id == "c0"  # fallback to first

    def test_citation_ordering(self) -> None:
        cits = _make_citations(5)
        result = _extract_citations("[source:3] and [source:1] and [source:5]", cits)
        assert [c.chunk_id for c in result] == ["c0", "c2", "c4"]


class TestEstimateConfidence:
    """Confidence scoring heuristic."""

    def test_no_sources_zero_confidence(self) -> None:
        assert _estimate_confidence("answer", [], 0) == 0.0

    def test_good_citation_coverage(self) -> None:
        answer = "Answer. [source:1] [source:2]"
        cits = _make_citations(2)
        conf = _estimate_confidence(answer, cits, 2)
        assert conf > 0.5

    def test_hedging_reduces_confidence(self) -> None:
        answer_good = "The penalty is $1000. [source:1]"
        answer_bad = "I cannot determine the penalty. [source:1]"
        cits = _make_citations(1)
        conf_good = _estimate_confidence(answer_good, cits, 1)
        conf_bad = _estimate_confidence(answer_bad, cits, 1)
        assert conf_good > conf_bad

    def test_vietnamese_hedging(self) -> None:
        answer_good = "Phạt vi phạm là 500 triệu. [source:1]"
        answer_bad = "Không đủ thông tin để trả lời. [source:1]"
        cits = _make_citations(1)
        conf_good = _estimate_confidence(answer_good, cits, 1)
        conf_bad = _estimate_confidence(answer_bad, cits, 1)
        assert conf_good > conf_bad

    def test_confidence_bounded_0_1(self) -> None:
        cits = _make_citations(1)
        conf = _estimate_confidence("[source:1] " * 20, cits, 1)
        assert 0.0 <= conf <= 1.0

    def test_multiple_hedging_phrases(self) -> None:
        answer_none = "Good answer with penalty details. [source:1]"
        answer_hedge = "I cannot determine. It seems possibly unclear. [source:1]"
        cits = _make_citations(1)
        conf_none = _estimate_confidence(answer_none, cits, 1)
        conf_hedge = _estimate_confidence(answer_hedge, cits, 1)
        assert conf_hedge < conf_none


class TestAnswerGenerator:
    """AnswerGenerator.generate integration."""

    @pytest.mark.asyncio
    async def test_returns_answer(self) -> None:
        llm = MockLLM("The penalty is $500. [source:1]")
        gen = AnswerGenerator(llm_provider=llm)
        ctx = _make_context()
        answer = await gen.generate("What is the penalty?", ctx)
        assert isinstance(answer, Answer)
        assert "penalty" in answer.text.lower()

    @pytest.mark.asyncio
    async def test_citations_extracted(self) -> None:
        llm = MockLLM("Answer with [source:1] and [source:2].")
        gen = AnswerGenerator(llm_provider=llm)
        ctx = _make_context()
        answer = await gen.generate("query", ctx)
        assert len(answer.citations) == 2

    @pytest.mark.asyncio
    async def test_confidence_set(self) -> None:
        llm = MockLLM("Good answer. [source:1] [source:2]")
        gen = AnswerGenerator(llm_provider=llm)
        ctx = _make_context()
        answer = await gen.generate("query", ctx)
        assert 0.0 <= answer.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_llm_failure_graceful(self) -> None:
        gen = AnswerGenerator(llm_provider=FailingLLM())
        ctx = _make_context()
        answer = await gen.generate("query", ctx)
        assert "unable" in answer.text.lower() or "try again" in answer.text.lower()

    @pytest.mark.asyncio
    async def test_prompt_passed_to_llm(self) -> None:
        llm = MockLLM("response [source:1]")
        gen = AnswerGenerator(llm_provider=llm)
        ctx = _make_context()
        await gen.generate("What is X?", ctx)
        assert llm.last_prompt is not None
        assert "What is X?" in llm.last_prompt

    @pytest.mark.asyncio
    async def test_override_llm_provider(self) -> None:
        default_llm = MockLLM("default [source:1]")
        override_llm = MockLLM("override [source:1]")
        gen = AnswerGenerator(llm_provider=default_llm)
        ctx = _make_context()
        answer = await gen.generate("query", ctx, llm_provider=override_llm)
        assert "override" in answer.text

    @pytest.mark.asyncio
    async def test_empty_context(self) -> None:
        llm = MockLLM("Cannot find info. [source:1]")
        gen = AnswerGenerator(llm_provider=llm)
        ctx = ContextPack()
        answer = await gen.generate("query", ctx)
        assert isinstance(answer, Answer)
