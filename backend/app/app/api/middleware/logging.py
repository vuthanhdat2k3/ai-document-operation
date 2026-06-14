"""Structured request logging ASGI middleware."""

from __future__ import annotations

import time

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class LoggingMiddleware:
    """ASGI middleware that logs every HTTP request with structured metadata.

    Logs method, path, query string, status code, duration in milliseconds,
    and the request ID (from request.state). Uses INFO for 2xx/3xx, WARNING
    for 4xx, and ERROR for 5xx.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = structlog.get_logger("api.access")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "")
        query_string = scope.get("query_string", b"").decode("utf-8")

        status_code = 500

        async def capture_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            request_id = scope.get("state", {}).get("request_id", "unknown")

            log_event: dict[str, object] = {
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "request_id": request_id,
            }
            if query_string:
                log_event["query_string"] = query_string

            if status_code >= 500:
                self.logger.error("http_request", **log_event)
            elif status_code >= 400:
                self.logger.warning("http_request", **log_event)
            else:
                self.logger.info("http_request", **log_event)
