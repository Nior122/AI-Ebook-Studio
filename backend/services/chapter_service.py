"""Chapter service.

Implements the flat chapter API on top of the document-tree ``Chapter`` model.
Responsibilities:

* Ownership enforcement (via the parent book/project → workspace permission).
* ``chapter_number`` <-> ``position`` mapping (users see 1-indexed numbers).
* Word-count calculation from the flat ``content`` field.
* Ordered insertion, updates, deletion with renumbering, and bulk reorder.
"""

from __future__ import annotations

import re
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ResourceNotFoundError, ValidationAppError
from models.accounts import User
from models.document import Chapter
from models.project import Book, Project
from schemas.chapters import ChapterCreate, ChapterReorderRequest, ChapterUpdate
from services.rbac_service import require_workspace_permission


def _word_count(content: str) -> int:
    """Return the number of whitespace-delimited words in ``content``."""
    return len(content.split()) if content and content.strip() else 0


def _slugify(title: str) -> str:
    """Build a URL-safe slug from a chapter title (uniqueness handled by suffix)."""
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return base or "chapter"


async def _authorize_book(
    session: AsyncSession,
    user: User,
    book_id: UUID,
    permission: str,
) -> Book:
    """Resolve a book the user may access through its project/workspace."""
    book = await session.get(Book, book_id)
    if book is None or book.deleted_at is not None:
        raise ResourceNotFoundError("Book not found.")
    project = await session.get(Project, book.project_id)
    if project is None or project.deleted_at is not None:
        raise ResourceNotFoundError("Book not found.")
    await require_workspace_permission(session, user, project.workspace_id, permission)
    return book


async def _authorize_chapter(
    session: AsyncSession,
    user: User,
    chapter_id: UUID,
    permission: str,
) -> Chapter:
    """Resolve a chapter the user may access."""
    chapter = await session.get(Chapter, chapter_id)
    if chapter is None or chapter.deleted_at is not None:
        raise ResourceNotFoundError("Chapter not found.")
    await _authorize_book(session, user, chapter.book_id, permission)
    return chapter


async def _ordered_chapters(session: AsyncSession, book_id: UUID) -> list[Chapter]:
    """Return a book's non-deleted chapters ordered by position."""
    result = await session.execute(
        select(Chapter)
        .where(Chapter.book_id == book_id, Chapter.deleted_at.is_(None))
        .order_by(Chapter.position),
    )
    return list(result.scalars())


def _to_chapter_number(chapters: list[Chapter], chapter: Chapter) -> int:
    """Return the 1-indexed number of a chapter within an ordered list."""
    return chapters.index(chapter) + 1


async def list_chapters(session: AsyncSession, user: User, book_id: UUID) -> list[Chapter]:
    """List all chapters of a book in order."""
    await _authorize_book(session, user, book_id, "project:read")
    return await _ordered_chapters(session, book_id)


async def create_chapter(
    session: AsyncSession,
    user: User,
    book_id: UUID,
    payload: ChapterCreate,
) -> Chapter:
    """Create a chapter, inserting it at the requested 1-indexed position."""
    book = await _authorize_book(session, user, book_id, "project:update")
    chapters = await _ordered_chapters(session, book_id)

    target_index = len(chapters)
    if payload.chapter_number is not None:
        if payload.chapter_number > len(chapters) + 1:
            raise ValidationAppError(
                f"chapter_number {payload.chapter_number} is out of range "
                f"(max {len(chapters) + 1})."
            )
        target_index = payload.chapter_number - 1

    # Shift positions of chapters at or after the insertion point.
    for existing in chapters[target_index:]:
        existing.position += 1

    chapter = Chapter(
        project_id=book.project_id,
        book_id=book.id,
        title=payload.title,
        slug=f"{_slugify(payload.title)}-{uuid4().hex[:8]}",
        position=target_index,
        content=payload.content,
        word_count=_word_count(payload.content),
    )
    session.add(chapter)
    await session.commit()
    await session.refresh(chapter)
    return chapter


async def update_chapter(
    session: AsyncSession,
    user: User,
    chapter_id: UUID,
    payload: ChapterUpdate,
) -> Chapter:
    """Update a chapter's title/content/status and optionally its position."""
    chapter = await _authorize_chapter(session, user, chapter_id, "project:update")

    if payload.title is not None:
        chapter.title = payload.title
    if payload.content is not None:
        chapter.content = payload.content
        chapter.word_count = _word_count(payload.content)
    if payload.status is not None:
        chapter.status = payload.status

    if payload.chapter_number is not None:
        await _move_chapter(session, chapter, payload.chapter_number)

    await session.commit()
    await session.refresh(chapter)
    return chapter


async def _move_chapter(session: AsyncSession, chapter: Chapter, chapter_number: int) -> None:
    """Move ``chapter`` to a new 1-indexed position, renumbering the rest."""
    chapters = await _ordered_chapters(session, chapter.book_id)
    if chapter_number > len(chapters):
        raise ValidationAppError(
            f"chapter_number {chapter_number} is out of range (max {len(chapters)})."
        )
    chapters = [c for c in chapters if c.id != chapter.id]
    chapters.insert(chapter_number - 1, chapter)
    for index, item in enumerate(chapters):
        item.position = index


async def reorder_chapters(
    session: AsyncSession,
    user: User,
    book_id: UUID,
    payload: ChapterReorderRequest,
) -> list[Chapter]:
    """Apply an explicit chapter ordering for a book."""
    await _authorize_book(session, user, book_id, "project:update")
    chapters = {c.id: c for c in await _ordered_chapters(session, book_id)}

    numbers = [item.chapter_number for item in payload.items]
    if sorted(numbers) != list(range(1, len(chapters) + 1)):
        raise ValidationAppError(
            "Reorder must assign each chapter a unique number from 1..N covering all chapters."
        )

    for item in payload.items:
        chapter = chapters.get(item.chapter_id)
        if chapter is None:
            raise ValidationAppError(f"Chapter {item.chapter_id} does not belong to this book.")
        chapter.position = item.chapter_number - 1

    await session.commit()
    return await _ordered_chapters(session, book_id)


async def delete_chapter(session: AsyncSession, user: User, chapter_id: UUID) -> None:
    """Soft-delete a chapter and renumber the remaining chapters."""
    chapter = await _authorize_chapter(session, user, chapter_id, "project:delete")
    from datetime import UTC, datetime

    chapter.deleted_at = datetime.now(UTC)
    remaining = [
        c for c in await _ordered_chapters(session, chapter.book_id) if c.id != chapter.id
    ]
    for index, item in enumerate(remaining):
        item.position = index
    await session.commit()
