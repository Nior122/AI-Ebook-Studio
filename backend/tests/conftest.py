"""Shared test fixtures for Stage 4 API tests."""

from collections.abc import AsyncIterator, Iterator
from typing import Any

import os

# Job-runner sessions use the GLOBAL engine (AsyncSessionLocal), so point it at
# a SQLite file BEFORE any app import. In-memory engines can't be shared across
# sessions, and background jobs would otherwise hit the configured Postgres.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./var/test_studio.db")
os.makedirs(os.path.join(os.path.dirname(__file__), "..", "var"), exist_ok=True)

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import models  # noqa: F401
from app.main import app
from database.base import Base
from database.session import get_db_session


@pytest.fixture()
def db_engine() -> Iterator[Any]:
    """Create an isolated in-memory SQLite engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine


@pytest.fixture()
def session_factory(db_engine: Any) -> Iterator[async_sessionmaker[AsyncSession]]:
    """Return a reusable async session factory bound to the test engine."""
    yield async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(
    db_engine: Any,
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """Create an isolated API client backed by an in-memory SQLite database."""

    async with db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
    await db_engine.dispose()


@pytest.fixture()
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Provide direct DB access for integration tests that seed structured content."""
    async with session_factory() as session:
        bind = session.get_bind()
        assert bind is not None
        await session.run_sync(lambda _sync_session: Base.metadata.create_all(bind))
        yield session
