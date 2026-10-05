"""One-click book generation endpoints.

POST /generation/setup                          — validate, create project+book, enqueue job
POST /generation/books/{id}/generate/resume     — resume interrupted generation
GET  /generation/books/{id}/generation-status   — stage, chapters, word counts, quality report
POST /generation/books/{id}/chapters/{n}/regenerate — regenerate one chapter
POST /generation/books/{id}/validate            — run the book-level quality audit
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel

from sqlalchemy import select

from api.dependencies import CurrentUser, DatabaseSession
from core.exceptions import ResourceNotFoundError, ServiceUnavailableError
from models.book_writing import WritingBook, WritingBookSettings
from models.operations import Job
from models.project import Book, Project
from providers.ai.base import AIProviderError
from schemas.book_setup import BookSetupRequest, BookSetupResponse
from schemas.projects import BookCreateRequest
from services import book_service as project_book_service
from services.book_writing.engine import BookWritingEngine
from services.generation.pipeline import (
    get_generation_status,
    regenerate_chapter as pipeline_regenerate_chapter,
    validate_book as pipeline_validate_book,
)
from services.jobs import enqueue_and_schedule
from services.jobs.enums import JobType
from services.studio_service import build_ai_service_for_user
from services.workspace_service import get_or_create_default_workspace

router = APIRouter(prefix="/generation", tags=["generation"])


def _check_ambiguities(setup: BookSetupRequest) -> list[dict[str, str]]:
    """Only flag truly blocking issues. Never let users get stuck in a loop.

    Hard blocks:
    - Chapter count vs word count is physically impossible (< 300 words/chap).
    - Topic is empty (nothing to write about).
    """
    questions: list[dict[str, str]] = []

    if not setup.details.topic or len(setup.details.topic.strip()) < 5:
        questions.append({
            "id": "topic",
            "question": "What topic would you like the book to cover? Please be a little more specific.",
            "placeholder": "e.g., Morning routines for sustainable productivity",
        })

    if setup.size.chapters_override:
        words_per_chapter = setup.size.total_word_count // setup.size.chapters_override
        if words_per_chapter < 300:
            questions.append({
                "id": "chapter_count",
                "question": (
                    f"The requested word count ({setup.size.total_word_count:,} words) "
                    f"is impossible with {setup.size.chapters_override} chapters - "
                    f"that is only ~{words_per_chapter} words per chapter. "
                    "Lower the chapter count or raise the word count."
                ),
                "placeholder": "e.g., 8 chapters or 20,000 words",
            })

    return questions


@router.post("/setup", response_model=BookSetupResponse, status_code=status.HTTP_201_CREATED)
async def start_book_generation(
    payload: BookSetupRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> BookSetupResponse:
    """Start book generation from the single-page setup.

    Creates project + book, enqueues a BOOK_GENERATION background job.
    If the setup has potential ambiguities, returns clarification_questions
    before creating anything.
    """
    questions = _check_ambiguities(payload)
    if questions:
        return BookSetupResponse(
            project_id=None,
            book_id=None,
            writing_book_id=None,
            job_id=None,
            clarification_questions=questions,
        )

    # Create project + book
    ws = await get_or_create_default_workspace(session, user)
    project = Project(
        workspace_id=ws.id,
        owner_user_id=user.id,
        name=payload.details.title,
        title=payload.details.title,
        description=payload.details.topic,
        status="active",
    )
    session.add(project)
    await session.flush()

    book = await project_book_service.create_primary_book(
        session, user, project,
        BookCreateRequest(
            title=payload.details.title,
            subtitle=payload.details.subtitle,
            language=payload.details.language,
            target_audience=payload.details.target_audience,
            writing_style=f"{payload.details.tone} / {payload.details.writing_style}",
        ),
    )
    wb_result = await session.execute(
        select(WritingBook).where(
            WritingBook.user_id == user.id,
            WritingBook.title == book.title,
            WritingBook.deleted_at.is_(None),
        ).order_by(WritingBook.created_at.desc())
    )
    wbook = wb_result.scalar()

    handle = await enqueue_and_schedule(
        JobType.BOOK_GENERATION,
        {
            "user_id": str(user.id),
            "project_id": str(project.id),
            "book_id": str(book.id),
            "writing_book_id": str(wbook.id) if wbook else None,
            "setup": payload.model_dump(),
        },
    )
    return BookSetupResponse(
        project_id=project.id,
        book_id=book.id,
        writing_book_id=wbook.id if wbook else None,
        job_id=handle.id,
        clarification_questions=None,
    )


# ---------------------------------------------------------------------------
# Phase 6 repair — pipeline control endpoints
# ---------------------------------------------------------------------------
async def _get_owned_writing_book(
    session: DatabaseSession, user: CurrentUser, book_id: UUID
) -> WritingBook:
    """Return a WritingBook owned by *user* or raise 404."""
    wbook = await session.get(WritingBook, book_id)
    if wbook is None or wbook.deleted_at is not None or wbook.user_id != user.id:
        raise ResourceNotFoundError("Book not found.")
    return wbook


async def _stored_ai_options(session: DatabaseSession, book_id: UUID) -> dict[str, str | None]:
    """Provider/model stored on the book's writing settings, if any."""
    result = await session.execute(
        select(WritingBookSettings).where(WritingBookSettings.book_id == book_id)
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        return {"provider": None, "model": None}
    return {"provider": settings.preferred_provider, "model": settings.preferred_model}


class GenerateOptions(BaseModel):
    """Optional provider/model overrides for synchronous pipeline operations."""

    provider: str | None = None
    model: str | None = None


@router.post(
    "/books/{book_id}/generate/resume",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Resume interrupted book generation",
)
async def resume_book_generation(
    book_id: UUID, session: DatabaseSession, user: CurrentUser
) -> dict[str, str]:
    """Re-enqueue the BOOK_GENERATION job for an existing book.

    Completed stages (spec, blueprint, outlines, written chapters) are kept;
    only missing/failed work is regenerated.
    """
    wbook = await _get_owned_writing_book(session, user, book_id)

    book_result = await session.execute(
        select(Book).where(Book.metadata_json["writing_book_id"].as_string() == str(wbook.id))
    )
    book = book_result.scalars().first()

    # Prefer the original setup payload from the most recent generation job so
    # layout/AI choices survive the resume.
    payload: dict[str, object] = {
        "user_id": str(user.id),
        "writing_book_id": str(wbook.id),
    }
    if book is not None:
        payload["book_id"] = str(book.id)
        payload["project_id"] = str(book.project_id)
        job_result = await session.execute(
            select(Job)
            .where(
                Job.job_type == JobType.BOOK_GENERATION.value,
                Job.user_id == user.id,
                Job.book_id == book.id,
            )
            .order_by(Job.created_at.desc())
            .limit(5)
        )
        for job_row in job_result.scalars():
            stored = (job_row.payload or {}).get("setup")
            if stored:
                payload["setup"] = stored
                break

    handle = await enqueue_and_schedule(JobType.BOOK_GENERATION, payload)
    return {
        "job_id": str(handle.id),
        "book_id": str(wbook.id),
        "status": "resumed",
    }


@router.get(
    "/books/{book_id}/generation-status",
    summary="Where generation stands for a book",
)
async def generation_status(
    book_id: UUID, session: DatabaseSession, user: CurrentUser
) -> dict[str, Any]:
    """Stage, per-chapter progress, word counts, and the quality report."""
    wbook = await _get_owned_writing_book(session, user, book_id)
    return await get_generation_status(session, wbook)


@router.post(
    "/books/{book_id}/chapters/{chapter_number}/regenerate",
    summary="Regenerate one chapter through the pipeline",
)
async def regenerate_chapter_endpoint(
    book_id: UUID,
    chapter_number: int,
    session: DatabaseSession,
    user: CurrentUser,
    options: GenerateOptions | None = None,
) -> dict[str, Any]:
    """Rewrite one chapter: outline sections → prose → validate → revise."""
    wbook = await _get_owned_writing_book(session, user, book_id)
    stored = await _stored_ai_options(session, wbook.id)
    provider = (options.provider if options and options.provider else stored["provider"]) or None
    model = (options.model if options and options.model else stored["model"]) or None

    engine = BookWritingEngine(await build_ai_service_for_user(session, user))
    try:
        chapter = await pipeline_regenerate_chapter(
            session, engine,
            user_id=user.id, wbook=wbook, chapter_number=chapter_number,
            provider=provider, model=model,
        )
    except LookupError as exc:
        raise ResourceNotFoundError(str(exc)) from exc
    except AIProviderError as exc:
        raise ServiceUnavailableError(
            "AI generation failed. Existing content was not changed.",
            details={"provider_error": str(exc)},
        ) from exc

    validation = chapter.validation_result or {}
    return {
        "chapter_id": str(chapter.id),
        "chapter_number": chapter.chapter_number,
        "title": chapter.title,
        "status": chapter.status,
        "word_count": chapter.actual_word_count,
        "target_word_count": chapter.target_word_count,
        "relevance_score": validation.get("relevance_score"),
        "outline_coverage": validation.get("outline_coverage"),
        "depth_score": validation.get("depth_score"),
        "continuity_score": validation.get("continuity_score"),
        "passed": validation.get("passed"),
        "revision_count": chapter.revision_count,
    }


@router.post(
    "/books/{book_id}/validate",
    summary="Run the book-level quality audit",
)
async def validate_book_endpoint(
    book_id: UUID, session: DatabaseSession, user: CurrentUser
) -> dict[str, Any]:
    """Score the assembled manuscript against its specification."""
    wbook = await _get_owned_writing_book(session, user, book_id)
    stored = await _stored_ai_options(session, wbook.id)
    engine = BookWritingEngine(await build_ai_service_for_user(session, user))
    try:
        return await pipeline_validate_book(
            session, engine,
            user_id=user.id, wbook=wbook,
            provider=stored["provider"], model=stored["model"],
        )
    except AIProviderError as exc:
        raise ServiceUnavailableError(
            "Validation failed.",
            details={"provider_error": str(exc)},
        ) from exc