"""Phase 7 — AI Editing & Proofreading API.

Mounted under /api/v1/editing. Every route is authenticated and enforces
ownership through the service layer (transitive user → book → chapter check).
AI calls and DB access live in services.editing, never here.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, status

from api.dependencies import CurrentUser, DatabaseSession
from schemas.editing import (
    BulkActionResponse,
    ChapterReviewResponse,
    DiffResponse,
    EditingSessionResponse,
    ReviewJobResponse,
    ReviewRequest,
    ReviewSummaryResponse,
    SelectionActionRequest,
    StartFullReviewRequest,
    SuggestionResponse,
    SuggestionStatusUpdate,
)
from services.editing import diff as diff_util
from services.editing.service import (
    accept_all,
    accept_suggestion,
    act_on_selection,
    get_review_job,
    get_suggestion,
    ignore_suggestion,
    list_review_jobs,
    list_suggestions,
    regenerate_suggestion,
    reject_all,
    reject_suggestion,
    review_chapter,
    review_summary,
    start_full_review,
    process_review_job,
)

router = APIRouter(prefix="/editing", tags=["ai-editing"])


# ---------------------------------------------------------------------------
# Review endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/chapters/{chapter_id}/review",
    response_model=ChapterReviewResponse,
    summary="Run an AI review on a chapter",
)
async def run_review(
    chapter_id: UUID,
    payload: Annotated[ReviewRequest, Body(embed=True)],
    session: DatabaseSession,
    user: CurrentUser,
) -> ChapterReviewResponse:
    result = await review_chapter(session, user, chapter_id, payload)
    return ChapterReviewResponse(
        session=EditingSessionResponse.model_validate(result["session"]),
        suggestions=[SuggestionResponse.model_validate(s) for s in result["suggestions"]],
    )


@router.post(
    "/chapters/{chapter_id}/review-selection",
    response_model=SuggestionResponse,
    summary="Rewrite / improve selected text (quick action)",
)
async def run_selection_action(
    chapter_id: UUID,
    payload: Annotated[SelectionActionRequest, Body(embed=True)],
    session: DatabaseSession,
    user: CurrentUser,
) -> SuggestionResponse:
    result = await act_on_selection(session, user, chapter_id, payload)
    return SuggestionResponse.model_validate(result["suggestion"])


# ---------------------------------------------------------------------------
# Individual suggestion routes (global /suggestions prefix)
# ---------------------------------------------------------------------------
@router.get(
    "/suggestions/{suggestion_id}",
    response_model=SuggestionResponse,
    summary="Get a single suggestion",
)
async def get_one_suggestion(
    suggestion_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> SuggestionResponse:
    sug = await get_suggestion(session, user, suggestion_id)
    return SuggestionResponse.model_validate(sug)


@router.post(
    "/suggestions/{suggestion_id}/accept",
    response_model=SuggestionResponse,
    summary="Accept a suggestion (applies to manuscript, creates version)",
)
async def accept_one(
    suggestion_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> SuggestionResponse:
    result = await accept_suggestion(session, user, suggestion_id)
    return SuggestionResponse.model_validate(result["suggestion"])


@router.post(
    "/suggestions/{suggestion_id}/reject",
    response_model=SuggestionResponse,
    summary="Reject a suggestion (manuscript unchanged)",
)
async def reject_one(
    suggestion_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    payload: Annotated[SuggestionStatusUpdate | None, Body(embed=True)] = None,
) -> SuggestionResponse:
    suggestion = await reject_suggestion(
        session, user, suggestion_id,
        reason=payload.reason if payload else None,
    )
    return SuggestionResponse.model_validate(suggestion)


@router.post(
    "/suggestions/{suggestion_id}/ignore",
    response_model=SuggestionResponse,
    summary="Ignore a suggestion (hide without changing manuscript)",
)
async def ignore_one(
    suggestion_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> SuggestionResponse:
    sug = await ignore_suggestion(session, user, suggestion_id)
    return SuggestionResponse.model_validate(sug)


@router.post(
    "/suggestions/{suggestion_id}/regenerate",
    response_model=SuggestionResponse,
    summary="Regenerate a suggestion (marks old as ignored, creates new pending)",
)
async def regen_one(
    suggestion_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> SuggestionResponse:
    sug = await regenerate_suggestion(session, user, suggestion_id)
    return SuggestionResponse.model_validate(sug)


# ---------------------------------------------------------------------------
# Chapter-scoped suggestion lists & bulk actions
# ---------------------------------------------------------------------------
@router.get(
    "/chapters/{chapter_id}/suggestions",
    response_model=list[SuggestionResponse],
    summary="List suggestions for a chapter",
)
async def list_chapter_suggestions(
    chapter_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    category: str | None = None,
    severity: str | None = None,
    status_filter: str | None = None,
) -> list[SuggestionResponse]:
    suggestions = await list_suggestions(
        session, user, chapter_id,
        category=category, severity=severity, status=status_filter,
    )
    return [SuggestionResponse.model_validate(s) for s in suggestions]


@router.post(
    "/chapters/{chapter_id}/suggestions/accept-all",
    response_model=BulkActionResponse,
    summary="Accept all pending suggestions for a chapter",
)
async def accept_all_pending(
    chapter_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> BulkActionResponse:
    result = await accept_all(session, user, chapter_id)
    return BulkActionResponse(**result)


@router.post(
    "/chapters/{chapter_id}/suggestions/reject-all",
    response_model=BulkActionResponse,
    summary="Reject all pending suggestions for a chapter",
)
async def reject_all_pending(
    chapter_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> BulkActionResponse:
    result = await reject_all(session, user, chapter_id)
    return BulkActionResponse(**result)


# ---------------------------------------------------------------------------
# Review summary
# ---------------------------------------------------------------------------
@router.get(
    "/chapters/{chapter_id}/review-summary",
    response_model=ReviewSummaryResponse,
    summary="Get review stats for a chapter",
)
async def get_review_summary(
    chapter_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> ReviewSummaryResponse:
    stats = await review_summary(session, user, chapter_id)
    return ReviewSummaryResponse(**stats)


# ---------------------------------------------------------------------------
# Diff utility
# ---------------------------------------------------------------------------
@router.post(
    "/diff",
    response_model=DiffResponse,
    summary="Compute textual diff between original_text and suggested_text",
)
async def compute_text_diff(
    payload: Annotated[dict[str, str], Body()],
) -> DiffResponse:
    """Return a segment diff for `original_text` vs `suggested_text`."""
    original = payload.get("original_text", "")
    suggested = payload.get("suggested_text", "")
    segments = diff_util.compute_diff(original, suggested)
    return DiffResponse(original=original, suggested=suggested, segments=segments)


# ---------------------------------------------------------------------------
# Review jobs (full manuscript batch)
# ---------------------------------------------------------------------------
@router.post(
    "/books/{book_id}/review-job/start",
    response_model=ReviewJobResponse,
    summary="Start a full-manuscript review job",
)
async def start_review_job(
    book_id: UUID,
    payload: Annotated[StartFullReviewRequest, Body(embed=True)],
    session: DatabaseSession,
    user: CurrentUser,
) -> ReviewJobResponse:
    job = await start_full_review(session, user, book_id, payload)
    return ReviewJobResponse.model_validate(job)


@router.post(
    "/review-jobs/{job_id}/process",
    response_model=ReviewJobResponse,
    summary="Process the next chapter in a review job",
)
async def process_job(
    job_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> ReviewJobResponse:
    job = await process_review_job(session, user, job_id)
    return ReviewJobResponse.model_validate(job)


@router.get(
    "/review-jobs/{job_id}",
    response_model=ReviewJobResponse,
    summary="Get review job status",
)
async def get_job(
    job_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> ReviewJobResponse:
    job = await get_review_job(session, user, job_id)
    return ReviewJobResponse.model_validate(job)


@router.get(
    "/books/{book_id}/review-jobs",
    response_model=list[ReviewJobResponse],
    summary="List review jobs for a book",
)
async def list_jobs(
    book_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> list[ReviewJobResponse]:
    jobs = await list_review_jobs(session, user, book_id)
    return [ReviewJobResponse.model_validate(j) for j in jobs]