"""Job queue abstraction and a default in-memory implementation.

The :class:`JobQueueProtocol` is what feature code depends on. The
:class:`InMemoryJobQueue` is a minimal, dependency-free implementation used for
local development and tests; it records jobs but does not execute them in the
background. A production backend (Celery/RQ/Dramatiq over Redis) will implement
the same protocol and be swapped in via :func:`get_job_queue`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from uuid import UUID, uuid4

from services.jobs.enums import JobStatus, JobType


@dataclass
class JobHandle:
    """A lightweight, in-process representation of an enqueued job.

    The authoritative record lives in the ``jobs`` database table; this handle is
    what the queue backend returns to the caller after enqueuing.
    """

    id: UUID
    job_type: JobType
    status: JobStatus
    payload: dict[str, object]
    progress: int = 0
    current_step: str | None = None
    result: dict[str, object] | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class JobQueueProtocol(ABC):
    """Interface every job queue backend must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical backend name, e.g. ``memory`` or ``celery``."""

    @abstractmethod
    async def enqueue(
        self,
        job_type: JobType,
        payload: dict[str, object] | None = None,
    ) -> JobHandle:
        """Register a new job and return its handle."""

    @abstractmethod
    async def get(self, job_id: UUID) -> JobHandle | None:
        """Return the handle for ``job_id`` or ``None`` if unknown."""

    @abstractmethod
    async def cancel(self, job_id: UUID) -> bool:
        """Request cancellation; return ``True`` if the job was cancellable."""

    @abstractmethod
    async def update_status(
        self, job_id: UUID, status: JobStatus, error_message: str | None = None
    ) -> None:
        """Transition a job to a new status (used by in-process workers)."""

    @abstractmethod
    async def update_progress(
        self, job_id: UUID, progress: int, current_step: str | None = None
    ) -> None:
        """Update progress percentage and optional step description."""

    @abstractmethod
    async def handle_completed(
        self, job_id: UUID, result: dict[str, object] | None = None
    ) -> None:
        """Mark a job as completed."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the backend is reachable."""


class InMemoryJobQueue(JobQueueProtocol):
    """Non-persistent queue for development and tests with optional async execution."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, JobHandle] = {}

    @property
    def name(self) -> str:
        """Return the canonical backend name."""
        return "memory"

    async def enqueue(
        self,
        job_type: JobType,
        payload: dict[str, object] | None = None,
    ) -> JobHandle:
        """Record a new job in the ``QUEUED`` state and return its handle."""
        handle = JobHandle(
            id=uuid4(),
            job_type=job_type,
            status=JobStatus.QUEUED,
            payload=payload or {},
        )
        self._jobs[handle.id] = handle
        return handle

    async def get(self, job_id: UUID) -> JobHandle | None:
        """Return the handle for ``job_id`` if present."""
        return self._jobs.get(job_id)

    async def cancel(self, job_id: UUID) -> bool:
        """Cancel a non-terminal job and return whether it was cancellable."""
        handle = self._jobs.get(job_id)
        if handle is None or handle.status.is_terminal:
            return False
        handle.status = JobStatus.CANCELLED
        handle.completed_at = datetime.now(UTC)
        handle.updated_at = handle.completed_at
        return True

    async def update_status(
        self, job_id: UUID, status: JobStatus, error_message: str | None = None
    ) -> None:
        """Transition a job to a new status."""
        handle = self._jobs.get(job_id)
        if handle is None:
            return
        handle.status = status
        if status == JobStatus.RUNNING and handle.started_at is None:
            handle.started_at = datetime.now(UTC)
        if status.is_terminal and handle.completed_at is None:
            handle.completed_at = datetime.now(UTC)
        handle.updated_at = datetime.now(UTC)
        if error_message:
            handle.error_message = error_message

    async def update_progress(
        self, job_id: UUID, progress: int, current_step: str | None = None
    ) -> None:
        """Update progress percentage and optional step description."""
        handle = self._jobs.get(job_id)
        if handle is None:
            return
        handle.progress = max(0, min(100, progress))
        if current_step is not None:
            handle.current_step = current_step
        handle.updated_at = datetime.now(UTC)

    async def handle_completed(
        self, job_id: UUID, result: dict[str, object] | None = None
    ) -> None:
        """Mark a job as completed with an optional result payload."""
        handle = self._jobs.get(job_id)
        if handle is None:
            return
        handle.status = JobStatus.COMPLETED
        handle.progress = 100
        handle.result = result
        handle.completed_at = datetime.now(UTC)
        handle.updated_at = handle.completed_at

    async def health_check(self) -> bool:
        """The in-memory queue is always available."""
        return True


@lru_cache
def get_job_queue() -> JobQueueProtocol:
    """Return the process-wide job queue backend.

    Currently returns the in-memory queue. A later phase selects a Redis-backed
    worker system based on settings without changing callers.
    """
    return InMemoryJobQueue()
