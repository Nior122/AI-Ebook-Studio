"""Phase 6 — Book Writing & Manuscript Management API.

Mounted under ``/api/v1/book-writing``. Every route is authenticated and
enforces ownership through the service layer (``user_id`` scoping). DB access
and AI calls live in :mod:`services.book_writing`, never here.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, status

from api.dependencies import CurrentUser, DatabaseSession
from core.exceptions import ResourceNotFoundError, ValidationAppError
from schemas.book_writing import (
    AutosaveRequest,
    BookBriefResponse,
    BookBriefUpdateRequest,
    BookBlueprintResponse,
    BookBlueprintUpdateRequest,
    BookCreateRequest,
    BookResponse,
    BookSettingsResponse,
    BookSettingsUpdateRequest,
    BookUpdateRequest,
    BookWorkflowResponse,
    ChapterCreateRequest,
    ChapterRead,
    ChapterReorderRequest,
    ChapterUpdateRequest,
    ChapterVersionResponse,
    GenerateRequest as _GenerateRequest,
    ManuscriptResponse,
    WritingSessionCreateRequest,
    WritingSessionResponse,
)
from services import book_writing as svc

router = APIRouter(prefix="/book-writing", tags=["book-writing"])

# Optional embedded JSON body for AI generation requests:
#   {"payload": {"provider": "...", "model": "...", "instruction": "..."}}
AnnotatedGenerate = Annotated[_GenerateRequest | None, Body(embed=True)]


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------
@router.post(
    "/books",
    response_model=BookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a book (Book Idea step)",
)
async def create_book(
    payload: BookCreateRequest, session: DatabaseSession, user: CurrentUser
) -> BookResponse:
    book = await svc.create_book(session, user, payload)
    return BookResponse.model_validate(book)


@router.get("/books", response_model=list[BookResponse], summary="List my books")
async def list_books(session: DatabaseSession, user: CurrentUser) -> list[BookResponse]:
    books = await svc.list_books(session, user)
    return [BookResponse.model_validate(b) for b in books]


@router.get("/books/{book_id}", response_model=BookResponse, summary="Get a book")
async def get_book(book_id: UUID, session: DatabaseSession, user: CurrentUser) -> BookResponse:
    book = await svc.get_book(session, user, book_id)
    return BookResponse.model_validate(book)


@router.patch("/books/{book_id}", response_model=BookResponse, summary="Update a book")
async def update_book(
    book_id: UUID, payload: Annotated[BookUpdateRequest, Body(embed=True)], session: DatabaseSession, user: CurrentUser
) -> BookResponse:
    book = await svc.update_book(session, user, book_id, payload)
    return BookResponse.model_validate(book)


@router.delete(
    "/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a book (soft)"
)
async def delete_book(book_id: UUID, session: DatabaseSession, user: CurrentUser):
    await svc.delete_book(session, user, book_id)


@router.get(
    "/books/{book_id}/workflow",
    response_model=BookWorkflowResponse,
    summary="Get book workflow progress",
)
async def get_workflow(
    book_id: UUID, session: DatabaseSession, user: CurrentUser
) -> BookWorkflowResponse:
    data = await svc.get_workflow(session, user, book_id)
    return BookWorkflowResponse(**data)


# ---------------------------------------------------------------------------
# Book Brief
# ---------------------------------------------------------------------------
@router.post(
    "/books/{book_id}/brief/generate",
    response_model=BookBriefResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a Book Brief with AI",
)
async def generate_brief(
    book_id: UUID, session: DatabaseSession, user: CurrentUser,
    payload: AnnotatedGenerate = None,
) -> BookBriefResponse:
    provider = getattr(payload, "provider", None) if payload else None
    model = getattr(payload, "model", None) if payload else None
    brief = await svc.generate_brief(session, user, book_id, provider=provider, model=model)
    return BookBriefResponse.model_validate(brief)


@router.get("/books/{book_id}/brief", response_model=BookBriefResponse, summary="Get the Book Brief")
async def get_brief(book_id: UUID, session: DatabaseSession, user: CurrentUser) -> BookBriefResponse:
    from core.exceptions import ResourceNotFoundError

    brief = await svc.get_brief(session, user, book_id)
    if brief is None:
        raise ResourceNotFoundError("Book brief not found. Generate one first.")
    return BookBriefResponse.model_validate(brief)


@router.patch(
    "/books/{book_id}/brief", response_model=BookBriefResponse, summary="Update the Book Brief"
)
async def update_brief(
    book_id: UUID, payload: Annotated[BookBriefUpdateRequest, Body(embed=True)], session: DatabaseSession, user: CurrentUser
) -> BookBriefResponse:
    brief = await svc.update_brief(session, user, book_id, payload)
    return BookBriefResponse.model_validate(brief)


# ---------------------------------------------------------------------------
# Book Blueprint
# ---------------------------------------------------------------------------
@router.post(
    "/books/{book_id}/blueprint/generate",
    response_model=BookBlueprintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a Book Blueprint with AI",
)
async def generate_blueprint(
    book_id: UUID, session: DatabaseSession, user: CurrentUser,
    payload: AnnotatedGenerate = None,
) -> BookBlueprintResponse:
    provider = getattr(payload, "provider", None) if payload else None
    model = getattr(payload, "model", None) if payload else None
    blueprint = await svc.generate_blueprint(session, user, book_id, provider=provider, model=model)
    return BookBlueprintResponse.model_validate(blueprint)


@router.get(
    "/books/{book_id}/blueprint",
    response_model=BookBlueprintResponse,
    summary="Get the Book Blueprint",
)
async def get_blueprint(
    book_id: UUID, session: DatabaseSession, user: CurrentUser
) -> BookBlueprintResponse:
    from core.exceptions import ResourceNotFoundError

    blueprint = await svc.get_blueprint(session, user, book_id)
    if blueprint is None:
        raise ResourceNotFoundError("Book blueprint not found. Generate one first.")
    return BookBlueprintResponse.model_validate(blueprint)


@router.patch(
    "/books/{book_id}/blueprint",
    response_model=BookBlueprintResponse,
    summary="Update the Book Blueprint",
)
async def update_blueprint(
    book_id: UUID, payload: Annotated[BookBlueprintUpdateRequest, Body(embed=True)], session: DatabaseSession, user: CurrentUser
) -> BookBlueprintResponse:
    blueprint = await svc.update_blueprint(session, user, book_id, payload)
    return BookBlueprintResponse.model_validate(blueprint)


# ---------------------------------------------------------------------------
# Chapters
# ---------------------------------------------------------------------------
@router.get("/books/{book_id}/chapters", response_model=list[ChapterRead], summary="List chapters")
async def list_chapters(
    book_id: UUID, session: DatabaseSession, user: CurrentUser
) -> list[ChapterRead]:
    chapters = await svc.list_chapters(session, user, book_id)
    return [ChapterRead.model_validate(c) for c in chapters]


@router.post(
    "/books/{book_id}/chapters",
    response_model=ChapterRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a chapter",
)
async def create_chapter(
    book_id: UUID, payload: ChapterCreateRequest, session: DatabaseSession, user: CurrentUser
) -> ChapterRead:
    chapter = await svc.create_chapter(session, user, book_id, payload)
    return ChapterRead.model_validate(chapter)


@router.post(
    "/books/{book_id}/chapters/reorder",
    response_model=list[ChapterRead],
    summary="Reorder chapters",
)
async def reorder_chapters(
    book_id: UUID, payload: ChapterReorderRequest, session: DatabaseSession, user: CurrentUser
) -> list[ChapterRead]:
    chapters = await svc.reorder_chapters(session, user, book_id, payload)
    return [ChapterRead.model_validate(c) for c in chapters]


@router.get("/chapters/{chapter_id}", response_model=ChapterRead, summary="Get a chapter")
async def get_chapter(
    chapter_id: UUID, session: DatabaseSession, user: CurrentUser
) -> ChapterRead:
    chapter = await svc._get_chapter(session, user, chapter_id)
    return ChapterRead.model_validate(chapter)


@router.patch("/chapters/{chapter_id}", response_model=ChapterRead, summary="Update a chapter")
async def update_chapter(
    chapter_id: UUID, payload: Annotated[ChapterUpdateRequest, Body(embed=True)], session: DatabaseSession, user: CurrentUser
) -> ChapterRead:
    chapter = await svc.update_chapter(session, user, chapter_id, payload)
    return ChapterRead.model_validate(chapter)


@router.delete(
    "/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a chapter"
)
async def delete_chapter(chapter_id: UUID, session: DatabaseSession, user: CurrentUser):
    await svc.delete_chapter(session, user, chapter_id)


# ---------------------------------------------------------------------------
# Chapter AI actions
# ---------------------------------------------------------------------------
@router.post(
    "/chapters/{chapter_id}/outline/generate",
    response_model=ChapterRead,
    summary="Generate a chapter outline with AI",
)
async def generate_outline(
    chapter_id: UUID, session: DatabaseSession, user: CurrentUser,
    payload: AnnotatedGenerate = None,
) -> ChapterRead:
    provider = getattr(payload, "provider", None) if payload else None
    model = getattr(payload, "model", None) if payload else None
    chapter = await svc.generate_chapter_outline(session, user, chapter_id, provider=provider, model=model)
    return ChapterRead.model_validate(chapter)


@router.post(
    "/chapters/{chapter_id}/generate",
    response_model=ChapterRead,
    summary="Generate chapter content with AI",
)
async def generate_chapter(
    chapter_id: UUID, session: DatabaseSession, user: CurrentUser,
    payload: AnnotatedGenerate = None,
) -> ChapterRead:
    provider = getattr(payload, "provider", None) if payload else None
    model = getattr(payload, "model", None) if payload else None
    chapter = await svc.generate_chapter_content(session, user, chapter_id, provider=provider, model=model)
    return ChapterRead.model_validate(chapter)


@router.post(
    "/chapters/{chapter_id}/continue",
    response_model=ChapterRead,
    summary="Continue chapter content with AI",
)
async def continue_chapter(
    chapter_id: UUID, session: DatabaseSession, user: CurrentUser,
    payload: AnnotatedGenerate = None,
) -> ChapterRead:
    provider = getattr(payload, "provider", None) if payload else None
    model = getattr(payload, "model", None) if payload else None
    chapter = await svc.continue_chapter_content(session, user, chapter_id, provider=provider, model=model)
    return ChapterRead.model_validate(chapter)


@router.post(
    "/chapters/{chapter_id}/rewrite",
    response_model=ChapterRead,
    summary="Rewrite chapter content with AI",
)
async def rewrite_chapter(
    chapter_id: UUID, session: DatabaseSession, user: CurrentUser,
    payload: AnnotatedGenerate = None,
) -> ChapterRead:
    provider = getattr(payload, "provider", None) if payload else None
    model = getattr(payload, "model", None) if payload else None
    instruction = getattr(payload, "instruction", None) if payload else None
    selected = getattr(payload, "selected_text", None) if payload else None
    chapter = await svc.edit_chapter(
        session, user, chapter_id, "rewrite",
        instruction=instruction, selected_text=selected, provider=provider, model=model,
    )
    return ChapterRead.model_validate(chapter)


@router.post(
    "/chapters/{chapter_id}/expand",
    response_model=ChapterRead,
    summary="Expand chapter content with AI",
)
async def expand_chapter(
    chapter_id: UUID, session: DatabaseSession, user: CurrentUser,
    payload: AnnotatedGenerate = None,
) -> ChapterRead:
    provider = getattr(payload, "provider", None) if payload else None
    model = getattr(payload, "model", None) if payload else None
    instruction = getattr(payload, "instruction", None) if payload else None
    selected = getattr(payload, "selected_text", None) if payload else None
    chapter = await svc.edit_chapter(
        session, user, chapter_id, "expand",
        instruction=instruction, selected_text=selected, provider=provider, model=model,
    )
    return ChapterRead.model_validate(chapter)


@router.post(
    "/chapters/{chapter_id}/shorten",
    response_model=ChapterRead,
    summary="Shorten chapter content with AI",
)
async def shorten_chapter(
    chapter_id: UUID, session: DatabaseSession, user: CurrentUser,
    payload: AnnotatedGenerate = None,
) -> ChapterRead:
    provider = getattr(payload, "provider", None) if payload else None
    model = getattr(payload, "model", None) if payload else None
    instruction = getattr(payload, "instruction", None) if payload else None
    selected = getattr(payload, "selected_text", None) if payload else None
    chapter = await svc.edit_chapter(
        session, user, chapter_id, "shorten",
        instruction=instruction, selected_text=selected, provider=provider, model=model,
    )
    return ChapterRead.model_validate(chapter)


@router.post(
    "/chapters/{chapter_id}/edit/{action}",
    response_model=ChapterRead,
    summary="Apply a generic AI editing action to a chapter",
)
async def edit_action(
    chapter_id: UUID, action: str, session: DatabaseSession, user: CurrentUser,
    payload: AnnotatedGenerate = None,
) -> ChapterRead:
    provider = getattr(payload, "provider", None) if payload else None
    model = getattr(payload, "model", None) if payload else None
    instruction = getattr(payload, "instruction", None) if payload else None
    selected = getattr(payload, "selected_text", None) if payload else None
    chapter = await svc.edit_chapter(
        session, user, chapter_id, action,
        instruction=instruction, selected_text=selected, provider=provider, model=model,
    )
    return ChapterRead.model_validate(chapter)


# ---------------------------------------------------------------------------
# Chapter versions
# ---------------------------------------------------------------------------
@router.get(
    "/chapters/{chapter_id}/versions",
    response_model=list[ChapterVersionResponse],
    summary="List chapter versions",
)
async def list_versions(
    chapter_id: UUID, session: DatabaseSession, user: CurrentUser
) -> list[ChapterVersionResponse]:
    versions = await svc.list_chapter_versions(session, user, chapter_id)
    return [ChapterVersionResponse.model_validate(v) for v in versions]


@router.post(
    "/chapters/{chapter_id}/versions/{version_id}/restore",
    response_model=ChapterRead,
    summary="Restore a chapter version",
)
async def restore_version(
    chapter_id: UUID, version_id: UUID, session: DatabaseSession, user: CurrentUser
) -> ChapterRead:
    chapter = await svc.restore_chapter_version(session, user, chapter_id, version_id)
    return ChapterRead.model_validate(chapter)


# ---------------------------------------------------------------------------
# Manuscript
# ---------------------------------------------------------------------------
@router.post(
    "/books/{book_id}/manuscript/refresh",
    response_model=ManuscriptResponse,
    summary="Refresh the assembled manuscript snapshot",
)
async def refresh_manuscript(
    book_id: UUID, session: DatabaseSession, user: CurrentUser
) -> ManuscriptResponse:
    manuscript = await svc.refresh_manuscript(session, user, book_id)
    return ManuscriptResponse.model_validate(manuscript)


@router.get(
    "/books/{book_id}/manuscript",
    response_model=ManuscriptResponse,
    summary="Get the manuscript snapshot",
)
async def get_manuscript(
    book_id: UUID, session: DatabaseSession, user: CurrentUser
) -> ManuscriptResponse:
    from core.exceptions import ResourceNotFoundError

    manuscript = await svc.refresh_manuscript(session, user, book_id)
    if manuscript is None:
        raise ResourceNotFoundError("Manuscript not found.")
    return ManuscriptResponse.model_validate(manuscript)


# ---------------------------------------------------------------------------
# Autosave / writing sessions
# ---------------------------------------------------------------------------
@router.post(
    "/books/{book_id}/writing-session",
    response_model=WritingSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Begin a writing session (autosave)",
)
async def begin_session(
    book_id: UUID, payload: WritingSessionCreateRequest, session: DatabaseSession, user: CurrentUser
) -> WritingSessionResponse:
    ws = await svc.begin_writing_session(
        session, user, book_id,
        chapter_id=payload.chapter_id,
        session_type=payload.session_type,
        resume_context=payload.resume_context,
    )
    return WritingSessionResponse.model_validate(ws)


@router.put(
    "/books/{book_id}/chapters/{chapter_id}/autosave",
    response_model=ChapterRead,
    summary="Autosave chapter content (debounced by client)",
)
async def autosave(
    book_id: UUID, chapter_id: UUID,
    payload: Annotated[AutosaveRequest, Body(embed=True)],
    session: DatabaseSession, user: CurrentUser,
) -> ChapterRead:
    if payload.chapter_id != chapter_id:
        from core.exceptions import ValidationAppError

        raise ValidationAppError("chapter_id in body does not match path.")
    chapter = await svc.autosave_chapter(
        session, user, book_id, chapter_id, payload.content, version_type=payload.version_type
    )
    return ChapterRead.model_validate(chapter)


# ---------------------------------------------------------------------------
# Book settings (writing style profile)
# ---------------------------------------------------------------------------
@router.get(
    "/books/{book_id}/settings",
    response_model=BookSettingsResponse,
    summary="Get book writing-style settings",
)
async def get_settings(
    book_id: UUID, session: DatabaseSession, user: CurrentUser
) -> BookSettingsResponse:
    settings = await svc.get_or_create_settings(session, user, book_id)
    return BookSettingsResponse.model_validate(settings)


@router.patch(
    "/books/{book_id}/settings",
    response_model=BookSettingsResponse,
    summary="Update book writing-style settings",
)
async def update_settings(
    book_id: UUID, payload: Annotated[BookSettingsUpdateRequest, Body(embed=True)], session: DatabaseSession, user: CurrentUser
) -> BookSettingsResponse:
    settings = await svc.update_settings(session, user, book_id, payload)
    return BookSettingsResponse.model_validate(settings)

