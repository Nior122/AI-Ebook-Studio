"""Regression tests for truthful background-handler and job outcomes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest

from services.jobs import handlers, runner
from services.jobs.enums import JobStatus, JobType
from services.jobs.queue import JobHandle


@pytest.mark.asyncio
async def test_cover_handler_propagates_generation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider error must fail the job, not return a successful error object."""
    book_id = uuid4()
    user_id = uuid4()
    progress_updates: list[tuple[int, str | None]] = []

    async def load_user(_session: object, _user_id: object) -> object:
        return object()

    async def update_progress(value: int, step: str | None = None) -> None:
        progress_updates.append((value, step))

    class FailedCoverEngine:
        async def generate_front_cover(
            self, _session: object, _user: object, _book_id: object
        ) -> dict[str, str]:
            raise RuntimeError("image provider is temporarily unavailable")

    monkeypatch.setattr(handlers, "_load_user", load_user)
    monkeypatch.setattr(handlers, "get_cover_engine", lambda _ai: FailedCoverEngine())
    monkeypatch.setattr("services.ai_service.AIService", lambda: object())

    with pytest.raises(RuntimeError, match="temporarily unavailable"):
        await handlers._cover_handler(
            session=None,  # type: ignore[arg-type]
            job_id=uuid4(),
            payload={"user_id": str(user_id), "book_id": str(book_id), "component": "front"},
            progress=update_progress,
        )

    assert progress_updates[-1] == (20, "Generating front cover")
    assert (100, "Cover complete") not in progress_updates


@pytest.mark.asyncio
async def test_cover_handler_rejects_unknown_component(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unsupported component cannot complete with an empty result."""

    async def load_user(_session: object, _user_id: object) -> object:
        return object()

    monkeypatch.setattr(handlers, "_load_user", load_user)

    with pytest.raises(ValueError, match="Unsupported cover component"):
        await handlers._cover_handler(
            session=None,  # type: ignore[arg-type]
            job_id=uuid4(),
            payload={
                "user_id": str(uuid4()),
                "book_id": str(uuid4()),
                "component": "poster",
            },
            progress=_noop_progress,
        )


async def _noop_progress(_value: int, _step: str | None = None) -> None:
    return None


@pytest.mark.asyncio
async def test_restore_point_storage_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """A job cannot report completed when its required restore point failed."""
    import services.studio_service as studio_service

    user_id = uuid4()
    project_id = uuid4()

    class FakeSession:
        async def get(self, _model: object, _identifier: UUID) -> object:
            return object()

    @asynccontextmanager
    async def fake_session_local() -> AsyncIterator[FakeSession]:
        yield FakeSession()

    async def get_project_id(_payload: dict[str, object]) -> UUID:
        return project_id

    async def fail_create_version(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("version store unavailable")

    monkeypatch.setattr(runner, "AsyncSessionLocal", fake_session_local)
    monkeypatch.setattr(runner, "_job_project_id", get_project_id)
    monkeypatch.setattr(studio_service, "create_version", fail_create_version)

    handle = JobHandle(
        id=uuid4(),
        job_type=JobType.COVER_GENERATION,
        status=JobStatus.RUNNING,
        payload={"user_id": str(user_id), "project_id": str(project_id)},
    )

    with pytest.raises(RuntimeError, match="version store unavailable"):
        await runner._create_auto_restore_point(handle)
