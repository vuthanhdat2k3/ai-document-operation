"""Per-agent rate limiter — sliding window counter with optional Redis backend.

Tracks invocation counts per agent (and optionally per user) within a
configurable time window.  When the limit is exceeded, a
``RateLimitExceededError`` is raised.

Usage::

    limiter = get_rate_limiter()

    # Check before executing an agent
    try:
        limiter.check("doc-qa", user_id)
    except RateLimitExceededError:
        return 429

    # Or use async check
    await limiter.acquire("doc-qa", user_id)
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class RateLimitExceededError(Exception):
    """Raised when an agent's rate limit is exceeded."""

    def __init__(
        self,
        agent_name: str,
        limit: int,
        window_seconds: int,
        retry_after: float,
    ) -> None:
        self.agent_name = agent_name
        self.limit = limit
        self.window_seconds = window_seconds
        self.retry_after = retry_after
        super().__init__(
            f"Agent '{agent_name}' rate limit exceeded: {limit} calls "
            f"per {window_seconds}s. Retry after {retry_after:.1f}s."
        )


@dataclass
class RateLimitConfig:
    """Rate limit configuration for an agent.

    Attributes:
        max_calls: Maximum number of invocations in the window.
        window_seconds: Sliding window duration in seconds.
        per_user: If True, the limit applies per user (not globally for the agent).
    """

    max_calls: int = 60
    window_seconds: int = 60
    per_user: bool = False


class _SlidingWindowCounter:
    """In-memory sliding window counter per key."""

    def __init__(self) -> None:
        self._windows: dict[str, list[float]] = defaultdict(list)

    def _purge(self, key: str, window_seconds: int, now: float) -> None:
        cutoff = now - window_seconds
        self._windows[key] = [t for t in self._windows[key] if t > cutoff]

    def check(self, key: str, max_calls: int, window_seconds: int) -> tuple[bool, float]:
        """Check if the key is within rate limits.

        Returns:
            Tuple of ``(allowed, retry_after_seconds)``.
        """
        now = time.monotonic()
        self._purge(key, window_seconds, now)
        count = len(self._windows[key])
        if count >= max_calls:
            oldest = self._windows[key][0] if self._windows else now
            retry_after = max(0.0, (oldest + window_seconds) - now)
            return False, retry_after
        return True, 0.0

    def increment(self, key: str) -> None:
        """Record an invocation for the key."""
        self._windows[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        """Clear all records for a key."""
        self._windows.pop(key, None)


class RateLimiter:
    """Per-agent rate limiter.

    Supports both global-per-agent and per-user-per-agent limits.
    Uses an in-memory sliding window counter by default.
    """

    _instance: RateLimiter | None = None

    def __new__(cls) -> RateLimiter:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._default_config: dict[str, RateLimitConfig] = {}
            cls._instance._counter = _SlidingWindowCounter()
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_default_config"):
            self._default_config: dict[str, RateLimitConfig] = {}
        if not hasattr(self, "_counter"):
            self._counter = _SlidingWindowCounter()

    def set_config(self, agent_name: str, config: RateLimitConfig) -> None:
        """Set rate limit configuration for an agent.

        Args:
            agent_name: Agent identifier.
            config: Rate limit configuration.
        """
        self._default_config[agent_name] = config
        logger.info("Rate limit for %s: %d calls/%ds (per_user=%s)",
                     agent_name, config.max_calls, config.window_seconds, config.per_user)

    def get_config(self, agent_name: str) -> RateLimitConfig:
        """Get rate limit configuration for an agent.

        Returns the configured limit or a default (60 calls/min).
        """
        return self._default_config.get(agent_name, RateLimitConfig())

    def _make_key(self, agent_name: str, user_id: str | None, config: RateLimitConfig) -> str:
        if config.per_user and user_id:
            return f"{agent_name}:user:{user_id}"
        return f"{agent_name}:global"

    def check(self, agent_name: str, user_id: str | None = None) -> None:
        """Check rate limit for an agent, raising on exceed.

        Args:
            agent_name: Agent identifier.
            user_id: Optional user ID for per-user limits.

        Raises:
            RateLimitExceededError: If the limit is exceeded.
        """
        config = self.get_config(agent_name)
        key = self._make_key(agent_name, user_id, config)
        allowed, retry_after = self._counter.check(key, config.max_calls, config.window_seconds)
        if not allowed:
            raise RateLimitExceededError(agent_name, config.max_calls, config.window_seconds, retry_after)
        self._counter.increment(key)

    async def acquire(self, agent_name: str, user_id: str | None = None) -> None:
        """Async check — same as ``check()`` but awaitable for future Redis support."""
        self.check(agent_name, user_id)

    def reset(self, agent_name: str, user_id: str | None = None) -> None:
        """Reset rate limit counters for an agent.

        Args:
            agent_name: Agent identifier.
            user_id: If set, only reset the per-user counter.
        """
        config = self.get_config(agent_name)
        key = self._make_key(agent_name, user_id, config)
        self._counter.reset(key)
        logger.info("Rate limit reset for %s (key=%s)", agent_name, key)

    def status(self, agent_name: str, user_id: str | None = None) -> dict:
        """Get current rate limit status for an agent.

        Returns:
            Dict with ``allowed``, ``remaining``, ``reset_after``.
        """
        config = self.get_config(agent_name)
        key = self._make_key(agent_name, user_id, config)
        allowed, retry_after = self._counter.check(key, config.max_calls, config.window_seconds)
        return {
            "agent": agent_name,
            "user_id": user_id,
            "limit": config.max_calls,
            "window_seconds": config.window_seconds,
            "allowed": allowed,
            "remaining": config.max_calls - 1 if allowed else 0,  # approximate
            "retry_after_seconds": retry_after,
            "per_user": config.per_user,
        }


def get_rate_limiter() -> RateLimiter:
    """Return the singleton RateLimiter instance."""
    return RateLimiter()
