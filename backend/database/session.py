"""SQLAlchemy async engine and session management.

The engine is configured for Neon PostgreSQL with connection pooling driven by
environment settings. SQLite (used in tests) does not support pool sizing, so
those parameters are only applied to PostgreSQL URLs.
"""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings

settings = get_settings()


def _engine_kwargs() -> dict[str, Any]:
    """Build engine keyword arguments, applying pool tuning only where supported."""
    kwargs: dict[str, Any] = {
        "echo": settings.sql_echo,
        "pool_pre_ping": True,
        "future": True,
    }
    # SQLite / aiosqlite does not accept pool_size / max_overflow.
    if not settings.database_url.startswith("sqlite"):
        kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
        )
    return kwargs


engine: AsyncEngine = create_async_engine(settings.database_url, **_engine_kwargs())

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped async database session (FastAPI dependency)."""
    async with AsyncSessionLocal() as session:
        yield session


async def dispose_engine() -> None:
    """Dispose database connections during shutdown or tests."""
    await engine.dispose()
