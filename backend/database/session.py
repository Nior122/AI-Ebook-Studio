"""SQLAlchemy async engine and session management.

The engine is configured for Neon PostgreSQL with connection pooling driven by
environment settings. SQLite (used in tests) does not support pool sizing, so
those parameters are only applied to PostgreSQL URLs.
"""

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlencode, parse_qs, urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings

settings = get_settings()


def _clean_database_url(url: str) -> tuple[str, dict[str, Any]]:
    """Strip asyncpg-incompatible query params (sslmode, channel_binding) and
    return them as connect_args so SQLAlchemy can pass them to asyncpg safely.
    """
    connect_args: dict[str, Any] = {}
    if not url.startswith("postgresql"):
        return url, connect_args
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    if "sslmode" in qs or "ssl" in qs:
        mode = qs.pop("sslmode", qs.pop("ssl", ["require"]))[0]
        connect_args["ssl"] = mode if mode != "disable" else False
    if "channel_binding" in qs:
        qs.pop("channel_binding")
    new_query = urlencode({k: v[0] for k, v in qs.items()})
    cleaned = urlunparse(parsed._replace(query=new_query))
    return cleaned, connect_args


def _engine_kwargs() -> tuple[str, dict[str, Any]]:
    """Build engine keyword arguments, applying pool tuning only where supported."""
    cleaned_url, connect_args = _clean_database_url(settings.database_url)
    kwargs: dict[str, Any] = {
        "echo": settings.sql_echo,
        "pool_pre_ping": True,
        "future": True,
        "connect_args": connect_args,
    }
    # SQLite / aiosqlite does not accept pool_size / max_overflow.
    if not settings.database_url.startswith("sqlite"):
        kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
        )
    return cleaned_url, kwargs


_cleaned_url, _kwargs = _engine_kwargs()
engine: AsyncEngine = create_async_engine(_cleaned_url, **_kwargs)

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
