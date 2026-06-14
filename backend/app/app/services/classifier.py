"""Document classifier using rule-based and keyword-based approaches."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DOCUMENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "contract": [
        "hợp đồng", "hop dong", "contract", "agreement", "bên a", "bên b",
        "ben a", "ben b", "điều khoản", "dieu khoan", "cam kết", "cam ket",
        "thỏa thuận", "thoa thuan", "phụ lục", "phu luc", "nghĩa vụ",
        "nghia vu", "bồi thường", "boi thuong", "giá trị hợp đồng",
        "ngày ký", "ngay ky", "chữ ký", "chu ky", "đại diện", "dai dien",
        "thời hạn hợp đồng", "thoi han hop dong",
    ],
    "invoice": [
        "hóa đơn", "hoa don", "invoice", "receipt", "biên lai", "bien lai",
        "thanh toán", "thanh toan", "tổng cộng", "tong cong", "tiền hàng",
        "tien hang", "thuế", "thue", "vat", "giá trị gia tăng",
        "số hóa đơn", "so hoa don", "mã số thuế", "ma so thue",
        "người mua", "nguoi mua", "người bán", "nguoi ban",
        "phiếu thu", "phieu thu", "phiếu chi", "phieu chi",
    ],
    "report": [
        "báo cáo", "bao cao", "report", "tổng hợp", "tong hop",
        "thống kê", "thong ke", "phân tích", "phan tich",
        "kết quả", "ket qua", "đánh giá", "danh gia", "năm tài chính",
        "nam tai chinh", "quý", "quy", "doanh thu", "lợi nhuận",
        "loi nhuan", "báo cáo tài chính", "bao cao tai chinh",
        "bảng cân đối", "bang can doi",
    ],
    "minutes": [
        "biên bản", "bien ban", "minutes", "meeting minutes",
        "cuộc họp", "cuoc hop", "hội nghị", "hoi nghi",
        "nội dung thảo luận", "noi dung thao luan",
        "kết luận", "ket luan", "tham dự", "tham du",
        "chủ tọa", "chu toa", "thư ký", "thu ky",
        "biên bản bàn giao", "bien ban ban giao",
        "biên bản nghiệm thu", "bien ban nghiem thu",
    ],
    "regulation": [
        "quy định", "quy dinh", "regulation", "policy", "nội quy", "noi quy",
        "quy chế", "quy che", "điều lệ", "dieu le", "thông tư", "thong tu",
        "nghị định", "nghi dinh", "quyết định", "quyet dinh",
        "pháp luật", "phap luat", "văn bản", "van ban",
        "công văn", "cong van", "thông báo", "thong bao",
        "chỉ thị", "chi thi", "nghị quyết", "nghi quyet",
    ],
    "dispatch": [
        "công văn", "cong van", "dispatch", "official letter",
        "số công văn", "so cong van", "v/v", "về việc", "ve viec",
        "kính gửi", "kinh gui", "nơi nhận", "noi nhan",
        "chuyển phát", "chuyen phat", "khẩn", "khan",
        "hỏa tốc", "hoa toc", "công văn số", "trình",
    ],
}

KEYWORD_WEIGHTS: dict[str, float] = {
    "hợp đồng": 3.0, "contract": 3.0, "agreement": 2.5,
    "hóa đơn": 3.0, "invoice": 3.0, "receipt": 2.0,
    "báo cáo": 3.0, "report": 3.0,
    "biên bản": 3.0, "minutes": 3.0, "meeting minutes": 2.5,
    "quy định": 3.0, "regulation": 3.0, "quy chế": 2.5,
    "công văn": 3.0, "dispatch": 3.0, "official letter": 2.5,
}


@dataclass
class ClassificationResult:
    """Result of document classification."""

    document_type: str
    confidence: float
    subtypes: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)


class DocumentClassifier:
    """Classifies documents into types using keyword matching and heuristics.

    Supports Vietnamese and English keywords for: contract, invoice, report,
    minutes, regulation, dispatch.
    """

    DEFAULT_TYPE = "unknown"
    MIN_CONFIDENCE = 0.15
    SUBTYPE_THRESHOLD_RATIO = 0.6

    def classify(self, text: str) -> ClassificationResult:
        """Classify a document based on its text content.

        Args:
            text: The full text content of the document.

        Returns:
            ClassificationResult with document_type, confidence, and subtypes.
        """
        if not text or not text.strip():
            return ClassificationResult(
                document_type=self.DEFAULT_TYPE,
                confidence=0.0,
            )

        normalized = self._normalize_text(text)
        scores = self._compute_scores(normalized)

        if not scores or max(scores.values()) == 0:
            return ClassificationResult(
                document_type=self.DEFAULT_TYPE,
                confidence=0.0,
                scores=scores,
            )

        primary_type = max(scores, key=lambda k: scores[k])
        max_score = scores[primary_type]
        total_score = sum(scores.values())

        confidence = self._calculate_confidence(max_score, total_score, normalized)

        subtypes = self._detect_subtypes(scores, max_score)

        return ClassificationResult(
            document_type=primary_type if confidence >= self.MIN_CONFIDENCE else self.DEFAULT_TYPE,
            confidence=round(confidence, 4),
            subtypes=subtypes,
            scores={k: round(v, 4) for k, v in scores.items()},
        )

    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching."""
        text = text.lower()
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _compute_scores(self, text: str) -> dict[str, float]:
        """Compute classification scores for each document type."""
        scores: dict[str, float] = {}

        for doc_type, keywords in DOCUMENT_TYPE_KEYWORDS.items():
            type_score = 0.0
            for keyword in keywords:
                count = text.count(keyword)
                if count > 0:
                    weight = KEYWORD_WEIGHTS.get(keyword, 1.0)
                    type_score += count * weight
            scores[doc_type] = type_score

        pattern_scores = self._pattern_boost(text)
        for doc_type, boost in pattern_scores.items():
            scores[doc_type] = scores.get(doc_type, 0.0) + boost

        return scores

    def _pattern_boost(self, text: str) -> dict[str, float]:
        """Apply regex-based pattern matching for structural signals."""
        boosts: dict[str, float] = {}

        if re.search(r"(bên\s+[ab]|party\s+[ab]|chủ đầu tư|nhà thầu)", text):
            boosts["contract"] = boosts.get("contract", 0) + 2.0

        if re.search(r"(số\s*:\s*\S+|no\s*:\s*\S+).*?(ngày|date)", text, re.DOTALL):
            boosts["contract"] = boosts.get("contract", 0) + 1.0
            boosts["dispatch"] = boosts.get("dispatch", 0) + 0.5

        if re.search(r"(tổng\s*(tiền|cộng|thanh toán)|total\s*(amount|due|payable))", text):
            boosts["invoice"] = boosts.get("invoice", 0) + 2.0

        if re.search(r"(mã\s*số\s*thuế|mst|tax\s*id|tax\s*code)", text):
            boosts["invoice"] = boosts.get("invoice", 0) + 1.5

        if re.search(r"(quý\s*\d|q[1-4]|năm\s*\d{4}|fy\s*\d{4})", text):
            boosts["report"] = boosts.get("report", 0) + 1.5

        if re.search(r"(tham\s*dự|chủ\s*tọa|thư\s*ký|attendees?|chairperson)", text):
            boosts["minutes"] = boosts.get("minutes", 0) + 2.0

        if re.search(r"(điều\s*\d+|article\s*\d+|khoản\s*\d+|section\s*\d+)", text):
            boosts["regulation"] = boosts.get("regulation", 0) + 1.5
            boosts["contract"] = boosts.get("contract", 0) + 1.0

        if re.search(r"(v/v|về\s*việc|kính\s*gửi|nơi\s*nhận)", text):
            boosts["dispatch"] = boosts.get("dispatch", 0) + 2.5

        return boosts

    def _calculate_confidence(
        self, max_score: float, total_score: float, text: str
    ) -> float:
        """Calculate normalized confidence score."""
        if total_score == 0:
            return 0.0

        ratio = max_score / total_score

        text_length_factor = min(len(text) / 500, 1.0)

        raw_confidence = ratio * 0.7 + text_length_factor * 0.3
        return min(max(raw_confidence, 0.0), 1.0)

    def _detect_subtypes(
        self, scores: dict[str, float], max_score: float
    ) -> list[str]:
        """Detect secondary document types as subtypes."""
        threshold = max_score * self.SUBTYPE_THRESHOLD_RATIO
        subtypes = []
        for doc_type, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            if score >= threshold and score < max_score:
                subtypes.append(doc_type)
        return subtypes
