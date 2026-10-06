"""Canonical identity helpers for project books and writing books.

Public writing routes use ``WritingBook.id`` while legacy project assets and
records reference ``Book.id``. Every crossing between those namespaces must use
``WritingBook.project_book_id``; title or metadata matching is intentionally not
supported here.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ResourceNotFoundError, ValidationAppError
from models.accounts import User
from models.book_writing import WritingBook
from models.project import Book as ProjectBook


def require_project_book_id(book: WritingBook) -> UUID:
    """Return the persisted project-book link or fail closed if unresolved."""
    if book.project_book_id is None:
        raise ValidationAppError(
            "Book link missing: this writing book has no unambiguous project-book link, "
            "so project assets cannot be created yet. Contact support to repair the link."
        )
    return book.project_book_id


async def get_owned_writing_book(
    session: AsyncSession,
    user: User,
    writing_book_id: UUID,
) -> WritingBook:
    """Load a non-deleted writing book owned by the authenticated user."""
    book = await session.get(WritingBook, writing_book_id)
    if book is None or book.deleted_at is not None or book.user_id != user.id:
        raise ResourceNotFoundError("Book not found.")
    return book


async def get_owned_writing_book_by_project_book_id(
    session: AsyncSession,
    user: User,
    project_book_id: UUID,
) -> WritingBook:
    """Resolve a project-level asset parent back to its owned writing book."""
    result = await session.execute(
        select(WritingBook).where(
            WritingBook.project_book_id == project_book_id,
            WritingBook.user_id == user.id,
            WritingBook.deleted_at.is_(None),
        )
    )
    book = result.scalar_one_or_none()
    if book is None:
        raise ResourceNotFoundError("Book not found.")
    return book


async def resolve_project_book_id(
    session: AsyncSession,
    raw_book_id: object | None,
) -> UUID | None:
    """Resolve either a project-book ID or writing-book ID to ``Book.id``.

    This is for nullable persistence fields such as job records. Feature-facing
    APIs should use :func:`get_owned_writing_book` and
    :func:`require_project_book_id` so unresolved identity is surfaced rather
    than silently detached.
    """
    if raw_book_id is None:
        return None
    try:
        book_id = UUID(str(raw_book_id))
    except (TypeError, ValueError):
        return None

    project_book = await session.get(ProjectBook, book_id)
    writing_book = await session.get(WritingBook, book_id)
    if project_book is not None:
        if writing_book is not None and writing_book.project_book_id != project_book.id:
            return None
        return project_book.id

    return writing_book.project_book_id if writing_book is not None else None
