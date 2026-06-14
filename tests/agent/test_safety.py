"""Tests for safety controls: LoopDetector, CostTracker, iteration/time guards."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app.agents.safety import (
    CostRecord,
    CostTracker,
    LoopDetector,
    MaxIterationGuard,
    WallClockGuard,
)


class TestLoopDetector:
    """Loop detection for repeated tool calls."""

    def test_no_loop_initial(self) -> None:
        ld = LoopDetector(max_repeats=3)
        assert ld.record_call("search", {"query": "test"}) is False

    def test_loop_detected_at_threshold(self) -> None:
        ld = LoopDetector(max_repeats=3)
        for _ in range(2):
            assert ld.record_call("search", {"query": "test"}) is False
        assert ld.record_call("search", {"query": "test"}) is True

    def test_different_args_no_loop(self) -> None:
        ld = LoopDetector(max_repeats=3)
        for i in range(5):
            assert ld.record_call("search", {"query": f"query_{i}"}) is False

    def test_different_tools_no_loop(self) -> None:
        ld = LoopDetector(max_repeats=3)
        for _ in range(2):
            assert ld.record_call("tool_a", {"x": 1}) is False
            assert ld.record_call("tool_b", {"x": 1}) is False
        # third time for tool_a triggers loop
        assert ld.record_call("tool_a", {"x": 1}) is True

    def test_is_loop_without_record(self) -> None:
        ld = LoopDetector(max_repeats=3)
        assert ld.is_loop("search", {"q": "test"}) is False
        ld.record_call("search", {"q": "test"})
        ld.record_call("search", {"q": "test"})
        ld.record_call("search", {"q": "test"})
        assert ld.is_loop("search", {"q": "test"}) is True

    def test_is_loop_does_not_record(self) -> None:
        ld = LoopDetector(max_repeats=3)
        ld.record_call("search", {"q": "test"})
        ld.record_call("search", {"q": "test"})
        # is_loop should not increment the count
        ld.is_loop("search", {"q": "test"})
        # count is still 2, so calling is_loop again should still return False (2 < 3)
        assert ld.is_loop("search", {"q": "test"}) is False
        # but a real record_call makes it 3, triggering loop
        assert ld.record_call("search", {"q": "test"}) is True

    def test_reset_clears_state(self) -> None:
        ld = LoopDetector(max_repeats=2)
        ld.record_call("search", {"q": "test"})
        ld.record_call("search", {"q": "test"})
        assert ld.record_call("search", {"q": "test"}) is True
        ld.reset()
        assert ld.record_call("search", {"q": "test"}) is False

    def test_custom_max_repeats(self) -> None:
        ld = LoopDetector(max_repeats=5)
        for _ in range(4):
            assert ld.record_call("x", {}) is False
        assert ld.record_call("x", {}) is True

    def test_hash_deterministic(self) -> None:
        h1 = LoopDetector._hash_call("search", {"q": "test"})
        h2 = LoopDetector._hash_call("search", {"q": "test"})
        assert h1 == h2

    def test_hash_different_for_different_args(self) -> None:
        h1 = LoopDetector._hash_call("search", {"q": "a"})
        h2 = LoopDetector._hash_call("search", {"q": "b"})
        assert h1 != h2


class TestCostTracker:
    """Token and cost tracking."""

    def test_initial_state(self) -> None:
        ct = CostTracker()
        assert ct.total_tokens == 0
        assert ct.total_cost_usd == 0.0
        assert ct.records == []

    def test_record_creates_cost_record(self) -> None:
        ct = CostTracker()
        rec = ct.record("retrieve", iteration=0, prompt_tokens=100, completion_tokens=50)
        assert isinstance(rec, CostRecord)
        assert rec.step_name == "retrieve"
        assert rec.total_tokens == 150

    def test_accumulates_tokens(self) -> None:
        ct = CostTracker()
        ct.record("step1", iteration=0, prompt_tokens=100, completion_tokens=50)
        ct.record("step2", iteration=1, prompt_tokens=200, completion_tokens=100)
        assert ct.total_tokens == 450

    def test_accumulates_cost(self) -> None:
        ct = CostTracker()
        ct.record("step1", iteration=0, estimated_cost_usd=0.05)
        ct.record("step2", iteration=1, estimated_cost_usd=0.10)
        assert ct.total_cost_usd == pytest.approx(0.15)

    def test_budget_exceeded_by_cost(self) -> None:
        ct = CostTracker(max_cost_usd=1.0)
        ct.record("step1", iteration=0, estimated_cost_usd=0.5)
        assert ct.is_budget_exceeded() is False
        ct.record("step2", iteration=1, estimated_cost_usd=0.6)
        assert ct.is_budget_exceeded() is True

    def test_budget_exceeded_by_tokens(self) -> None:
        ct = CostTracker(max_tokens=1000)
        ct.record("step1", iteration=0, prompt_tokens=600, completion_tokens=300)
        assert ct.is_budget_exceeded() is False
        ct.record("step2", iteration=1, prompt_tokens=200, completion_tokens=0)
        assert ct.is_budget_exceeded() is True

    def test_budget_not_exceeded(self) -> None:
        ct = CostTracker(max_cost_usd=10.0, max_tokens=1_000_000)
        ct.record("step1", iteration=0, prompt_tokens=100, completion_tokens=50, estimated_cost_usd=0.01)
        assert ct.is_budget_exceeded() is False

    def test_summary_structure(self) -> None:
        ct = CostTracker()
        ct.record("step1", iteration=0, prompt_tokens=100, completion_tokens=50, estimated_cost_usd=0.05, duration_ms=200)
        summary = ct.summary()
        assert summary["total_tokens"] == 150
        assert summary["total_cost_usd"] == pytest.approx(0.05)
        assert summary["budget_exceeded"] is False
        assert len(summary["steps"]) == 1
        assert summary["steps"][0]["step"] == "step1"

    def test_summary_empty(self) -> None:
        ct = CostTracker()
        summary = ct.summary()
        assert summary["total_tokens"] == 0
        assert summary["steps"] == []

    def test_cost_record_fields(self) -> None:
        rec = CostRecord(
            step_name="test",
            iteration=5,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.03,
            duration_ms=500,
        )
        assert rec.step_name == "test"
        assert rec.iteration == 5
        assert rec.prompt_tokens == 100
        assert rec.completion_tokens == 50
        assert rec.total_tokens == 150
        assert rec.estimated_cost_usd == 0.03
        assert rec.duration_ms == 500


class TestMaxIterationGuard:
    """Iteration limit enforcement."""

    def test_not_exceeded_initially(self) -> None:
        guard = MaxIterationGuard(max_iterations=10)
        assert guard.should_stop(0) is False

    def test_not_exceeded_below_limit(self) -> None:
        guard = MaxIterationGuard(max_iterations=10)
        assert guard.should_stop(9) is False

    def test_exceeded_at_limit(self) -> None:
        guard = MaxIterationGuard(max_iterations=10)
        assert guard.should_stop(10) is True

    def test_exceeded_above_limit(self) -> None:
        guard = MaxIterationGuard(max_iterations=10)
        assert guard.should_stop(15) is True

    def test_remaining_full(self) -> None:
        guard = MaxIterationGuard(max_iterations=10)
        assert guard.remaining(0) == 10

    def test_remaining_partial(self) -> None:
        guard = MaxIterationGuard(max_iterations=10)
        assert guard.remaining(7) == 3

    def test_remaining_zero(self) -> None:
        guard = MaxIterationGuard(max_iterations=10)
        assert guard.remaining(10) == 0

    def test_remaining_negative_clamped(self) -> None:
        guard = MaxIterationGuard(max_iterations=10)
        assert guard.remaining(15) == 0

    def test_custom_limit(self) -> None:
        guard = MaxIterationGuard(max_iterations=3)
        assert guard.should_stop(2) is False
        assert guard.should_stop(3) is True


class TestWallClockGuard:
    """Wall-clock timeout enforcement."""

    def test_not_expired_before_start(self) -> None:
        guard = WallClockGuard(max_seconds=10)
        assert guard.is_expired() is False

    def test_not_expired_immediately_after_start(self) -> None:
        guard = WallClockGuard(max_seconds=10)
        guard.start()
        assert guard.is_expired() is False

    def test_expired_after_timeout(self) -> None:
        guard = WallClockGuard(max_seconds=0)
        guard.start()
        # With max_seconds=0, should expire immediately
        assert guard.is_expired() is True

    def test_elapsed_seconds_before_start(self) -> None:
        guard = WallClockGuard(max_seconds=10)
        assert guard.elapsed_seconds() == 0.0

    def test_elapsed_seconds_after_start(self) -> None:
        guard = WallClockGuard(max_seconds=10)
        guard.start()
        elapsed = guard.elapsed_seconds()
        assert elapsed >= 0.0
        assert elapsed < 1.0  # should be nearly instant

    def test_custom_timeout(self) -> None:
        guard = WallClockGuard(max_seconds=1)
        guard.start()
        assert guard.is_expired() is False
        # Wait enough for 1s timeout
        time.sleep(1.1)
        assert guard.is_expired() is True

    @patch("app.agents.safety.time.monotonic")
    def test_expired_with_mocked_time(self, mock_time: object) -> None:
        from unittest.mock import call

        mock_time.side_effect = [100.0, 401.0]  # start=100, check=401 (>300s limit)
        guard = WallClockGuard(max_seconds=300)
        guard.start()
        assert guard.is_expired() is True

    @patch("app.agents.safety.time.monotonic")
    def test_not_expired_with_mocked_time(self, mock_time: object) -> None:
        from unittest.mock import call

        mock_time.side_effect = [100.0, 200.0]  # start=100, check=200 (<300s limit)
        guard = WallClockGuard(max_seconds=300)
        guard.start()
        assert guard.is_expired() is False
