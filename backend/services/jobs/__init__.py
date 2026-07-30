"""Job system abstraction.

Ebook operations (generation, proofreading, image work, exports, translation,
marketing, KDP validation) are long-running and must not block HTTP requests.
This package defines the *contract* for enqueuing and tracking jobs so a concrete
backend (Redis + Celery/RQ/Dramatiq) can be added later without changing callers.

    from services.jobs import JobType, JobStatus, get_job_queue

    queue = get_job_queue()
    handle = await queue.enqueue(JobType.BOOK_GENERATION, payload={...})
"""

from services.jobs.enums import JobStatus, JobType
from services.jobs.queue import (
    InMemoryJobQueue,
    JobHandle,
    JobQueueProtocol,
    get_job_queue,
)
from services.jobs.runner import (
    JobHandler,
    ProgressCallback,
    enqueue_and_schedule,
    register_handler,
)

__all__ = [
    "InMemoryJobQueue",
    "JobHandle",
    "JobQueueProtocol",
    "JobStatus",
    "JobType",
    "JobHandler",
    "ProgressCallback",
    "enqueue_and_schedule",
    "get_job_queue",
    "register_handler",
]
