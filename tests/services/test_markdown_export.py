"""Tests for MarkdownExporter — Markdown report rendering."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.services.markdown_export import MarkdownExporter


@pytest.fixture()
def exporter() -> MarkdownExporter:
    return MarkdownExporter()


def _make_report(
    *,
    title: str = "Test Report — contract.pdf",
    report_type: str = "detailed",
    content: dict | None = None,
) -> MagicMock:
    report = MagicMock()
    report.id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    report.title = title
    report.report_type = report_type
    report.document_id = uuid.UUID("87654321-4321-8765-4321-876543218765")
    report.generated_at = datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC)
    report.content = content or _default_content(report_type)
    return report


def _default_content(report_type: str = "detailed") -> dict:
    return {
        "report_type": report_type,
        "generated_at": "2024-06-15T10:30:00+00:00",
        "document": {
            "id": "87654321-4321-8765-4321-876543218765",
            "filename": "contract.pdf",
            "mime_type": "application/pdf",
            "status": "extraction_complete",
            "page_count": 5,
            "document_type": "contract",
        },
        "overview": {
            "filename": "contract.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": 102400,
            "page_count": 5,
            "document_type": "contract",
            "status": "extraction_complete",
            "uploaded_at": "2024-01-15T00:00:00+00:00",
            "processed_at": "2024-01-16T00:00:00+00:00",
        },
        "key_findings": [
            "5 fields extracted, 2 verified, 3 high-confidence.",
            "No risks identified.",
        ],
        "extracted_fields": [
            {
                "field_name": "contract_number",
                "field_value": {"value": "HD-2024-001"},
                "raw_text": "Số: HD-2024-001",
                "confidence": 0.95,
                "page_number": 1,
                "is_verified": True,
            },
            {
                "field_name": "total_amount",
                "field_value": {"value": 50000000, "currency": "VND"},
                "raw_text": "50,000,000 VND",
                "confidence": 0.85,
                "page_number": 2,
                "is_verified": False,
            },
        ],
        "risks": [
            {
                "id": str(uuid.uuid4()),
                "category": "financial",
                "severity": "high",
                "title": "High-value amount",
                "description": "Amount exceeds threshold.",
                "evidence": {"amount": 50000000},
                "page_number": 1,
                "status": "open",
                "resolution": None,
                "detected_by": "rule_engine",
            },
        ],
        "checklist": [
            {"item": "Document uploaded", "status": "pass"},
            {"item": "Document processed", "status": "pass"},
            {"item": "Fields extracted", "status": "pass"},
            {"item": "All fields verified", "status": "warning"},
            {"item": "Critical/high risks resolved", "status": "fail"},
        ],
        "recommendations": [
            "Review and verify 1 extracted field(s).",
            "Address 1 critical/high severity risk(s).",
        ],
    }


class TestTitleRendering:
    """Test title section rendering."""

    def test_title_present(self, exporter: MarkdownExporter) -> None:
        report = _make_report(title="My Report")
        md = exporter.export(report)
        assert md.startswith("# My Report")

    def test_title_with_special_chars(self, exporter: MarkdownExporter) -> None:
        report = _make_report(title="Report — file.pdf")
        md = exporter.export(report)
        assert "# Report — file.pdf" in md


class TestMetadataRendering:
    """Test metadata table rendering."""

    def test_metadata_table_has_report_id(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "Report ID" in md
        assert "12345678" in md

    def test_metadata_has_report_type(self, exporter: MarkdownExporter) -> None:
        report = _make_report(report_type="summary")
        md = exporter.export(report)
        assert "Report Type" in md

    def test_metadata_has_generated_at(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "Generated At" in md
        assert "2024-06-15" in md

    def test_metadata_has_document_id(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "Document ID" in md


class TestOverviewRendering:
    """Test overview section rendering."""

    def test_overview_section_present(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "## Overview" in md

    def test_overview_has_filename(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "contract.pdf" in md

    def test_overview_has_file_size(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "KB" in md

    def test_overview_empty_skipped(self, exporter: MarkdownExporter) -> None:
        """Empty overview dict is falsy, but `content or _default_content()` in
        _make_report falls through to default when content={}. Use a truthy
        content with explicit empty overview."""
        content = _default_content()
        content["overview"] = {}
        report = _make_report(content=content)
        md = exporter.export(report)
        assert "## Overview" not in md


class TestRiskSummaryRendering:
    """Test risk summary section for risk_assessment reports."""

    def test_risk_summary_present_for_risk_assessment(self, exporter: MarkdownExporter) -> None:
        content = _default_content("risk_assessment")
        content["risk_summary"] = {
            "total": 3, "critical": 1, "high": 1, "medium": 1, "low": 0, "info": 0,
            "open": 2, "resolved": 1,
        }
        report = _make_report(report_type="risk_assessment", content=content)
        md = exporter.export(report)
        assert "## Risk Summary" in md
        assert "Total risks:** 3" in md

    def test_risk_summary_not_present_for_detailed(self, exporter: MarkdownExporter) -> None:
        report = _make_report(report_type="detailed")
        md = exporter.export(report)
        assert "## Risk Summary" not in md


class TestKeyFindingsRendering:
    """Test key findings section rendering."""

    def test_findings_list(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "## Key Findings" in md
        assert "- 5 fields extracted" in md

    def test_empty_findings_skipped(self, exporter: MarkdownExporter) -> None:
        content = _default_content()
        content["key_findings"] = []
        report = _make_report(content=content)
        md = exporter.export(report)
        assert "## Key Findings" not in md


class TestExtractedFieldsRendering:
    """Test extracted fields table rendering."""

    def test_fields_table_present(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "## Extracted Fields" in md
        assert "contract_number" in md

    def test_fields_table_has_confidence(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "95.0%" in md

    def test_fields_verified_icon(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        # Verified field should have checkmark
        assert "✅" in md or "❌" in md

    def test_empty_fields_skipped(self, exporter: MarkdownExporter) -> None:
        content = _default_content()
        content["extracted_fields"] = []
        report = _make_report(content=content)
        md = exporter.export(report)
        assert "## Extracted Fields" not in md

    def test_fields_without_raw_text_table(self, exporter: MarkdownExporter) -> None:
        content = _default_content()
        content["extracted_fields"] = [
            {"field_name": "name", "field_value": {"value": "Test"}, "confidence": 0.9}
        ]
        report = _make_report(content=content)
        md = exporter.export(report)
        assert "| Field | Value | Confidence |" in md


class TestRisksRendering:
    """Test risks section rendering."""

    def test_risks_section_present(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "## Risks" in md
        assert "[HIGH] High-value amount" in md

    def test_risks_sorted_by_severity(self, exporter: MarkdownExporter) -> None:
        content = _default_content()
        content["risks"] = [
            {"severity": "low", "title": "Low risk", "category": "test", "status": "open", "description": "desc"},
            {"severity": "critical", "title": "Critical risk", "category": "test", "status": "open", "description": "desc"},
        ]
        report = _make_report(content=content)
        md = exporter.export(report)
        critical_pos = md.find("[CRITICAL]")
        low_pos = md.find("[LOW]")
        assert critical_pos < low_pos

    def test_risk_has_evidence(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "Evidence" in md

    def test_empty_risks_skipped(self, exporter: MarkdownExporter) -> None:
        content = _default_content()
        content["risks"] = []
        report = _make_report(content=content)
        md = exporter.export(report)
        assert "## Risks" not in md


class TestChecklistRendering:
    """Test compliance checklist rendering."""

    def test_checklist_section_present(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "## Compliance Checklist" in md

    def test_checklist_status_icons(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "✅" in md  # pass
        assert "❌" in md or "⚠️" in md  # fail or warning

    def test_empty_checklist_skipped(self, exporter: MarkdownExporter) -> None:
        content = _default_content()
        content["checklist"] = []
        report = _make_report(content=content)
        md = exporter.export(report)
        assert "## Compliance Checklist" not in md


class TestRecommendationsRendering:
    """Test recommendations section rendering."""

    def test_recommendations_numbered(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "## Recommendations" in md
        assert "1. Review" in md

    def test_empty_recommendations_skipped(self, exporter: MarkdownExporter) -> None:
        content = _default_content()
        content["recommendations"] = []
        report = _make_report(content=content)
        md = exporter.export(report)
        assert "## Recommendations" not in md


class TestFooterRendering:
    """Test footer rendering."""

    def test_footer_present(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "---" in md
        assert "AI Document Operations Agent" in md

    def test_footer_has_date(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "2024-06-15" in md


class TestHelperMethods:
    """Test helper/utility methods."""

    def test_format_field_value_none(self, exporter: MarkdownExporter) -> None:
        assert MarkdownExporter._format_field_value(None) == "-"

    def test_format_field_value_dict(self, exporter: MarkdownExporter) -> None:
        result = MarkdownExporter._format_field_value({"value": 42, "currency": "VND"})
        assert "value: 42" in result
        assert "currency: VND" in result

    def test_format_field_value_list(self, exporter: MarkdownExporter) -> None:
        result = MarkdownExporter._format_field_value(["a", "b", "c"])
        assert result == "a, b, c"

    def test_format_field_value_string(self, exporter: MarkdownExporter) -> None:
        assert MarkdownExporter._format_field_value("hello") == "hello"

    def test_format_confidence_high(self, exporter: MarkdownExporter) -> None:
        result = MarkdownExporter._format_confidence(0.95)
        assert "95.0%" in result
        assert "🟢" in result

    def test_format_confidence_medium(self, exporter: MarkdownExporter) -> None:
        result = MarkdownExporter._format_confidence(0.65)
        assert "65.0%" in result
        assert "🟡" in result

    def test_format_confidence_low(self, exporter: MarkdownExporter) -> None:
        result = MarkdownExporter._format_confidence(0.3)
        assert "30.0%" in result
        assert "🔴" in result

    def test_format_confidence_none(self, exporter: MarkdownExporter) -> None:
        assert MarkdownExporter._format_confidence(None) == "N/A"

    def test_format_file_size_bytes(self, exporter: MarkdownExporter) -> None:
        assert MarkdownExporter._format_file_size(500) == "500 B"

    def test_format_file_size_kb(self, exporter: MarkdownExporter) -> None:
        result = MarkdownExporter._format_file_size(5120)
        assert "KB" in result

    def test_format_file_size_mb(self, exporter: MarkdownExporter) -> None:
        result = MarkdownExporter._format_file_size(5 * 1024 * 1024)
        assert "MB" in result

    def test_format_file_size_gb(self, exporter: MarkdownExporter) -> None:
        result = MarkdownExporter._format_file_size(2 * 1024 * 1024 * 1024)
        assert "GB" in result

    def test_format_dt_none(self, exporter: MarkdownExporter) -> None:
        assert MarkdownExporter._format_dt(None) == "N/A"

    def test_format_dt_valid(self, exporter: MarkdownExporter) -> None:
        dt = datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC)
        result = MarkdownExporter._format_dt(dt)
        assert "2024-06-15 10:30:00 UTC" in result


class TestFullExport:
    """Test complete Markdown export."""

    def test_full_export_non_empty(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert len(md) > 100

    def test_full_export_has_all_sections(self, exporter: MarkdownExporter) -> None:
        report = _make_report()
        md = exporter.export(report)
        assert "# " in md  # title
        assert "## Overview" in md
        assert "## Key Findings" in md
        assert "## Extracted Fields" in md
        assert "## Risks" in md
        assert "## Compliance Checklist" in md
        assert "## Recommendations" in md

    def test_export_with_minimal_content(self, exporter: MarkdownExporter) -> None:
        report = _make_report(content={})
        md = exporter.export(report)
        # Should at least have title, metadata, footer
        assert "# " in md
        assert "Report ID" in md
        assert "AI Document Operations Agent" in md
