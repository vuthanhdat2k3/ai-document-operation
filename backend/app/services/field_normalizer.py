"""Field normalizer for standardizing extracted field values."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from app.services.field_extractor import ExtractedFieldValue

logger = logging.getLogger(__name__)

DATE_FORMATS = [
    ("%d/%m/%Y", re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")),
    ("%d-%m-%Y", re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$")),
    ("%d.%m.%Y", re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}$")),
    ("%Y/%m/%d", re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$")),
    ("%Y-%m-%d", re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")),
    ("%d/%m/%y", re.compile(r"^\d{1,2}/\d{1,2}/\d{2}$")),
    ("%m/%d/%Y", re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")),
]

CURRENCY_SYMBOLS = {
    "vnd": "VND",
    "vnđ": "VND",
    "đ": "VND",
    "₫": "VND",
    "dong": "VND",
    "vn dong": "VND",
    "việt nam đồng": "VND",
    "usd": "USD",
    "$": "USD",
    "dollar": "USD",
    "dollar us": "USD",
}


class FieldNormalizer:
    """Normalizes extracted field values to consistent formats.

    Handles date, currency, phone number, and address normalization.
    """

    def normalize(self, fields: list[ExtractedFieldValue]) -> list[ExtractedFieldValue]:
        """Normalize all extracted fields.

        Args:
            fields: List of extracted field values.

        Returns:
            New list with normalized field values.
        """
        normalized: list[ExtractedFieldValue] = []

        for fv in fields:
            value = fv.field_value.get("value") if fv.field_value else None
            if value is None:
                normalized.append(fv)
                continue

            new_value = self._normalize_value(fv.field_name, value, fv.field_value)
            if new_value != fv.field_value:
                normalized.append(
                    ExtractedFieldValue(
                        field_name=fv.field_name,
                        field_value=new_value,
                        raw_text=fv.raw_text,
                        confidence=fv.confidence,
                        page_number=fv.page_number,
                    )
                )
            else:
                normalized.append(fv)

        return normalized

    def _normalize_value(
        self, field_name: str, value: Any, field_value: dict[str, Any]
    ) -> dict[str, Any]:
        """Normalize a single field value based on its name and content."""
        name_lower = field_name.lower()
        result = dict(field_value)

        if not isinstance(value, str):
            return field_value

        if any(kw in name_lower for kw in ("date", "ngày", "ngay", "time", "thời")):
            normalized_date = self._normalize_date(value)
            if normalized_date:
                result["value"] = normalized_date
                result["original_format"] = value
                return result

        if any(kw in name_lower for kw in ("amount", "tiền", "tien", "total", "giá", "gia", "cost", "price", "fee", "phí", "phi")):
            normalized_currency = self._normalize_currency(value)
            if normalized_currency is not None:
                result.update(normalized_currency)
                result["original_text"] = value
                return result

        if any(kw in name_lower for kw in ("phone", "điện thoại", "dien thoai", "sđt", "sdt", "tel", "mobile", "hotline")):
            normalized_phone = self._normalize_phone(value)
            if normalized_phone:
                result["value"] = normalized_phone
                result["original_format"] = value
                return result

        if any(kw in name_lower for kw in ("email", "mail")):
            normalized_email = value.strip().lower()
            if normalized_email != value:
                result["value"] = normalized_email
                return result

        if any(kw in name_lower for kw in ("address", "địa chỉ", "dia chi")):
            normalized_addr = self._normalize_address(value)
            if normalized_addr != value:
                result["value"] = normalized_addr
                return result

        if any(kw in name_lower for kw in ("tax", "thuế", "thue", "mst")):
            normalized_tax = re.sub(r"[^\d\-]", "", value)
            if normalized_tax and normalized_tax != value:
                result["value"] = normalized_tax
                result["original_format"] = value
                return result

        return field_value

    def _normalize_date(self, value: str) -> str | None:
        """Normalize date to ISO 8601 format (YYYY-MM-DD).

        Args:
            value: Raw date string.

        Returns:
            ISO 8601 date string, or None if parsing fails.
        """
        cleaned = value.strip()

        for fmt, pattern in DATE_FORMATS:
            if pattern.match(cleaned):
                try:
                    dt = datetime.strptime(cleaned, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue

        cleaned_dot = cleaned.replace(".", "/").replace("-", "/")
        for fmt, _ in DATE_FORMATS:
            try:
                dt = datetime.strptime(cleaned_dot, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        vn_match = re.match(
            r"(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})",
            cleaned,
            re.IGNORECASE,
        )
        if vn_match:
            day, month, year = vn_match.groups()
            try:
                dt = datetime(int(year), int(month), int(day))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        try:
            dt = datetime.fromisoformat(cleaned)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass

        return None

    def _normalize_currency(self, value: str) -> dict[str, Any] | None:
        """Normalize currency value.

        Args:
            value: Raw currency string.

        Returns:
            Dict with 'value' (numeric), 'currency', and 'formatted', or None.
        """
        cleaned = value.strip()

        currency = "VND"
        for symbol, code in CURRENCY_SYMBOLS.items():
            if symbol in cleaned.lower():
                currency = code
                break

        numeric_str = re.sub(r"[^\d.,\-]", "", cleaned)
        if not numeric_str:
            return None

        if "," in numeric_str and "." in numeric_str:
            if numeric_str.rindex(",") > numeric_str.rindex("."):
                numeric_str = numeric_str.replace(".", "").replace(",", ".")
            else:
                numeric_str = numeric_str.replace(",", "")
        elif "," in numeric_str:
            parts = numeric_str.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                numeric_str = numeric_str.replace(",", ".")
            else:
                numeric_str = numeric_str.replace(",", "")

        try:
            amount = float(numeric_str)
        except ValueError:
            return None

        if currency == "VND":
            amount = round(amount, 0)
            formatted = f"{amount:,.0f} VND".replace(",", ".")
        else:
            formatted = f"{amount:,.2f} {currency}"

        return {
            "value": amount,
            "currency": currency,
            "formatted": formatted,
        }

    def _normalize_phone(self, value: str) -> str | None:
        """Normalize phone number.

        Args:
            value: Raw phone string.

        Returns:
            Normalized phone string, or None if invalid.
        """
        cleaned = value.strip()

        digits = re.sub(r"[^\d\+]", "", cleaned)
        if not digits or len(re.sub(r"[^\d]", "", digits)) < 8:
            return None

        if digits.startswith("+84"):
            local = "0" + digits[3:]
        elif digits.startswith("84") and len(digits) >= 11:
            local = "0" + digits[2:]
        elif digits.startswith("0"):
            local = digits
        else:
            local = digits

        local_digits = re.sub(r"[^\d]", "", local)

        if len(local_digits) == 10 and local_digits.startswith("0"):
            return f"{local_digits[:4]} {local_digits[4:7]} {local_digits[7:]}"
        elif len(local_digits) == 9 and not local_digits.startswith("0"):
            return f"0{local_digits[:3]} {local_digits[3:6]} {local_digits[6:]}"

        return local_digits

    def _normalize_address(self, value: str) -> str:
        """Normalize address string.

        Args:
            value: Raw address string.

        Returns:
            Cleaned and standardized address string.
        """
        addr = value.strip()

        addr = re.sub(r"\s+", " ", addr)

        replacements = {
            r"\bTP\.\s*": "TP. ",
            r"\bTp\.\s*": "TP. ",
            r"\btp\.\s*": "TP. ",
            r"\bQ\.\s*": "Q. ",
            r"\bq\.\s*": "Q. ",
            r"\bP\.\s*": "P. ",
            r"\bp\.\s*": "P. ",
            r"\bTX\.\s*": "TX. ",
            r"\bhuyện\s": "H. ",
            r"\btỉnh\s": "",
        }

        for pattern, replacement in replacements.items():
            addr = re.sub(pattern, replacement, addr, flags=re.IGNORECASE)

        addr = addr.rstrip(".,; ")

        return addr
