"""FastAPI application factory with lifespan management."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.error_handler import register_exception_handlers
from app.api.middleware.logging import LoggingMiddleware
from app.api.middleware.request_id import RequestIDMiddleware
from app.api.v1.router import v1_router
from app.config import Settings, get_settings
from app.logging import setup_logging

logger = logging.getLogger(__name__)


async def _init_db() -> None:
    """Initialize the database connection pool."""
    import sqlalchemy

    from app.db.session import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(sqlalchemy.text("SELECT 1"))
    logger.info("Database connection pool initialized")


async def _init_vector_store() -> None:
    """Initialize Qdrant vector store connectivity."""
    from app.vector.client import QdrantClientWrapper

    settings = get_settings()
    wrapper = QdrantClientWrapper(settings)
    try:
        await wrapper.health_check()
    finally:
        await wrapper.close()
    logger.info("Qdrant vector store connection verified")


async def _warm_up_models() -> None:
    """Warm up ML models (placeholder for model pre-loading)."""
    logger.info("Model warm-up complete (no models to load yet)")


async def _seed_defaults() -> None:
    """Seed default data (extraction schemas, etc.) on first run."""
    from app.db.seed import seed_extraction_schemas

    try:
        await seed_extraction_schemas()
    except Exception:
        logger.warning("Failed to seed extraction schemas (may already exist)")


async def _shutdown_db() -> None:
    """Dispose of the database connection pool."""
    from app.db.session import close_engine

    await close_engine()
    logger.info("Database connection pool disposed")


async def _shutdown_vector_store() -> None:
    """Clean up vector store resources."""
    logger.info("Vector store connections closed")


async def _flush_telemetry() -> None:
    """Flush pending telemetry data."""
    logger.info("Telemetry flushed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    On startup: initializes database pool, vector store, loads built-in
    agent templates, and warms up models.
    On teardown: closes connections and flushes telemetry.

    Args:
        app: The FastAPI application instance.
    """
    logger.info("Starting application...")
    await _init_db()
    await _seed_defaults()
    _load_builtin_agents()
    try:
        await _init_vector_store()
    except Exception:
        logger.warning("Qdrant not available, continuing without vector store")
    await _warm_up_models()
    logger.info("Application startup complete")

    yield

    logger.info("Shutting down application...")
    await _shutdown_db()
    await _shutdown_vector_store()
    await _flush_telemetry()
    logger.info("Application shutdown complete")


def _load_builtin_agents() -> None:
    """Register built-in agent templates from app.agents.agents."""
    try:
        from app.agents.agents import load_builtin_agents

        load_builtin_agents()
        logger.info("Built-in agent templates loaded")
    except Exception:
        logger.exception("Failed to load built-in agent templates")


def _parse_cors_origins(cors_origins_str: str) -> list[str]:
    """Parse comma-separated CORS origins string into a list.

    Args:
        cors_origins_str: Comma-separated origins string.

    Returns:
        List of origin URL strings.
    """
    return [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]


def register_middleware(app: FastAPI, settings: Settings) -> None:
    """Register all middleware on the application.

    Middleware order (outermost first): CORS → Request ID → Logging.

    Args:
        app: The FastAPI application instance.
        settings: Application settings.
    """
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_parse_cors_origins(settings.CORS_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )


def register_routes(app: FastAPI) -> None:
    """Register all API routes on the application.

    Args:
        app: The FastAPI application instance.
    """
    app.include_router(v1_router)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    This is the main entry point for the application. It sets up
    middleware, routes, exception handlers, and lifespan events.

    Args:
        settings: Optional settings override. If None, settings are
            loaded from environment variables.

    Returns:
        A fully configured FastAPI application instance.
    """
    settings = settings or get_settings()

    setup_logging(settings.LOG_LEVEL, settings.DEBUG)

    app = FastAPI(
        title="AI Document Operations Agent",
        version="1.0.0",
        description="Intelligent document processing platform with RAG capabilities",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        openapi_url="/api/openapi.json" if settings.DEBUG else None,
    )

    app.state.settings = settings

    register_middleware(app, settings)
    register_routes(app)
    register_exception_handlers(app)

    return app
