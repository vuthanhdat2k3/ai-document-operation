"""Tests for query understanding: intent, language, entities, complexity."""

from __future__ import annotations

import pytest

from app.rag.query_understanding import (
    QueryAnalysis,
    QueryAnalyzer,
    QueryIntent,
    _assess_complexity,
    _classify_intent,
    _detect_language,
    _extract_entities,
)


class TestClassifyIntent:
    """Intent classification via _classify_intent."""

    def test_factual_what_is(self) -> None:
        assert _classify_intent("What is the penalty amount?") == QueryIntent.FACTUAL

    def test_factual_how_much(self) -> None:
        assert _classify_intent("How much is the contract value?") == QueryIntent.FACTUAL

    def test_factual_vietnamese_keywords(self) -> None:
        assert _classify_intent("Giá trị hợp đồng là bao nhiêu?") == QueryIntent.FACTUAL

    def test_factual_fallback_question_mark(self) -> None:
        assert _classify_intent("Random unknown text?") == QueryIntent.FACTUAL

    def test_summary_english(self) -> None:
        assert _classify_intent("Summarize the contract") == QueryIntent.SUMMARY

    def test_summary_vietnamese(self) -> None:
        assert _classify_intent("Tóm tắt hợp đồng") == QueryIntent.SUMMARY

    def test_summary_key_points(self) -> None:
        assert _classify_intent("What are the key points?") == QueryIntent.SUMMARY

    def test_comparison_english(self) -> None:
        assert _classify_intent("Compare contract A vs contract B") == QueryIntent.COMPARISON

    def test_comparison_vietnamese(self) -> None:
        assert _classify_intent("So sánh hai hợp đồng khác nhau") == QueryIntent.COMPARISON

    def test_extraction_english(self) -> None:
        assert _classify_intent("List all penalty clauses") == QueryIntent.EXTRACTION

    def test_extraction_vietnamese(self) -> None:
        assert _classify_intent("Trích xuất tất cả điều khoản") == QueryIntent.EXTRACTION

    def test_procedural_how_to(self) -> None:
        assert _classify_intent("How to submit the approval form?") == QueryIntent.PROCEDURAL

    def test_procedural_vietnamese(self) -> None:
        assert _classify_intent("Quy trình phê duyệt như thế nào?") == QueryIntent.PROCEDURAL

    def test_temporal_deadline(self) -> None:
        assert _classify_intent("Check deadline trước Q1 2024") == QueryIntent.TEMPORAL

    def test_temporal_vietnamese(self) -> None:
        assert _classify_intent("Thời hạn từ tháng 1 đến tháng 6 trước khi hết hạn") == QueryIntent.TEMPORAL

    def test_exploratory_risks(self) -> None:
        assert _classify_intent("What are the risks in this contract?") == QueryIntent.EXPLORATORY

    def test_exploratory_describe(self) -> None:
        assert _classify_intent("Describe the warranty terms") == QueryIntent.EXPLORATORY

    def test_exploratory_fallback_no_keywords_no_question(self) -> None:
        assert _classify_intent("contract penalty amount details") == QueryIntent.EXPLORATORY

    def test_higher_score_wins(self) -> None:
        query = "Compare the deadline and penalty clauses in the contract"
        intent = _classify_intent(query)
        assert intent in (QueryIntent.COMPARISON, QueryIntent.TEMPORAL)


class TestDetectLanguage:
    """Language detection via _detect_language."""

    def test_english(self) -> None:
        assert _detect_language("What is the contract value?") == "en"

    def test_vietnamese_diacritics_only(self) -> None:
        assert _detect_language("điều") == "vi"

    def test_vietnamese_domain_words(self) -> None:
        assert _detect_language("hợp đồng thanh toán bảo hiểm") == "mixed"

    def test_mixed_languages(self) -> None:
        assert _detect_language("Contract hợp đồng penalty thanh toán") == "mixed"

    def test_pure_ascii_no_domain_words(self) -> None:
        assert _detect_language("hello world test") == "en"

    def test_vietnamese_no_diacritics_but_domain(self) -> None:
        assert _detect_language("hop dong thanh toan") == "en"

    def test_mixed_english_domain_and_vietnamese(self) -> None:
        assert _detect_language("What is the giá trị hợp đồng?") == "mixed"


class TestExtractEntities:
    """Entity extraction via _extract_entities."""

    def test_section_reference(self) -> None:
        entities = _extract_entities("See Section 3.2 for details")
        assert any("Section 3.2" in e for e in entities)

    def test_vietnamese_section_reference(self) -> None:
        entities = _extract_entities("Xem điều 5.1 trong hợp đồng")
        assert any("điều 5.1" in e.lower() for e in entities)

    def test_date_pattern(self) -> None:
        entities = _extract_entities("The deadline is 15/06/2024")
        assert any("15/06/2024" in e for e in entities)

    def test_date_iso(self) -> None:
        entities = _extract_entities("Start date 2024-01-15 end date 2024-12-31")
        assert any("2024-01-15" in e for e in entities)
        assert any("2024-12-31" in e for e in entities)

    def test_number_pattern(self) -> None:
        entities = _extract_entities("The penalty is 5000000 VNĐ")
        assert any("5000000" in e for e in entities)

    def test_percentage(self) -> None:
        entities = _extract_entities("Tax rate is 10%")
        assert any("10" in e for e in entities)

    def test_person_org(self) -> None:
        entities = _extract_entities("Signed by Nguyen Van Company")
        assert any("Nguyen Van Company" in e for e in entities)

    def test_deduplication(self) -> None:
        entities = _extract_entities("Section 3.2 and Section 3.2 again")
        section_ents = [e for e in entities if "Section 3.2" in e]
        assert len(section_ents) == 1

    def test_empty_query(self) -> None:
        assert _extract_entities("") == []

    def test_no_entities(self) -> None:
        assert _extract_entities("just some plain text without anything") == []


class TestAssessComplexity:
    """Complexity assessment via _assess_complexity."""

    def test_simple_short_factual(self) -> None:
        assert _assess_complexity("What is the penalty?", QueryIntent.FACTUAL) == "simple"

    def test_moderate_summary(self) -> None:
        assert _assess_complexity("Summarize the contract", QueryIntent.SUMMARY) == "moderate"

    def test_moderate_extraction(self) -> None:
        assert _assess_complexity("Extract all clauses", QueryIntent.EXTRACTION) == "moderate"

    def test_moderate_procedural(self) -> None:
        assert _assess_complexity("What is the process?", QueryIntent.PROCEDURAL) == "moderate"

    def test_complex_comparison(self) -> None:
        assert _assess_complexity("Compare the two", QueryIntent.COMPARISON) == "complex"

    def test_complex_temporal(self) -> None:
        assert _assess_complexity("What deadlines", QueryIntent.TEMPORAL) == "complex"

    def test_complex_many_words(self) -> None:
        query = "What are all the penalty clauses and warranty terms defined in the contract agreement between the two parties involved in this project"
        assert _assess_complexity(query, QueryIntent.FACTUAL) == "complex"

    def test_complex_many_entities(self) -> None:
        query = "Section 3.2 dated 01/01/2024 value 5000000 VNĐ"
        assert _assess_complexity(query, QueryIntent.FACTUAL) == "complex"

    def test_moderate_two_entities(self) -> None:
        query = "section 5.1 details"
        assert _assess_complexity(query, QueryIntent.FACTUAL) == "moderate"

    def test_moderate_word_count(self) -> None:
        query = "What are the main penalty and warranty clauses in this agreement"
        assert _assess_complexity(query, QueryIntent.FACTUAL) == "moderate"


class TestQueryAnalyzer:
    """Full integration via QueryAnalyzer.analyze."""

    def test_returns_query_analysis(self) -> None:
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What is the contract value?")
        assert isinstance(result, QueryAnalysis)

    def test_empty_query(self) -> None:
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("")
        assert result.intent == QueryIntent.FACTUAL
        assert result.entities == []
        assert result.language == "en"
        assert result.complexity == "simple"

    def test_whitespace_only(self) -> None:
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("   ")
        assert result.intent == QueryIntent.FACTUAL

    def test_vietnamese_query(self) -> None:
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("Tóm tắt các điều khoản hợp đồng")
        assert result.intent == QueryIntent.SUMMARY
        assert result.language in ("vi", "mixed")

    def test_comparison_query(self) -> None:
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("Compare contract A vs contract B regarding penalty clauses")
        assert result.intent == QueryIntent.COMPARISON
        assert result.complexity == "complex"

    def test_entity_extraction_integrated(self) -> None:
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What is the value in Section 3.2 dated 15/06/2024?")
        assert any("Section 3.2" in e for e in result.entities)
        assert any("15/06/2024" in e for e in result.entities)

    def test_mixed_language_detection(self) -> None:
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What is the giá trị hợp đồng?")
        assert result.language == "mixed"

    def test_complexity_for_many_word_summary(self) -> None:
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("Summarize")
        assert result.intent == QueryIntent.SUMMARY
        assert result.complexity == "moderate"
