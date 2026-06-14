"""Tests for ReportGenerator — report content generation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from app.services.report_generator import (
    VALID_REPORT_TYPES,
    DocumentNotFoundError,
    InvalidReportTypeError,
    ReportGenerator,
)


def _make_document(
    *,
    filename: str = "test.pdf",
    mime_type: str = "application/pdf",
    status: str = "extraction_complete",
    doc_type: str = "contract",
    page_count: int = 5,
) -> MagicMock:
    doc = MagicMock()
    doc.id = uuid.uuid4()
    doc.original_filename = filename
    doc.mime_type = mime_type
    doc.status = status
    doc.document_type = doc_type
    doc.page_count = page_count
    doc.file_size_bytes = 1024 * 100
    doc.uploaded_at = datetime(2024, 1, 15, tzinfo=UTC)
    doc.processed_at = datetime(2024, 1, 16, tzinfo=UTC)
    doc.deleted_at = None
    return doc


def _make_extracted_field(
    name: str = "total_amount",
    value: dict | None = None,
    confidence: float = 0.9,
    is_verified: bool = False,
) -> MagicMock:
    f = MagicMock()
    f.field_name = name
    f.field_value = value or {"value": 50000000}
    f.raw_text = "50,000,000 VND"
    f.confidence = confidence
    f.page_number = 1
    f.is_verified = is_verified
    return f


def _make_risk_item(
    title: str = "High-value amount",
    severity: str = "high",
    category: str = "financial",
    status: str = "open",
) -> MagicMock:
    r = MagicMock()
    r.id = uuid.uuid4()
    r.title = title
    r.severity = severity
    r.category = category
    r.description = f"Description of {title}"
    r.evidence = {"amount": 50000000}
    r.page_number = 1
    r.status = status
    r.resolution = None
    r.detected_by = "rule_engine"
    return r


@pytest.fixture()
def generator() -> ReportGenerator:
    return ReportGenerator()


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


class TestReportTypeValidation:
    """Test report type validation."""

    def test_valid_types(self) -> None:
        assert "summary" in VALID_REPORT_TYPES
        assert "detailed" in VALID_REPORT_TYPES
        assert "risk_assessment" in VALID_REPORT_TYPES

    @pytest.mark.asyncio
    async def test_invalid_report_type_raises(self, generator: ReportGenerator, mock_db: AsyncMock) -> None:
        with pytest.raises(InvalidReportTypeError, match="Unsupported report type"):
            await generator.generate("some-id", "invalid_type", uuid.uuid4(), mock_db)


class TestReportTitle:
    """Test report title generation."""

    def test_summary_title(self, generator: ReportGenerator) -> None:
        doc = _make_document(filename="contract.pdf")
        title = generator._build_title(doc, "summary")
        assert "Summary Report" in title
        assert "contract.pdf" in title

    def test_detailed_title(self, generator: ReportGenerator) -> None:
        doc = _make_document(filename="invoice.pdf")
        title = generator._build_title(doc, "detailed")
        assert "Detailed Analysis Report" in title

    def test_risk_assessment_title(self, generator: ReportGenerator) -> None:
        doc = _make_document(filename="report.pdf")
        title = generator._build_title(doc, "risk_assessment")
        assert "Risk Assessment Report" in title

    def test_unknown_type_default_label(self, generator: ReportGenerator) -> None:
        doc = _make_document()
        title = generator._build_title(doc, "custom")
        assert "Report" in title


class TestKeyFindings:
    """Test key findings generation."""

    def test_findings_with_extracted_fields(self, generator: ReportGenerator) -> None:
        fields = [
            _make_extracted_field(is_verified=True, confidence=0.95),
            _make_extracted_field(name="date", confidence=0.3, is_verified=False),
        ]
        findings = generator._build_key_findings(fields, [])
        assert any("2 fields extracted" in f for f in findings)
        assert any("1 verified" in f for f in findings)

    def test_findings_no_fields(self, generator: ReportGenerator) -> None:
        findings = generator._build_key_findings([], [])
        assert any("No fields" in f for f in findings)

    def test_findings_with_risks(self, generator: ReportGenerator) -> None:
        risks = [
            _make_risk_item(severity="critical"),
            _make_risk_item(severity="high"),
        ]
        findings = generator._build_key_findings([], risks)
        assert any("2 risk" in f for f in findings)
        assert any("CRITICAL" in f for f in findings)

    def test_findings_no_risks(self, generator: ReportGenerator) -> None:
        findings = generator._build_key_findings([], [])
        assert any("No risks" in f for f in findings)


class TestChecklist:
    """Test report checklist generation."""

    def test_checklist_document_uploaded(self, generator: ReportGenerator) -> None:
        doc = _make_document()
        checklist = generator._build_checklist(doc, [], [])
        upload_item = next(item for item in checklist if item["item"] == "Document uploaded")
        assert upload_item["status"] == "pass"

    def test_checklist_document_processed(self, generator: ReportGenerator) -> None:
        doc = _make_document(status="extraction_complete")
        checklist = generator._build_checklist(doc, [], [])
        proc_item = next(item for item in checklist if item["item"] == "Document processed")
        assert proc_item["status"] == "pass"

    def test_checklist_document_not_processed(self, generator: ReportGenerator) -> None:
        doc = _make_document(status="uploaded")
        checklist = generator._build_checklist(doc, [], [])
        proc_item = next(item for item in checklist if item["item"] == "Document processed")
        assert proc_item["status"] == "pending"

    def test_checklist_fields_extracted(self, generator: ReportGenerator) -> None:
        doc = _make_document()
        fields = [_make_extracted_field()]
        checklist = generator._build_checklist(doc, fields, [])
        item = next(i for i in checklist if i["item"] == "Fields extracted")
        assert item["status"] == "pass"

    def test_checklist_no_fields_extracted(self, generator: ReportGenerator) -> None:
        doc = _make_document()
        checklist = generator._build_checklist(doc, [], [])
        item = next(i for i in checklist if i["item"] == "Fields extracted")
        assert item["status"] == "fail"

    def test_checklist_all_verified(self, generator: ReportGenerator) -> None:
        doc = _make_document()
        fields = [_make_extracted_field(is_verified=True)]
        checklist = generator._build_checklist(doc, fields, [])
        item = next(i for i in checklist if i["item"] == "All fields verified")
        assert item["status"] == "pass"

    def test_checklist_some_unverified(self, generator: ReportGenerator) -> None:
        doc = _make_document()
        fields = [_make_extracted_field(is_verified=False)]
        checklist = generator._build_checklist(doc, fields, [])
        item = next(i for i in checklist if i["item"] == "All fields verified")
        assert item["status"] == "warning"

    def test_checklist_critical_risks_fail(self, generator: ReportGenerator) -> None:
        doc = _make_document()
        risks = [_make_risk_item(severity="critical", status="open")]
        checklist = generator._build_checklist(doc, [], risks)
        item = next(i for i in checklist if "risks resolved" in i["item"])
        assert item["status"] == "fail"

    def test_checklist_no_critical_risks_pass(self, generator: ReportGenerator) -> None:
        doc = _make_document()
        risks = [_make_risk_item(severity="low", status="resolved")]
        checklist = generator._build_checklist(doc, [], risks)
        item = next(i for i in checklist if "risks resolved" in i["item"])
        assert item["status"] == "pass"

    def test_checklist_low_confidence_warning(self, generator: ReportGenerator) -> None:
        doc = _make_document()
        fields = [_make_extracted_field(confidence=0.3)]
        checklist = generator._build_checklist(doc, fields, [])
        item = next(i for i in checklist if "low-confidence" in i["item"])
        assert item["status"] == "warning"


class TestRecommendations:
    """Test recommendation generation."""

    def test_recommendation_unverified_fields(self, generator: ReportGenerator) -> None:
        fields = [_make_extracted_field(is_verified=False)]
        recs = generator._build_recommendations([], fields)
        assert any("verify" in r.lower() and "1" in r for r in recs)

    def test_recommendation_low_confidence_fields(self, generator: ReportGenerator) -> None:
        fields = [_make_extracted_field(confidence=0.3)]
        recs = generator._build_recommendations([], fields)
        assert any("low-confidence" in r.lower() for r in recs)

    def test_recommendation_critical_risks(self, generator: ReportGenerator) -> None:
        risks = [_make_risk_item(severity="critical", status="open")]
        recs = generator._build_recommendations(risks, [])
        assert any("critical" in r.lower() for r in recs)

    def test_recommendation_no_issues(self, generator: ReportGenerator) -> None:
        fields = [_make_extracted_field(is_verified=True, confidence=0.95)]
        recs = generator._build_recommendations([], fields)
        assert any("no immediate action" in r.lower() for r in recs)

    def test_recommendation_no_fields(self, generator: ReportGenerator) -> None:
        recs = generator._build_recommendations([], [])
        assert any("No fields extracted" in r for r in recs)


class TestContentBuilding:
    """Test full content building."""

    def test_summary_type_trims_fields(self, generator: ReportGenerator) -> None:
        doc = _make_document()
        fields = [_make_extracted_field()]
        risks = [_make_risk_item()]
        content = generator._build_content(
            document=doc, extracted_fields=fields, risk_items=risks, report_type="summary"
        )
        # In summary mode, extracted_fields should have fewer keys
        for f in content["extracted_fields"]:
            assert "field_name" in f
            assert "field_value" in f
            assert "confidence" in f
            assert "raw_text" not in f  # trimmed in summary

    def test_risk_assessment_emphasizes_risks(self, generator: ReportGenerator) -> None:
        doc = _make_document()
        risks = [_make_risk_item(severity="critical"), _make_risk_item(severity="high")]
        content = generator._build_content(
            document=doc, extracted_fields=[], risk_items=risks, report_type="risk_assessment"
        )
        assert "risk_summary" in content
        assert content["risk_summary"]["total"] == 2
        assert content["risk_summary"]["critical"] == 1

    def test_detailed_type_full_content(self, generator: ReportGenerator) -> None:
        doc = _make_document()
        content = generator._build_content(
            document=doc, extracted_fields=[], risk_items=[], report_type="detailed"
        )
        assert "overview" in content
        assert "key_findings" in content
        assert "extracted_fields" in content
        assert "risks" in content
        assert "checklist" in content
        assert "recommendations" in content
        assert "risk_summary" not in content  # Only for risk_assessment

    def test_content_has_document_info(self, generator: ReportGenerator) -> None:
        doc = _make_document(filename="test.pdf", doc_type="contract")
        content = generator._build_content(
            document=doc, extracted_fields=[], risk_items=[], report_type="summary"
        )
        assert content["document"]["filename"] == "test.pdf"
        assert content["document"]["document_type"] == "contract"
