"""ARQ background worker configuration for document processing tasks."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import redis.asyncio as aioredis
from arq.connections import RedisSettings

from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_arq_redis_settings() -> RedisSettings:
    """Derive ARQ RedisSettings from the application configuration.

    Returns:
        RedisSettings configured from the application REDIS_URL.
    """
    settings = get_settings()
    parsed = urlparse(settings.REDIS_URL)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
        ssl=parsed.scheme == "rediss",
    )


async def startup(ctx: dict[str, Any]) -> None:
    """ARQ startup hook — runs once when the worker starts.

    Initialises a dedicated Redis connection for task progress tracking
    and stores it in the worker context.

    Args:
        ctx: ARQ worker context dictionary.
    """
    settings = get_settings()
    ctx["redis"] = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    logger.info("ARQ worker started, Redis connection established")


async def shutdown(ctx: dict[str, Any]) -> None:
    """ARQ shutdown hook — runs when the worker is stopping.

    Closes the Redis connection stored in the worker context.

    Args:
        ctx: ARQ worker context dictionary.
    """
    redis_client: aioredis.Redis[str] | None = ctx.get("redis")
    if redis_client is not None:
        await redis_client.aclose()
    logger.info("ARQ worker shut down, Redis connection closed")


class WorkerSettings:
    """ARQ worker settings class.

    Attributes:
        functions: List of task functions the worker can execute.
        on_startup: Coroutine called when the worker starts.
        on_shutdown: Coroutine called when the worker stops.
        redis_settings: ARQ Redis connection settings derived from app config.
        max_jobs: Maximum number of concurrent jobs.
        job_timeout: Maximum runtime per job in seconds.
        max_tries: Maximum number of retry attempts per job.
        retry_delay: Delay between retries in seconds.
    """

    from app.workers.tasks.process_document import process_document_task

    functions: list[Any] = [process_document_task]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings: RedisSettings = _get_arq_redis_settings()
    max_jobs: int = 10
    job_timeout: int = 600
    max_tries: int = 3
    retry_delay: int = 30
