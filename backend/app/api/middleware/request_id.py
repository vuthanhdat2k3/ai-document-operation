"""X-Request-ID ASGI middleware for end-to-end request tracing."""

from __future__ import annotations

import uuid

import structlog.contextvars
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestIDMiddleware:
    """Pure ASGI middleware that assigns a unique X-Request-ID to every request.

    If the incoming request already contains an ``X-Request-ID`` header,
    that value is preserved. Otherwise a new UUID4 is generated. The ID is
    stored on ``request.state``, added to response headers, and bound to
    the structlog contextvars so all log entries include it automatically.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id", b"").decode("utf-8") or str(uuid.uuid4())

        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
