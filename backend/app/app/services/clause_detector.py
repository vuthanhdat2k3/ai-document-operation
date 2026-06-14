"""Template-based missing clause detection for Vietnamese business documents."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MissingClause:
    """A detected missing clause or section."""

    clause_name: str
    description: str
    severity: str
    suggestion: str


@dataclass(frozen=True)
class _ClauseTemplate:
    """Internal clause specification."""

    name: str
    description: str
    keywords: list[str]
    severity: str
    suggestion: str
    min_matches: int = 1


_CONTRACT_CLAUSES: list[_ClauseTemplate] = [
    _ClauseTemplate(
        name="parties",
        description="Identification of contracting parties",
        keywords=[
            "bên a", "bên b", "bên mua", "bên bán",
            "chủ đầu tư", "nhà thầu", "party a", "party b",
            "bên cho thuê", "bên thuê", "bên sử dụng",
            "đơn vị", "công ty", "tổ chức",
        ],
        severity="critical",
        suggestion="Add a clear section identifying all contracting parties with full legal names, addresses, and representative information.",
    ),
    _ClauseTemplate(
        name="terms_and_scope",
        description="Contract terms and scope of work",
        keywords=[
            "điều khoản", "phạm vi", "nội dung công việc",
            "scope of work", "terms", "mô tả công việc",
            "đối tượng hợp đồng", "phạm vi hợp đồng",
        ],
        severity="critical",
        suggestion="Define the scope, deliverables, and key terms of the agreement clearly.",
    ),
    _ClauseTemplate(
        name="payment_terms",
        description="Payment terms and conditions",
        keywords=[
            "thanh toán", "giá trị hợp đồng", "đơn giá",
            "payment", "giá trị thanh toán", "tiền lương",
            "hình thức thanh toán", "lịch thanh toán",
        ],
        severity="critical",
        suggestion="Specify payment amounts, schedule, method, currency, and any applicable taxes.",
    ),
    _ClauseTemplate(
        name="duration_and_effective_date",
        description="Contract duration and effective date",
        keywords=[
            "thời hạn", "thời gian thực hiện", "ngày hiệu lực",
            "duration", "effective date", "ngày bắt đầu",
            "ngày kết thúc", "thời gian hợp đồng",
        ],
        severity="high",
        suggestion="State the effective date, duration, and any renewal or extension provisions.",
    ),
    _ClauseTemplate(
        name="termination",
        description="Termination conditions",
        keywords=[
            "chấm dứt", "hủy bỏ", "termination",
            "terminate", "kết thúc hợp đồng",
            "đơn phương chấm dứt", "thoát hợp đồng",
        ],
        severity="high",
        suggestion="Include termination conditions, notice periods, and consequences of early termination.",
    ),
    _ClauseTemplate(
        name="dispute_resolution",
        description="Dispute resolution mechanism",
        keywords=[
            "tranh chấp", "giải quyết tranh chấp", "dispute",
            "arbitration", "trọng tài", "tòa án",
            "hòa giải", "mediation",
        ],
        severity="medium",
        suggestion="Define the dispute resolution process: negotiation → mediation → arbitration/court.",
    ),
    _ClauseTemplate(
        name="force_majeure",
        description="Force majeure clause",
        keywords=[
            "bất khả kháng", "force majeure", "sự kiện bất khả kháng",
            "thiên tai", "dịch bệnh", "hành động của chính phủ",
        ],
        severity="medium",
        suggestion="Include force majeure events that excuse performance, notification requirements, and remedies.",
    ),
    _ClauseTemplate(
        name="confidentiality",
        description="Confidentiality obligations",
        keywords=[
            "bảo mật", "confidential", "non-disclosure",
            "thông tin bí mật", "bí mật thương mại", "nda",
        ],
        severity="low",
        suggestion="Add confidentiality obligations covering scope, duration, and exceptions.",
    ),
    _ClauseTemplate(
        name="liability_and_indemnity",
        description="Liability and indemnification",
        keywords=[
            "trách nhiệm", "bồi thường", "liability",
            "indemnity", "thiệt hại", "giới hạn trách nhiệm",
        ],
        severity="medium",
        suggestion="Define liability limits, indemnification obligations, and caps on damages.",
    ),
    _ClauseTemplate(
        name="insurance",
        description="Insurance requirements",
        keywords=[
            "bảo hiểm", "insurance", "hợp đồng bảo hiểm",
            "chứng nhận bảo hiểm",
        ],
        severity="low",
        suggestion="Specify required insurance coverage types, amounts, and proof requirements.",
    ),
]

_INVOICE_CLAUSES: list[_ClauseTemplate] = [
    _ClauseTemplate(
        name="line_items",
        description="Itemized list of goods/services",
        keywords=[
            "hàng hóa", "dịch vụ", "sản phẩm", "mặt hàng",
            "items", "line items", "mô tả hàng hóa",
        ],
        severity="critical",
        suggestion="Include a detailed itemized list with descriptions, quantities, and unit prices.",
    ),
    _ClauseTemplate(
        name="amounts_and_totals",
        description="Financial amounts and totals",
        keywords=[
            "tổng cộng", "thành tiền", "tổng tiền", "total",
            "subtotal", "tổng thanh toán", "grand total",
        ],
        severity="critical",
        suggestion="Clearly show subtotal, taxes, discounts, and grand total.",
    ),
    _ClauseTemplate(
        name="tax_information",
        description="Tax details (VAT, etc.)",
        keywords=[
            "thuế", "vat", "thuế gtgt", "thuế giá trị gia tăng",
            "mã số thuế", "tax", "thuế suất",
        ],
        severity="high",
        suggestion="Include VAT rate, tax amount, tax registration number, and any exemptions.",
    ),
    _ClauseTemplate(
        name="due_date",
        description="Payment due date",
        keywords=[
            "ngày đến hạn", "hạn thanh toán", "due date",
            "ngày hết hạn", "payment due", "thời hạn thanh toán",
        ],
        severity="high",
        suggestion="Clearly state the payment due date and any early payment discounts.",
    ),
    _ClauseTemplate(
        name="payment_method",
        description="Accepted payment methods",
        keywords=[
            "hình thức thanh toán", "chuyển khoản", "payment method",
            "tiền mặt", "bank transfer", "tài khoản ngân hàng",
            "số tài khoản",
        ],
        severity="medium",
        suggestion="Specify accepted payment methods and bank account details if applicable.",
    ),
    _ClauseTemplate(
        name="issuer_info",
        description="Issuer identification",
        keywords=[
            "người bán", "bên bán", "seller", "issuer",
            "người lập hóa đơn", "đơn vị bán", "công ty phát hành",
        ],
        severity="high",
        suggestion="Include full legal name, address, and tax ID of the invoice issuer.",
    ),
    _ClauseTemplate(
        name="recipient_info",
        description="Buyer/recipient identification",
        keywords=[
            "người mua", "bên mua", "buyer", "recipient",
            "khách hàng", "đơn vị nhận", "customer",
        ],
        severity="high",
        suggestion="Include full legal name, address, and tax ID of the buyer.",
    ),
]

_TEMPLATES: dict[str, list[_ClauseTemplate]] = {
    "contract": _CONTRACT_CLAUSES,
    "hợp đồng": _CONTRACT_CLAUSES,
    "invoice": _INVOICE_CLAUSES,
    "hóa đơn": _INVOICE_CLAUSES,
}


class ClauseDetector:
    """Detects missing clauses in documents based on template requirements.

    Supports contract and invoice templates with extensible clause definitions.
    """

    def detect_missing(self, text: str, document_type: str) -> list[MissingClause]:
        """Check *text* for missing clauses based on *document_type* template.

        Args:
            text: Full document text.
            document_type: e.g. ``"contract"``, ``"invoice"``, ``"proposal"``.

        Returns:
            List of ``MissingClause`` for clauses not found in the text.
        """
        templates = _TEMPLATES.get(document_type.lower())
        if templates is None:
            templates = _CONTRACT_CLAUSES + _INVOICE_CLAUSES

        text_lower = text.lower()
        missing: list[MissingClause] = []

        for tpl in templates:
            matches = sum(1 for kw in tpl.keywords if kw in text_lower)
            if matches < tpl.min_matches:
                missing.append(
                    MissingClause(
                        clause_name=tpl.name,
                        description=tpl.description,
                        severity=tpl.severity,
                        suggestion=tpl.suggestion,
                    )
                )

        logger.info(
            "Clause detection completed for '%s': %d missing out of %d checked",
            document_type,
            len(missing),
            len(templates),
        )
        return missing
