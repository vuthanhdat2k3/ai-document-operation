"""Tests for ClauseDetector — missing clause detection."""

from __future__ import annotations

import pytest

from app.services.clause_detector import ClauseDetector, MissingClause


@pytest.fixture()
def detector() -> ClauseDetector:
    return ClauseDetector()


class TestContractClauseDetection:
    """Test missing clause detection for contracts."""

    def test_empty_contract_has_all_critical_missing(self, detector: ClauseDetector) -> None:
        missing = detector.detect_missing("", "contract")
        critical = [m for m in missing if m.severity == "critical"]
        assert len(critical) >= 3  # parties, terms, payment

    def test_complete_contract_no_missing(self, detector: ClauseDetector) -> None:
        text = (
            "HỢP ĐỒNG DỊCH VỤ\n"
            "Bên A: Công ty ABC, đại diện: Ông X\n"
            "Bên B: Công ty XYZ, đại diện: Bà Y\n"
            "Điều 1: Phạm vi và nội dung công việc\n"
            "Điều 2: Thời hạn hợp đồng: 12 tháng\n"
            "Điều 3: Giá trị hợp đồng và hình thức thanh toán\n"
            "Điều 4: Điều khoản chấm dứt hợp đồng\n"
            "Điều 5: Giải quyết tranh chấp tại trọng tài\n"
            "Điều 6: Sự kiện bất khả kháng\n"
            "Điều 7: Bảo mật thông tin\n"
            "Điều 8: Trách nhiệm và bồi thường thiệt hại\n"
            "Điều 9: Bảo hiểm\n"
        )
        missing = detector.detect_missing(text, "contract")
        assert len(missing) == 0

    def test_partial_contract_some_missing(self, detector: ClauseDetector) -> None:
        text = (
            "HỢP ĐỒNG\n"
            "Bên A: Công ty ABC\n"
            "Bên B: Công ty XYZ\n"
            "Giá trị hợp đồng: 100,000,000 VND\n"
            "Hình thức thanh toán: Chuyển khoản\n"
        )
        missing = detector.detect_missing(text, "contract")
        missing_names = {m.clause_name for m in missing}
        assert "duration_and_effective_date" in missing_names
        assert "dispute_resolution" in missing_names
        assert "force_majeure" in missing_names

    def test_contract_missing_only_parties(self, detector: ClauseDetector) -> None:
        text = "Điều khoản chung. Giá trị hợp đồng 100 triệu. Thời hạn 6 tháng."
        missing = detector.detect_missing(text, "contract")
        missing_names = {m.clause_name for m in missing}
        assert "parties" in missing_names

    def test_contract_missing_clause_has_suggestion(self, detector: ClauseDetector) -> None:
        missing = detector.detect_missing("", "contract")
        for m in missing:
            assert len(m.suggestion) > 0

    def test_contract_missing_clause_has_description(self, detector: ClauseDetector) -> None:
        missing = detector.detect_missing("", "contract")
        for m in missing:
            assert len(m.description) > 0


class TestInvoiceClauseDetection:
    """Test missing clause detection for invoices."""

    def test_empty_invoice_has_critical_missing(self, detector: ClauseDetector) -> None:
        missing = detector.detect_missing("", "invoice")
        critical = [m for m in missing if m.severity == "critical"]
        assert len(critical) >= 2  # line_items, amounts_and_totals

    def test_complete_invoice_no_missing(self, detector: ClauseDetector) -> None:
        text = (
            "HÓA ĐƠN\n"
            "Người bán: Công ty ABC, mã số thuế 0123456789\n"
            "Người mua: Công ty XYZ\n"
            "Hàng hóa: Dịch vụ tư vấn\n"
            "Tổng cộng: 10,000,000 VND\n"
            "Thuế GTGT: 10%\n"
            "Hạn thanh toán: 30/06/2024\n"
            "Hình thức thanh toán: Chuyển khoản\n"
        )
        missing = detector.detect_missing(text, "invoice")
        assert len(missing) == 0

    def test_invoice_missing_tax_info(self, detector: ClauseDetector) -> None:
        text = "Hóa đơn. Hàng hóa: Dịch vụ. Tổng cộng: 1,000,000 VND."
        missing = detector.detect_missing(text, "invoice")
        missing_names = {m.clause_name for m in missing}
        assert "tax_information" in missing_names

    def test_invoice_missing_due_date(self, detector: ClauseDetector) -> None:
        text = "Hóa đơn. Sản phẩm A. Tổng tiền: 5,000,000. Thuế VAT 10%."
        missing = detector.detect_missing(text, "invoice")
        missing_names = {m.clause_name for m in missing}
        assert "due_date" in missing_names


class TestUnknownDocumentType:
    """Test clause detection for unsupported document types."""

    def test_unknown_type_checks_all_templates(self, detector: ClauseDetector) -> None:
        missing = detector.detect_missing("", "report")
        # Should combine contract + invoice clauses
        names = {m.clause_name for m in missing}
        assert "parties" in names  # from contract
        assert "line_items" in names  # from invoice

    def test_unknown_type_mixed_vietnamese(self, detector: ClauseDetector) -> None:
        missing = detector.detect_missing("", "hợp đồng")
        # "hợp đồng" is in _TEMPLATES
        contract_names = {m.clause_name for m in missing}
        assert "parties" in contract_names

    def test_nonexistent_type(self, detector: ClauseDetector) -> None:
        missing = detector.detect_missing("some text", "memo")
        assert isinstance(missing, list)
        assert len(missing) > 0  # Should check all templates


class TestEdgeCases:
    """Test edge cases in clause detection."""

    def test_keyword_case_insensitive(self, detector: ClauseDetector) -> None:
        text = "BÊN A and BÊN B agree. THANH TOÁN via bank transfer."
        missing = detector.detect_missing(text, "contract")
        missing_names = {m.clause_name for m in missing}
        assert "parties" not in missing_names
        assert "payment_terms" not in missing_names

    def test_partial_keyword_match(self, detector: ClauseDetector) -> None:
        # "bên a" alone shouldn't match "parties" template since min_matches=1
        text = "Chỉ có Bên A tham gia"
        missing = detector.detect_missing(text, "contract")
        missing_names = {m.clause_name for m in missing}
        # "bên a" matches one keyword, min_matches=1, so parties is NOT missing
        assert "parties" not in missing_names

    def test_severity_levels_present(self, detector: ClauseDetector) -> None:
        missing = detector.detect_missing("", "contract")
        severities = {m.severity for m in missing}
        assert "critical" in severities
        assert "high" in severities
        assert "medium" in severities
        assert "low" in severities
