"""Field validation for extracted document fields."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.services.field_extractor import ExtractedFieldValue

logger = logging.getLogger(__name__)

DATE_PATTERNS = [
    (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),
    (r"^\d{2}/\d{2}/\d{4}$", "%d/%m/%Y"),
    (r"^\d{2}-\d{2}-\d{4}$", "%d-%m-%Y"),
    (r"^\d{1,2}/\d{1,2}/\d{4}$", "%d/%m/%Y"),
    (r"^\d{2}\.\d{2}\.\d{4}$", "%d.%m.%Y"),
    (r"^\d{4}/\d{2}/\d{2}$", "%Y/%m/%d"),
]

EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

PHONE_PATTERN = re.compile(
    r"^[\+]?[(]?[0-9]{1,4}[)]?[-\s./0-9]*$"
)

VND_MONEY_PATTERN = re.compile(
    r"^[\d.,]+\s*(VND|VNĐ|đ|vnd|VNĐ|₫)$|^(VND|VNĐ|đ|vnd|VNĐ|₫)\s*[\d.,]+$"
)


@dataclass
class ValidationResult:
    """Result of field validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(self.errors or self.warnings)


class FieldValidator:
    """Validates extracted fields against schema definitions.

    Performs type checking, required field checking, and format validation.
    """

    def validate(
        self, fields: list[ExtractedFieldValue], schema: dict[str, Any]
    ) -> ValidationResult:
        """Validate extracted fields against a schema.

        Args:
            fields: List of extracted field values.
            schema: The extraction schema with field definitions.

        Returns:
            ValidationResult with is_valid flag, errors, and warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        fields_def = schema.get("fields", schema.get("properties", {}))
        required_fields = schema.get("required", [])
        field_map = {f.field_name: f for f in fields}

        # Normalize fields_def: handle list format [{"name": ..., "type": ..., "required": ...}]
        if isinstance(fields_def, list):
            fields_dict: dict[str, dict] = {}
            for item in fields_def:
                if isinstance(item, dict) and "name" in item:
                    fields_dict[item["name"]] = item
                    if item.get("required") and item["name"] not in required_fields:
                        required_fields.append(item["name"])
            fields_def = fields_dict

        for field_name in required_fields:
            if field_name not in field_map:
                errors.append(f"Required field '{field_name}' is missing.")
            else:
                fv = field_map[field_name]
                if fv.field_value is None or fv.field_value.get("value") is None:
                    errors.append(f"Required field '{field_name}' has no value.")

        for field_name, field_def in fields_def.items():
            if not isinstance(field_def, dict):
                continue

            if field_name not in field_map:
                continue

            fv = field_map[field_name]
            value = fv.field_value.get("value") if fv.field_value else None

            if value is None:
                if field_name in required_fields:
                    errors.append(f"Field '{field_name}' value is null but is required.")
                continue

            field_type = field_def.get("type", "string")
            type_errors = self._validate_type(field_name, value, field_type)
            errors.extend(type_errors)

            format_errors, format_warnings = self._validate_format(
                field_name, value, field_def
            )
            errors.extend(format_errors)
            warnings.extend(format_warnings)

            if fv.confidence < 0.5 and fv.confidence > 0:
                warnings.append(
                    f"Field '{field_name}' has low confidence ({fv.confidence:.2f})."
                )

        extracted_names = {f.field_name for f in fields}
        for field_name in fields_def:
            if field_name not in extracted_names:
                warnings.append(f"Field '{field_name}' defined in schema but not extracted.")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _validate_type(
        self, field_name: str, value: Any, expected_type: str
    ) -> list[str]:
        """Validate field value type."""
        errors: list[str] = []

        if expected_type == "string":
            if not isinstance(value, str):
                errors.append(
                    f"Field '{field_name}' expected string, got {type(value).__name__}."
                )

        elif expected_type in ("number", "float"):
            if isinstance(value, str):
                cleaned = value.replace(",", "").replace(" ", "")
                cleaned = re.sub(r"[^\d.\-]", "", cleaned)
                try:
                    float(cleaned)
                except ValueError:
                    errors.append(
                        f"Field '{field_name}' expected number, got non-numeric string '{value}'."
                    )
            elif not isinstance(value, (int, float)):
                errors.append(
                    f"Field '{field_name}' expected number, got {type(value).__name__}."
                )

        elif expected_type == "integer":
            if isinstance(value, str):
                cleaned = value.replace(",", "").replace(" ", "")
                try:
                    int(float(cleaned))
                except ValueError:
                    errors.append(
                        f"Field '{field_name}' expected integer, got non-numeric string '{value}'."
                    )
            elif isinstance(value, float):
                if value != int(value):
                    errors.append(
                        f"Field '{field_name}' expected integer, got float {value}."
                    )
            elif not isinstance(value, int):
                errors.append(
                    f"Field '{field_name}' expected integer, got {type(value).__name__}."
                )

        elif expected_type == "boolean":
            if not isinstance(value, bool):
                errors.append(
                    f"Field '{field_name}' expected boolean, got {type(value).__name__}."
                )

        elif expected_type == "date":
            if not isinstance(value, str):
                errors.append(
                    f"Field '{field_name}' expected date string, got {type(value).__name__}."
                )

        return errors

    def _validate_format(
        self, field_name: str, value: Any, field_def: dict[str, Any]
    ) -> tuple[list[str], list[str]]:
        """Validate field format (dates, emails, phones, etc.)."""
        errors: list[str] = []
        warnings: list[str] = []

        if not isinstance(value, str):
            return errors, warnings

        field_format = field_def.get("format", "")
        field_type = field_def.get("type", "")

        if field_format == "date" or field_type == "date":
            if not self._is_valid_date(value):
                errors.append(
                    f"Field '{field_name}' has invalid date format: '{value}'."
                )

        elif field_format == "email":
            if not EMAIL_PATTERN.match(value):
                errors.append(
                    f"Field '{field_name}' has invalid email format: '{value}'."
                )

        elif field_format == "phone":
            if not PHONE_PATTERN.match(value):
                errors.append(
                    f"Field '{field_name}' has invalid phone format: '{value}'."
                )
            elif len(re.sub(r"[^\d]", "", value)) < 8:
                warnings.append(
                    f"Field '{field_name}' phone number seems too short: '{value}'."
                )

        elif field_format == "currency" or field_def.get("currency"):
            if not self._is_valid_currency(value):
                warnings.append(
                    f"Field '{field_name}' may have invalid currency format: '{value}'."
                )

        pattern = field_def.get("pattern")
        if pattern and isinstance(value, str):
            if not re.match(pattern, value):
                errors.append(
                    f"Field '{field_name}' does not match pattern '{pattern}': '{value}'."
                )

        min_val = field_def.get("minimum")
        max_val = field_def.get("maximum")
        if isinstance(value, (int, float)):
            if min_val is not None and value < min_val:
                errors.append(
                    f"Field '{field_name}' value {value} is below minimum {min_val}."
                )
            if max_val is not None and value > max_val:
                errors.append(
                    f"Field '{field_name}' value {value} is above maximum {max_val}."
                )

        max_length = field_def.get("maxLength")
        if max_length and isinstance(value, str) and len(value) > max_length:
            warnings.append(
                f"Field '{field_name}' length {len(value)} exceeds maxLength {max_length}."
            )

        return errors, warnings

    def _is_valid_date(self, value: str) -> bool:
        """Check if a string is a valid date."""
        for pattern, fmt in DATE_PATTERNS:
            if re.match(pattern, value):
                try:
                    datetime.strptime(value, fmt)
                    return True
                except ValueError:
                    continue
        try:
            datetime.fromisoformat(value)
            return True
        except (ValueError, TypeError):
            return False

    def _is_valid_currency(self, value: str) -> bool:
        """Check if a string looks like a valid currency amount."""
        if not isinstance(value, str):
            return isinstance(value, (int, float))

        cleaned = re.sub(r"[\s,._]", "", value)
        cleaned = re.sub(r"(VND|VNĐ|vnd|đ|₫|USD|usd|\$)", "", cleaned).strip()
        try:
            float(cleaned)
            return True
        except ValueError:
            return False
