from __future__ import annotations

import logging
import re

from app.processing.parsers.base import ParseResult

logger = logging.getLogger(__name__)

_WEIGHTS = {
    "text_density": 0.3,
    "structure": 0.2,
    "encoding": 0.2,
    "completeness": 0.2,
    "language": 0.1,
}


class QualityScorer:
    """Compute a weighted quality score (0.0-1.0) for a ``ParseResult``.

    Scoring factors and their weights:
        - text_density (0.3): ratio of non-empty pages
        - structure (0.2): presence of tables / images / headings
        - encoding (0.2): absence of replacement characters and mojibake
        - completeness (0.2): pages extracted vs expected total
        - language (0.1): consistency of detected language tokens
    """

    def score(self, result: ParseResult, total_pages: int) -> float:
        """Return a quality score between 0.0 and 1.0.

        Args:
            result: The parsed document result.
            total_pages: Total expected page count (from the document model or
                parser metadata).

        Returns:
            A float in [0.0, 1.0].
        """
        if not result.pages:
            return 0.0

        factors = {
            "text_density": self._text_density(result),
            "structure": self._structure(result),
            "encoding": self._encoding(result),
            "completeness": self._completeness(result, total_pages),
            "language": self._language(result),
        }

        score = sum(factors[k] * _WEIGHTS[k] for k in _WEIGHTS)
        return round(max(0.0, min(1.0, score)), 4)

    def _text_density(self, result: ParseResult) -> float:
        """Fraction of pages with meaningful text (>= 50 chars)."""
        if not result.pages:
            return 0.0
        meaningful = sum(1 for p in result.pages if len(p.text.strip()) >= 50)
        return meaningful / len(result.pages)

    def _structure(self, result: ParseResult) -> float:
        """Reward presence of structural elements (tables, images, headings)."""
        if not result.pages:
            return 0.0

        scores: list[float] = []
        for page in result.pages:
            page_score = 0.0
            if page.tables:
                page_score += 0.4
            if page.images:
                page_score += 0.2
            if re.search(r"^#{1,6}\s", page.text, re.MULTILINE):
                page_score += 0.2
            if page.text.strip():
                page_score += 0.2
            scores.append(min(1.0, page_score))

        return sum(scores) / len(scores)

    def _encoding(self, result: ParseResult) -> float:
        """Penalise replacement characters (U+FFFD) and common mojibake."""
        if not result.pages:
            return 0.0

        total_chars = 0
        bad_chars = 0
        for page in result.pages:
            text = page.text
            total_chars += max(len(text), 1)
            bad_chars += text.count("\ufffd")
            bad_chars += len(re.findall(r"[ÃÂ]{2,}", text))

        bad_ratio = bad_chars / max(total_chars, 1)
        return max(0.0, 1.0 - bad_ratio * 10)

    def _completeness(self, result: ParseResult, total_pages: int) -> float:
        """Ratio of parsed pages to expected total pages."""
        if total_pages <= 0:
            return 1.0
        parsed = len(result.pages)
        return min(1.0, parsed / total_pages)

    def _language(self, result: ParseResult) -> float:
        """Heuristic language consistency check.

        Checks that the majority of alphabetic characters fall within a
        single Unicode block range (basic Latin, Latin Extended, CJK, etc.).
        A consistent block suggests the text is in one language.
        """
        if not result.pages:
            return 0.0

        combined = " ".join(p.text for p in result.pages)
        alpha_chars = [c for c in combined if c.isalpha()]
        if not alpha_chars:
            return 0.5

        block_counts: dict[str, int] = {}
        for ch in alpha_chars:
            block = self._unicode_block(ch)
            block_counts[block] = block_counts.get(block, 0) + 1

        dominant = max(block_counts.values())
        return min(1.0, dominant / len(alpha_chars) + 0.2)

    @staticmethod
    def _unicode_block(ch: str) -> str:
        cp = ord(ch)
        if cp < 0x0080:
            return "basic_latin"
        if cp < 0x0100:
            return "latin_supplement"
        if cp < 0x0250:
            return "latin_extended"
        if cp < 0x0400:
            return "ipa_extensions"
        if cp < 0x0500:
            return "cyrillic"
        if cp < 0x0600:
            return "armenian"
        if cp < 0x0700:
            return "arabic"
        if cp < 0x0E00:
            return "devanagari_thai"
        if cp < 0x3000:
            return "cjk_misc"
        if cp < 0x3100:
            return "cjk_symbols"
        if cp < 0xAC00:
            return "cjk_unified"
        if cp < 0xD800:
            return "hangul"
        return "other"
