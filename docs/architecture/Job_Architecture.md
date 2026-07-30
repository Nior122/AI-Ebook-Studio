# Job Architecture

## Principle

Ebook operations are long-running and must not block HTTP requests. Requests
enqueue jobs and return immediately; clients poll job status. The system is
designed so a real worker backend (Redis + Celery/RQ/Dramatiq) can be added
later without changing callers.

## Components

```text
JobType / JobStatus        (services/jobs/enums.py)   # canonical enums
JobQueueProtocol           (services/jobs/queue.py)   # backend contract
  ├── InMemoryJobQueue     (dev / tests, non-executing)
  └── Redis/Celery backend (later phase)
get_job_queue()            # process-wide backend selector
Job (SQLAlchemy model)     (models/operations.py)     # authoritative record
JobResponse / JobCreateRequest (schemas/jobs.py)      # API contract
```

## Job types

`BOOK_GENERATION`, `PROOFREADING`, `IMAGE_ANALYSIS`, `IMAGE_GENERATION`,
`DOCX_BUILD`, `PDF_EXPORT`, `EPUB_EXPORT`, `TRANSLATION`,
`MARKETING_GENERATION`, `KDP_VALIDATION`.

## Lifecycle statuses

`PENDING` → `QUEUED` → `RUNNING` → (`COMPLETED` | `FAILED` | `CANCELLED`).
`JobStatus.is_terminal` identifies end states. Jobs also track a `progress`
percentage, `result`, `error_message`, and timestamps.

## Queue interface

`JobQueueProtocol` defines `enqueue(job_type, payload)`, `get(job_id)`,
`cancel(job_id)`, and `health_check()`. The current `InMemoryJobQueue` records
jobs but does not execute them — it exists so the contract and endpoints are
testable now. Feature endpoints will enqueue jobs internally in later phases.

## API surface (Phase 2)

- `GET /api/v1/jobs/{job_id}` — job status (`JobResponse`).
- `POST /api/v1/jobs/{job_id}/cancel` — cancel a non-terminal job.
- `GET /api/v1/jobs` — placeholder (persisted listing added later).

## Adding a real backend

Implement `JobQueueProtocol` over Redis with a worker system, then update
`get_job_queue()` to select it from settings. The `Job` model already provides
persistence for status/result/error.
