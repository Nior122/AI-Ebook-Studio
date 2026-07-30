"""Job API schemas.

Response/request models for the jobs endpoints. These wrap the shared
``JobType`` / ``JobStatus`` enums so the API contract stays aligned with the
worker layer and the ``jobs`` database table.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from services.jobs.enums import JobStatus, JobType


class JobResponse(BaseModel):
    """Canonical job representation returned by the API."""

    id: UUID
    job_type: JobType
    status: JobStatus
    progress: int = Field(ge=0, le=100, description="Completion percentage (0-100).")
    current_step: str | None = None
    result: dict[str, object] | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class JobCreateRequest(BaseModel):
    """Request body for enqueuing a job (used by future feature endpoints)."""

    job_type: JobType
    payload: dict[str, object] = Field(default_factory=dict)
