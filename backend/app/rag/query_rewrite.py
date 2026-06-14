"""Query rewriting: HyDE and query expansion for improved retrieval."""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

_VI_ABBREVIATIONS: dict[str, str] = {
    "hđ": "hợp đồng",
    "đv": "đơn vị",
    "pct": "phó chủ tịch",
    "tgđ": "tổng giám đốc",
    "gđ": "giám đốc",
    "ks": "kỹ sư",
    "cn": "công nhân",
    "kh": "khách hàng",
    "bt": "bảo trì",
    "ql": "quản lý",
    "qt": "quy trình",
    "nv": "nhân viên",
    "hs": "hồ sơ",
    "tb": "thông báo",
    "qd": "quyết định",
    "nd": "nghị định",
    "tt": "thông tư",
}

_SYNONYMS: dict[str, list[str]] = {
    "penalty": ["fine", "sanction", "liquidated damages", "phạt", "chế tài", "bồi thường thiệt hại"],
    "contract": ["agreement", "deal", "hợp đồng", "thỏa thuận"],
    "termination": ["cancellation", "ending", "chấm dứt", "hủy bỏ", "thanh lý"],
    "payment": ["disbursement", "payout", "thanh toán", "chi trả"],
    "deadline": ["due date", "time limit", "thời hạn", "hạn chót"],
    "budget": ["cost estimate", "funding", "ngân sách", "dự toán"],
    "warranty": ["guarantee", "bảo hành", "bảo đảm"],
    "amendment": ["modification", "addendum", "sửa đổi", "phụ lục"],
    "approval": ["authorization", "endorsement", "phê duyệt", "chấp thuận"],
    "risk": ["hazard", "threat", "rủi ro", "nguy cơ"],
    "scope": ["range", "extent", "phạm vi"],
    "milestone": ["checkpoint", "mốc tiến độ", "cột mốc"],
    "deliverable": ["output", "kết quả", "sản phẩm bàn giao"],
}


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal interface for an LLM that can complete a prompt."""

    async def generate(self, prompt: str, max_tokens: int = 256, temperature: float = 0.3) -> str: ...


class _FallbackLLM:
    """Deterministic stub used when no real LLM is available."""

    async def generate(self, prompt: str, max_tokens: int = 256, temperature: float = 0.3) -> str:
        return (
            "Based on the available documentation, the relevant information "
            "pertains to the queried topic. Please refer to the source document "
            "for specific details and exact values."
        )


class QueryRewriter:
    """Rewrite and expand queries to improve retrieval recall.

    Supports HyDE (Hypothetical Document Embeddings) and synonym-based
    query expansion.

    Args:
        llm_provider: An object implementing the ``LLMProvider`` protocol.
            Falls back to a deterministic stub when ``None``.
    """

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self._llm = llm_provider or _FallbackLLM()

    async def hyde_rewrite(self, query: str, llm_provider: LLMProvider | None = None) -> str:
        """Generate a hypothetical answer passage for better embedding retrieval.

        The hypothetical document contains domain-specific terminology whose
        embedding is typically closer to actual document passages than the
        raw question embedding.

        Args:
            query: The original user query.
            llm_provider: Optional override LLM provider (uses instance default
                when ``None``).

        Returns:
            A hypothetical document passage that would answer the query.
        """
        provider = llm_provider or self._llm

        prompt = (
            "You are a helpful assistant. Write a short, factual paragraph "
            "(3-5 sentences) that would answer the following question. "
            "Write as if you are excerpting from an official document. "
            "Do NOT include any uncertainty or hedging.\n\n"
            f"Question: {query}\n\n"
            "Hypothetical document passage:"
        )

        try:
            result = await provider.generate(prompt, max_tokens=256, temperature=0.3)
            result = result.strip()
            if result:
                return result
        except Exception:
            logger.warning("HyDE generation failed, falling back to original query", exc_info=True)

        return query

    def expand_query(self, query: str) -> list[str]:
        """Generate alternative phrasings of the query using synonyms and normalisation.

        Returns 1-3 alternative phrasings (does **not** include the original query).

        Args:
            query: The original user query.

        Returns:
            List of alternative query strings.
        """
        expansions: list[str] = []

        normalised = self._normalise_vietnamese(query)
        if normalised != query.lower().strip():
            expansions.append(normalised)

        synonym_expanded = self._apply_synonyms(query)
        if synonym_expanded != query and synonym_expanded not in expansions:
            expansions.append(synonym_expanded)

        rephrased = self._rephrase(query)
        if rephrased and rephrased not in expansions:
            expansions.append(rephrased)

        return expansions[:3]

    @staticmethod
    def _normalise_vietnamese(query: str) -> str:
        """Expand Vietnamese abbreviations and normalise whitespace."""
        text = query.lower().strip()
        for abbr, full in _VI_ABBREVIATIONS.items():
            text = re.sub(rf"\b{re.escape(abbr)}\b", full, text, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _apply_synonyms(query: str) -> str:
        """Replace recognised terms with a synonym variant."""
        words = query.lower().split()
        replaced = False
        new_words: list[str] = []
        for word in words:
            clean = re.sub(r"[^\w]", "", word)
            if clean in _SYNONYMS and not replaced:
                synonyms = _SYNONYMS[clean]
                new_words.append(synonyms[0] if synonyms else word)
                replaced = True
            else:
                new_words.append(word)
        return " ".join(new_words)

    @staticmethod
    def _rephrase(query: str) -> str | None:
        """Produce a simple rephrasing by converting question forms."""
        q = query.strip()
        m = re.match(r"^what\s+(?:is|are)\s+the\s+(.+?)(?:\?*)$", q, re.IGNORECASE)
        if m:
            return f"Provide details about {m.group(1)}"

        m = re.match(r"^how\s+(?:much|many)\s+(.+?)(?:\?*)$", q, re.IGNORECASE)
        if m:
            return f"The amount/quantity of {m.group(1)}"

        m = re.match(r"^(.+?)\s+là\s+gì\s*\??$", q, re.IGNORECASE)
        if m:
            return f"Cho biết thông tin về {m.group(1)}"

        m = re.match(r"^tóm\s*tắt\s+(.+?)(?:\?*)$", q, re.IGNORECASE)
        if m:
            return f"Thông tin chính về {m.group(1)}"

        return None
