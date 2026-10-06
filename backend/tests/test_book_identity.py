"""Regression coverage for project-book / writing-book identity boundaries."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ValidationAppError
from models.book_writing import WritingBook
from models.project import Book as ProjectBook
from services.book_identity import require_project_book_id, resolve_project_book_id


def test_require_project_book_id_rejects_unlinked_writing_book() -> None:
    book = WritingBook(user_id=uuid4(), title="Unlinked manuscript")

    with pytest.raises(ValidationAppError, match="project-book link"):
        require_project_book_id(book)


@pytest.mark.asyncio
async def test_resolve_project_book_id_uses_explicit_link(db_session: AsyncSession) -> None:
    project_book_id = uuid4()
    writing_book_id = uuid4()
    project_book = ProjectBook(
        id=project_book_id,
        project_id=uuid4(),
        title="Canonical project book",
    )
    writing_book = WritingBook(
        id=writing_book_id,
        user_id=uuid4(),
        title="Writing manuscript",
        project_book_id=project_book_id,
    )
    ambiguous_id = uuid4()
    other_project_book_id = uuid4()
    ambiguous_project_book = ProjectBook(
        id=ambiguous_id,
        project_id=uuid4(),
        title="Colliding project ID",
    )
    other_project_book = ProjectBook(
        id=other_project_book_id,
        project_id=uuid4(),
        title="Linked target",
    )
    ambiguous_writing_book = WritingBook(
        id=ambiguous_id,
        user_id=uuid4(),
        title="Colliding writing ID",
        project_book_id=other_project_book_id,
    )
    db_session.add_all([
        project_book,
        writing_book,
        ambiguous_project_book,
        other_project_book,
        ambiguous_writing_book,
    ])
    await db_session.flush()

    assert writing_book_id != project_book_id
    assert await resolve_project_book_id(db_session, writing_book_id) == project_book_id
    assert await resolve_project_book_id(db_session, project_book_id) == project_book_id
    assert await resolve_project_book_id(db_session, ambiguous_id) is None
    assert await resolve_project_book_id(db_session, uuid4()) is None
