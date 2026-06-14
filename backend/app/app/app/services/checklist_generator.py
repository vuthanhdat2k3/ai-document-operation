"""Checklist generation from risks, missing clauses, and anomalies."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_SEVERITY_DUE_DAYS: dict[str, int] = {
    "critical": 1,
    "high": 3,
    "medium": 7,
    "low": 14,
    "info": 30,
}

_SEVERITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


@dataclass(frozen=True)
class ChecklistItem:
    """A single actionable checklist item derived from analysis."""

    description: str
    severity: str
    category: str
    suggested_action: str
    due_days: int


class ChecklistGenerator:
    """Generates prioritised action checklists from analysis results."""

    def generate(
        self,
        risks: list,
        missing_clauses: list,
        anomalies: list,
    ) -> list[ChecklistItem]:
        """Build a merged, deduplicated checklist from all analysis inputs.

        Args:
            risks: List of ``RiskItem`` objects.
            missing_clauses: List of ``MissingClause`` objects.
            anomalies: List of ``Anomaly`` objects.

        Returns:
            Sorted list of ``ChecklistItem`` (most urgent first).
        """
        items: list[ChecklistItem] = []

        items.extend(self._from_risks(risks))
        items.extend(self._from_missing_clauses(missing_clauses))
        items.extend(self._from_anomalies(anomalies))

        items = self._deduplicate(items)
        items.sort(key=lambda i: (_SEVERITY_ORDER.get(i.severity, 99), i.due_days))

        logger.info("Checklist generated: %d items", len(items))
        return items

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    def _from_risks(self, risks: list) -> list[ChecklistItem]:
        items: list[ChecklistItem] = []
        for r in risks:
            severity = getattr(r, "severity", "medium")
            items.append(
                ChecklistItem(
                    description=f"[RISK] {getattr(r, 'title', 'Unknown risk')}",
                    severity=severity,
                    category=getattr(r, "category", "general"),
                    suggested_action=self._risk_action(r),
                    due_days=_SEVERITY_DUE_DAYS.get(severity, 7),
                )
            )
        return items

    def _from_missing_clauses(self, missing: list) -> list[ChecklistItem]:
        items: list[ChecklistItem] = []
        for mc in missing:
            severity = getattr(mc, "severity", "medium")
            items.append(
                ChecklistItem(
                    description=f"[MISSING CLAUSE] {getattr(mc, 'clause_name', 'Unknown clause')}: {getattr(mc, 'description', '')}",
                    severity=severity,
                    category="compliance",
                    suggested_action=getattr(mc, "suggestion", "Add the missing clause to the document."),
                    due_days=_SEVERITY_DUE_DAYS.get(severity, 7),
                )
            )
        return items

    def _from_anomalies(self, anomalies: list) -> list[ChecklistItem]:
        items: list[ChecklistItem] = []
        for a in anomalies:
            severity = getattr(a, "severity", "medium")
            field_name = getattr(a, "field_name", "unknown")
            value = getattr(a, "value", "N/A")
            expected = getattr(a, "expected_range", "N/A")
            items.append(
                ChecklistItem(
                    description=(
                        f"[ANOMALY] Field '{field_name}' value "
                        f"({value}) outside expected range ({expected})"
                    ),
                    severity=severity,
                    category="operational",
                    suggested_action=(
                        f"Verify the value of '{field_name}' — "
                        f"current value deviates significantly from historical norms."
                    ),
                    due_days=_SEVERITY_DUE_DAYS.get(severity, 7),
                )
            )
        return items

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _risk_action(risk) -> str:
        category = getattr(risk, "category", "")
        title = getattr(risk, "title", "").lower()

        if "high-value" in title:
            return "Review the high-value amount with the finance team and verify correctness."
        if "missing payment" in title:
            return "Add explicit payment terms including amount, schedule, and method."
        if "penalty" in title:
            return "Review penalty clause for reasonableness and legal compliance."
        if "deadline" in title:
            return "Negotiate a more reasonable deadline or prepare expedited execution plan."
        if "signature" in title:
            return "Add proper signature blocks with authorized signatory information."
        if "expired" in title:
            return "Update the expired date or confirm document validity with counterparties."
        if "low-confidence" in title:
            return "Manually verify the extracted field value against the source document."
        return f"Investigate the {category} risk and take appropriate corrective action."

    @staticmethod
    def _deduplicate(items: list[ChecklistItem]) -> list[ChecklistItem]:
        seen: set[str] = set()
        unique: list[ChecklistItem] = []
        for item in items:
            key = f"{item.category}:{item.description}"
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique
