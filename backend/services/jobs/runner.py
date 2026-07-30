"""Job runner — executes jobs in background asyncio tasks.

Maps each JobType to an async handler that receives (payload, progress_callback).
Progress callbacks update the JobHandle's state so clients polling GET /jobs/{id}
see live progress updates.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import AsyncSessionLocal
from models.operations import Job
from services.jobs.enums import JobStatus, JobType
from services.jobs.queue import JobHandle, get_job_queue

logger = logging.getLogger("api.jobs.runner")

ProgressCallback = Callable[[int, str | None], Awaitable[None]]
JobHandler = Callable[
    [AsyncSession, UUID, dict[str, object], ProgressCallback],
    Awaitable[dict[str, object] | None],
]

_job_handlers: dict[JobType, JobHandler] = {}


def register_handler(job_type: JobType, handler: JobHandler) -> None:
    """Register a handler function for a specific job type."""
    _job_handlers[job_type] = handler


def get_handler(job_type: JobType) -> JobHandler | None:
    """Return the registered handler for a job type, or None."""
    return _job_handlers.get(job_type)


async def _persist_job(handle: JobHandle, db: AsyncSession) -> Job:
    """Upsert a job record in the database from the in-memory handle."""
    result = await db.execute(select(Job).where(Job.id == handle.id))
    job = result.scalar()
    if job is None:
        payload = handle.payload
        user_id_str = payload.get("user_id")
        user_id = UUID(str(user_id_str)) if user_id_str else None
        book_id_str = payload.get("book_id")
        book_id = UUID(str(book_id_str)) if book_id_str else None

        job = Job(
            id=handle.id,
            user_id=user_id,
            book_id=book_id,
            job_type=handle.job_type.value,
            status=handle.status.value,
            progress=handle.progress,
            current_step=handle.current_step,
            payload=handle.payload,
            result=handle.result,
            error_message=handle.error_message,
            started_at=handle.created_at,
            completed_at=None,
        )
        db.add(job)
    else:
        job.status = handle.status.value
        job.progress = handle.progress
        job.current_step = handle.current_step
        job.result = handle.result
        job.error_message = handle.error_message
        if handle.status.is_terminal:
            job.completed_at = datetime.now(UTC)
    await db.commit()
    return job


async def run_job(handle: JobHandle) -> None:
    """Execute a job in the background, updating Handle progress through callbacks.

    Called via asyncio.create_task() after enqueuing. Fetches a fresh DB session
    to avoid sharing sessions across async contexts.
    """
    queue = get_job_queue()
    handler = get_handler(handle.job_type)
    if handler is None:
        await queue.update_status(
            handle.id,
            JobStatus.FAILED,
            error_message=f"No handler registered for {handle.job_type}",
        )
        return

    async def update_progress(progress: int, current_step: str | None = None) -> None:
        await queue.update_progress(handle.id, progress, current_step)

    db_stored = False
    try:
        await queue.update_status(handle.id, JobStatus.RUNNING)
        async with AsyncSessionLocal() as session:
            handle.started_at = datetime.now(UTC)
            await _persist_job(handle, session)
            db_stored = True

            result = await handler(session, handle.id, handle.payload, update_progress)

            await queue.handle_completed(handle.id, result)
            handle.result = result
            await _persist_job(handle, session)
    except Exception as exc:
        logger.exception("Job %s (%s) failed: %s", handle.id, handle.job_type, exc)
        await queue.update_status(handle.id, JobStatus.FAILED, error_message=str(exc))
        try:
            async with AsyncSessionLocal() as session:
                handle.status = JobStatus.FAILED
                handle.error_message = str(exc)
                await _persist_job(handle, session)
        except Exception:
            logger.exception("Failed to persist job failure for %s", handle.id)


def _enqueue(
    job_type: JobType, payload: dict[str, object] | None = None
) -> "Awaitable[JobHandle]":
    """Build an awaitable that enqueues a job and schedules its execution."""
    queue = get_job_queue()

    async def _impl() -> JobHandle:
        handle = await queue.enqueue(job_type, payload or {})
        asyncio.create_task(run_job(handle))
        return handle

    return _impl()


async def enqueue_and_schedule(
    job_type: JobType, payload: dict[str, object] | None = None
) -> JobHandle:
    """Enqueue a job and immediately schedule it to run in the background."""
    handle = await get_job_queue().enqueue(job_type, payload or {})
    asyncio.create_task(run_job(handle))
    return handle