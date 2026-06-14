"""Groundedness validation: verify that answer claims are supported by sources."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+|(?<=[。！？；])\s*")
_TOKENIZE = re.compile(r"\b\w{3,}\b", re.UNICODE)

_STOPWORDS: set[str] = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "has",
    "her", "was", "one", "our", "out", "this", "that", "with", "have",
    "from", "they", "been", "said", "each", "which", "their", "time",
    "will", "way", "about", "many", "then", "them", "these", "some",
    "would", "make", "like", "into", "could", "other", "than", "its",
    "over", "such", "after", "also", "upon", "where", "when", "what",
    "there", "using", "based", "provided", "information", "context",
    "according", "trong", "của", "và", "là", "cho", "các", "được",
    "không", "này", "đó", "với", "từ", "có", "những", "một",
}


def _split_claims(answer: str) -> list[str]:
    """Split the answer into individual claims (sentences).

    Filters out very short fragments and the source citation tags themselves.
    """
    raw = _SENTENCE_SPLIT.split(answer.strip())
    claims: list[str] = []
    for s in raw:
        cleaned = re.sub(r"\[source:\d+\]", "", s).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if len(cleaned) > 15:
            claims.append(cleaned)
    return claims if claims else [answer.strip()]


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text, excluding stop words."""
    tokens = _TOKENIZE.findall(text.lower())
    return {t for t in tokens if t not in _STOPWORDS}


@dataclass
class GroundednessResult:
    """Result of groundedness validation.

    Attributes:
        score: Overall groundedness score between 0.0 (unsupported) and 1.0 (fully supported).
        claims: All claims extracted from the answer.
        supported_claims: Claims that have supporting evidence in the sources.
        unsupported_claims: Claims without sufficient evidence in the sources.
    """

    score: float = 0.0
    claims: list[str] = field(default_factory=list)
    supported_claims: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)


class GroundednessValidator:
    """Validate that answer claims are supported by the provided sources.

    Uses keyword-overlap heuristics to check whether each claim in the answer
    has at least partial evidence in the source texts.

    Args:
        support_threshold: Minimum fraction of claim keywords that must appear
            in sources for a claim to be considered supported (0.0–1.0).
    """

    def __init__(self, support_threshold: float = 0.3) -> None:
        self._threshold = support_threshold

    def validate(self, answer: str, sources: list[str]) -> GroundednessResult:
        """Validate answer groundedness against source texts.

        Args:
            answer: The generated answer text.
            sources: List of source text passages used to generate the answer.

        Returns:
            A ``GroundednessResult`` with the score and claim breakdown.
        """
        if not answer.strip():
            return GroundednessResult(score=0.0)

        if not sources:
            return GroundednessResult(
                score=0.0,
                claims=_split_claims(answer),
                supported_claims=[],
                unsupported_claims=_split_claims(answer),
            )

        source_keywords: set[str] = set()
        for src in sources:
            source_keywords |= _extract_keywords(src)

        claims = _split_claims(answer)
        supported: list[str] = []
        unsupported: list[str] = []

        for claim in claims:
            claim_kw = _extract_keywords(claim)
            if not claim_kw:
                supported.append(claim)
                continue

            overlap = claim_kw & source_keywords
            ratio = len(overlap) / len(claim_kw)

            if ratio >= self._threshold:
                supported.append(claim)
            else:
                unsupported.append(claim)

        score = len(supported) / len(claims) if claims else 0.0
        score = round(score, 3)

        logger.debug(
            "Groundedness: score=%.3f, supported=%d, unsupported=%d, total=%d",
            score,
            len(supported),
            len(unsupported),
            len(claims),
        )

        return GroundednessResult(
            score=score,
            claims=claims,
            supported_claims=supported,
            unsupported_claims=unsupported,
        )
