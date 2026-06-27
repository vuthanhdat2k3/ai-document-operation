"""Query understanding: intent classification, entity extraction, language detection."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)

_VIETNAMESE_DIACRITICALS = re.compile(r"[ăâêôơưđ]", re.IGNORECASE)
_VIETNAMESE_WORDS = re.compile(
    r"\b(?:hợp\s*đồng|dự\s*án|thanh\s*toán|tiến\s*độ|bảo\s*hiểm|"
    r"phạt|vi\s*phạm|bồi\s*thường|điều\s*khoản|phụ\s*lục|"
    r"chủ\s*đầu\s*tư|nhà\s*thầu|giám\s*sát|nghiệm\s*thu|"
    r"người|công\s*ty|tổ\s*chức|cơ\s*quan|bộ\s*phận)\b",
    re.IGNORECASE,
)
_ENGLISH_WORDS = re.compile(
    r"\b(?:contract|project|payment|schedule|penalty|clause|"
    r"amendment|appendix|contractor|client|supervision|"
    r"approval|budget|milestone|deliverable|warranty)\b",
    re.IGNORECASE,
)

_SECTION_REF = re.compile(r"(?:section|điều|mục|phần|appendix|phụ\s*lục)\s+[\dA-Za-z]+(?:\.[\dA-Za-z]+)*", re.IGNORECASE)
_DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
    r"(?:Q[1-4])\s*\d{4}|"
    r"(?:tháng|month)\s*\d{1,2}(?:\s*(?:năm|year)\s*\d{4})?|"
    r"\d{1,2}\s*(?:tháng|month)\s*\d{4})\b",
    re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)*(?:\s*(?:%|VNĐ|VND|USD|triệu|tỷ|nghìn))?\b", re.IGNORECASE)
_PERSON_ORG = re.compile(
    r"\b(?:[A-Z][a-zà-ỹ]+\s+){1,3}(?:Company|Corp|Ltd|JSC|Inc|"
    r"Công\s*ty|Tổng\s*công\s*ty|Chi\s*nhánh)\b",
    re.UNICODE,
)


class QueryIntent(StrEnum):
    """Classified intent of a user query."""

    FACTUAL = "factual"
    SUMMARY = "summary"
    COMPARISON = "comparison"
    EXTRACTION = "extraction"
    PROCEDURAL = "procedural"
    TEMPORAL = "temporal"
    EXPLORATORY = "exploratory"
    GENERAL_CHAT = "general_chat"


@dataclass
class QueryAnalysis:
    """Result of analysing a user query.

    Attributes:
        intent: The classified intent of the query.
        entities: Extracted entities (names, dates, amounts, etc.).
        language: Detected language code (``"vi"``, ``"en"``, ``"mixed"``).
        complexity: Complexity level (``"simple"``, ``"moderate"``, ``"complex"``).
    """

    intent: QueryIntent
    entities: list[str] = field(default_factory=list)
    language: str = "en"
    complexity: str = "simple"


_GENERAL_CHAT_PATTERNS = [
    re.compile(r"\b(?:hello|hi|hey|greetings|chào|xin\s*chào|alo)\b", re.I),
    re.compile(r"\b(?:thank|thanks|cảm\s*ơn|cám\s*ơn)\b", re.I),
    re.compile(r"\b(?:how\s+are\s+you|bạn\s*(?:khỏe|thế\s*nào|sao))\b", re.I),
    re.compile(r"\b(?:what's?\s+up|giúp|help|hỗ\s*trợ)\b", re.I),
    re.compile(r"\b(?:who\s+(?:are|created|made)\s+you|ai\s*(?:tạo|đã|xây\s*dựng))\b", re.I),
    re.compile(r"\b(?:what\s+(?:are|can)\s+you\s+do|bạn\s*(?:có\s*thể|làm\s*được)\s*gì)\b", re.I),
    re.compile(r"\b(?:bye|goodbye|tạm\s*biệt|hẹn\s*gặp)\b", re.I),
    re.compile(r"\byou\s+(?:are|were)\s+(?:a\s+great|helpful|useful|awesome)\b", re.I),
    re.compile(r"^chào$|^hello$|^hi$|^hey$|^test$|^testing$", re.I),
]

_INTENT_KEYWORDS: dict[QueryIntent, list[re.Pattern[str]]] = {
    QueryIntent.GENERAL_CHAT: _GENERAL_CHAT_PATTERNS,
    QueryIntent.FACTUAL: [
        re.compile(r"\b(?:what\s+is|who\s+is|when\s+is|where\s+is|how\s+much|how\s+many|giá\s*trị|bao\s*nhieu|ai|ở\s*đâu|khi\s*nào)\b", re.I),
        re.compile(r"\b(?:số\s*tiền|ngày\s*tháng|thời\s*hạn|hiệu\s*lực)\b", re.I),
    ],
    QueryIntent.SUMMARY: [
        re.compile(r"\b(?:summar[yi]ze|overview|tóm\s*tắt|tổng\s*quan|概述)\b", re.I),
        re.compile(r"\b(?:main\s*points?|key\s*points?|điểm\s*chính)\b", re.I),
    ],
    QueryIntent.COMPARISON: [
        re.compile(r"\b(?:compar[eio]|vs\.?|versus|khác\s*nhau|so\s*sánh|đối\s*chiếu)\b", re.I),
        re.compile(r"\b(?:differen(?:ce|t)|similar|giống|khác)\b", re.I),
    ],
    QueryIntent.EXTRACTION: [
        re.compile(r"\b(?:list|extract|all|find\s+all|trích\s*xuất|liệt\s*kê|tất\s*cả)\b", re.I),
        re.compile(r"\b(?:every\s+each|mỗi)\b", re.I),
    ],
    QueryIntent.PROCEDURAL: [
        re.compile(r"\b(?:how\s+to|process|procedure|steps?|quy\s*trình|các\s*bước|thủ\s*tục)\b", re.I),
        re.compile(r"\b(?:workflow|approval|phê\s*duyệt)\b", re.I),
    ],
    QueryIntent.TEMPORAL: [
        re.compile(r"\b(?:deadline|due\s*date|before|after|between|thời\s*hạn|trước|sau|từ.*đến)\b", re.I),
        re.compile(r"\b(?:Q[1-4]\s*\d{4}|tháng\s*\d+)\b", re.I),
    ],
    QueryIntent.EXPLORATORY: [
        re.compile(r"\b(?:what\s+are\s+the\s+(?:risks?|issues?|concerns?)|risks?|những\s*(?:rủi\s*ro|vấn\s*đề))\b", re.I),
        re.compile(r"\b(?:tell\s+me\s+about|describe|explain|giải\s*thích|mô\s*tả)\b", re.I),
    ],
}


def _classify_intent(query: str) -> QueryIntent:
    """Rule-based intent classification using keyword patterns.

    Returns ``GENERAL_CHAT`` for greetings, thanks, small talk, etc.
    Falls back to document-related intents for queries about documents.
    """
    # Fast-path: pure conversational queries
    if _GENERAL_CHAT_PATTERNS[0].search(query) or _GENERAL_CHAT_PATTERNS[-1].search(query):
        return QueryIntent.GENERAL_CHAT

    scores: dict[QueryIntent, int] = {}
    for intent, patterns in _INTENT_KEYWORDS.items():
        count = sum(1 for p in patterns if p.search(query))
        if count:
            scores[intent] = count

    if not scores:
        if "?" in query and not any(
            p.search(query) for p in _GENERAL_CHAT_PATTERNS
        ):
            return QueryIntent.FACTUAL
        return QueryIntent.EXPLORATORY

    return max(scores, key=scores.get)  # type: ignore[arg-type]


def _extract_entities(query: str) -> list[str]:
    """Extract named entities, dates, amounts, and section references."""
    entities: list[str] = []

    for m in _SECTION_REF.finditer(query):
        entities.append(m.group().strip())

    for m in _DATE_PATTERN.finditer(query):
        entities.append(m.group().strip())

    for m in _NUMBER_PATTERN.finditer(query):
        entities.append(m.group().strip())

    for m in _PERSON_ORG.finditer(query):
        entities.append(m.group().strip())

    deduped: list[str] = []
    seen: set[str] = set()
    for e in entities:
        key = e.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    return deduped


def _detect_language(query: str) -> str:
    """Detect query language: ``'vi'``, ``'en'``, or ``'mixed'``."""
    has_vi_diacritics = bool(_VIETNAMESE_DIACRITICALS.search(query))
    has_vi_words = bool(_VIETNAMESE_WORDS.search(query))
    has_en_words = bool(_ENGLISH_WORDS.search(query))

    is_vietnamese = has_vi_diacritics or has_vi_words
    is_english = has_en_words or bool(re.search(r"[a-zA-Z]{3,}", query))

    if is_vietnamese and is_english:
        return "mixed"
    if is_vietnamese:
        return "vi"
    return "en"


def _assess_complexity(query: str, intent: QueryIntent) -> str:
    """Assess query complexity: ``'simple'``, ``'moderate'``, or ``'complex'``."""
    word_count = len(query.split())
    entity_count = len(_extract_entities(query))

    if intent in (QueryIntent.COMPARISON, QueryIntent.TEMPORAL):
        return "complex"

    if word_count > 20 or entity_count >= 3:
        return "complex"
    if word_count > 10 or entity_count >= 2 or intent in (
        QueryIntent.SUMMARY,
        QueryIntent.EXTRACTION,
        QueryIntent.PROCEDURAL,
    ):
        return "moderate"
    return "simple"


class QueryAnalyzer:
    """Analyse a user query to extract intent, entities, language, and complexity.

    Usage::

        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What are the penalty clauses in the contract?")
        print(result.intent)       # QueryIntent.FACTUAL
        print(result.complexity)   # "simple"
    """

    def analyze(self, query: str) -> QueryAnalysis:
        """Analyse the given query string.

        Args:
            query: Raw user query text.

        Returns:
            A ``QueryAnalysis`` with classified intent, extracted entities,
            detected language, and assessed complexity.
        """
        query = query.strip()
        if not query:
            return QueryAnalysis(
                intent=QueryIntent.FACTUAL,
                entities=[],
                language="en",
                complexity="simple",
            )

        intent = _classify_intent(query)
        entities = _extract_entities(query)
        language = _detect_language(query)
        complexity = _assess_complexity(query, intent)

        logger.debug(
            "Query analysis — intent=%s, lang=%s, complexity=%s, entities=%s",
            intent,
            language,
            complexity,
            entities,
        )

        return QueryAnalysis(
            intent=intent,
            entities=entities,
            language=language,
            complexity=complexity,
        )
