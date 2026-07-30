"""Async job-based endpoints for book operations.

These endpoints enqueue a background job for long-running work (exports,
validation, cover, marketing, translation) and return immediately with a job
id. Clients poll ``GET /api/v1/jobs/{job_id}`` for progress.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from api.dependencies import CurrentUser, DatabaseSession
from schemas.jobs import JobResponse
from services.jobs import enqueue_and_schedule
from services.jobs.enums import JobStatus, JobType

router = APIRouter(prefix="/async", tags=["async-jobs"])


@router.post(
    "/books/{book_id}/exports/{fmt}",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Export book in the background",
)
async def export_book_async(
    book_id: UUID, fmt: str, user: CurrentUser
) -> JobResponse:
    """Schedule a DOCX/PDF/EPUB export job for the given book."""
    fmt_to_type = {
        "docx": JobType.DOCX_BUILD,
        "pdf": JobType.PDF_EXPORT,
        "epub": JobType.EPUB_EXPORT,
    }
    job_type = fmt_to_type.get(fmt.lower())
    if job_type is None:
        from core.exceptions import ValidationAppError

        raise ValidationAppError(f"Unsupported export format '{fmt}'.")

    handle = await enqueue_and_schedule(
        job_type,
        {
            "user_id": str(user.id),
            "book_id": str(book_id),
            "format": fmt.lower(),
            "include_front_matter": True,
            "include_toc": True,
            "include_back_matter": True,
        },
    )
    return JobResponse(
        id=handle.id,
        job_type=handle.job_type,
        status=JobStatus.QUEUED,
        progress=0,
        current_step=None,
        result=None,
        error_message=None,
        created_at=handle.created_at,
        updated_at=handle.updated_at,
    )


@router.post(
    "/books/{book_id}/kdp-validate",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run KDP validation in the background",
)
async def kdp_validate_async(
    book_id: UUID, user: CurrentUser
) -> JobResponse:
    """Schedule a KDP validation job for the given book."""
    handle = await enqueue_and_schedule(
        JobType.KDP_VALIDATION,
        {"user_id": str(user.id), "book_id": str(book_id)},
    )
    return JobResponse(
        id=handle.id,
        job_type=handle.job_type,
        status=JobStatus.QUEUED,
        progress=0,
        current_step=None,
        result=None,
        error_message=None,
        created_at=handle.created_at,
        updated_at=handle.updated_at,
    )


@router.post(
    "/books/{book_id}/marketing/{asset_type}",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate a marketing asset in the background",
)
async def marketing_async(
    book_id: UUID, asset_type: str, user: CurrentUser
) -> JobResponse:
    """Schedule a marketing asset generation job."""
    handle = await enqueue_and_schedule(
        JobType.MARKETING_GENERATION,
        {
            "user_id": str(user.id),
            "book_id": str(book_id),
            "asset_type": asset_type,
        },
    )
    return JobResponse(
        id=handle.id,
        job_type=handle.job_type,
        status=JobStatus.QUEUED,
        progress=0,
        current_step=None,
        result=None,
        error_message=None,
        created_at=handle.created_at,
        updated_at=handle.updated_at,
    )


@router.post(
    "/books/{book_id}/cover",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate cover design in the background",
)
async def cover_async(
    book_id: UUID,
    user: CurrentUser,
    component: str = "all",
) -> JobResponse:
    """Schedule a cover design generation job."""
    handle = await enqueue_and_schedule(
        JobType.COVER_GENERATION,
        {
            "user_id": str(user.id),
            "book_id": str(book_id),
            "component": component,
        },
    )
    return JobResponse(
        id=handle.id,
        job_type=handle.job_type,
        status=JobStatus.QUEUED,
        progress=0,
        current_step=None,
        result=None,
        error_message=None,
        created_at=handle.created_at,
        updated_at=handle.updated_at,
    )


@router.post(
    "/books/{book_id}/translate",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Translate book in the background",
)
async def translate_async(
    book_id: UUID,
    source_lang: str,
    target_lang: str,
    user: CurrentUser,
) -> JobResponse:
    """Schedule a translation job for the given book."""
    handle = await enqueue_and_schedule(
        JobType.TRANSLATION,
        {
            "user_id": str(user.id),
            "book_id": str(book_id),
            "source_lang": source_lang,
            "target_lang": target_lang,
        },
    )
    return JobResponse(
        id=handle.id,
        job_type=handle.job_type,
        status=JobStatus.QUEUED,
        progress=0,
        current_step=None,
        result=None,
        error_message=None,
        created_at=handle.created_at,
        updated_at=handle.updated_at,
    )
