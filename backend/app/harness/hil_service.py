"""Human-in-the-loop service — gate management, pause/resume, approve/reject.

Each agent session can define HIL gates (via ``GuardrailConfig.hil_gates``)
that pause execution at specified trigger points.  The ``HILService``
maintains pending requests, notifies connected WebSocket clients, and
provides approve/reject APIs for the UI.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.harness.event_manager import get_event_manager
from app.harness.agent_spec import HILGateConfig

logger = logging.getLogger(__name__)

# ── In-memory pending HIL requests ──────────────────────────────────────
# In production this should use Redis/DB for reliability across restarts.
# For now an in-memory dict is sufficient for single-process deployments.

_pending_hil: dict[str, dict[str, Any]] = {}


class HILTimeoutError(TimeoutError):
    """Raised when a HIL gate times out."""


class HILNotFoundError(LookupError):
    """Raised when a HIL request is not found."""


def _make_hil_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class HILService:
    """Manage human-in-the-loop gates for agent sessions.

    Thread-safe design for async single-event-loop usage.
    """

    async def request_approval(
        self,
        session_id: str,
        gate: HILGateConfig,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a HIL request and wait for human decision.

        This coroutine **pauses** until the human approves/rejects or the
        gate timeout expires.

        Args:
            session_id: Agent session UUID.
            gate: The HIL gate configuration.
            context: Optional context (e.g. tool call details, risk flags).

        Returns:
            Decision dict: ``{"decision": "approved" | "rejected", "reason": str, ...}``

        Raises:
            HILTimeoutError: If the gate timeout expires and action is ``"fail"``.
        """
        hil_id = _make_hil_id()
        event_mgr = get_event_manager()

        request: dict[str, Any] = {
            "hil_id": hil_id,
            "session_id": session_id,
            "gate_type": gate.gate_type,
            "trigger_condition": gate.trigger_condition,
            "status": "pending",
            "context": context or {},
            "created_at": _now_iso(),
            "timeout_seconds": gate.timeout_seconds,
            "on_timeout_action": gate.on_timeout_action,
        }

        _pending_hil[hil_id] = request
        logger.info(
            "HIL request %s for session %s (gate=%s, timeout=%ds)",
            hil_id, session_id, gate.gate_type, gate.timeout_seconds,
        )

        # Notify WebSocket clients
        await event_mgr.emit_hil_request(session_id, request)
        await event_mgr.emit_paused(session_id, reason=f"HIL gate: {gate.gate_type}")

        # Wait for resolution with timeout
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        request["_future"] = future  # type: ignore[assignment]

        try:
            done, _ = await asyncio.wait(
                {future},
                timeout=gate.timeout_seconds,
            )
            if done:
                result = future.result()
                return result
            # Timeout
            return await self._handle_timeout(hil_id, gate)
        except asyncio.CancelledError:
            return {"decision": "cancelled", "reason": "Agent execution cancelled"}
        finally:
            _pending_hil.pop(hil_id, None)

    async def approve(self, hil_id: str, reason: str = "") -> dict[str, Any]:
        """Approve a pending HIL request, allowing execution to resume.

        Args:
            hil_id: HIL request UUID.
            reason: Optional human-provided reason.

        Returns:
            The resolved request data.

        Raises:
            HILNotFoundError: If the HIL request is not found.
        """
        request = _pending_hil.get(hil_id)
        if request is None:
            raise HILNotFoundError(f"HIL request {hil_id} not found or already resolved")

        future = request.pop("_future", None)
        if future and not future.done():
            future.set_result({"decision": "approved", "reason": reason, "approved_at": _now_iso()})
            logger.info("HIL request %s approved", hil_id)

        request["status"] = "approved"
        request["resolved_at"] = _now_iso()
        return request

    async def reject(self, hil_id: str, reason: str = "") -> dict[str, Any]:
        """Reject a pending HIL request, allowing execution to resume with guidance.

        Args:
            hil_id: HIL request UUID.
            reason: Optional human-provided reason / feedback.

        Returns:
            The resolved request data.

        Raises:
            HILNotFoundError: If the HIL request is not found.
        """
        request = _pending_hil.get(hil_id)
        if request is None:
            raise HILNotFoundError(f"HIL request {hil_id} not found or already resolved")

        future = request.pop("_future", None)
        if future and not future.done():
            future.set_result({"decision": "rejected", "reason": reason, "rejected_at": _now_iso()})
            logger.info("HIL request %s rejected: %s", hil_id, reason)

        request["status"] = "rejected"
        request["resolved_at"] = _now_iso()
        return request

    async def _handle_timeout(
        self,
        hil_id: str,
        gate: HILGateConfig,
    ) -> dict[str, Any]:
        """Handle a HIL request timeout based on the gate's on_timeout_action."""
        request = _pending_hil.get(hil_id)
        if request:
            future = request.pop("_future", None)
            if future and not future.done():
                if gate.on_timeout_action == "continue":
                    future.set_result({"decision": "approved", "reason": "timeout-auto-continue"})
                    logger.info("HIL request %s timed out — auto-continue", hil_id)
                elif gate.on_timeout_action == "fail":
                    future.set_result({"decision": "rejected", "reason": "timeout-auto-fail"})
                    logger.info("HIL request %s timed out — auto-fail", hil_id)
                else:  # fallback
                    future.set_result({"decision": "approved", "reason": "timeout-auto-fallback"})
                    logger.info("HIL request %s timed out — auto-fallback", hil_id)

            request["status"] = f"timeout_{gate.on_timeout_action}"
            request["resolved_at"] = _now_iso()

        if gate.on_timeout_action == "fail":
            raise HILTimeoutError(f"HIL gate '{gate.gate_type}' timed out after {gate.timeout_seconds}s")
        return {"decision": "approved" if gate.on_timeout_action != "fail" else "rejected", "reason": f"timeout-{gate.on_timeout_action}"}

    def list_pending(self, session_id: str | None = None) -> list[dict[str, Any]]:
        """List pending HIL requests, optionally filtered by session."""
        requests = list(_pending_hil.values())
        if session_id:
            requests = [r for r in requests if r["session_id"] == session_id]
        return [
            {k: v for k, v in r.items() if not k.startswith("_")}
            for r in requests
        ]

    def get_pending(self, hil_id: str) -> dict[str, Any] | None:
        """Get a single pending HIL request by ID."""
        request = _pending_hil.get(hil_id)
        if request is None:
            return None
        return {k: v for k, v in request.items() if not k.startswith("_")}


def get_hil_service() -> HILService:
    """Return the singleton HILService instance."""
    return HILService()
