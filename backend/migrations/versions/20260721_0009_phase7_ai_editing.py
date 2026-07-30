"""phase 7 ai editing engine

Revision ID: 20260721_0009
Revises: 20260720_0008
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

from database.base import GUID

revision: str = "20260721_0009"
down_revision: str | None = "20260720_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind: Connection, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Create the Phase 7 AI editing engine tables."""
    bind = op.get_bind()
    if _has_table(bind, "ed_sessions"):
        return

    # ed_sessions -----------------------------------------------------------
    op.create_table(
        "ed_sessions",
        sa.Column("book_id", GUID(), sa.ForeignKey("bw_books.id"), nullable=False),
        sa.Column("chapter_id", GUID(), sa.ForeignKey("bw_chapters.id"), nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("mode", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="running"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ed_sessions")),
    )
    op.create_index("ix_ed_sessions_chapter_id", "ed_sessions", ["chapter_id"])
    op.create_index("ix_ed_sessions_book_id", "ed_sessions", ["book_id"])
    op.create_index("ix_ed_sessions_status", "ed_sessions", ["status"])

    # ed_batches ------------------------------------------------------------
    op.create_table(
        "ed_batches",
        sa.Column("chapter_id", GUID(), sa.ForeignKey("bw_chapters.id"), nullable=False),
        sa.Column("session_id", GUID(), sa.ForeignKey("ed_sessions.id"), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=True),
        sa.Column("superseded_by_batch_id", GUID(), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ed_batches")),
    )
    op.create_index("ix_ed_batches_chapter_id", "ed_batches", ["chapter_id"])
    op.create_index("ix_ed_batches_session_id", "ed_batches", ["session_id"])

    # ed_suggestions --------------------------------------------------------
    op.create_table(
        "ed_suggestions",
        sa.Column("chapter_id", GUID(), sa.ForeignKey("bw_chapters.id"), nullable=False),
        sa.Column("session_id", GUID(), sa.ForeignKey("ed_sessions.id"), nullable=False),
        sa.Column("batch_id", GUID(), sa.ForeignKey("ed_batches.id"), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="low"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("suggested_text", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("location_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ignored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ed_suggestions")),
    )
    op.create_index("ix_ed_suggestions_chapter_id", "ed_suggestions", ["chapter_id"])
    op.create_index("ix_ed_suggestions_session_id", "ed_suggestions", ["session_id"])
    op.create_index("ix_ed_suggestions_status", "ed_suggestions", ["status"])
    op.create_index("ix_ed_suggestions_category", "ed_suggestions", ["category"])
    op.create_index("ix_ed_suggestions_severity", "ed_suggestions", ["severity"])

    # ed_review_jobs --------------------------------------------------------
    op.create_table(
        "ed_review_jobs",
        sa.Column("book_id", GUID(), sa.ForeignKey("bw_books.id"), nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chapter_id", GUID(), sa.ForeignKey("bw_chapters.id"), nullable=True),
        sa.Column("mode", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="queued"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("progress_data", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ed_review_jobs")),
    )
    op.create_index("ix_ed_review_jobs_book_id", "ed_review_jobs", ["book_id"])
    op.create_index("ix_ed_review_jobs_status", "ed_review_jobs", ["status"])


def downgrade() -> None:
    """Drop the Phase 7 AI editing engine tables."""
    bind = op.get_bind()
    tables = ["ed_review_jobs", "ed_suggestions", "ed_batches", "ed_sessions"]
    for table in tables:
        if _has_table(bind, table):
            op.drop_table(table)