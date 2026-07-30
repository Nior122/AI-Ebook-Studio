"""Book, chapter, and book-settings endpoints.

All routes require authentication and enforce ownership through the service
layer (Book → Project → workspace permission). Database access lives in services,
never inline here.

Route groups (mounted under ``/api/v1``):

* ``/projects/{project_id}/book``      — primary book create/read
* ``/books/{book_id}``                 — book read/update
* ``/books/{book_id}/chapters``        — chapter list/create/reorder
* ``/chapters/{chapter_id}``           — chapter update/delete
* ``/books/{book_id}/settings``        — formatting settings read/update
"""

from uuid import UUID

from fastapi import APIRouter, status

from api.dependencies import CurrentUser, DatabaseSession
from core.exceptions import ConflictError, ResourceNotFoundError
from models.document import Chapter
from schemas.book_settings import BookSettingsRead, BookSettingsUpdate
from schemas.chapters import (
    ChapterCreate,
    ChapterRead,
    ChapterReorderRequest,
    ChapterUpdate,
)
from schemas.projects import BookCreateRequest, BookResponse, BookUpdateRequest
from services import book_service, book_settings_service, chapter_service
from services.project_service import get_project

router = APIRouter(tags=["books"])


def _chapter_read(chapters: list[Chapter], chapter: Chapter) -> ChapterRead:
    """Build a ChapterRead, deriving 1-indexed chapter_number from ordering."""
    number = chapters.index(chapter) + 1
    return ChapterRead(
        id=chapter.id,
        book_id=chapter.book_id,
        chapter_number=number,
        title=chapter.title,
        content=chapter.content,
        word_count=chapter.word_count,
        status=chapter.status,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
    )


# ---------------------------------------------------------------------------
# Primary book (project-scoped)
# ---------------------------------------------------------------------------
@router.post(
    "/projects/{project_id}/book",
    response_model=BookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create the primary book for a project",
)
async def create_project_book(
    project_id: UUID,
    payload: BookCreateRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> BookResponse:
    """Create the project's primary book (one primary book per project)."""
    project = await get_project(session, user, project_id)
    existing = await book_service.get_primary_book_for_project(session, user, project)
    if existing is not None:
        raise ConflictError("This project already has a primary book.")
    book = await book_service.create_primary_book(session, user, project, payload)
    return BookResponse.model_validate(book)


@router.get(
    "/projects/{project_id}/book",
    response_model=BookResponse,
    summary="Get the primary book for a project",
)
async def get_project_book(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> BookResponse:
    """Return the project's primary book."""
    project = await get_project(session, user, project_id)
    book = await book_service.get_primary_book_for_project(session, user, project)
    if book is None:
        raise ResourceNotFoundError("This project has no book yet.")
    return BookResponse.model_validate(book)


# ---------------------------------------------------------------------------
# Book (direct)
# ---------------------------------------------------------------------------
@router.get("/books/{book_id}", response_model=BookResponse, summary="Get a book")
async def get_book(book_id: UUID, session: DatabaseSession, user: CurrentUser) -> BookResponse:
    """Return a single book the user owns."""
    book = await book_service.get_book(session, user, book_id)
    return BookResponse.model_validate(book)


@router.patch("/books/{book_id}", response_model=BookResponse, summary="Update a book")
async def update_book(
    book_id: UUID,
    payload: BookUpdateRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> BookResponse:
    """Update editable book fields."""
    book = await book_service.update_book(session, user, book_id, payload)
    return BookResponse.model_validate(book)


# ---------------------------------------------------------------------------
# Chapters
# ---------------------------------------------------------------------------
@router.get(
    "/books/{book_id}/chapters",
    response_model=list[ChapterRead],
    summary="List chapters",
)
async def list_chapters(
    book_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> list[ChapterRead]:
    """List a book's chapters in order."""
    chapters = await chapter_service.list_chapters(session, user, book_id)
    return [_chapter_read(chapters, chapter) for chapter in chapters]


@router.post(
    "/books/{book_id}/chapters",
    response_model=ChapterRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a chapter",
)
async def create_chapter(
    book_id: UUID,
    payload: ChapterCreate,
    session: DatabaseSession,
    user: CurrentUser,
) -> ChapterRead:
    """Create a chapter at an optional position."""
    await chapter_service.create_chapter(session, user, book_id, payload)
    chapters = await chapter_service.list_chapters(session, user, book_id)
    created = next(c for c in chapters if c.title == payload.title)
    return _chapter_read(chapters, created)


@router.post(
    "/books/{book_id}/chapters/reorder",
    response_model=list[ChapterRead],
    summary="Reorder chapters",
)
async def reorder_chapters(
    book_id: UUID,
    payload: ChapterReorderRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> list[ChapterRead]:
    """Apply a full 1..N reordering of a book's chapters."""
    chapters = await chapter_service.reorder_chapters(session, user, book_id, payload)
    return [_chapter_read(chapters, chapter) for chapter in chapters]


@router.patch(
    "/chapters/{chapter_id}",
    response_model=ChapterRead,
    summary="Update a chapter",
)
async def update_chapter(
    chapter_id: UUID,
    payload: ChapterUpdate,
    session: DatabaseSession,
    user: CurrentUser,
) -> ChapterRead:
    """Update a chapter's content/title/position."""
    chapter = await chapter_service.update_chapter(session, user, chapter_id, payload)
    chapters = await chapter_service.list_chapters(session, user, chapter.book_id)
    return _chapter_read(chapters, next(c for c in chapters if c.id == chapter.id))


@router.delete(
    "/chapters/{chapter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chapter",
)
async def delete_chapter(
    chapter_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> None:
    """Soft-delete a chapter and renumber the rest."""
    await chapter_service.delete_chapter(session, user, chapter_id)


# ---------------------------------------------------------------------------
# Book settings
# ---------------------------------------------------------------------------
@router.get(
    "/books/{book_id}/settings",
    response_model=BookSettingsRead,
    summary="Get book formatting settings",
)
async def get_book_settings(
    book_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> BookSettingsRead:
    """Return a book's formatting settings (created with defaults if absent)."""
    settings = await book_settings_service.get_or_create_settings(session, user, book_id)
    return BookSettingsRead.model_validate(settings)


@router.patch(
    "/books/{book_id}/settings",
    response_model=BookSettingsRead,
    summary="Update book formatting settings",
)
async def update_book_settings(
    book_id: UUID,
    payload: BookSettingsUpdate,
    session: DatabaseSession,
    user: CurrentUser,
) -> BookSettingsRead:
    """Update a book's formatting settings before final conversion."""
    settings = await book_settings_service.update_settings(session, user, book_id, payload)
    return BookSettingsRead.model_validate(settings)
