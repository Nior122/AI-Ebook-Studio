"""KDP validation schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class KDPCheckItem(BaseModel):
    """A single validation check result."""

    check: str
    message: str
    recommendation: str | None = None


class KDPValidationReportResponse(BaseModel):
    """KDP validation report response."""

    id: UUID
    book_id: UUID
    status: str
    score: int
    issues: list[dict[str, object]]
    warnings: list[dict[str, object]]
    passed_checks: list[dict[str, object]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KDPValidationSummary(BaseModel):
    """Summary stats for KDP validation."""

    total_checks: int
    passed: int
    warnings: int
    issues: int
    status: str
    score: int