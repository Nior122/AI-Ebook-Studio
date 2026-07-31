"""Jobs endpoints.

Exposes the job-tracking foundation. Enqueuing is not exposed directly yet —
future feature endpoints (book generation, exports, etc.) will enqueue jobs
internally. These endpoints let clients inspect and cancel jobs by id using the
current queue backend.
"""

from uuid import UUID

from fastapi import APIRouter, Query, status

from core.exceptions import ResourceNotFoundError
from api.dependencies import CurrentUser, DatabaseSession
from models.operations import Job
from sqlalchemy import select
from schemas.jobs import JobCreateRequest, JobResponse
from services.jobs import enqueue_and_schedule
from services.jobs.enums import JobStatus, JobType
from services.jobs.queue import JobQueueProtocol, get_job_queue

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _queue() -> JobQueueProtocol:
    """Resolve the active job queue backend."""
    return get_job_queue()


@router.get("", response_model=list[JobResponse], summary="List my jobs")
async def list_jobs(
    session: DatabaseSession,
    user: CurrentUser,
    job_type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[JobResponse]:
    """List the caller jobs from the persisted job table (newest first)."""
    query = (
        select(Job)
        .where(Job.user_id == user.id)
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    if job_type:
        query = query.where(Job.job_type == job_type)
    if status:
        query = query.where(Job.status == status)
    result = await session.execute(query)
    rows = list(result.scalars())
    response: list[JobResponse] = []
    for job in rows:
        try:
            response.append(
                JobResponse(
                    id=job.id,
                    job_type=JobType(job.job_type),
                    status=JobStatus(job.status),
                    progress=job.progress or 0,
                    current_step=job.current_step,
                    result=job.result_data or job.result,
                    error_message=job.error_message,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                )
            )
        except ValueError:
            continue
    return response


@router.get("/{job_id}", response_model=JobResponse, summary="Get job status")
async def get_job(job_id: UUID) -> JobResponse:
    """Return the current status of a job by id."""
    handle = await _queue().get(job_id)
    if handle is None:
        raise ResourceNotFoundError(f"Job '{job_id}' was not found.")
    return JobResponse(
        id=handle.id,
        job_type=handle.job_type,
        status=handle.status,
        progress=handle.progress,
        current_step=handle.current_step,
        result=handle.result,
        error_message=handle.error_message,
        created_at=handle.created_at,
        updated_at=handle.updated_at,
    )


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue and run a job",
)
async def create_job(payload: JobCreateRequest) -> JobResponse:
    """Enqueue a job and immediately schedule it for background execution.

    The caller polls ``GET /api/v1/jobs/{job_id}`` (using the returned ``id``)
    to track progress. The handler for ``job_type`` must be registered on
    application startup.
    """
    handle = await enqueue_and_schedule(payload.job_type, payload.payload)
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


@router.post("/{job_id}/cancel", summary="Cancel a job")
async def cancel_job(job_id: UUID) -> dict[str, object]:
    """Attempt to cancel a non-terminal job."""
    cancelled = await _queue().cancel(job_id)
    if not cancelled:
        raise ResourceNotFoundError(
            f"Job '{job_id}' was not found or is already in a terminal state."
        )
    return {"success": True, "data": {"id": str(job_id), "status": "CANCELLED"}}
