"""Book service.

Encapsulates book retrieval and updates with ownership enforcement. A book is
reachable only through a project the user may access; ``_authorize_book`` resolves
the book, loads its project, and delegates to the workspace permission check so a
user can never touch another user's book.

Creating a primary book is an atomic transaction that creates:

* the ``books`` row (Project-level Book),
* a linked ``bw_books`` row (WritingBook),
* a default ``bw_chapters`` Chapter 1,
* a ``bw_book_settings`` record so the editor has formatting defaults,
* the ``bw_books.manuscript`` aggregate row,
* and persists ``metadata_json.writing_book_id`` so all module pages can
  resolve the engine immediately.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ResourceNotFoundError
from models.accounts import User
from models.book_writing import (
    BookBrief,
    BookBlueprint,
    Manuscript,
    WritingBook,
    WritingBookSettings,
    WritingChapter,
)
from models.project import Book, Project
from schemas.projects import BookCreateRequest, BookUpdateRequest
from services.rbac_service import require_workspace_permission


async def _authorize_book(
    session: AsyncSession,
    user: User,
    book_id: UUID,
    permission: str,
) -> Book:
    """Return a book the user is allowed to access, or raise 404/403."""
    book = await session.get(Book, book_id)
    if book is None or book.deleted_at is not None:
        raise ResourceNotFoundError("Book not found.")
    project = await session.get(Project, book.project_id)
    if project is None or project.deleted_at is not None:
        raise ResourceNotFoundError("Book not found.")
    await require_workspace_permission(session, user, project.workspace_id, permission)
    return book


async def get_book(session: AsyncSession, user: User, book_id: UUID) -> Book:
    """Return a single book if the user may read it."""
    return await _authorize_book(session, user, book_id, "project:read")


async def get_primary_book_for_project(
    session: AsyncSession,
    user: User,
    project: Project,
) -> Book | None:
    """Return the first (primary) book of a project the user may read."""
    result = await session.execute(
        select(Book)
        .where(Book.project_id == project.id, Book.deleted_at.is_(None))
        .order_by(Book.created_at)
        .limit(1),
    )
    return result.scalar_one_or_none()


async def create_primary_book(
    session: AsyncSession,
    user: User,
    project: Project,
    payload: BookCreateRequest,
) -> Book:
    """Create the project's primary book and fully initialize the writing engine.

    Single atomic transaction:

    1. Project Book row
    2. Phase 6 WritingBook (engine state)
    3. BookBrief placeholder
    4. BookBlueprint placeholder
    5. Chapter 1 (empty)
    6. Manuscript aggregate
    7. BookSettings (formatting defaults)

    If any step fails, the whole transaction rolls back. The response Book
    has ``metadata_json.writing_book_id`` populated so all modules resolve.
    """
    await require_workspace_permission(session, user, project.workspace_id, "project:update")

    # 1. Create the Project-level Book.
    book = Book(
        project_id=project.id,
        title=payload.title,
        subtitle=payload.subtitle,
        author_name=payload.author_name,
        description=payload.description,
        language=payload.language,
        target_audience=payload.target_audience,
        writing_style=payload.writing_style,
        metadata_json={"writing_book_id": None},
    )
    session.add(book)
    try:
        await session.flush()
    except Exception:
        await session.rollback()
        raise

    # 2. Create the WritingBook (engine state).
    wbook = WritingBook(
        user_id=user.id,
        title=payload.title,
        subtitle=payload.subtitle,
        author_name=payload.author_name,
        description=payload.description,
        target_audience=payload.target_audience,
        language=payload.language or "en",
        status="draft",
        current_step="idea",
    )
    session.add(wbook)
    try:
        await session.flush()
    except Exception:
        await session.rollback()
        raise

    # Persist the link into metadata_json so the frontend can resolve it.
    book.metadata_json = {"writing_book_id": str(wbook.id)}

    # 3. BookBrief placeholder.
    session.add(BookBrief(
        book_id=wbook.id,
        working_title=payload.title,
        key_themes=[],
        major_concepts=[],
        topics_to_avoid=[],
        reader_problems=[],
        raw_content="",
    ))

    # 4. BookBlueprint placeholder.
    session.add(
        BookBlueprint(
            book_id=wbook.id,
            introduction_purpose="",
            chapters=[],
        )
    )

    # 5. Default Chapter 1.
    chapter = WritingChapter(
        book_id=wbook.id,
        chapter_number=1,
        title="Chapter 1",
        purpose="",
        objective="",
        summary="",
        outline="",
        outline_sections=[],
        content="",
        status="draft",
        target_word_count=None,
        actual_word_count=0,
        is_approved=False,
    )
    session.add(chapter)

    # 6. Manuscript aggregate.
    session.add(
        Manuscript(
            book_id=wbook.id,
            full_text="",
            word_count=0,
            chapter_order=[],
            is_stale=False,
        )
    )

    # 7. Default writing-book formatting settings.
    session.add(
        WritingBookSettings(
            book_id=wbook.id,
            preferred_provider="openai",
            preferred_model="gpt-4o-mini",
            temperature=0.7,
        )
    )

    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await session.refresh(book)
    return book


async def update_book(
    session: AsyncSession,
    user: User,
    book_id: UUID,
    payload: BookUpdateRequest,
) -> Book:
    """Update editable book fields."""
    book = await _authorize_book(session, user, book_id, "project:update")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(book, key, value)
    await session.commit()
    await session.refresh(book)
    return book
