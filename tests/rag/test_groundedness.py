"""Tests for groundedness validation: claims, evidence, scoring."""

from __future__ import annotations

import pytest

from app.rag.groundedness import (
    GroundednessResult,
    GroundednessValidator,
    _extract_keywords,
    _split_claims,
)


class TestSplitClaims:
    """Claim extraction from answer text."""

    def test_single_sentence(self) -> None:
        claims = _split_claims("This is a single claim about the contract.")
        assert len(claims) == 1

    def test_multiple_sentences(self) -> None:
        answer = "The penalty is $500. The deadline is March 2024. The warranty covers defects."
        claims = _split_claims(answer)
        assert len(claims) == 3

    def test_source_tags_removed(self) -> None:
        answer = "The penalty is $500. [source:1] The deadline is March 2024."
        claims = _split_claims(answer)
        for claim in claims:
            assert "[source:" not in claim

    def test_short_fragments_filtered(self) -> None:
        answer = "Yes. The penalty is five hundred dollars according to section 3.2."
        claims = _split_claims(answer)
        assert all(len(c) > 15 for c in claims)

    def test_very_short_answer_returns_original(self) -> None:
        answer = "No info"
        claims = _split_claims(answer)
        assert len(claims) == 1
        assert claims[0] == "No info"

    def test_empty_answer(self) -> None:
        claims = _split_claims("")
        assert len(claims) == 1

    def test_vietnamese_sentences(self) -> None:
        answer = "Phạt vi phạm là 500 triệu. Thời hạn bảo hành là 12 tháng."
        claims = _split_claims(answer)
        assert len(claims) >= 2

    def test_newline_split(self) -> None:
        answer = "First claim about the contract terms here.\nSecond claim about penalties here."
        claims = _split_claims(answer)
        assert len(claims) >= 2


class TestExtractKeywords:
    """Keyword extraction from text."""

    def test_basic_keywords(self) -> None:
        kw = _extract_keywords("The contract penalty amount")
        assert "contract" in kw
        assert "penalty" in kw
        assert "amount" in kw

    def test_stopwords_excluded(self) -> None:
        kw = _extract_keywords("the and for are but not")
        assert len(kw) == 0

    def test_short_tokens_excluded(self) -> None:
        kw = _extract_keywords("I am ok")
        assert len(kw) == 0  # all tokens < 3 chars

    def test_case_insensitive(self) -> None:
        kw = _extract_keywords("CONTRACT Contract contract")
        assert "contract" in kw
        assert len([k for k in kw if k == "contract"]) == 1

    def test_vietnamese_stopwords(self) -> None:
        kw = _extract_keywords("trong của và là cho các được")
        assert len(kw) == 0

    def test_empty_text(self) -> None:
        assert _extract_keywords("") == set()

    def test_mixed_content(self) -> None:
        kw = _extract_keywords("The penalty clause in hợp đồng")
        assert "penalty" in kw
        assert "clause" in kw
        assert "hợp" in kw or "đồng" in kw


class TestGroundednessResult:
    """GroundednessResult dataclass."""

    def test_defaults(self) -> None:
        r = GroundednessResult()
        assert r.score == 0.0
        assert r.claims == []
        assert r.supported_claims == []
        assert r.unsupported_claims == []


class TestGroundednessValidator:
    """GroundednessValidator.validate tests."""

    def test_fully_grounded_answer(self) -> None:
        validator = GroundednessValidator(support_threshold=0.3)
        answer = "The contract penalty is five hundred dollars for late delivery."
        sources = [
            "The contract specifies a penalty of five hundred dollars for late delivery of goods.",
        ]
        result = validator.validate(answer, sources)
        assert result.score == 1.0
        assert len(result.unsupported_claims) == 0

    def test_fully_ungrounded_answer(self) -> None:
        validator = GroundednessValidator(support_threshold=0.3)
        answer = "The aliens arrived on purple elephants wearing monocles."
        sources = [
            "The contract covers construction project timelines and budgets.",
        ]
        result = validator.validate(answer, sources)
        assert result.score == 0.0
        assert len(result.supported_claims) == 0

    def test_partially_grounded_answer(self) -> None:
        validator = GroundednessValidator(support_threshold=0.3)
        answer = (
            "The contract penalty is five hundred dollars. "
            "The aliens arrived on purple elephants wearing monocles."
        )
        sources = [
            "The contract specifies a penalty of five hundred dollars for late delivery.",
        ]
        result = validator.validate(answer, sources)
        assert 0.0 < result.score < 1.0
        assert len(result.supported_claims) >= 1
        assert len(result.unsupported_claims) >= 1

    def test_empty_answer(self) -> None:
        validator = GroundednessValidator()
        result = validator.validate("", ["some source"])
        assert result.score == 0.0

    def test_empty_sources(self) -> None:
        validator = GroundednessValidator()
        answer = "This is a claim about contract penalty and warranty."
        result = validator.validate(answer, [])
        assert result.score == 0.0
        assert len(result.unsupported_claims) >= 1

    def test_multiple_sources_combined(self) -> None:
        validator = GroundednessValidator(support_threshold=0.3)
        answer = "The penalty is five hundred. The warranty covers defects."
        sources = [
            "The penalty clause specifies five hundred dollars.",
            "The warranty covers manufacturing defects for two years.",
        ]
        result = validator.validate(answer, sources)
        assert result.score == 1.0

    def test_custom_threshold(self) -> None:
        strict = GroundednessValidator(support_threshold=0.8)
        lenient = GroundednessValidator(support_threshold=0.1)
        answer = "The contract penalty and warranty clause for defects."
        sources = ["The penalty clause is specified in the agreement."]
        strict_result = strict.validate(answer, sources)
        lenient_result = lenient.validate(answer, sources)
        assert lenient_result.score >= strict_result.score

    def test_source_tags_in_answer_removed(self) -> None:
        validator = GroundednessValidator(support_threshold=0.3)
        answer = "The penalty is five hundred dollars. [source:1] [source:2]"
        sources = ["The penalty is five hundred dollars for breach."]
        result = validator.validate(answer, sources)
        assert result.score > 0

    def test_score_is_rounded(self) -> None:
        validator = GroundednessValidator(support_threshold=0.3)
        answer = "First claim about penalty clause. Second claim about warranty defects."
        sources = [
            "The penalty clause is important. The warranty covers defects.",
        ]
        result = validator.validate(answer, sources)
        assert result.score == round(result.score, 3)

    def test_claims_list_populated(self) -> None:
        validator = GroundednessValidator()
        answer = "The penalty clause is defined in section 3.2 of the agreement."
        sources = ["The penalty clause in section 3.2 defines the fine."]
        result = validator.validate(answer, sources)
        assert len(result.claims) >= 1

    def test_vietnamese_answer(self) -> None:
        validator = GroundednessValidator(support_threshold=0.2)
        answer = "Phạt vi phạm hợp đồng là 500 triệu đồng."
        sources = ["Hợp đồng quy định phạt vi phạm là 500 triệu đồng."]
        result = validator.validate(answer, sources)
        assert result.score > 0.5
