"""Redis-backed sliding-window rate limit ASGI middleware."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import redis.asyncio as aioredis
from starlette.responses import JSONResponse

from app.config import get_settings

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 100
DEFAULT_WINDOW = 60


class RateLimitMiddleware:
    """ASGI middleware implementing a Redis-backed sliding window rate limiter.

    Rate limit keys follow the pattern ``rate_limit:{client_ip}:{endpoint}``.
    When the limit is exceeded the middleware returns ``429 Too Many Requests``
    with a ``Retry-After`` header.

    Args:
        app: The wrapped ASGI application.
        max_requests: Maximum requests allowed per window. Defaults to 100.
        window_seconds: Sliding window duration in seconds. Defaults to 60.
        redis_url: Redis connection URL. Defaults to the application setting.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int = DEFAULT_LIMIT,
        window_seconds: int = DEFAULT_WINDOW,
        redis_url: str | None = None,
    ) -> None:
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        settings = get_settings()
        self._redis: aioredis.Redis[str] = aioredis.from_url(
            redis_url or settings.REDIS_URL,
            decode_responses=True,
        )

    def _get_client_ip(self, scope: Scope) -> str:
        """Extract the client IP from the ASGI scope.

        Checks ``X-Forwarded-For`` first (for reverse-proxy setups),
        then falls back to the raw client address.
        """
        headers = dict(scope.get("headers", []))
        forwarded = headers.get(b"x-forwarded-for")
        if forwarded:
            return forwarded.decode("utf-8").split(",")[0].strip()
        client = scope.get("client")
        if client:
            return client[0]
        return "unknown"

    def _get_endpoint(self, scope: Scope) -> str:
        """Derive a rate-limit key segment from the request path."""
        return scope.get("path", "/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client_ip = self._get_client_ip(scope)
        endpoint = self._get_endpoint(scope)
        key = f"rate_limit:{client_ip}:{endpoint}"
        now = time.time()
        window_start = now - self.window_seconds

        try:
            pipe = self._redis.pipeline(transaction=True)
            pipe.zremrangebyscore(key, "-inf", window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, self.window_seconds + 1)
            _, _, request_count, _ = await pipe.execute()

            if request_count > self.max_requests:
                retry_after = self.window_seconds
                logger.warning(
                    "rate_limit_exceeded",
                    client_ip=client_ip,
                    endpoint=endpoint,
                    count=request_count,
                )
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds}s.",
                        }
                    },
                    headers={"Retry-After": str(retry_after)},
                )
                await response(scope, receive, send)
                return
        except Exception:
            logger.warning("Rate limit check failed, allowing request", exc_info=True)

        await self.app(scope, receive, send)
