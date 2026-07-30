"""Phase 7 — AI editing & proofreading schemas.

Pydantic v2 models used by both the API layer (request/response serialization)
and the service layer (typed payloads). Where possible the schema mirrors the
ORM model so `model_validate(orm_obj)` round-trips cleanly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SuggestionCategory = Literal[
    "grammar",
    "spelling",
    "punctuation",
    "clarity",
    "style",
    "tone",
    "structure",
    "consistency",
    "repetition",
    "fact_check",
]
SuggestionSeverity = Literal["low", "medium", "high"]
SuggestionStatus = Literal["pending", "accepted", "rejected", "ignored"]
EditingMode = Literal[
    "proofreading",
    "clarity_editing",
    "style_editing",
    "structural_editing",
    "consistency_check",
    "repetition_check",
    "full_review",
    "fact_check",
]
ReviewJobStatus = Literal[
    "queued", "processing", "saving_suggestions", "completed", "failed", "cancelled"
]


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------
class ReviewRequest(BaseModel):
    """Run an AI review / proofread / analysis on a chapter.

    `selected_text` (when present) limits the review to that excerpt; otherwise
    the whole chapter is reviewed. `mode` selects which editing checks run.
    """
    mode: EditingMode = "proofreading"
    selected_text: str | None = None
    instruction: str | None = None
    provider: str | None = None
    model: str | None = None


class SelectionActionRequest(BaseModel):
    """Rewrite / improve a selected piece of text (single suggestion)."""
    selected_text: str
    action: Literal[
        "rewrite",
        "improve_clarity",
        "make_more_professional",
        "make_more_conversational",
        "simplify",
        "improve_flow",
        "reduce_repetition",
        "expand_explanation",
        "shorten",
        "proofread",
    ]
    instruction: str | None = None
    provider: str | None = None
    model: str | None = None


class StartFullReviewRequest(BaseModel):
    """Start a full-manuscript (multi-chapter) review job."""
    mode: EditingMode = "full_review"
    chapter_ids: list[UUID] | None = None
    provider: str | None = None
    model: str | None = None


class SuggestionStatusUpdate(BaseModel):
    """Optional metadata when accepting/rejecting a suggestion."""
    reason: str | None = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
class SuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chapter_id: UUID
    session_id: UUID
    batch_id: UUID | None = None
    category: SuggestionCategory
    severity: SuggestionSeverity
    confidence: float
    original_text: str
    suggested_text: str | None = None
    explanation: str | None = None
    location_data: dict = Field(default_factory=dict)
    status: SuggestionStatus
    created_at: datetime
    updated_at: datetime
    accepted_at: datetime | None = None
    rejected_at: datetime | None = None
    ignored_at: datetime | None = None


class EditingSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    book_id: UUID
    chapter_id: UUID
    user_id: UUID
    mode: EditingMode
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    suggestions: list[SuggestionResponse] = Field(default_factory=list)


class ReviewJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    book_id: UUID
    chapter_id: UUID | None = None
    mode: EditingMode
    status: ReviewJobStatus
    total_items: int
    processed_items: int
    progress: float
    progress_data: list[dict] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    failed_at: datetime | None = None


class ReviewSummaryResponse(BaseModel):
    """Aggregate stats shown on the review dashboard."""
    total: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    high_severity: int = 0
    accepted: int = 0
    rejected: int = 0
    pending: int = 0
    ignored: int = 0


class ChapterReviewResponse(BaseModel):
    """Returned by single-chapter review endpoints."""
    session: EditingSessionResponse
    suggestions: list[SuggestionResponse]


class DiffResponse(BaseModel):
    """Result of comparing original_text vs suggested_text."""
    original: str
    suggested: str
    segments: list[dict]


class BulkActionResponse(BaseModel):
    """Result of accept-all / reject-all on a chapter."""
    updated: int
    chapter_version_created: bool
    chapter_id: UUID
