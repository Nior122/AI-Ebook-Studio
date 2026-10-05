"""phase 6 repair — book specification (topic lock), word counts, validation fields

Revision ID: 20260819_0001
Revises: 20260731_0001
Create Date: 2026-08-19

Adds:
* ``bw_book_specifications`` table (the locked book definition / topic lock)
* word-count + generation bookkeeping columns on ``bw_books``
* validation / revision tracking columns on ``bw_chapters``

Both column additions are guarded so the migration is safe on fresh databases
(where ``Base.metadata.create_all`` already materialised the full schema) and
on databases migrated incrementally.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import models  # noqa: F401
from database.base import Base

revision: str = "20260819_0001"
down_revision: str | None = "20260731_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_column_if_missing(inspector: sa.Inspector, table: str, column: sa.Column) -> None:
    columns = {c["name"] for c in inspector.get_columns(table)}
    if column.name not in columns:
        op.add_column(table, column)


def upgrade() -> None:
    """Create the specification table and add Phase 6 repair columns."""
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    inspector = sa.inspect(bind)

    # --- bw_books ---
    _add_column_if_missing(inspector, "bw_books", sa.Column("target_word_count", sa.Integer(), nullable=True))
    _add_column_if_missing(inspector, "bw_books", sa.Column("min_word_count", sa.Integer(), nullable=True))
    _add_column_if_missing(inspector, "bw_books", sa.Column("max_word_count", sa.Integer(), nullable=True))
    _add_column_if_missing(
        inspector, "bw_books",
        sa.Column("actual_word_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(inspector, "bw_books", sa.Column("generation_job_id", sa.UUID(), nullable=True))
    _add_column_if_missing(
        inspector, "bw_books",
        sa.Column("generation_state", sa.JSON(), nullable=False, server_default="{}"),
    )
    _add_column_if_missing(inspector, "bw_books", sa.Column("quality_report", sa.JSON(), nullable=True))

    # --- bw_chapters ---
    _add_column_if_missing(inspector, "bw_chapters", sa.Column("validation_result", sa.JSON(), nullable=True))
    _add_column_if_missing(
        inspector, "bw_chapters",
        sa.Column("revision_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(inspector, "bw_chapters", sa.Column("content_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove the Phase 6 repair columns and specification table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for column in ("content_summary", "revision_count", "validation_result"):
        columns = {c["name"] for c in inspector.get_columns("bw_chapters")}
        if column in columns:
            op.drop_column("bw_chapters", column)

    for column in (
        "quality_report", "generation_state", "generation_job_id",
        "actual_word_count", "max_word_count", "min_word_count", "target_word_count",
    ):
        columns = {c["name"] for c in inspector.get_columns("bw_books")}
        if column in columns:
            op.drop_column("bw_books", column)

    tables = set(inspector.get_table_names())
    if "bw_book_specifications" in tables:
        op.drop_table("bw_book_specifications")
