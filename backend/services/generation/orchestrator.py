"""Book generation orchestrator.

Runs the one-click book generation flow as a background job. Delegates the
actual book production to :class:`services.generation.pipeline.GenerationPipeline`
— a multi-stage, resume-friendly pipeline:

    Specification (topic lock) → Blueprint → Chapter outlines
    → section-by-section writing → validation → auto-revision
    → introduction/conclusion → manuscript assembly + quality report

This module keeps the job-integration concerns: resolving user/project/book,
persisting setup choices, progress reporting, activity/notification recording,
and failure handling.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictError, ResourceNotFoundError
from models.accounts import User as UserModel
from models.assets import BookSettings
from models.book_writing import (
    WritingBook,
    WritingBookSettings,
)
from models.project import Book, Project
from schemas.book_setup import BookSetupRequest
from schemas.projects import BookCreateRequest
from services import book_service as project_book_service
from services import studio_service
from services.book_writing.engine import BookWritingEngine
from services.events import publish_project_event
from services.generation.pipeline import GenerationPipeline
from services.jobs.runner import ProgressCallback
from services.workspace_service import get_or_create_default_workspace

logger = logging.getLogger("api.generation.orchestrator")


async def _reconstruct_setup(
    session: AsyncSession, book: Book, wbook: WritingBook
) -> BookSetupRequest:
    """Rebuild a setup payload from stored state (resume without original)."""
    from services.generation.pipeline import load_specification

    spec = await load_specification(session, wbook.id)
    ai_meta = (book.metadata_json or {}).get("ai_settings", {}) or {}

    topic = (
        (spec.topic if spec is not None else None)
        or book.description
        or wbook.description
        or wbook.title
    )
    words = (
        (spec.target_word_count if spec is not None else None)
        or wbook.target_word_count
        or 10000
    )
    chapters = spec.chapter_count if spec is not None else None

    return BookSetupRequest.model_validate(
        {
            "details": {
                "title": wbook.title,
                "subtitle": wbook.subtitle,
                "topic": topic,
                "target_audience": wbook.target_audience or "general readers",
                "tone": wbook.tone or "conversational",
                "writing_style": "practical_guide",
                "language": wbook.language or "en",
                "author": wbook.author_name,
            },
            "size": {
                "total_word_count": words,
                **({"chapters_override": chapters} if chapters else {}),
            },
            "ai": {
                "provider": ai_meta.get("provider", "openrouter"),
                "model": ai_meta.get("model", "openai/gpt-4o-mini"),
                **(
                    {"creativity": ai_meta["creativity"]}
                    if ai_meta.get("creativity")
                    else {}
                ),
            },
            "special_instructions": {
                "instructions": (book.metadata_json or {}).get("special_instructions") or ""
            },
        }
    )


async def _get_or_create(
    session: AsyncSession, payload: dict[str, object]
) -> tuple[UserModel, Project, Book, WritingBook, BookSetupRequest]:
    user_id = UUID(str(payload["user_id"]))

    user_result = await session.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    user = user_result.scalar()
    if user is None:
        raise ValueError(f"User {user_id} not found.")

    raw_setup = payload.get("setup")
    setup = BookSetupRequest.model_validate(raw_setup) if raw_setup else None

    book: Book | None = None
    wbook: WritingBook | None = None

    # Resume path 1: writing book id (most reliable).
    existing_writing_book_id = payload.get("writing_book_id")
    if existing_writing_book_id:
        wbook = await session.get(WritingBook, UUID(str(existing_writing_book_id)))
        if wbook is None or wbook.deleted_at is not None or wbook.user_id != user.id:
            raise ResourceNotFoundError("WritingBook not found for existing book")
        if wbook.project_book_id is not None:
            book = await session.get(Book, wbook.project_book_id)

    # Resume path 2: primary book id.
    if wbook is None and payload.get("book_id"):
        book = await session.get(Book, UUID(str(payload["book_id"])))
        if book is not None:
            wbook_result = await session.execute(
                select(WritingBook).where(
                    WritingBook.project_book_id == book.id,
                    WritingBook.user_id == user.id,
                    WritingBook.deleted_at.is_(None),
                )
            )
            wbook = wbook_result.scalar_one_or_none()
            if wbook is None:
                raise ConflictError(
                    "This project book has no unambiguous writing-book link. "
                    "Repair the relationship before resuming generation."
                )

    if wbook is not None:
        if book is None:
            raise ResourceNotFoundError("Primary Book not found for writing book")
        if wbook.deleted_at is not None or wbook.user_id != user.id:
            raise ResourceNotFoundError("WritingBook not found for existing book")
        if setup is None:
            setup = await _reconstruct_setup(session, book, wbook)
        project = await session.get(Project, book.project_id)
        return user, project, book, wbook, setup

    if setup is None:
        raise ValueError("Payload must include a setup for first-run generation.")

    ws = await get_or_create_default_workspace(session, user)
    project = Project(
        workspace_id=ws.id,
        owner_user_id=user.id,
        name=setup.details.title,
        title=setup.details.title,
        description=setup.details.topic,
        status="active",
    )
    session.add(project)
    await session.flush()

    book = await project_book_service.create_primary_book(
        session,
        user,
        project,
        BookCreateRequest(
            title=setup.details.title,
            subtitle=setup.details.subtitle,
            language=setup.details.language,
            target_audience=setup.details.target_audience,
            writing_style=f"{setup.details.tone} / {setup.details.writing_style}",
            author_name=setup.details.author,
            description=setup.details.topic,
        ),
    )
    await session.refresh(book)

    wb_result = await session.execute(
        select(WritingBook).where(
            WritingBook.project_book_id == book.id,
            WritingBook.user_id == user.id,
            WritingBook.deleted_at.is_(None),
        )
    )
    wbook = wb_result.scalar_one_or_none()
    if wbook is None:
        raise RuntimeError("WritingBook relationship was not created with the project book")
    return user, project, book, wbook, setup


def _apply_setup_side_effects(
    book: Book, project: Project, setup: BookSetupRequest
) -> None:
    """Persist setup choices that live outside the writing pipeline."""
    project.stage = "generating"
    project.updated_at = datetime.now(UTC)
    if setup.details.author and not book.author_name:
        book.author_name = setup.details.author
    if not book.description and setup.details.topic:
        book.description = setup.details.topic
    book.metadata_json = {
        **(book.metadata_json or {}),
        "ai_settings": {
            "creativity": setup.ai.creativity,
            "speed": setup.ai.speed,
            "provider": setup.ai.provider,
            "model": setup.ai.model,
            "reading_level": setup.ai.reading_level,
            "writing_quality": setup.ai.writing_quality,
            "use_citations": setup.ai.use_citations,
            "generate_exercises": setup.ai.generate_exercises,
            "generate_summaries": setup.ai.generate_summaries,
        },
        "special_instructions": setup.special_instructions.instructions,
    }


async def _apply_layout_settings(
    session: AsyncSession, book: Book, setup: BookSetupRequest
) -> None:
    """Apply layout settings to the Project BookSettings (formatting model)."""
    bs_result = await session.execute(
        select(BookSettings).where(BookSettings.book_id == book.id)
    )
    bs = bs_result.scalar()
    if bs is None:
        bs = BookSettings(book_id=book.id)
        session.add(bs)
        await session.flush()

    bs.kdp_trim_size = str(setup.layout.page_size)
    bs.body_font = str(setup.layout.body_font)
    bs.body_font_size = float(setup.layout.body_size)
    bs.heading_font = str(setup.layout.header_font)
    bs.line_spacing = float(setup.layout.line_spacing)
    bs.paragraph_spacing = float(setup.layout.paragraph_spacing)
    bs.margin_top = float(setup.layout.margins.get("top", 1))
    bs.margin_bottom = float(setup.layout.margins.get("bottom", 1))
    bs.margin_left = float(setup.layout.margins.get("left", 1))
    bs.margin_right = float(setup.layout.margins.get("right", 1))
    bs.image_width = float(setup.layout.image_width)
    bs.image_aspect_ratio = str(setup.layout.image_ratio)
    bs.image_style = str(setup.layout.default_image_style)
    if setup.layout.custom_page_size:
        bs.custom_format_enabled = True
        bs.page_width = float(setup.layout.custom_page_size.get("width", 6))
        bs.page_height = float(setup.layout.custom_page_size.get("height", 9))
    await session.flush()


async def generation_handler(
    session: AsyncSession,
    job_id: UUID,
    payload: dict[str, object],
    progress: ProgressCallback,
) -> dict[str, object] | None:
    await progress(0, "Starting book generation")

    user, project, book, wbook, setup = await _get_or_create(session, payload)

    _apply_setup_side_effects(book, project, setup)

    # Record which job is driving this book (resume/status support).
    wbook.generation_job_id = job_id
    await session.flush()

    temp_map = {"creative": 0.9, "balanced": 0.7, "precise": 0.4, "fast": 0.8}
    temp = temp_map.get(setup.ai.creativity, 0.7)
    provider = setup.ai.provider
    model = setup.ai.model

    from services.studio_service import build_ai_service_for_user

    engine = BookWritingEngine(await build_ai_service_for_user(session, user))

    # Persist writing-style preferences onto the book settings row.
    ws_result = await session.execute(
        select(WritingBookSettings).where(WritingBookSettings.book_id == wbook.id)
    )
    wb_settings = ws_result.scalar_one_or_none()
    if wb_settings is None:
        wb_settings = WritingBookSettings(book_id=wbook.id)
        session.add(wb_settings)
    wb_settings.tone = setup.details.tone
    if setup.ai.reading_level:
        wb_settings.reading_level = setup.ai.reading_level
    wb_settings.use_practical_exercises = (
        "high" if setup.ai.generate_exercises else "medium"
    )
    wb_settings.preferred_provider = provider
    wb_settings.preferred_model = model
    wb_settings.temperature = temp
    await session.flush()

    async def announce(kind: str, message: str) -> None:
        await studio_service.record_activity(
            session, user.id, project.id, kind, message, {}
        )

    pipeline = GenerationPipeline(
        session,
        engine,
        user_id=user.id,
        wbook=wbook,
        setup=setup.model_dump(),
        provider=provider,
        model=model,
        temperature=temp,
        progress=progress,
        announce=announce,
    )

    try:
        summary = await pipeline.run()
    except Exception as exc:
        logger.exception("Book generation failed for book %s", wbook.id)
        wbook.status = "failed"
        state = dict(wbook.generation_state or {})
        state["last_error"] = str(exc)
        wbook.generation_state = {**state}
        project.stage = "draft"
        project.updated_at = datetime.now(UTC)
        # Commit explicitly: the job runner rolls back its session when the
        # handler raises, so the failure state would otherwise be lost.
        await session.commit()
        raise

    # Layout + formatting side effects.
    await _apply_layout_settings(session, book, setup)
    await studio_service.record_activity(
        session, user.id, project.id, "formatting_complete",
        f"Formatting applied — {setup.layout.page_size} page, "
        f"{setup.layout.body_font} {setup.layout.body_size}pt body",
        {"page_size": setup.layout.page_size},
    )

    chapter_count = int(summary.get("chapter_count", 0))
    total_words = int(summary.get("total_words", 0))
    status = str(summary.get("status", "ready_for_formatting"))
    quality_report = summary.get("quality_report") or {}
    fallback_units = int(quality_report.get("fallback_generated_units") or 0)

    project.stage = "review"
    project.updated_at = datetime.now(UTC)
    await session.flush()

    if fallback_units:
        await studio_service.record_activity(
            session, user.id, project.id, "generation_complete",
            f"Book generated with quality warnings — {chapter_count} chapters, "
            f"{total_words:,} words ({fallback_units} section(s) written by the "
            "offline fallback because the AI provider was unavailable)",
            {"chapter_count": chapter_count, "total_words": total_words,
             "fallback_generated_units": fallback_units},
        )
        await studio_service.create_notification(
            session, user.id, project.id, "generation_complete",
            "Book generated — review needed",
            f"Your book was generated ({chapter_count} chapters, {total_words:,} words), "
            "but the AI provider became unavailable partway through and some content "
            "came from the offline template. Please regenerate before publishing.",
            level="warning",
            action_type="open_project",
            action_payload={"project_id": str(project.id)},
        )
    else:
        await studio_service.record_activity(
            session, user.id, project.id, "generation_complete",
            f"Book generated — {chapter_count} chapters, {total_words:,} words",
            {"chapter_count": chapter_count, "total_words": total_words},
        )
        await studio_service.create_notification(
            session, user.id, project.id, "generation_complete",
            "Book generation complete",
            f"Your book is ready to review — {chapter_count} chapters, {total_words:,} words.",
            level="success",
            action_type="open_project",
            action_payload={"project_id": str(project.id)},
        )
    await studio_service.create_version(
        session, user, project.id,
        "After generation",
        "Automatic restore point created after full book generation.",
        created_by="auto",
        announce=False,
    )
    publish_project_event(str(project.id), "generation.completed", {
        "project_id": str(project.id), "book_id": str(book.id),
        "chapter_count": chapter_count, "total_words": total_words,
        "status": status,
    })

    return {
        "project_id": str(project.id),
        "book_id": str(book.id),
        "writing_book_id": str(wbook.id),
        "chapter_count": chapter_count,
        "total_words": total_words,
        "status": status,
        "quality_report": summary.get("quality_report"),
    }
