"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return or create the async SQLAlchemy engine.

    Returns:
        The singleton async engine instance.
    """
    global _engine  # noqa: PLW0603
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            echo=settings.DB_ECHO,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return or create the async session factory.

    Returns:
        The singleton async session maker instance.
    """
    global _session_factory  # noqa: PLW0603
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for dependency injection.

    Yields:
        An AsyncSession instance that is automatically closed after use.
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session


@asynccontextmanager
async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Standalone async context manager for database sessions.

    Usage::

        async with get_async_session() as db:
            result = await db.execute(...)

    This is a convenience wrapper around ``get_session_factory()``
    for use outside of FastAPI dependency injection (e.g. in tools,
    background workers, or scripts).
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def close_engine() -> None:
    """Dispose of the async engine and clear cached references."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
