"""Tests for ChecklistGenerator — checklist generation from risks/clauses/anomalies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.services.checklist_generator import ChecklistGenerator, ChecklistItem


@pytest.fixture()
def generator() -> ChecklistGenerator:
    return ChecklistGenerator()


@dataclass(frozen=True)
class FakeRisk:
    title: str
    severity: str
    category: str = "financial"


@dataclass(frozen=True)
class FakeMissingClause:
    clause_name: str
    description: str
    severity: str
    suggestion: str


@dataclass(frozen=True)
class FakeAnomaly:
    field_name: str
    value: Any
    expected_range: str
    deviation: float
    severity: str


class TestChecklistFromRisks:
    """Test checklist generation from risk items."""

    def test_single_risk(self, generator: ChecklistGenerator) -> None:
        risks = [FakeRisk(title="High-value amount detected", severity="high")]
        items = generator.generate(risks, [], [])
        assert len(items) == 1
        assert "[RISK]" in items[0].description
        assert items[0].severity == "high"
        assert items[0].category == "financial"

    def test_risk_action_high_value(self, generator: ChecklistGenerator) -> None:
        risks = [FakeRisk(title="High-value financial amount detected", severity="high")]
        items = generator.generate(risks, [], [])
        assert "finance team" in items[0].suggested_action.lower()

    def test_risk_action_missing_payment(self, generator: ChecklistGenerator) -> None:
        risks = [FakeRisk(title="Missing payment terms", severity="high")]
        items = generator.generate(risks, [], [])
        assert "payment" in items[0].suggested_action.lower()

    def test_risk_action_penalty(self, generator: ChecklistGenerator) -> None:
        risks = [FakeRisk(title="Unusually high penalty percentage", severity="medium")]
        items = generator.generate(risks, [], [])
        assert "penalty" in items[0].suggested_action.lower()

    def test_risk_action_deadline(self, generator: ChecklistGenerator) -> None:
        risks = [FakeRisk(title="Short deadline detected", severity="medium")]
        items = generator.generate(risks, [], [])
        assert "deadline" in items[0].suggested_action.lower()

    def test_risk_action_signature(self, generator: ChecklistGenerator) -> None:
        risks = [FakeRisk(title="Missing signature section", severity="medium")]
        items = generator.generate(risks, [], [])
        assert "signature" in items[0].suggested_action.lower()

    def test_risk_action_expired(self, generator: ChecklistGenerator) -> None:
        risks = [FakeRisk(title="Expired date reference found", severity="critical")]
        items = generator.generate(risks, [], [])
        assert "expired" in items[0].suggested_action.lower()

    def test_risk_action_low_confidence(self, generator: ChecklistGenerator) -> None:
        risks = [FakeRisk(title="Low-confidence extraction: total_amount", severity="medium")]
        items = generator.generate(risks, [], [])
        assert "verify" in items[0].suggested_action.lower()

    def test_due_days_by_severity(self, generator: ChecklistGenerator) -> None:
        risks = [
            FakeRisk(title="Critical risk", severity="critical"),
            FakeRisk(title="High risk", severity="high"),
            FakeRisk(title="Medium risk", severity="medium"),
            FakeRisk(title="Low risk", severity="low"),
        ]
        items = generator.generate(risks, [], [])
        by_severity = {item.severity: item.due_days for item in items}
        assert by_severity["critical"] < by_severity["high"]
        assert by_severity["high"] < by_severity["medium"]
        assert by_severity["medium"] < by_severity["low"]


class TestChecklistFromMissingClauses:
    """Test checklist generation from missing clause items."""

    def test_single_missing_clause(self, generator: ChecklistGenerator) -> None:
        clauses = [
            FakeMissingClause(
                clause_name="payment_terms",
                description="Payment terms and conditions",
                severity="critical",
                suggestion="Specify payment amounts.",
            )
        ]
        items = generator.generate([], clauses, [])
        assert len(items) == 1
        assert "[MISSING CLAUSE]" in items[0].description
        assert items[0].category == "compliance"
        assert items[0].suggested_action == "Specify payment amounts."

    def test_multiple_missing_clauses(self, generator: ChecklistGenerator) -> None:
        clauses = [
            FakeMissingClause("payment_terms", "Payment terms", "critical", "Add payment terms."),
            FakeMissingClause("dispute_resolution", "Dispute resolution", "medium", "Add dispute clause."),
        ]
        items = generator.generate([], clauses, [])
        assert len(items) == 2


class TestChecklistFromAnomalies:
    """Test checklist generation from anomaly items."""

    def test_single_anomaly(self, generator: ChecklistGenerator) -> None:
        anomalies = [
            FakeAnomaly(
                field_name="total_value",
                value=50_000_000_000,
                expected_range="0 – 21,000,000,000",
                deviation=4.5,
                severity="high",
            )
        ]
        items = generator.generate([], [], anomalies)
        assert len(items) == 1
        assert "[ANOMALY]" in items[0].description
        assert items[0].category == "operational"
        assert "total_value" in items[0].description

    def test_anomaly_suggested_action(self, generator: ChecklistGenerator) -> None:
        anomalies = [
            FakeAnomaly("total_value", 100, "0 – 50", 3.0, "high")
        ]
        items = generator.generate([], [], anomalies)
        assert "verify" in items[0].suggested_action.lower()


class TestDeduplication:
    """Test that duplicate checklist items are removed."""

    def test_duplicate_risks_deduplicated(self, generator: ChecklistGenerator) -> None:
        risks = [
            FakeRisk(title="High-value amount detected", severity="high"),
            FakeRisk(title="High-value amount detected", severity="high"),
        ]
        items = generator.generate(risks, [], [])
        assert len(items) == 1

    def test_different_severities_deduplicated_same_description(self, generator: ChecklistGenerator) -> None:
        """Dedup key is category:description — same title produces same description, so deduped."""
        risks = [
            FakeRisk(title="Some risk", severity="high"),
            FakeRisk(title="Some risk", severity="low"),
        ]
        items = generator.generate(risks, [], [])
        # Same title → same "[RISK] Some risk" description → deduplicated
        assert len(items) == 1

    def test_different_descriptions_not_deduplicated(self, generator: ChecklistGenerator) -> None:
        risks = [
            FakeRisk(title="Risk A", severity="high"),
            FakeRisk(title="Risk B", severity="high"),
        ]
        items = generator.generate(risks, [], [])
        assert len(items) == 2


class TestPrioritySorting:
    """Test that checklist items are sorted by priority."""

    def test_critical_before_high(self, generator: ChecklistGenerator) -> None:
        risks = [
            FakeRisk(title="High risk", severity="high"),
            FakeRisk(title="Critical risk", severity="critical"),
        ]
        items = generator.generate(risks, [], [])
        assert items[0].severity == "critical"
        assert items[1].severity == "high"

    def test_same_severity_sorted_by_due_days(self, generator: ChecklistGenerator) -> None:
        clauses = [
            FakeMissingClause("a", "desc A", "medium", "action A"),
            FakeMissingClause("b", "desc B", "medium", "action B"),
        ]
        items = generator.generate([], clauses, [])
        assert len(items) == 2
        # Both should have same due_days (7 for medium), so order preserved
        assert all(item.due_days == 7 for item in items)


class TestEmptyInputs:
    """Test checklist generation with empty inputs."""

    def test_all_empty_returns_empty(self, generator: ChecklistGenerator) -> None:
        items = generator.generate([], [], [])
        assert len(items) == 0

    def test_mixed_inputs(self, generator: ChecklistGenerator) -> None:
        risks = [FakeRisk(title="Risk 1", severity="high")]
        clauses = [
            FakeMissingClause("clause_1", "desc", "critical", "action")
        ]
        anomalies = [FakeAnomaly("field", 100, "0-50", 3.0, "medium")]
        items = generator.generate(risks, clauses, anomalies)
        assert len(items) == 3
        categories = {item.category for item in items}
        assert "financial" in categories
        assert "compliance" in categories
        assert "operational" in categories
