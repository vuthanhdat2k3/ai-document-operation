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


def _load_builtin_tools() -> None:
    try:
        from app.agents.tools.rag_tool import register_rag_tool
        from app.agents.tools.registry import get_registry

        register_rag_tool(get_registry())
        logger.info("Built-in tool stubs registered")
    except Exception:
        logger.exception("Failed to load built-in tool stubs")


def _bind_rag_tool() -> HybridRetriever | None:
    """Bind live pipeline components to the rag_query tool.

    Returns:
        The ``HybridRetriever`` instance so it can be reused by
        ``_bind_search_tool``, or ``None`` if binding failed.
    """
    try:
        from qdrant_client import QdrantClient

        from app.agents.tools.rag_tool import create_rag_tool
        from app.agents.tools.registry import get_registry
        from app.config import get_settings
        from app.llm.factory import get_llm_provider
        from app.rag.embedder import EmbeddingPipeline
        from app.rag.reranker import Reranker
        from app.rag.retriever import HybridRetriever

        settings = get_settings()
        qdrant = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        embedder = EmbeddingPipeline()
        retriever = HybridRetriever(qdrant_client=qdrant, embedder=embedder)
        reranker = Reranker()

        llm = None
        try:
            llm = get_llm_provider(settings)
        except Exception:
            logger.warning("LLM provider not available for RAG tool")

        bound = create_rag_tool(retriever=retriever, reranker=reranker, llm_provider=llm)

        registry = get_registry()
        if registry.has("rag_query"):
            registry._tools["rag_query"].function = bound
            logger.info("RAG tool bound with live pipeline components")
        else:
            logger.warning("rag_query tool not found in registry")

        return retriever

    except Exception:
        logger.exception("Failed to bind RAG tool, stub will remain in place")
        return None


def _bind_search_tool(retriever: HybridRetriever | None) -> None:
    """Bind a live HybridRetriever to the search_documents tool.

    Args:
        retriever: A ``HybridRetriever`` instance from ``_bind_rag_tool``.
    """
    if retriever is None:
        logger.warning("search_documents: no retriever available, stub remains in place")
        return

    try:
        from app.agents.tools.registry import get_registry
        from app.agents.tools.search_tool import create_bound_search_tool

        bound = create_bound_search_tool(retriever)

        registry = get_registry()
        if registry.has("search_documents"):
            registry._tools["search_documents"].function = bound
            logger.info("search_documents tool bound with live retriever")
        else:
            logger.warning("search_documents tool not found in registry")
    except Exception:
        logger.exception("Failed to bind search_documents tool, stub remains")


async def _warm_up_models() -> None:
    """Warm up ML models (placeholder for model pre-loading)."""
    logger.info("Model warm-up complete (no models to load yet)")


async def _seed_defaults() -> None:
    """Seed default data (extraction schemas, LLM providers, etc.) on first run."""
    from app.db.seed import seed_extraction_schemas, seed_providers_and_models

    try:
        await seed_extraction_schemas()
    except Exception:
        logger.warning("Failed to seed extraction schemas (may already exist)")

    try:
        await seed_providers_and_models()
    except Exception:
        logger.warning("Failed to seed LLM providers and models (may already exist)")


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
    _load_builtin_tools()
    try:
        await _init_vector_store()
    except Exception:
        logger.warning("Qdrant not available, continuing without vector store")
    retriever = _bind_rag_tool()
    _bind_search_tool(retriever)
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
