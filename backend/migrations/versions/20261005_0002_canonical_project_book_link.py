"""Add a canonical FK between writing books and project books.

Revision ID: 20261005_0002
Revises: 20261005_0001
Create Date: 2026-10-05

The JSON link remains for client compatibility, while backend ownership,
formatting, export and autosave resolution use ``bw_books.project_book_id``.
Only unambiguous legacy metadata references are backfilled.
"""

import json
from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

from database.base import GUID

revision: str = "20261005_0002"
down_revision: str | None = "20261005_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX_NAME = "ix_bw_books_project_book_id"
_FK_NAME = "fk_bw_books_project_book_id_books"


def _backfill_unambiguous_links(bind: sa.Connection) -> None:
    books = sa.table(
        "books",
        sa.column("id", GUID()),
        sa.column("metadata_json", sa.JSON()),
    )
    writing_books = sa.table(
        "bw_books",
        sa.column("id", GUID()),
        sa.column("project_book_id", GUID()),
    )

    matches: dict[UUID, list[UUID]] = {}
    rows = bind.execute(sa.select(books.c.id, books.c.metadata_json)).all()
    for project_book_id, metadata in rows:
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (TypeError, ValueError):
                continue
        if not isinstance(metadata, dict):
            continue
        raw_writing_book_id = metadata.get("writing_book_id")
        if not raw_writing_book_id:
            continue
        try:
            writing_book_id = UUID(str(raw_writing_book_id))
        except (TypeError, ValueError):
            continue
        matches.setdefault(writing_book_id, []).append(project_book_id)

    existing_ids = set(bind.execute(sa.select(writing_books.c.id)).scalars())
    for writing_book_id, project_book_ids in matches.items():
        if writing_book_id not in existing_ids or len(project_book_ids) != 1:
            continue
        bind.execute(
            sa.update(writing_books)
            .where(
                writing_books.c.id == writing_book_id,
                writing_books.c.project_book_id.is_(None),
            )
            .values(project_book_id=project_book_ids[0])
        )


def upgrade() -> None:
    """Add the nullable relationship and backfill only unique legacy links."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("bw_books")}
    if "project_book_id" not in columns:
        with op.batch_alter_table("bw_books") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "project_book_id",
                    GUID(),
                    sa.ForeignKey("books.id", name=_FK_NAME, ondelete="SET NULL"),
                    nullable=True,
                )
            )

    _backfill_unambiguous_links(bind)

    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("bw_books")}
    if _INDEX_NAME not in indexes:
        op.create_index(_INDEX_NAME, "bw_books", ["project_book_id"], unique=True)


def downgrade() -> None:
    """Remove the relationship column and its index."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("bw_books")}
    if _INDEX_NAME in indexes:
        op.drop_index(_INDEX_NAME, table_name="bw_books")

    columns = {column["name"] for column in sa.inspect(bind).get_columns("bw_books")}
    if "project_book_id" in columns:
        with op.batch_alter_table("bw_books") as batch_op:
            batch_op.drop_column("project_book_id")
