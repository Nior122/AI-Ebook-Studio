"""Phase 6 — Book writing service layer.

Encapsulates all book-writing business logic and **enforces ownership** on every
operation: a ``user_id`` is always resolved from the authenticated user and used
in every query/lookup, so users can never access another user's books, chapters,
or versions (IDOR protection). All DB access lives here — the API router only
calls these functions and serializes responses.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConflictError, ResourceNotFoundError, ServiceUnavailableError
from models.accounts import User
from models.book_writing import (
    WritingBook as Book,
    BookBlueprint,
    BookBrief,
    WritingBookSettings as BookSettings,
    WritingChapter as Chapter,
    ChapterVersion,
    Manuscript,
    WritingSession,
)
from providers.ai.base import AIProviderError
from schemas.book_writing import (
    BlueprintChapterPlan,
    BookBriefUpdateRequest,
    BookBlueprintUpdateRequest,
    BookCreateRequest,
    BookSettingsUpdateRequest,
    BookUpdateRequest,
    ChapterCreateRequest,
    ChapterOutlineSection,
    ChapterReorderRequest,
    ChapterUpdateRequest,
)
from services.ai_service import AIService, get_ai_service

from .engine import BookWritingEngine


# ---------------------------------------------------------------------------
# ownership helpers
# ---------------------------------------------------------------------------
def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


async def _get_book(session: AsyncSession, user: User, book_id: UUID) -> Book:
    """Return a book owned by *user* or raise 404."""
    book = await session.get(Book, book_id)
    if book is None or book.deleted_at is not None or book.user_id != user.id:
        raise ResourceNotFoundError("Book not found.")
    return book


async def _get_chapter(session: AsyncSession, user: User, chapter_id: UUID) -> Chapter:
    """Return a chapter owned (transitively) by *user* or raise 404."""
    chapter = await session.get(Chapter, chapter_id)
    if chapter is None or chapter.deleted_at is not None:
        raise ResourceNotFoundError("Chapter not found.")
    book = await _get_book(session, user, chapter.book_id)
    return chapter


def _engine(user: User | None = None) -> BookWritingEngine:
    ai: AIService = get_ai_service()
    return BookWritingEngine(ai)


from contextlib import asynccontextmanager


@asynccontextmanager
async def _ai_guard():
    """Convert raw provider errors into a clean 503, preserving existing content."""
    try:
        yield
    except AIProviderError as exc:
        raise ServiceUnavailableError(
            "AI generation failed. Your existing content was not changed.",
            details={"provider_error": str(exc)},
        ) from exc


# ---------------------------------------------------------------------------
# Book CRUD
# ---------------------------------------------------------------------------
async def create_book(session: AsyncSession, user: User, payload: BookCreateRequest) -> Book:
    book = Book(user_id=user.id, **payload.model_dump())
    session.add(book)
    await session.commit()
    await session.refresh(book)
    return book


async def list_books(session: AsyncSession, user: User) -> list[Book]:
    result = await session.execute(
        select(Book).where(Book.user_id == user.id, Book.deleted_at.is_(None)).order_by(Book.created_at)
    )
    return list(result.scalars().all())


async def get_book(session: AsyncSession, user: User, book_id: UUID) -> Book:
    return await _get_book(session, user, book_id)


async def update_book(
    session: AsyncSession, user: User, book_id: UUID, payload: BookUpdateRequest
) -> Book:
    book = await _get_book(session, user, book_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(book, key, value)
    await session.commit()
    await session.refresh(book)
    return book


async def delete_book(session: AsyncSession, user: User, book_id: UUID) -> None:
    book = await _get_book(session, user, book_id)
    book.deleted_at = datetime.now(UTC)
    await session.commit()


# ---------------------------------------------------------------------------
# Book Brief
# ---------------------------------------------------------------------------
async def generate_brief(
    session: AsyncSession,
    user: User,
    book_id: UUID,
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.7,
) -> BookBrief:
    book = await _get_book(session, user, book_id)
    engine = _engine(user)
    async with _ai_guard():
        data = await engine.generate_brief(
            session, book, provider=provider, model=model, temperature=temperature, user_id=user.id
    )
    brief = await _upsert_brief(session, book, data)
    book.current_step = "blueprint"
    await session.commit()
    await session.refresh(brief)
    return brief


async def _upsert_brief(session: AsyncSession, book: Book, data: dict[str, Any]) -> BookBrief:
    result = await session.execute(select(BookBrief).where(BookBrief.book_id == book.id))
    brief = result.scalar_one_or_none()
    if brief is None:
        brief = BookBrief(book_id=book.id)
        session.add(brief)
    _apply_brief_fields(brief, data)
    await session.flush()
    return brief


def _apply_brief_fields(brief: BookBrief, data: dict[str, Any]) -> None:
    brief.working_title = data.get("working_title")
    brief.subtitle = data.get("subtitle")
    brief.book_purpose = data.get("book_purpose")
    brief.target_reader = data.get("target_reader")
    brief.reader_problems = data.get("reader_problems") or []
    brief.promised_transformation = data.get("promised_transformation")
    brief.tone = data.get("tone")
    brief.writing_style = data.get("writing_style")
    brief.key_themes = data.get("key_themes") or []
    brief.major_concepts = data.get("major_concepts") or []
    brief.topics_to_avoid = data.get("topics_to_avoid") or []
    brief.suggested_structure = data.get("suggested_structure")
    brief.estimated_chapter_count = data.get("estimated_chapter_count")
    brief.estimated_word_count = data.get("estimated_word_count")
    brief.raw_content = None


async def update_brief(
    session: AsyncSession, user: User, book_id: UUID, payload: BookBriefUpdateRequest
) -> BookBrief:
    book = await _get_book(session, user, book_id)
    result = await session.execute(select(BookBrief).where(BookBrief.book_id == book.id))
    brief = result.scalar_one_or_none()
    if brief is None:
        brief = BookBrief(book_id=book.id)
        session.add(brief)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(brief, key, value)
    await session.commit()
    await session.refresh(brief)
    return brief


async def get_brief(session: AsyncSession, user: User, book_id: UUID) -> BookBrief | None:
    book = await _get_book(session, user, book_id)
    result = await session.execute(
        select(BookBrief).where(BookBrief.book_id == book.id, BookBrief.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Book Blueprint
# ---------------------------------------------------------------------------
async def generate_blueprint(
    session: AsyncSession,
    user: User,
    book_id: UUID,
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.7,
) -> BookBlueprint:
    book = await _get_book(session, user, book_id)
    engine = _engine(user)
    async with _ai_guard():
        data = await engine.generate_blueprint(
            session, book, provider=provider, model=model, temperature=temperature, user_id=user.id
        )
    blueprint = await _upsert_blueprint(session, book, data)
    book.current_step = "outline"
    await session.commit()
    await session.refresh(blueprint)
    return blueprint


async def _upsert_blueprint(
    session: AsyncSession, book: Book, data: dict[str, Any]
) -> BookBlueprint:
    result = await session.execute(select(BookBlueprint).where(BookBlueprint.book_id == book.id))
    blueprint = result.scalar_one_or_none()
    if blueprint is None:
        blueprint = BookBlueprint(book_id=book.id)
        session.add(blueprint)
    chapters = [c for c in (data.get("chapters") or []) if isinstance(c, dict)]
    blueprint.introduction_purpose = data.get("introduction_purpose")
    blueprint.chapters = chapters
    blueprint.estimated_total_word_count = data.get("estimated_total_word_count")
    await session.flush()
    return blueprint


async def update_blueprint(
    session: AsyncSession, user: User, book_id: UUID, payload: BookBlueprintUpdateRequest
) -> BookBlueprint:
    book = await _get_book(session, user, book_id)
    result = await session.execute(select(BookBlueprint).where(BookBlueprint.book_id == book.id))
    blueprint = result.scalar_one_or_none()
    if blueprint is None:
        blueprint = BookBlueprint(book_id=book.id)
        session.add(blueprint)
    if payload.introduction_purpose is not None:
        blueprint.introduction_purpose = payload.introduction_purpose
    if payload.chapters is not None:
        blueprint.chapters = [c.model_dump() for c in payload.chapters]
    if payload.estimated_total_word_count is not None:
        blueprint.estimated_total_word_count = payload.estimated_total_word_count
    await session.commit()
    await session.refresh(blueprint)
    return blueprint


async def get_blueprint(session: AsyncSession, user: User, book_id: UUID) -> BookBlueprint | None:
    book = await _get_book(session, user, book_id)
    result = await session.execute(
        select(BookBlueprint).where(
            BookBlueprint.book_id == book.id, BookBlueprint.deleted_at.is_(None)
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Chapters
# ---------------------------------------------------------------------------
async def list_chapters(session: AsyncSession, user: User, book_id: UUID) -> list[Chapter]:
    book = await _get_book(session, user, book_id)
    result = await session.execute(
        select(Chapter)
        .where(Chapter.book_id == book.id, Chapter.deleted_at.is_(None))
        .order_by(Chapter.chapter_number)
    )
    return list(result.scalars().all())


async def create_chapter(
    session: AsyncSession, user: User, book_id: UUID, payload: ChapterCreateRequest
) -> Chapter:
    book = await _get_book(session, user, book_id)
    existing = await session.execute(
        select(Chapter).where(Chapter.book_id == book.id, Chapter.deleted_at.is_(None))
    )
    chapters = list(existing.scalars().all())

    if payload.chapter_number is None:
        number = (chapters[-1].chapter_number + 1) if chapters else 1
    else:
        number = payload.chapter_number
        await _shift_chapters(session, book.id, number)

    chapter = Chapter(
        book_id=book.id,
        chapter_number=number,
        title=payload.title,
        purpose=payload.purpose,
        objective=payload.objective,
        summary=payload.summary,
        target_word_count=payload.target_word_count,
        status="planned",
    )
    session.add(chapter)
    await session.commit()
    await session.refresh(chapter)
    return chapter


async def _shift_chapters(session: AsyncSession, book_id: UUID, from_number: int) -> None:
    result = await session.execute(
        select(Chapter).where(
            Chapter.book_id == book_id,
            Chapter.chapter_number >= from_number,
            Chapter.deleted_at.is_(None),
        )
    )
    for ch in result.scalars().all():
        ch.chapter_number += 1


async def update_chapter(
    session: AsyncSession, user: User, chapter_id: UUID, payload: ChapterUpdateRequest
) -> Chapter:
    chapter = await _get_chapter(session, user, chapter_id)
    data = payload.model_dump(exclude_unset=True)
    if "outline_sections" in data and data["outline_sections"] is not None:
        data["outline_sections"] = [s.model_dump() for s in data["outline_sections"]]
    if "content" in data and data["content"] is not None:
        chapter.actual_word_count = _word_count(data["content"])
        chapter.is_approved = False
    for key, value in data.items():
        setattr(chapter, key, value)
    await session.commit()
    await session.refresh(chapter)
    return chapter


async def reorder_chapters(
    session: AsyncSession, user: User, book_id: UUID, payload: ChapterReorderRequest
) -> list[Chapter]:
    book = await _get_book(session, user, book_id)
    result = await session.execute(
        select(Chapter).where(Chapter.book_id == book.id, Chapter.deleted_at.is_(None))
    )
    chapters = {ch.id: ch for ch in result.scalars().all()}
    if set(payload.chapter_ids) != set(chapters.keys()):
        raise ConflictError("Reorder must include all chapters of the book.")
    for index, chapter_id in enumerate(payload.chapter_ids, start=1):
        chapters[chapter_id].chapter_number = index
    await session.commit()
    return await list_chapters(session, user, book_id)


async def delete_chapter(session: AsyncSession, user: User, chapter_id: UUID) -> None:
    chapter = await _get_chapter(session, user, chapter_id)
    book_id = chapter.book_id
    number = chapter.chapter_number
    chapter.deleted_at = datetime.now(UTC)
    # Renumber following chapters.
    result = await session.execute(
        select(Chapter).where(
            Chapter.book_id == book_id,
            Chapter.chapter_number > number,
            Chapter.deleted_at.is_(None),
        )
    )
    for ch in result.scalars().all():
        ch.chapter_number -= 1
    await session.commit()


# ---------------------------------------------------------------------------
# AI chapter operations
# ---------------------------------------------------------------------------
async def generate_chapter_outline(
    session: AsyncSession, user: User, chapter_id: UUID, *, provider=None, model=None, temperature=0.6
) -> Chapter:
    chapter = await _get_chapter(session, user, chapter_id)
    book = await _get_book(session, user, chapter.book_id)
    engine = _engine(user)
    async with _ai_guard():
        data = await engine.generate_chapter_outline(
            session, book, chapter, provider=provider, model=model,
            temperature=temperature, user_id=user.id,
        )
    sections = [
        ChapterOutlineSection(
            title=s.get("title", ""),
            purpose=s.get("purpose"),
            key_points=s.get("key_points") or [],
        )
        for s in (data.get("sections") or [])
    ]
    chapter.title = data.get("title") or chapter.title
    chapter.outline_sections = [s.model_dump() for s in sections]
    chapter.outline = "\n".join(f"{s.title}: " + "; ".join(s.key_points) for s in sections)
    chapter.status = "outlining"
    await session.commit()
    await session.refresh(chapter)
    return chapter


async def generate_chapter_content(
    session: AsyncSession, user: User, chapter_id: UUID, *, provider=None, model=None, temperature=0.8
) -> Chapter:
    chapter = await _get_chapter(session, user, chapter_id)
    book = await _get_book(session, user, chapter.book_id)
    engine = _engine(user)
    async with _ai_guard():
        content = await engine.generate_chapter_content(
            session, book, chapter, provider=provider, model=model,
            temperature=temperature, user_id=user.id,
        )
    return await _save_chapter_content(
        session, chapter, content, version_type="ai_generated",
        generation_metadata={"provider": provider, "model": model, "task": "generate_chapter_content"},
        user_id=user.id,
    )


async def continue_chapter_content(
    session: AsyncSession, user: User, chapter_id: UUID, *, provider=None, model=None, temperature=0.8
) -> Chapter:
    chapter = await _get_chapter(session, user, chapter_id)
    book = await _get_book(session, user, chapter.book_id)
    engine = _engine(user)
    async with _ai_guard():
        more = await engine.continue_chapter(
            session, book, chapter, provider=provider, model=model,
            temperature=temperature, user_id=user.id,
        )
    combined = (chapter.content or "") + "\n\n" + more if chapter.content else more
    return await _save_chapter_content(
        session, chapter, combined, version_type="ai_generated",
        generation_metadata={"provider": provider, "model": model, "task": "continue_chapter"},
        user_id=user.id,
    )


async def regenerate_chapter_content(
    session: AsyncSession, user: User, chapter_id: UUID, *, provider=None, model=None, temperature=0.8
) -> Chapter:
    """Regenerate replacing existing content (after a version snapshot)."""
    chapter = await _get_chapter(session, user, chapter_id)
    book = await _get_book(session, user, chapter.book_id)
    engine = _engine(user)
    async with _ai_guard():
        content = await engine.generate_chapter_content(
            session, book, chapter, provider=provider, model=model,
            temperature=temperature, user_id=user.id,
        )
    return await _save_chapter_content(
        session, chapter, content, version_type="ai_generated",
        generation_metadata={"provider": provider, "model": model, "task": "regenerate_chapter_content"},
        user_id=user.id,
    )


async def edit_chapter(
    session: AsyncSession, user: User, chapter_id: UUID, action: str, *,
    instruction: str | None = None, selected_text: str | None = None,
    provider=None, model=None, temperature=0.5,
) -> Chapter:
    chapter = await _get_chapter(session, user, chapter_id)
    book = await _get_book(session, user, chapter.book_id)
    engine = _engine(user)
    async with _ai_guard():
        revised = await engine.edit_text(
            session, book, chapter, action,
            instruction=instruction, selected_text=selected_text,
            provider=provider, model=model, temperature=temperature, user_id=user.id,
        )
    # Editing keeps existing content; the revised text is returned as the new
    # content (caller decides whether it replaces selection or whole chapter).
    version_type = "ai_edited" if action in {"rewrite", "expand", "shorten"} else "ai_edited"
    return await _save_chapter_content(
        session, chapter, revised, version_type=version_type,
        generation_metadata={"action": action, "provider": provider, "model": model},
        user_id=user.id,
    )


async def _save_chapter_content(
    session: AsyncSession, chapter: Chapter, content: str, *, version_type: str,
    generation_metadata: dict[str, Any], user_id: UUID | None,
) -> Chapter:
    chapter.content = content
    chapter.actual_word_count = _word_count(content)
    chapter.status = "draft"
    chapter.is_approved = False
    # Snapshot a version.
    latest = await session.execute(
        select(ChapterVersion.version_number)
        .where(ChapterVersion.chapter_id == chapter.id)
        .order_by(ChapterVersion.version_number.desc())
        .limit(1)
    )
    last_number = latest.scalar_one_or_none() or 0
    version = ChapterVersion(
        chapter_id=chapter.id,
        version_number=last_number + 1,
        content=content,
        word_count=chapter.actual_word_count,
        version_type=version_type,
        generation_metadata=generation_metadata,
        created_by=user_id,
    )
    session.add(version)
    await session.commit()
    await session.refresh(chapter)
    return chapter


# ---------------------------------------------------------------------------
# Chapter versions
# ---------------------------------------------------------------------------
async def list_chapter_versions(
    session: AsyncSession, user: User, chapter_id: UUID
) -> list[ChapterVersion]:
    await _get_chapter(session, user, chapter_id)
    result = await session.execute(
        select(ChapterVersion)
        .where(ChapterVersion.chapter_id == chapter_id, ChapterVersion.deleted_at.is_(None))
        .order_by(ChapterVersion.version_number)
    )
    return list(result.scalars().all())


async def restore_chapter_version(
    session: AsyncSession, user: User, chapter_id: UUID, version_id: UUID
) -> Chapter:
    chapter = await _get_chapter(session, user, chapter_id)
    result = await session.execute(
        select(ChapterVersion).where(
            ChapterVersion.id == version_id,
            ChapterVersion.chapter_id == chapter.id,
            ChapterVersion.deleted_at.is_(None),
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise ResourceNotFoundError("Version not found.")
    chapter.content = version.content
    chapter.actual_word_count = version.word_count
    chapter.is_approved = False
    # Record the restore as a new version for history.
    latest = await session.execute(
        select(ChapterVersion.version_number)
        .where(ChapterVersion.chapter_id == chapter.id)
        .order_by(ChapterVersion.version_number.desc())
        .limit(1)
    )
    last_number = latest.scalar_one_or_none() or 0
    new_version = ChapterVersion(
        chapter_id=chapter.id,
        version_number=last_number + 1,
        content=version.content,
        word_count=version.word_count,
        version_type="user_edited",
        generation_metadata={"restored_from": str(version.id)},
        created_by=user.id,
    )
    session.add(new_version)
    await session.commit()
    await session.refresh(chapter)
    return chapter


# ---------------------------------------------------------------------------
# Manuscript snapshot
# ---------------------------------------------------------------------------
async def refresh_manuscript(session: AsyncSession, user: User, book_id: UUID) -> Manuscript:
    book = await _get_book(session, user, book_id)
    chapters = await list_chapters(session, user, book.id)
    parts = [f"# {book.title}\n"]
    if book.subtitle:
        parts.append(f"## {book.subtitle}\n")
    order: list[str] = []
    for ch in chapters:
        order.append(str(ch.id))
        parts.append(f"\n\n# Chapter {ch.chapter_number}: {ch.title}\n\n")
        parts.append(ch.content or "")
    full_text = "".join(parts)
    result = await session.execute(select(Manuscript).where(Manuscript.book_id == book.id))
    manuscript = result.scalar_one_or_none()
    if manuscript is None:
        manuscript = Manuscript(book_id=book.id)
        session.add(manuscript)
    manuscript.full_text = full_text
    manuscript.word_count = _word_count(full_text)
    manuscript.chapter_order = order
    manuscript.is_stale = False
    await session.commit()
    await session.refresh(manuscript)
    return manuscript


# ---------------------------------------------------------------------------
# Writing sessions (autosave)
# ---------------------------------------------------------------------------
async def begin_writing_session(
    session: AsyncSession, user: User, book_id: UUID, *, chapter_id: UUID | None = None,
    session_type: str = "autosave", resume_context: dict[str, Any] | None = None,
) -> WritingSession:
    book = await _get_book(session, user, book_id)
    ws = WritingSession(
        book_id=book.id,
        user_id=user.id,
        chapter_id=chapter_id,
        session_type=session_type,
        resume_context=resume_context,
    )
    session.add(ws)
    await session.commit()
    await session.refresh(ws)
    return ws


async def autosave_chapter(
    session: AsyncSession, user: User, book_id: UUID, chapter_id: UUID, content: str,
    *, version_type: str = "user_edited",
) -> Chapter:
    """Persist editor content during autosave without losing prior versions."""
    chapter = await _get_chapter(session, user, chapter_id)
    # Validate chapter belongs to the stated book (IDOR guard, belt-and-suspenders).
    if chapter.book_id != book_id:
        raise ResourceNotFoundError("Chapter not found.")
    return await _save_chapter_content(
        session, chapter, content, version_type=version_type,
        generation_metadata={"source": "autosave"}, user_id=user.id,
    )


# ---------------------------------------------------------------------------
# Book settings (writing style profile)
# ---------------------------------------------------------------------------
async def get_or_create_settings(
    session: AsyncSession, user: User, book_id: UUID
) -> BookSettings:
    book = await _get_book(session, user, book_id)
    result = await session.execute(
        select(BookSettings).where(BookSettings.book_id == book.id, BookSettings.deleted_at.is_(None))
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = BookSettings(book_id=book.id)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings


async def update_settings(
    session: AsyncSession, user: User, book_id: UUID, payload: BookSettingsUpdateRequest
) -> BookSettings:
    settings = await get_or_create_settings(session, user, book_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    await session.commit()
    await session.refresh(settings)
    return settings


# ---------------------------------------------------------------------------
# Workflow status
# ---------------------------------------------------------------------------
async def get_workflow(session: AsyncSession, user: User, book_id: UUID) -> dict[str, Any]:
    book = await _get_book(session, user, book_id)
    brief = await get_brief(session, user, book.id)
    blueprint = await get_blueprint(session, user, book.id)
    chapters = await list_chapters(session, user, book.id)
    version_count = 0
    for ch in chapters:
        vr = await session.execute(
            select(ChapterVersion).where(
                ChapterVersion.chapter_id == ch.id, ChapterVersion.deleted_at.is_(None)
            )
        )
        version_count += len(vr.scalars().all())
    return {
        "book_id": str(book.id),
        "current_step": book.current_step,
        "status": book.status,
        "has_brief": brief is not None,
        "has_blueprint": blueprint is not None,
        "chapter_count": len(chapters),
        "approved_chapter_count": sum(1 for c in chapters if c.is_approved),
        "version_count": version_count,
    }
