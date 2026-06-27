"""WebSocket event manager for real-time agent execution streaming.

Provides a singleton ``EventManager`` that manages per-session WebSocket
connections and broadcasts structured events (step updates, HIL requests,
errors, completion) to connected clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


# ── Event types ──────────────────────────────────────────────────────────

EVENT_STEP = "step"
EVENT_HIL_REQUEST = "hil_request"
EVENT_ERROR = "error"
EVENT_COMPLETED = "completed"
EVENT_CANCELLED = "cancelled"
EVENT_PAUSED = "paused"


def _make_event(
    event_type: str,
    session_id: str,
    data: dict[str, Any],
) -> str:
    """Serialize an event to JSON string for WebSocket transmission."""
    payload = {
        "event": event_type,
        "session_id": session_id,
        "timestamp": time.time(),
        "data": data,
    }
    return json.dumps(payload, default=str)


class EventManager:
    """Manages WebSocket connections per agent session.

    Thread-safe single-threaded asyncio design — all operations happen
    on the event loop that created the manager.

    Usage::

        mgr = EventManager()

        # Client connects
        await mgr.connect(session_id, websocket)

        # Broadcast step update
        await mgr.emit_step(session_id, step_data)

        # Client disconnects
        mgr.disconnect(session_id)
    """

    _instance: EventManager | None = None

    def __new__(cls) -> EventManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connections: dict[str, set[WebSocket]] = {}
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        """Register a WebSocket connection for a session."""
        async with self._lock:
            if session_id not in self._connections:
                self._connections[session_id] = set()
            self._connections[session_id].add(ws)
            logger.debug("WebSocket connected for session %s (%d clients)", session_id, len(self._connections[session_id]))

    def disconnect(self, session_id: str, ws: WebSocket | None = None) -> None:
        """Remove a WebSocket connection for a session."""
        if session_id not in self._connections:
            return
        if ws:
            self._connections[session_id].discard(ws)
            if not self._connections[session_id]:
                del self._connections[session_id]
        else:
            del self._connections[session_id]

    def is_connected(self, session_id: str) -> bool:
        """Check if any client is connected to a session."""
        return session_id in self._connections and bool(self._connections[session_id])

    async def broadcast(self, session_id: str, payload: str) -> None:
        """Send a message to all clients connected to a session.

        Silently removes stale/errored connections.
        """
        if session_id not in self._connections:
            return

        active: set[WebSocket] = set()
        for ws in self._connections[session_id]:
            try:
                await ws.send_text(payload)
                active.add(ws)
            except Exception:
                logger.debug("Removing stale WebSocket for session %s", session_id)

        if active:
            self._connections[session_id] = active
        else:
            del self._connections[session_id]

    async def emit_step(self, session_id: str, step: dict[str, Any]) -> None:
        """Emit a step update event."""
        payload = _make_event(EVENT_STEP, session_id, step)
        await self.broadcast(session_id, payload)

    async def emit_hil_request(self, session_id: str, hil_data: dict[str, Any]) -> None:
        """Emit a human-in-the-loop request event."""
        payload = _make_event(EVENT_HIL_REQUEST, session_id, hil_data)
        await self.broadcast(session_id, payload)

    async def emit_completed(self, session_id: str, result: dict[str, Any]) -> None:
        """Emit a completion event."""
        payload = _make_event(EVENT_COMPLETED, session_id, result)
        await self.broadcast(session_id, payload)

    async def emit_error(self, session_id: str, error: str) -> None:
        """Emit an error event."""
        payload = _make_event(EVENT_ERROR, session_id, {"error": error})
        await self.broadcast(session_id, payload)

    async def emit_cancelled(self, session_id: str) -> None:
        """Emit a cancelled event."""
        payload = _make_event(EVENT_CANCELLED, session_id, {})
        await self.broadcast(session_id, payload)

    async def emit_paused(self, session_id: str, reason: str = "") -> None:
        """Emit a paused event (HIL gate triggered)."""
        payload = _make_event(EVENT_PAUSED, session_id, {"reason": reason})
        await self.broadcast(session_id, payload)


def get_event_manager() -> EventManager:
    """Return the singleton EventManager instance."""
    return EventManager()
