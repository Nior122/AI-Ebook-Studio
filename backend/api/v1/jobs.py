"""Jobs endpoints.

Exposes the job-tracking foundation. Enqueuing is not exposed directly yet —
future feature endpoints (book generation, exports, etc.) will enqueue jobs
internally. These endpoints let clients inspect and cancel jobs by id using the
current queue backend.
"""

from uuid import UUID

from fastapi import APIRouter, status

from core.exceptions import ResourceNotFoundError
from schemas.jobs import JobCreateRequest, JobResponse
from services.jobs import enqueue_and_schedule
from services.jobs.enums import JobStatus
from services.jobs.queue import JobQueueProtocol, get_job_queue

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _queue() -> JobQueueProtocol:
    """Resolve the active job queue backend."""
    return get_job_queue()


@router.get("", summary="List jobs (not implemented)")
async def list_jobs() -> dict[str, str]:
    """Placeholder: a future endpoint will list persisted jobs for the caller."""
    return {"message": "Endpoint not implemented yet"}


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
