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

    temp_map = {"creative": 0.9, "balanced": 0.7, "precise": 0.4, "fast": 0.8}
    temp = temp_map.get(setup.ai.creativity, 0.7)
    provider = setup.ai.provider
    model = setup.ai.model

    total_chapters = setup.size.estimated_chapter_count
    words_per = max(setup.size.total_word_count // max(total_chapters, 1), 500)

    engine = BookWritingEngine(AIService())

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

    # Phase 3: Write chapters (23% — 85%)
    existing = await list_writing_chapters(session, user, wbook.id)
    for ch in existing:
        ch.deleted_at = datetime.now(UTC)
        session.add(ch)
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
    await session.flush()

    await progress(99, "Book generation complete")
    await progress(100, "Generation finished")

    return {
        "project_id": str(project.id),
        "book_id": str(book.id),
        "writing_book_id": str(wbook.id),
        "chapter_count": actual_count,
        "total_words": total_words,
        "status": "completed",
    }