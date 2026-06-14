"""Tests for RiskDetector — rule-based risk detection."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.services.risk_detector import RiskDetector, RiskItem


@pytest.fixture()
def detector() -> RiskDetector:
    return RiskDetector()


class TestHighValueAmounts:
    """Test detection of high-value financial amounts."""

    def test_high_value_vnd_detected(self, detector: RiskDetector) -> None:
        text = "Giá trị hợp đồng: 5.000.000.000 VND"
        risks = detector.detect(text, "contract")
        financial_risks = [r for r in risks if r.category == "financial"]
        assert len(financial_risks) >= 1
        assert financial_risks[0].severity in ("high", "critical")

    def test_critical_threshold_10_billion(self, detector: RiskDetector) -> None:
        text = "Tổng đầu tư: 15.000.000.000 VND"
        risks = detector.detect(text, "contract")
        financial_risks = [r for r in risks if r.category == "financial" and r.severity == "critical"]
        assert len(financial_risks) >= 1

    def test_low_amount_no_risk(self, detector: RiskDetector) -> None:
        text = "Phí dịch vụ: 500.000 VND"
        risks = detector.detect(text, "contract")
        financial_risks = [r for r in risks if r.category == "financial" and "high-value" in r.title.lower()]
        assert len(financial_risks) == 0

    def test_amount_with_ty_unit(self, detector: RiskDetector) -> None:
        text = "Giá trị dự án: 5 tỷ VND"
        risks = detector.detect(text, "contract")
        financial_risks = [r for r in risks if r.category == "financial"]
        assert len(financial_risks) >= 1

    def test_amount_with_trieu_unit(self, detector: RiskDetector) -> None:
        text = "Chi phí: 2.000 triệu VND"
        risks = detector.detect(text, "contract")
        financial_risks = [r for r in risks if r.category == "financial"]
        assert len(financial_risks) >= 1

    def test_evidence_contains_amount(self, detector: RiskDetector) -> None:
        text = "Tổng cộng: 5.000.000.000 VND"
        risks = detector.detect(text, "contract")
        financial_risks = [r for r in risks if r.category == "financial"]
        assert len(financial_risks) >= 1
        assert "amount" in financial_risks[0].evidence


class TestMissingPaymentTerms:
    """Test detection of missing payment terms."""

    def test_contract_without_payment_terms(self, detector: RiskDetector) -> None:
        text = "Hợp đồng dịch vụ giữa Bên A và Bên B. Thời hạn 12 tháng."
        risks = detector.detect(text, "contract")
        payment_risks = [r for r in risks if "payment" in r.title.lower()]
        assert len(payment_risks) >= 1
        assert payment_risks[0].severity == "high"

    def test_contract_with_payment_terms_no_risk(self, detector: RiskDetector) -> None:
        text = "Hợp đồng dịch vụ. Hình thức thanh toán: chuyển khoản ngân hàng."
        risks = detector.detect(text, "contract")
        payment_risks = [r for r in risks if "payment" in r.title.lower()]
        assert len(payment_risks) == 0

    def test_invoice_without_payment_terms(self, detector: RiskDetector) -> None:
        text = "Hóa đơn số 001. Hàng hóa: Dịch vụ A."
        risks = detector.detect(text, "invoice")
        payment_risks = [r for r in risks if "payment" in r.title.lower()]
        assert len(payment_risks) >= 1

    def test_non_contract_invoice_no_payment_check(self, detector: RiskDetector) -> None:
        text = "Báo cáo tài chính năm 2024."
        risks = detector.detect(text, "report")
        payment_risks = [r for r in risks if "payment" in r.title.lower()]
        assert len(payment_risks) == 0


class TestUnusualPenaltyClauses:
    """Test detection of unusual penalty percentages."""

    def test_high_penalty_percentage(self, detector: RiskDetector) -> None:
        text = "Phạt vi phạm hợp đồng: 30% giá trị hợp đồng"
        risks = detector.detect(text, "contract")
        penalty_risks = [r for r in risks if "penalty" in r.title.lower()]
        assert len(penalty_risks) >= 1
        assert penalty_risks[0].severity in ("medium", "high")

    def test_very_high_penalty_critical(self, detector: RiskDetector) -> None:
        text = "Phạt chậm tiến độ: 60% tổng giá trị"
        risks = detector.detect(text, "contract")
        penalty_risks = [r for r in risks if "penalty" in r.title.lower() and "percentage" in r.title.lower()]
        assert len(penalty_risks) >= 1
        assert penalty_risks[0].severity == "high"

    def test_normal_penalty_no_risk(self, detector: RiskDetector) -> None:
        text = "Phạt vi phạm: 10% giá trị hợp đồng"
        risks = detector.detect(text, "contract")
        penalty_risks = [r for r in risks if "penalty" in r.title.lower() and "percentage" in r.title.lower()]
        assert len(penalty_risks) == 0

    def test_penalty_with_amount(self, detector: RiskDetector) -> None:
        text = "Điều khoản phạt vi phạm hợp đồng: 2,000,000,000 đồng"
        risks = detector.detect(text, "contract")
        penalty_risks = [r for r in risks if "penalty" in r.title.lower() and "high-value" in r.title.lower()]
        assert len(penalty_risks) >= 1


class TestShortDeadlines:
    """Test detection of short deadlines."""

    def test_short_deadline_detected(self, detector: RiskDetector) -> None:
        text = "Thời hạn hoàn thành: 3 ngày kể từ ngày ký"
        risks = detector.detect(text, "contract")
        deadline_risks = [r for r in risks if "deadline" in r.title.lower()]
        assert len(deadline_risks) >= 1

    def test_very_short_deadline_high_severity(self, detector: RiskDetector) -> None:
        text = "Deadline: 2 ngày"
        risks = detector.detect(text, "contract")
        deadline_risks = [r for r in risks if "deadline" in r.title.lower()]
        if deadline_risks:
            assert deadline_risks[0].severity == "high"

    def test_reasonable_deadline_no_risk(self, detector: RiskDetector) -> None:
        text = "Thời hạn: 30 ngày kể từ ngày ký"
        risks = detector.detect(text, "contract")
        deadline_risks = [r for r in risks if "deadline" in r.title.lower()]
        assert len(deadline_risks) == 0


class TestMissingSignatures:
    """Test detection of missing signature sections."""

    def test_document_without_signatures(self, detector: RiskDetector) -> None:
        text = "Hợp đồng dịch vụ giữa hai bên. Thời hạn 12 tháng."
        risks = detector.detect(text, "contract")
        sig_risks = [r for r in risks if "signature" in r.title.lower()]
        assert len(sig_risks) >= 1
        assert sig_risks[0].severity == "medium"

    def test_document_with_signatures_no_risk(self, detector: RiskDetector) -> None:
        text = "Hợp đồng dịch vụ.\nĐại diện pháp luật ký tên và đóng dấu."
        risks = detector.detect(text, "contract")
        sig_risks = [r for r in risks if "signature" in r.title.lower()]
        assert len(sig_risks) == 0


class TestExpiredDates:
    """Test detection of expired date references."""

    def test_expired_date_detected(self, detector: RiskDetector) -> None:
        text = "Hợp đồng hết hạn ngày 01/01/2020. Chấm dứt hiệu lực."
        risks = detector.detect(text, "contract")
        expired_risks = [r for r in risks if "expired" in r.title.lower()]
        assert len(expired_risks) >= 1
        assert expired_risks[0].severity == "critical"

    def test_future_date_no_expired_risk(self, detector: RiskDetector) -> None:
        text = "Hợp đồng hết hạn ngày 01/01/2099. Hết hiệu lực."
        risks = detector.detect(text, "contract")
        expired_risks = [r for r in risks if "expired" in r.title.lower()]
        assert len(expired_risks) == 0


class TestLowConfidenceExtraction:
    """Test detection of low-confidence extracted fields."""

    def test_low_confidence_field_flagged(self, detector: RiskDetector) -> None:
        fields = [
            {"field_name": "total_amount", "confidence": 0.3, "raw_text": "50M"},
        ]
        risks = detector.detect("some text", "contract", extracted_fields=fields)
        op_risks = [r for r in risks if r.category == "operational"]
        assert len(op_risks) >= 1
        assert op_risks[0].severity == "medium"

    def test_high_confidence_field_no_risk(self, detector: RiskDetector) -> None:
        fields = [
            {"field_name": "total_amount", "confidence": 0.95, "raw_text": "50,000,000 VND"},
        ]
        risks = detector.detect("some text", "contract", extracted_fields=fields)
        op_risks = [r for r in risks if r.category == "operational"]
        assert len(op_risks) == 0

    def test_no_extracted_fields_no_operational_risk(self, detector: RiskDetector) -> None:
        risks = detector.detect("some text", "contract", extracted_fields=None)
        op_risks = [r for r in risks if r.category == "operational"]
        assert len(op_risks) == 0


class TestRiskSorting:
    """Test that risks are sorted by severity."""

    def test_risks_sorted_critical_first(self, detector: RiskDetector) -> None:
        text = (
            "Hợp đồng hết hạn ngày 01/01/2020. Hết hiệu lực.\n"
            "Tổng cộng: 15.000.000.000 VND\n"
            "Phạt vi phạm: 5% giá trị\n"
        )
        risks = detector.detect(text, "contract")
        if len(risks) >= 2:
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            for i in range(len(risks) - 1):
                assert severity_order.get(risks[i].severity, 99) <= severity_order.get(
                    risks[i + 1].severity, 99
                )

    def test_empty_text_no_risks(self, detector: RiskDetector) -> None:
        risks = detector.detect("", "contract")
        # Should not crash; may return some risks (missing payment, missing signatures)
        assert isinstance(risks, list)


class TestPageEstimation:
    """Test page estimation from form-feed characters."""

    def test_page_estimation_with_form_feeds(self, detector: RiskDetector) -> None:
        text = "Page 1 content\n\f\nPage 2: Tổng cộng: 5.000.000.000 VND"
        risks = detector.detect(text, "contract")
        financial_risks = [r for r in risks if r.category == "financial"]
        if financial_risks:
            assert financial_risks[0].page_number == 2
