"""Cancellation token for cooperative agent execution cancellation.

Usage::

    token = CancelToken()

    # In a long-running graph loop:
    while True:
        token.check()  # raises CancelledError if cancelled
        ...

    # From another task/client:
    await token.cancel()
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class AgentCancelledError(asyncio.CancelledError):
    """Raised when an agent execution is cancelled via CancelToken.

    Distinct from ``asyncio.CancelledError`` so callers can distinguish
    between task-level cancellation and agent-level cancellation.
    """

    def __init__(self, session_id: str = "", reason: str = "Agent execution cancelled") -> None:
        self.session_id = session_id
        self.reason = reason
        super().__init__(f"[{session_id}] {reason}")


class CancelToken:
    """Cooperative cancellation token for agent graph execution.

    Thread-safe for async single-event-loop usage.  Multiple concurrent
    agents each get their own CancelToken.

    Usage::

        token = CancelToken()
        # Store token in a per-session registry
        token_registry[session_id] = token

        # In graph loop:
        token.check()

        # From cancel API:
        token_registry[session_id].cancel()
    """

    def __init__(self) -> None:
        self._cancelled = False
        self._reason: str = ""

    def cancel(self, reason: str = "Cancelled by user") -> None:
        """Request cancellation.  Idempotent."""
        self._cancelled = True
        self._reason = reason
        logger.info("CancelToken cancelled: %s", reason)

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled

    @property
    def reason(self) -> str:
        return self._reason

    def check(self) -> None:
        """Raise ``AgentCancelledError`` if cancelled.

        Call this periodically inside the agent graph loop.
        """
        if self._cancelled:
            raise AgentCancelledError(reason=self._reason)


# ── Global token registry ───────────────────────────────────────────────

_token_registry: dict[str, CancelToken] = {}


def register_cancel_token(session_id: str, token: CancelToken) -> None:
    """Register a cancel token for a session."""
    _token_registry[session_id] = token


def unregister_cancel_token(session_id: str) -> None:
    """Remove a cancel token from the registry."""
    _token_registry.pop(session_id, None)


def get_cancel_token(session_id: str) -> CancelToken | None:
    """Get the cancel token for a session."""
    return _token_registry.get(session_id)


def cancel_session(session_id: str, reason: str = "Cancelled by user") -> bool:
    """Request cancellation of an agent session by ID.

    Returns True if a token was found and cancelled.
    """
    token = _token_registry.get(session_id)
    if token is None:
        logger.warning("No CancelToken found for session %s", session_id)
        return False
    token.cancel(reason=reason)
    return True
