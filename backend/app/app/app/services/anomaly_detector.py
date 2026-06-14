"""Statistical anomaly detection for extracted document fields."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_NORMS: dict[str, dict[str, float]] = {
    "contract": {
        "total_value": 5_000_000_000,
        "duration_months": 24,
        "penalty_percentage": 10,
        "advance_payment_percentage": 30,
    },
    "invoice": {
        "total_amount": 500_000_000,
        "tax_rate": 10,
        "line_items_count": 10,
        "discount_percentage": 5,
    },
    "proposal": {
        "total_budget": 3_000_000_000,
        "timeline_months": 12,
        "team_size": 10,
    },
}

_NORMS_STD: dict[str, dict[str, float]] = {
    "contract": {
        "total_value": 8_000_000_000,
        "duration_months": 18,
        "penalty_percentage": 8,
        "advance_payment_percentage": 20,
    },
    "invoice": {
        "total_amount": 1_000_000_000,
        "tax_rate": 2,
        "line_items_count": 15,
        "discount_percentage": 5,
    },
    "proposal": {
        "total_budget": 5_000_000_000,
        "timeline_months": 8,
        "team_size": 8,
    },
}

_NUMERIC_RE = re.compile(r"^[\d.,]+$")
_VND_RE = re.compile(r"^[\d.,]+\s*(?:VND|VNĐ|đ|triệu|tỷ)?$", re.IGNORECASE)


@dataclass(frozen=True)
class Anomaly:
    """A detected field value anomaly."""

    field_name: str
    value: object
    expected_range: str
    deviation: float
    severity: str


class AnomalyDetector:
    """Detects statistical outliers in extracted document fields.

    Uses a z-score approach (>2σ flagged as anomaly) against historical
    norms per document type.
    """

    _DEVIATION_SEVERITY_THRESHOLD = {
        3.0: "high",
        2.0: "medium",
    }

    def detect(
        self,
        fields: list[dict],
        document_type: str | None = None,
    ) -> list[Anomaly]:
        """Analyse *fields* for statistical outliers.

        Each field dict is expected to have at least:
        ``field_name``, ``field_value`` (JSONB dict or primitive).

        Args:
            fields: Extracted field dicts from the database or extraction step.
            document_type: Optional type key into the norms table.

        Returns:
            List of ``Anomaly`` objects sorted by deviation descending.
        """
        if not fields:
            return []

        doc_type = (document_type or "contract").lower()
        norms = _NORMS.get(doc_type, {})
        norms_std = _NORMS_STD.get(doc_type, {})

        if not norms:
            logger.debug("No historical norms for document type '%s'", doc_type)
            return []

        anomalies: list[Anomaly] = []

        for fld in fields:
            field_name = fld.get("field_name", "")
            field_value = fld.get("field_value")

            if field_name not in norms:
                continue

            numeric_val = self._to_numeric(field_value)
            if numeric_val is None:
                continue

            expected_mean = norms[field_name]
            std = norms_std.get(field_name, expected_mean * 0.5)

            if std == 0:
                continue

            z_score = abs(numeric_val - expected_mean) / std

            if z_score >= 2.0:
                severity = "high" if z_score >= 3.0 else "medium"
                half_range = 2 * std
                low = max(0, expected_mean - half_range)
                high = expected_mean + half_range

                anomalies.append(
                    Anomaly(
                        field_name=field_name,
                        value=numeric_val,
                        expected_range=f"{low:,.0f} – {high:,.0f}",
                        deviation=round(z_score, 2),
                        severity=severity,
                    )
                )

        anomalies.sort(key=lambda a: a.deviation, reverse=True)
        logger.info("Anomaly detection completed: %d anomalies found", len(anomalies))
        return anomalies

    @staticmethod
    def _to_numeric(value: object) -> float | None:
        """Attempt to extract a float from a field value."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict):
            for key in ("value", "amount", "number", "total"):
                if key in value:
                    return AnomalyDetector._to_numeric(value[key])
            return None
        if isinstance(value, str):
            cleaned = re.sub(r"[^\d.,\-]", "", value)
            if not cleaned:
                return None
            cleaned = cleaned.replace(",", "")
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None
