"""Safety controls: loop detection, cost tracking, and iteration guards."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CostRecord:
    """Token and cost accounting for a single step."""

    step_name: str
    iteration: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    duration_ms: int = 0


class CostTracker:
    """Track token usage and estimated cost per step.

    Accumulates records across the lifetime of an agent run so the
    caller can inspect per-step and aggregate costs.

    Args:
        max_cost_usd: Abort threshold for cumulative cost.
        max_tokens: Abort threshold for cumulative token count.
    """

    def __init__(
        self,
        max_cost_usd: float = 5.0,
        max_tokens: int = 500_000,
    ) -> None:
        self.max_cost_usd = max_cost_usd
        self.max_tokens = max_tokens
        self.records: list[CostRecord] = []
        self._total_tokens = 0
        self._total_cost = 0.0

    def record(
        self,
        step_name: str,
        iteration: int,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        estimated_cost_usd: float = 0.0,
        duration_ms: int = 0,
    ) -> CostRecord:
        """Record usage for a step and return the cost record."""
        total = prompt_tokens + completion_tokens
        rec = CostRecord(
            step_name=step_name,
            iteration=iteration,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            estimated_cost_usd=estimated_cost_usd,
            duration_ms=duration_ms,
        )
        self.records.append(rec)
        self._total_tokens += total
        self._total_cost += estimated_cost_usd
        return rec

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    def total_cost_usd(self) -> float:
        return self._total_cost

    def is_budget_exceeded(self) -> bool:
        """Return True if cumulative cost or tokens exceed thresholds."""
        return self._total_cost >= self.max_cost_usd or self._total_tokens >= self.max_tokens

    def summary(self) -> dict:
        """Return a summary dict of all recorded costs."""
        return {
            "total_tokens": self._total_tokens,
            "total_cost_usd": round(self._total_cost, 6),
            "max_cost_usd": self.max_cost_usd,
            "budget_exceeded": self.is_budget_exceeded(),
            "steps": [
                {
                    "step": r.step_name,
                    "iteration": r.iteration,
                    "tokens": r.total_tokens,
                    "cost_usd": round(r.estimated_cost_usd, 6),
                    "duration_ms": r.duration_ms,
                }
                for r in self.records
            ],
        }


class LoopDetector:
    """Detect repeated identical tool calls that indicate an agent loop.

    Tracks the hash of each (tool_name, arguments) pair. If the same
    call is seen ``max_repeats`` times, the detector signals a loop.

    Args:
        max_repeats: Number of identical calls before flagging a loop (default 3).
    """

    def __init__(self, max_repeats: int = 3) -> None:
        self.max_repeats = max_repeats
        self._call_hashes: dict[str, int] = {}

    @staticmethod
    def _hash_call(tool_name: str, arguments: dict) -> str:
        """Produce a deterministic hash for a tool invocation."""
        payload = json.dumps(
            {"tool": tool_name, "args": arguments},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def record_call(self, tool_name: str, arguments: dict) -> bool:
        """Record a tool call and return True if a loop is detected."""
        h = self._hash_call(tool_name, arguments)
        self._call_hashes[h] = self._call_hashes.get(h, 0) + 1
        count = self._call_hashes[h]
        if count >= self.max_repeats:
            logger.warning(
                "Loop detected: tool=%s args=%s seen %d times",
                tool_name,
                arguments,
                count,
            )
            return True
        return False

    def is_loop(self, tool_name: str, arguments: dict) -> bool:
        """Check if adding this call would trigger a loop (without recording)."""
        h = self._hash_call(tool_name, arguments)
        return self._call_hashes.get(h, 0) >= self.max_repeats

    def reset(self) -> None:
        """Clear all tracked calls."""
        self._call_hashes.clear()


class MaxIterationGuard:
    """Enforce a hard iteration limit on agent execution.

    Args:
        max_iterations: Maximum number of iterations allowed (default 10).
    """

    def __init__(self, max_iterations: int = 10) -> None:
        self.max_iterations = max_iterations

    def should_stop(self, current_iteration: int) -> bool:
        """Return True if the agent has exceeded the iteration limit."""
        exceeded = current_iteration >= self.max_iterations
        if exceeded:
            logger.warning(
                "MaxIterationGuard: iteration %d >= limit %d, forcing stop",
                current_iteration,
                self.max_iterations,
            )
        return exceeded

    def remaining(self, current_iteration: int) -> int:
        """Return remaining iterations (0 if exceeded)."""
        return max(0, self.max_iterations - current_iteration)


class WallClockGuard:
    """Enforce a wall-clock time limit on agent execution.

    Args:
        max_seconds: Maximum wall-clock seconds allowed (default 300).
    """

    def __init__(self, max_seconds: int = 300) -> None:
        self.max_seconds = max_seconds
        self._start_time: float | None = None

    def start(self) -> None:
        """Mark the start of execution."""
        self._start_time = time.monotonic()

    def is_expired(self) -> bool:
        """Return True if the wall-clock budget is exhausted."""
        if self._start_time is None:
            return False
        elapsed = time.monotonic() - self._start_time
        exceeded = elapsed >= self.max_seconds
        if exceeded:
            logger.warning(
                "WallClockGuard: elapsed %.1fs >= limit %ds",
                elapsed,
                self.max_seconds,
            )
        return exceeded

    def elapsed_seconds(self) -> float:
        """Return seconds elapsed since start."""
        if self._start_time is None:
            return 0.0
        return time.monotonic() - self._start_time
