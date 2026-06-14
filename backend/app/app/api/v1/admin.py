"""Admin API endpoints for health and readiness checks."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import HealthResponse, ReadinessResponse
from app.config import Settings, get_settings
from app.db.session import get_db

router = APIRouter(tags=["admin"])

APP_VERSION = "1.0.0"


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return application health status.

    Returns:
        HealthResponse with status, version, and ISO-8601 timestamp.
    """
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


async def _check_postgres(db: AsyncSession) -> str:
    """Verify PostgreSQL connectivity with SELECT 1."""
    try:
        await db.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


async def _check_redis(settings: Settings) -> str:
    """Verify Redis connectivity with PING."""
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            await client.ping()
        finally:
            await client.aclose()
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


async def _check_qdrant(settings: Settings) -> str:
    """Verify Qdrant connectivity via /healthz endpoint."""
    try:
        import httpx

        url = f"{settings.QDRANT_URL.rstrip('/')}/healthz"
        headers: dict[str, str] = {}
        if settings.QDRANT_API_KEY:
            headers["api-key"] = settings.QDRANT_API_KEY

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


async def _check_minio(settings: Settings) -> str:
    """Verify MinIO connectivity by listing buckets."""
    try:
        from minio import Minio

        loop = asyncio.get_running_loop()
        mc = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL,
        )
        await loop.run_in_executor(None, mc.list_buckets)
        return "ok"
    except Exception as exc:
        return f"error: {exc}"


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ReadinessResponse:
    """Check connectivity to all downstream dependencies.

    Verifies PostgreSQL, Redis, Qdrant, and MinIO are reachable.
    Returns "ready" when all services are healthy, "degraded" otherwise.

    Returns:
        ReadinessResponse with individual service check results.
    """
    postgres, redis, qdrant, minio = await asyncio.gather(
        _check_postgres(db),
        _check_redis(settings),
        _check_qdrant(settings),
        _check_minio(settings),
    )

    services = {
        "postgres": postgres,
        "redis": redis,
        "qdrant": qdrant,
        "minio": minio,
    }

    all_ok = all(v == "ok" for v in services.values())
    status = "ready" if all_ok else "degraded"

    return ReadinessResponse(
        status=status,
        version=APP_VERSION,
        services=services,
    )
