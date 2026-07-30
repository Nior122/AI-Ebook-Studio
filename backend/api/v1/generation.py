"""One-click book generation endpoints.

POST /generation/setup  — validate, create project+book, enqueue BOOK_GENERATION job
"""

from uuid import UUID

from fastapi import APIRouter, status

from sqlalchemy import select

from api.dependencies import CurrentUser, DatabaseSession
from models.book_writing import WritingBook
from models.project import Project
from schemas.book_setup import BookSetupRequest, BookSetupResponse
from schemas.projects import BookCreateRequest
from services import book_service as project_book_service
from services.jobs import enqueue_and_schedule
from services.jobs.enums import JobType
from services.workspace_service import get_or_create_default_workspace

router = APIRouter(prefix="/generation", tags=["generation"])


def _check_ambiguities(setup: BookSetupRequest) -> list[dict[str, str]]:
    """Check for obvious missing information before AI analysis."""
    questions: list[dict[str, str]] = []
    if not setup.details.topic or len(setup.details.topic.strip()) < 10:
        questions.append({
            "id": "topic",
            "question": "What topic would you like the book to cover? Please be more specific.",
            "placeholder": "e.g. Morning routines for sustainable productivity",
        })
    if not setup.special_instructions.instructions.strip():
        questions.append({
            "id": "instructions",
            "question": "Any special instructions for the AI? For example: avoid jargon, write for beginners, include examples.",
            "placeholder": "Avoid jargon, use UK English, include Bible verses, etc.",
        })
    return questions


@router.post("/setup", response_model=BookSetupResponse, status_code=status.HTTP_201_CREATED)
async def start_book_generation(
    payload: BookSetupRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> BookSetupResponse:
    """Start book generation from the single-page setup.

    Creates project + book, enqueues a BOOK_GENERATION background job.
    If the setup has potential ambiguities, returns clarification_questions
    before creating anything.
    """
    questions = _check_ambiguities(payload)
    if questions:
        return BookSetupResponse(
            project_id=None,
            book_id=None,
            writing_book_id=None,
            job_id=None,
            clarification_questions=questions,
        )

    # Create project + book
    ws = await get_or_create_default_workspace(session, user)
    project = Project(
        workspace_id=ws.id,
        owner_user_id=user.id,
        name=payload.details.title,
        title=payload.details.title,
        description=payload.details.topic,
        status="active",
    )
    session.add(project)
    await session.flush()

    book = await project_book_service.create_primary_book(
        session, user, project,
        BookCreateRequest(
            title=payload.details.title,
            subtitle=payload.details.subtitle,
            language=payload.details.language,
            target_audience=payload.details.target_audience,
            writing_style=f"{payload.details.tone} / {payload.details.writing_style}",
        ),
    )
    wb_result = await session.execute(
        select(WritingBook).where(
            WritingBook.user_id == user.id,
            WritingBook.title == book.title,
            WritingBook.deleted_at.is_(None),
        ).order_by(WritingBook.created_at.desc())
    )
    wbook = wb_result.scalar()

    handle = await enqueue_and_schedule(
        JobType.BOOK_GENERATION,
        {
            "user_id": str(user.id),
            "project_id": str(project.id),
            "book_id": str(book.id),
            "setup": payload.model_dump(),
        },
    )
    return BookSetupResponse(
        project_id=project.id,
        book_id=book.id,
        writing_book_id=wbook.id if wbook else None,
        job_id=handle.id,
        clarification_questions=None,
    )