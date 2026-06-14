"""Tests for DocumentClassifier — Vietnamese + English classification."""

from __future__ import annotations

import pytest

from app.services.classifier import ClassificationResult, DocumentClassifier


@pytest.fixture()
def classifier() -> DocumentClassifier:
    return DocumentClassifier()


class TestDocumentClassifier:
    """Test document type classification via keyword matching."""

    def test_empty_text_returns_unknown(self, classifier: DocumentClassifier) -> None:
        result = classifier.classify("")
        assert result.document_type == "unknown"
        assert result.confidence == 0.0

    def test_none_like_empty_text(self, classifier: DocumentClassifier) -> None:
        result = classifier.classify("   \n\t  ")
        assert result.document_type == "unknown"
        assert result.confidence == 0.0

    def test_contract_vietnamese_keywords(self, classifier: DocumentClassifier) -> None:
        text = (
            "HỢP ĐỒNG DỊCH VỤ\n"
            "Bên A: Công ty ABC\n"
            "Bên B: Công ty XYZ\n"
            "Điều khoản: ...\n"
            "Ngày ký: 01/01/2024\n"
            "Giá trị hợp đồng: 500,000,000 VND\n"
        )
        result = classifier.classify(text)
        assert result.document_type == "contract"
        assert result.confidence > 0.3

    def test_contract_english_keywords(self, classifier: DocumentClassifier) -> None:
        text = (
            "SERVICE AGREEMENT\n"
            "Party A and Party B agree to the following terms.\n"
            "This contract is effective as of the date signed.\n"
            "The agreement shall remain in force for 12 months.\n"
        )
        result = classifier.classify(text)
        assert result.document_type == "contract"
        assert result.confidence > 0.3

    def test_invoice_vietnamese(self, classifier: DocumentClassifier) -> None:
        text = (
            "HÓA ĐƠN GTGT\n"
            "Số hóa đơn: 0012345\n"
            "Mã số thuế: 0123456789\n"
            "Người mua: Công ty DEF\n"
            "Người bán: Công ty GHI\n"
            "Tổng cộng: 10,000,000 VND\n"
            "Thuế VAT: 10%\n"
        )
        result = classifier.classify(text)
        assert result.document_type == "invoice"
        assert result.confidence > 0.3

    def test_invoice_english(self, classifier: DocumentClassifier) -> None:
        text = (
            "INVOICE #2024-001\n"
            "Receipt for services rendered.\n"
            "Total Amount Due: $5,000\n"
            "Tax ID: 12-3456789\n"
        )
        result = classifier.classify(text)
        assert result.document_type == "invoice"

    def test_report_vietnamese(self, classifier: DocumentClassifier) -> None:
        text = (
            "BÁO CÁO TÀI CHÍNH NĂM 2024\n"
            "Tổng hợp kết quả kinh doanh quý 4.\n"
            "Doanh thu: 50 tỷ VNĐ\n"
            "Lợi nhuận sau thuế: 5 tỷ\n"
            "Phân tích các chỉ số tài chính.\n"
        )
        result = classifier.classify(text)
        assert result.document_type == "report"

    def test_minutes_vietnamese(self, classifier: DocumentClassifier) -> None:
        text = (
            "BIÊN BẢN HỘI NGHỊ\n"
            "Cuộc họp: Họp giao ban tháng 6\n"
            "Tham dự: Ông A, Bà B\n"
            "Chủ tọa: Ông C\n"
            "Thư ký: Bà D\n"
            "Kết luận: Thống nhất phương án 1\n"
        )
        result = classifier.classify(text)
        assert result.document_type == "minutes"

    def test_regulation_vietnamese(self, classifier: DocumentClassifier) -> None:
        text = (
            "QUY ĐỊNH NỘI BỘ\n"
            "Điều 1: Phạm vi áp dụng\n"
            "Điều 2: Nghĩa vụ nhân viên\n"
            "Nghị định số 123/2024/NĐ-CP\n"
            "Thông tư hướng dẫn thực hiện\n"
        )
        result = classifier.classify(text)
        assert result.document_type == "regulation"

    def test_dispatch_vietnamese(self, classifier: DocumentClassifier) -> None:
        text = (
            "CÔNG VĂN SỐ: 123/CV-2024\n"
            "V/v: Về việc triển khai dự án\n"
            "Kính gửi: Giám đốc Sở\n"
            "Nơi nhận: Các phòng ban\n"
        )
        result = classifier.classify(text)
        assert result.document_type == "dispatch"

    def test_unrelated_text_returns_unknown(self, classifier: DocumentClassifier) -> None:
        text = "The quick brown fox jumps over the lazy dog."
        result = classifier.classify(text)
        assert result.document_type == "unknown"
        assert result.confidence < 0.15

    def test_confidence_bounded_0_to_1(self, classifier: DocumentClassifier) -> None:
        long_contract = "hợp đồng " * 200 + "bên a " * 100 + "điều khoản " * 100
        result = classifier.classify(long_contract)
        assert 0.0 <= result.confidence <= 1.0

    def test_subtype_detection(self, classifier: DocumentClassifier) -> None:
        text = (
            "HỢP ĐỒNG mua bán hàng hóa\n"
            "Hóa đơn đính kèm số 001\n"
            "Tổng cộng thanh toán: 100,000,000 VND\n"
            "Bên A, Bên B thống nhất\n"
        )
        result = classifier.classify(text)
        assert result.document_type == "contract"
        # invoice may appear as subtype due to invoice keywords
        assert isinstance(result.subtypes, list)

    def test_scores_dict_populated(self, classifier: DocumentClassifier) -> None:
        text = "hợp đồng dịch vụ bên a bên b"
        result = classifier.classify(text)
        assert "contract" in result.scores
        assert all(isinstance(v, float) for v in result.scores.values())

    def test_pattern_boost_party_ab(self, classifier: DocumentClassifier) -> None:
        text = "Document between Bên A and Bên B regarding services"
        result = classifier.classify(text)
        assert result.scores.get("contract", 0) > 0

    def test_pattern_boost_invoice_total(self, classifier: DocumentClassifier) -> None:
        text = "Tổng cộng thanh toán: 50,000,000 VND"
        result = classifier.classify(text)
        assert result.scores.get("invoice", 0) > 0

    def test_mixed_language_text(self, classifier: DocumentClassifier) -> None:
        text = (
            "This hợp đồng is an agreement between Party A and Bên B.\n"
            "The giá trị hợp đồng is 100,000,000 VND.\n"
        )
        result = classifier.classify(text)
        assert result.document_type == "contract"
