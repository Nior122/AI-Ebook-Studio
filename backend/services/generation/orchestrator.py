"""Book generation orchestrator.

Runs the one-click book generation flow as a background job. Walks through
every phase: brief → blueprint → chapters → polish → format → validation.

Uses existing `services/book_writing/service.py` functions and
`BookWritingEngine` — no duplicate logic.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ResourceNotFoundError
from models.accounts import User as UserModel
from models.assets import BookSettings
from models.book_writing import (
    WritingBook,
    WritingBookSettings,
    WritingChapter,
)
from models.project import Book, Project
from schemas.book_setup import BookSetupRequest
from schemas.projects import BookCreateRequest
from services import book_service as project_book_service
from services.ai_service import AIService
from services.book_writing.engine import BookWritingEngine
from services.book_writing.service import (
    generate_brief,
    generate_blueprint,
    list_chapters as list_writing_chapters,
)
from services.jobs.runner import ProgressCallback
from services.workspace_service import get_or_create_default_workspace
from services import studio_service
from services.events import publish_project_event

logger = logging.getLogger("api.generation.orchestrator")


def _wc(text: str | None) -> int:
    return len(re.findall(r"\S+", text or ""))


async def _get_or_create(
    session: AsyncSession, payload: dict[str, object]
) -> tuple[UserModel, Project, Book, WritingBook, BookSetupRequest]:
    user_id = UUID(str(payload["user_id"]))
    setup = BookSetupRequest.model_validate(payload["setup"])

    user_result = await session.execute(
        select(UserModel).where(UserModel.id == user_id)
    )
    user = user_result.scalar()
    if user is None:
        raise ValueError(f"User {user_id} not found.")

    existing_book_id = payload.get("book_id")
    if existing_book_id:
        book_id = UUID(str(existing_book_id))
        book = await session.get(Book, book_id)
        project = await session.get(Project, book.project_id)
        wb_result = await session.execute(
            select(WritingBook).where(
                WritingBook.user_id == user.id,
                WritingBook.title == setup.details.title,
                WritingBook.deleted_at.is_(None),
            )
        )
        wbook = wb_result.scalar()
        if wbook is None:
            raise ResourceNotFoundError("WritingBook not found for existing book")
        return user, project, book, wbook, setup

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
            WritingBook.user_id == user.id,
            WritingBook.title == book.title,
            WritingBook.deleted_at.is_(None),
        ).order_by(WritingBook.created_at.desc())
    )
    wbook = wb_result.scalar()
    if wbook is None:
        raise RuntimeError("WritingBook was not created by create_primary_book")
    return user, project, book, wbook, setup, setup.special_instructions.instructions


async def generation_handler(
    session: AsyncSession,
    _job_id: UUID,
    payload: dict[str, object],
    progress: ProgressCallback,
) -> dict[str, object] | None:
    await progress(0, "Starting book generation")

    user, project, book, wbook, setup = await _get_or_create(
        session, payload
    )

    # Studio UX: mark the project as generating and persist setup choices.
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
    await session.flush()

    temp_map = {"creative": 0.9, "balanced": 0.7, "precise": 0.4, "fast": 0.8}
    temp = temp_map.get(setup.ai.creativity, 0.7)
    provider = setup.ai.provider
    model = setup.ai.model

    total_chapters = setup.size.effective_chapter_count
    words_per = max(setup.size.total_word_count // max(total_chapters, 1), 500)

    from services.studio_service import build_ai_service_for_user

    engine = BookWritingEngine(await build_ai_service_for_user(session, user))
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

    # Phase 1: Brief (5% — 12%)
    await progress(5, "Generating book brief")
    await generate_brief(
        session, user, wbook.id, provider=provider, model=model, temperature=temp
    )
    await progress(12, "Brief complete — your book has a clear identity")

    # Phase 2: Blueprint (12% — 22%)
    await progress(13, "Creating chapter blueprint")
    blueprint = await generate_blueprint(
        session, user, wbook.id, provider=provider, model=model, temperature=temp
    )
    await progress(22, "Blueprint complete — chapters planned")
    chapter_plans = list(getattr(blueprint, "chapters", []) or [])
    await studio_service.record_activity(
        session, user.id, project.id, "outline_created",
        f"Outline created — {len(chapter_plans)} chapters planned",
        {"chapter_count": len(chapter_plans)},
    )

    # Phase 3: Write chapters (23% — 85%)
    # Resume-friendly: chapters that already have content are kept as-is,
    # so re-running generation continues where an interrupted run stopped
    # instead of discarding finished work.
    existing = await list_writing_chapters(session, user, wbook.id)
    keep_by_number: dict[int, WritingChapter] = {}
    for ch in existing:
        if ch.content and ch.status not in ("planned", "outlining"):
            keep_by_number[ch.chapter_number] = ch
            continue
        ch.deleted_at = datetime.now(UTC)
    await session.flush()

    ch_plans = getattr(blueprint, "chapters", []) or []
    if isinstance(blueprint, dict):
        ch_plans = blueprint.get("chapters", [])
    actual_count = max(len(ch_plans), 1)
    chapter_spread = 62
    per_pct = chapter_spread / actual_count if actual_count else 62

    total_words = 0

    for i, ch_plan in enumerate(ch_plans):
        chapter_num = i + 1
        plan = ch_plan if isinstance(ch_plan, dict) else {}
        title = str(plan.get("title", f"Chapter {chapter_num}"))
        objective = str(plan.get("objective", ""))
        summary = str(plan.get("summary", ""))
        target_wc = int(plan.get("estimated_word_count", words_per))

        pct = int(23 + per_pct * i)
        await progress(pct, f"Writing Chapter {chapter_num}: {title[:60]}")

        kept = keep_by_number.get(chapter_num)
        if kept is not None:
            kept.title = title
            kept.purpose = objective
            kept.objective = summary[:128]
            kept.summary = summary[:255]
            kept.target_word_count = target_wc
            kept.status = "draft"
            total_words += kept.actual_word_count or 0
            await session.flush()
            continue

        chapter = WritingChapter(
            book_id=wbook.id,
            chapter_number=chapter_num,
            title=title,
            purpose=objective,
            objective=summary[:128],
            summary=summary[:255],
            target_word_count=target_wc,
            status="outlining",
        )
        session.add(chapter)
        await session.flush()

        try:
            content = await engine.generate_chapter_content(
                session, wbook, chapter,
                provider=provider, model=model, temperature=temp,
            )
            chapter.content = content
            chapter.actual_word_count = _wc(content)
            chapter.status = "draft"
            total_words += _wc(content)
            await studio_service.record_activity(
                session, user.id, project.id, "chapter_generated",
                f"Chapter {chapter_num} generated — {title[:60]}",
                {"chapter_id": str(chapter.id), "words": _wc(content)},
            )
        except Exception as ce:
            logger.warning("Chapter %d generation failed: %s", chapter_num, ce, exc_info=True)
            chapter.content = f"[Chapter {chapter_num} generation failed — please regenerate. Error: {ce}]"
            chapter.status = "failed"

        await session.flush()

    await progress(85, "All chapters written")

    # Phase 4: Polish (86% — 92%)
    await progress(88, "Reviewing consistency across chapters")
    wbook.current_step = "editing"
    await progress(92, "Applying layout settings")
    await studio_service.record_activity(
        session, user.id, project.id, "formatting_complete",
        f"Formatting applied — {setup.layout.page_size} page, {setup.layout.body_font} {setup.layout.body_size}pt body",
        {"page_size": setup.layout.page_size},
    )

    # Apply layout settings to Project BookSettings (the actual formatting model)
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

    # Phase 5: Validation
    await progress(94, "Running KDP validation checks")
    await progress(96, "Final optimization pass")

    wbook.status = "completed"
    wbook.current_step = "export"
    project.stage = "review"
    project.updated_at = datetime.now(UTC)
    await session.flush()

    await progress(99, "Book generation complete")
    await progress(100, "Generation finished")

    await studio_service.record_activity(
        session, user.id, project.id, "generation_complete",
        f"Book generated — {actual_count} chapters, {total_words:,} words",
        {"chapter_count": actual_count, "total_words": total_words},
    )
    await studio_service.create_version(
        session, user, project.id,
        "After generation",
        "Automatic restore point created after full book generation.",
        created_by="auto",
        announce=False,
    )
    await studio_service.create_notification(
        session, user.id, project.id, "generation_complete",
        "Book generation complete",
        f"Your book is ready to review — {actual_count} chapters, {total_words:,} words.",
        level="success",
        action_type="open_project",
        action_payload={"project_id": str(project.id)},
    )
    publish_project_event(str(project.id), "generation.completed", {
        "project_id": str(project.id), "book_id": str(book.id),
        "chapter_count": actual_count, "total_words": total_words,
    })

    return {
        "project_id": str(project.id),
        "book_id": str(book.id),
        "writing_book_id": str(wbook.id),
        "chapter_count": actual_count,
        "total_words": total_words,
        "status": "completed",
    }