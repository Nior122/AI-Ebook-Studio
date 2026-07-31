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
from models.project import Book
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


JOB_LABELS = {
    JobType.BOOK_GENERATION: "Book generation",
    JobType.PROOFREADING: "Proofreading",
    JobType.IMAGE_ANALYSIS: "Image analysis",
    JobType.IMAGE_GENERATION: "Image generation",
    JobType.DOCX_BUILD: "DOCX export",
    JobType.PDF_EXPORT: "PDF export",
    JobType.EPUB_EXPORT: "EPUB export",
    JobType.TRANSLATION: "Translation",
    JobType.MARKETING_GENERATION: "Marketing copy",
    JobType.KDP_VALIDATION: "KDP validation",
    JobType.COVER_GENERATION: "Cover generation",
}

# Job types that should leave an automatic project restore point behind.
AUTO_VERSION_JOB_TYPES = {
    JobType.PROOFREADING,
    JobType.TRANSLATION,
    JobType.COVER_GENERATION,
    JobType.MARKETING_GENERATION,
    JobType.IMAGE_GENERATION,
    JobType.IMAGE_ANALYSIS,
    JobType.DOCX_BUILD,
    JobType.PDF_EXPORT,
    JobType.EPUB_EXPORT,
}


async def _job_project_id(payload: dict[str, object]) -> UUID | None:
    """Resolve the project a job belongs to (payload first, then Book lookup)."""
    raw = payload.get("project_id")
    if raw:
        try:
            return UUID(str(raw))
        except ValueError:
            return None
    raw_book = payload.get("book_id")
    if not raw_book:
        return None
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Book).where(Book.id == UUID(str(raw_book))))
            book = result.scalar_one_or_none()
            if book is not None:
                return book.project_id
            # Writing-book jobs carry the WritingBook id; the primary Book
            # records it in metadata_json.writing_book_id.
            result = await session.execute(
                select(Book).where(
                    Book.metadata_json["writing_book_id"].as_string() == str(raw_book)
                )
            )
            book = result.scalar_one_or_none()
            return book.project_id if book is not None else None
    except Exception:
        return None


def _friendly_job_error(job_type: JobType, raw: str | None) -> str:
    """Turn a raw exception message into an actionable, human-readable note."""
    message = (raw or "").strip()
    if not message:
        return "The operation did not complete. Check your configuration and retry."
    if "ProviderConfigurationError" in message or "api key" in message.lower() or "not configured" in message.lower() or "is not registered" in message:
        return (
            "This operation needs an AI provider key. Add one in Settings → AI "
            "(or set it in the Book Setup wizard), then retry. The local engine "
            "covers generation, proofreading, marketing, and covers without a key."
        )
    if "LibreTranslate" in message:
        return message
    return message[:400]


async def _notify_terminal(handle: JobHandle) -> None:
    """Record a notification + activity when a job finishes (success or failure)."""
    from services.events import publish_project_event, publish_user_event
    from services.studio_service import create_notification, record_activity

    payload = handle.payload
    raw_user = payload.get("user_id")
    if not raw_user:
        return
    try:
        user_id = UUID(str(raw_user))
    except ValueError:
        return
    project_id = await _job_project_id(payload)
    label = JOB_LABELS.get(handle.job_type, handle.job_type.value.replace("_", " ").title())

    if handle.status == JobStatus.COMPLETED:
        title = f"{label} complete"
        body = "The operation finished successfully."
        level = "success"
    elif handle.status == JobStatus.FAILED:
        title = f"{label} failed"
        body = _friendly_job_error(handle.job_type, handle.error_message)
        level = "error"
    else:
        return

    try:
        async with AsyncSessionLocal() as session:
            await create_notification(
                session, user_id, project_id,
                kind="job_completed" if handle.status == JobStatus.COMPLETED else "job_failed",
                title=title, body=body, level=level,
                action_type="open_project" if project_id is not None else None,
                action_payload={"project_id": str(project_id)} if project_id is not None else None,
            )
            if project_id is not None and handle.status == JobStatus.COMPLETED:
                await record_activity(
                    session, user_id, project_id, "job_completed", f"{label} complete",
                    {"job_id": str(handle.id), "job_type": handle.job_type.value},
                )
            if (
                project_id is not None
                and handle.status == JobStatus.COMPLETED
                and handle.job_type in AUTO_VERSION_JOB_TYPES
            ):
                from models.accounts import User
                from services.studio_service import create_version

                user = await session.get(User, user_id)
                if user is not None:
                    await create_version(
                        session, user, project_id,
                        label=f"After {label}",
                        reason=f"Automatic restore point created after {label}.",
                        created_by="auto",
                        announce=True,
                    )
    except Exception:
        logger.exception("Failed to record terminal notification for job %s", handle.id)

    publish_user_event(str(user_id), "job.terminal", {
        "job_id": str(handle.id), "job_type": handle.job_type.value,
        "status": handle.status.value, "title": title, "level": level,
    })
    if project_id is not None:
        publish_project_event(str(project_id), "job.terminal", {
            "job_id": str(handle.id), "job_type": handle.job_type.value,
            "status": handle.status.value, "title": title, "level": level,
        })


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

    from services.events import publish_project_event, publish_user_event

    async def update_progress(progress: int, current_step: str | None = None) -> None:
        await queue.update_progress(handle.id, progress, current_step)
        project_id = await _job_project_id(handle.payload)
        event = {
            "job_id": str(handle.id),
            "job_type": handle.job_type.value,
            "status": "RUNNING",
            "progress": progress,
            "current_step": current_step,
        }
        raw_user = handle.payload.get("user_id")
        if raw_user:
            publish_user_event(str(raw_user), "job.progress", event)
        if project_id is not None:
            publish_project_event(str(project_id), "job.progress", event)

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
        await _notify_terminal(handle)
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
        finally:
            await _notify_terminal(handle)


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