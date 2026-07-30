"""Book settings service.

Reads and updates per-book formatting settings with ownership enforcement.
Settings are lazily created with sensible defaults (6 x 9 trim, 16:9 images) the
first time they are requested. When a named ``kdp_trim_size`` is selected without
custom formatting, page dimensions are synced from :data:`models.enums.TRIM_SIZES`.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ResourceNotFoundError
from models.accounts import User
from models.assets import BookSettings
from models.enums import TRIM_SIZES
from models.project import Book, Project
from schemas.book_settings import BookSettingsUpdate
from services.rbac_service import require_workspace_permission


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


async def get_or_create_settings(
    session: AsyncSession,
    user: User,
    book_id: UUID,
) -> BookSettings:
    """Return a book's settings, creating defaults on first access."""
    await _authorize_book(session, user, book_id, "project:read")
    result = await session.execute(
        select(BookSettings).where(BookSettings.book_id == book_id),
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = BookSettings(book_id=book_id)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings


async def update_settings(
    session: AsyncSession,
    user: User,
    book_id: UUID,
    payload: BookSettingsUpdate,
) -> BookSettings:
    """Apply a partial update to a book's formatting settings."""
    await _authorize_book(session, user, book_id, "project:update")
    settings = await get_or_create_settings(session, user, book_id)

    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in changes.items():
        setattr(settings, key, value)

    # If a named trim size is chosen and custom formatting is off, sync page size.
    if not settings.custom_format_enabled and settings.kdp_trim_size in TRIM_SIZES:
        width, height = TRIM_SIZES[settings.kdp_trim_size]
        settings.page_width = width
        settings.page_height = height

    await session.commit()
    await session.refresh(settings)
    return settings
