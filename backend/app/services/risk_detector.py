"""Rule-based risk detection for Vietnamese business documents."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_VND_AMOUNT_PATTERN = re.compile(
    r"(\d{1,3}(?:[.,]\d{3})*)\s*(?:VND|VNĐ|đ|triệu|tỷ|nghìn|ngàn)",
    re.IGNORECASE,
)
_VND_PLAIN_PATTERN = re.compile(r"(\d{1,3}(?:[.,]\d{3})*)\s*(?:đồng|dong)", re.IGNORECASE)
_DATE_PATTERN = re.compile(
    r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})",
)
_DEADLINE_PATTERN = re.compile(
    r"(?:deadline|hạn|thời hạn|ngày hết hạn|ngày đến hạn|thời gian)[^.\n]{0,50}?(\d{1,2})\s*(?:ngày|day|days)",
    re.IGNORECASE,
)
_PENALTY_KEYWORDS = [
    "phạt", "penalty", "phạt vi phạm", "phạt chậm", "tiền phạt",
    "bồi thường thiệt hại", "phạt hợp đồng",
]
_PAYMENT_TERMS_KEYWORDS = [
    "thanh toán", "payment", "trả tiền", "chuyển khoản",
    "tiền mặt", "trả góp", "đặt cọc",
]
_SIGNATURE_KEYWORDS = [
    "chữ ký", "ký tên", "signature", "ký và đóng dấu",
    "đại diện pháp luật", "người đại diện",
]
_EXPIRED_DATE_KEYWORDS = [
    "hết hạn", "hết hiệu lực", "expired", "mất hiệu lực",
    "chấm dứt", "terminated",
]
_HIGH_VALUE_THRESHOLD_VND = 1_000_000_000
_SHORT_DEADLINE_DAYS = 7


@dataclass(frozen=True)
class RiskItem:
    """A single detected risk."""

    category: str
    severity: str
    title: str
    description: str
    evidence: dict = field(default_factory=dict)
    page_number: int | None = None


class RiskDetector:
    """Detects risks in document text using rule-based heuristics.

    Categories: financial, legal, temporal, compliance, operational.
    """

    _SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

    def detect(
        self,
        text: str,
        document_type: str,
        extracted_fields: list[dict] | None = None,
    ) -> list[RiskItem]:
        """Run all risk detection rules against *text*.

        Args:
            text: Full document text (OCR output or parsed).
            document_type: e.g. ``"contract"``, ``"invoice"``, ``"proposal"``.
            extracted_fields: Optional structured field list from extraction step.

        Returns:
            Sorted list of ``RiskItem`` (critical first).
        """
        risks: list[RiskItem] = []

        risks.extend(self._detect_high_value_amounts(text))
        risks.extend(self._detect_missing_payment_terms(text, document_type))
        risks.extend(self._detect_unusual_penalty_clauses(text))
        risks.extend(self._detect_short_deadlines(text))
        risks.extend(self._detect_missing_signatures(text))
        risks.extend(self._detect_expired_dates(text))
        risks.extend(self._detect_extracted_field_risks(extracted_fields))

        risks.sort(key=lambda r: self._SEVERITY_ORDER.get(r.severity, 99))
        logger.info("Risk detection completed: %d risks found", len(risks))
        return risks

    # ------------------------------------------------------------------
    # Individual rules
    # ------------------------------------------------------------------

    def _detect_high_value_amounts(self, text: str) -> list[RiskItem]:
        risks: list[RiskItem] = []
        for match in _VND_AMOUNT_PATTERN.finditer(text):
            raw_number = match.group(1).replace(",", "").replace(".", "")
            try:
                amount = int(raw_number)
            except ValueError:
                continue

            unit_text = match.group(0).lower()
            if "tỷ" in unit_text:
                amount *= 1_000_000_000
            elif "triệu" in unit_text:
                amount *= 1_000_000
            elif "nghìn" in unit_text or "ngàn" in unit_text:
                amount *= 1_000

            if amount >= _HIGH_VALUE_THRESHOLD_VND:
                severity = "critical" if amount >= 10_000_000_000 else "high"
                page = self._estimate_page(text, match.start())
                risks.append(
                    RiskItem(
                        category="financial",
                        severity=severity,
                        title="High-value financial amount detected",
                        description=(
                            f"Amount of {amount:,.0f} VND exceeds the "
                            f"{_HIGH_VALUE_THRESHOLD_VND:,.0f} VND threshold."
                        ),
                        evidence={"amount": amount, "raw_match": match.group(0)},
                        page_number=page,
                    )
                )
        return risks

    def _detect_missing_payment_terms(self, text: str, document_type: str) -> list[RiskItem]:
        if document_type.lower() not in ("contract", "invoice", "hợp đồng", "hóa đơn"):
            return []
        text_lower = text.lower()
        found = any(kw in text_lower for kw in _PAYMENT_TERMS_KEYWORDS)
        if found:
            return []
        return [
            RiskItem(
                category="financial",
                severity="high",
                title="Missing payment terms",
                description=(
                    "No payment terms or payment method found in the document. "
                    "Contracts and invoices should clearly specify payment conditions."
                ),
                evidence={"expected_keywords": _PAYMENT_TERMS_KEYWORDS},
            )
        ]

    def _detect_unusual_penalty_clauses(self, text: str) -> list[RiskItem]:
        risks: list[RiskItem] = []
        text_lower = text.lower()
        for keyword in _PENALTY_KEYWORDS:
            idx = text_lower.find(keyword)
            if idx == -1:
                continue

            context_start = max(0, idx - 50)
            context_end = min(len(text), idx + 150)
            context = text[context_start:context_end]

            pct_match = re.search(r"(\d+(?:[.,]\d+)?)\s*%", context)
            if pct_match:
                try:
                    pct = float(pct_match.group(1).replace(",", "."))
                except ValueError:
                    continue
                if pct > 20:
                    page = self._estimate_page(text, idx)
                    risks.append(
                        RiskItem(
                            category="legal",
                            severity="high" if pct > 50 else "medium",
                            title="Unusually high penalty percentage",
                            description=(
                                f"Penalty clause contains {pct}% which is unusually high. "
                                "Standard penalty clauses typically range from 5-20%."
                            ),
                            evidence={"percentage": pct, "context": context.strip()},
                            page_number=page,
                        )
                    )

            amount_match = re.search(r"(\d{1,3}(?:[.,]\d{3})*)", context)
            if amount_match and not pct_match:
                raw = amount_match.group(1).replace(",", "").replace(".", "")
                try:
                    amount = int(raw)
                except ValueError:
                    continue
                if amount >= _HIGH_VALUE_THRESHOLD_VND:
                    page = self._estimate_page(text, idx)
                    risks.append(
                        RiskItem(
                            category="legal",
                            severity="high",
                            title="High-value penalty clause detected",
                            description=(
                                f"Penalty clause references an amount of {amount:,.0f} VND. "
                                "Review for reasonableness."
                            ),
                            evidence={"amount": amount, "context": context.strip()},
                            page_number=page,
                        )
                    )
        return risks

    def _detect_short_deadlines(self, text: str) -> list[RiskItem]:
        risks: list[RiskItem] = []
        for match in _DEADLINE_PATTERN.finditer(text):
            try:
                days = int(match.group(1))
            except ValueError:
                continue
            if 0 < days < _SHORT_DEADLINE_DAYS:
                page = self._estimate_page(text, match.start())
                risks.append(
                    RiskItem(
                        category="temporal",
                        severity="high" if days <= 3 else "medium",
                        title="Short deadline detected",
                        description=(
                            f"A deadline of {days} day(s) was found, which is below "
                            f"the recommended minimum of {_SHORT_DEADLINE_DAYS} days."
                        ),
                        evidence={"days": days, "raw_match": match.group(0)},
                        page_number=page,
                    )
                )
        return risks

    def _detect_missing_signatures(self, text: str) -> list[RiskItem]:
        text_lower = text.lower()
        found = any(kw in text_lower for kw in _SIGNATURE_KEYWORDS)
        if found:
            return []
        return [
            RiskItem(
                category="compliance",
                severity="medium",
                title="Missing signature section",
                description=(
                    "No signature block or signing authority reference detected. "
                    "Documents should include proper signature sections for legal validity."
                ),
                evidence={"expected_keywords": _SIGNATURE_KEYWORDS},
            )
        ]

    def _detect_expired_dates(self, text: str) -> list[RiskItem]:
        risks: list[RiskItem] = []
        text_lower = text.lower()

        for keyword in _EXPIRED_DATE_KEYWORDS:
            idx = text_lower.find(keyword)
            if idx == -1:
                continue

            search_window = text[max(0, idx - 100) : min(len(text), idx + 100)]
            date_match = _DATE_PATTERN.search(search_window)
            if date_match:
                day_s, month_s, year_s = date_match.groups()
                try:
                    day, month, year = int(day_s), int(month_s), int(year_s)
                    if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
                        from datetime import date

                        ref_date = date(year, month, day)
                        if ref_date < date.today():
                            page = self._estimate_page(text, idx)
                            risks.append(
                                RiskItem(
                                    category="temporal",
                                    severity="critical",
                                    title="Expired date reference found",
                                    description=(
                                        f"Reference to expired date {ref_date.isoformat()} found "
                                        f"near '{keyword}' keyword. Document may be outdated or invalid."
                                    ),
                                    evidence={
                                        "date": ref_date.isoformat(),
                                        "keyword": keyword,
                                        "context": search_window.strip(),
                                    },
                                    page_number=page,
                                )
                            )
                except (ValueError, TypeError):
                    continue
        return risks

    def _detect_extracted_field_risks(
        self, extracted_fields: list[dict] | None
    ) -> list[RiskItem]:
        if not extracted_fields:
            return []

        risks: list[RiskItem] = []
        for field_dict in extracted_fields:
            confidence = field_dict.get("confidence")
            if confidence is not None and confidence < 0.5:
                risks.append(
                    RiskItem(
                        category="operational",
                        severity="medium",
                        title=f"Low-confidence extraction: {field_dict.get('field_name', 'unknown')}",
                        description=(
                            f"Field '{field_dict.get('field_name')}' was extracted with "
                            f"confidence {confidence:.0%}, below the 50% threshold. "
                            "Manual verification recommended."
                        ),
                        evidence={
                            "field_name": field_dict.get("field_name"),
                            "confidence": confidence,
                            "raw_text": field_dict.get("raw_text", "")[:200],
                        },
                        page_number=field_dict.get("page_number"),
                    )
                )
        return risks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_page(text: str, char_offset: int) -> int | None:
        """Estimate page number by counting form-feed or page-break markers."""
        if char_offset < 0 or char_offset >= len(text):
            return None
        return text[:char_offset].count("\f") + 1
