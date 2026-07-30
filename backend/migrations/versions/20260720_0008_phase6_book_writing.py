"""phase 6 book writing and manuscript management

Revision ID: 20260720_0008
Revises: 20260720_0007
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

from database.base import GUID

revision: str = "20260720_0008"
down_revision: str | None = "20260720_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind: Connection, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


_TABLES = [
    "bw_books",
    "bw_book_briefs",
    "bw_book_blueprints",
    "bw_chapters",
    "bw_chapter_versions",
    "bw_manuscripts",
    "bw_writing_sessions",
    "bw_book_settings",
]


def upgrade() -> None:
    """Create the Phase 6 book-writing tables."""
    bind = op.get_bind()
    if _has_table(bind, "bw_books"):
        return

    op.create_table(
        "bw_books",
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("subtitle", sa.String(length=300), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("author_name", sa.String(length=220), nullable=True),
        sa.Column("target_audience", sa.String(length=300), nullable=True),
        sa.Column("book_type", sa.String(length=80), nullable=True),
        sa.Column("language", sa.String(length=20), nullable=False, server_default="en"),
        sa.Column("tone", sa.String(length=160), nullable=True),
        sa.Column("approximate_length", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("current_step", sa.String(length=40), nullable=False, server_default="idea"),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bw_books_user_id", "bw_books", ["user_id"])
    op.create_index("ix_bw_books_status", "bw_books", ["status"])
    op.create_index("ix_bw_books_current_step", "bw_books", ["current_step"])

    op.create_table(
        "bw_book_briefs",
        sa.Column("book_id", GUID(), sa.ForeignKey("bw_books.id"), nullable=False, unique=True),
        sa.Column("working_title", sa.String(length=300), nullable=True),
        sa.Column("subtitle", sa.String(length=300), nullable=True),
        sa.Column("book_purpose", sa.Text(), nullable=True),
        sa.Column("target_reader", sa.Text(), nullable=True),
        sa.Column("reader_problems", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("promised_transformation", sa.Text(), nullable=True),
        sa.Column("tone", sa.String(length=160), nullable=True),
        sa.Column("writing_style", sa.String(length=160), nullable=True),
        sa.Column("key_themes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("major_concepts", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("topics_to_avoid", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("suggested_structure", sa.Text(), nullable=True),
        sa.Column("estimated_chapter_count", sa.Integer(), nullable=True),
        sa.Column("estimated_word_count", sa.Integer(), nullable=True),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_id", name="uq_bw_book_briefs_book_id"),
    )
    op.create_index("ix_bw_book_briefs_book_id", "bw_book_briefs", ["book_id"])

    op.create_table(
        "bw_book_blueprints",
        sa.Column("book_id", GUID(), sa.ForeignKey("bw_books.id"), nullable=False, unique=True),
        sa.Column("introduction_purpose", sa.Text(), nullable=True),
        sa.Column("chapters", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("estimated_total_word_count", sa.Integer(), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_id", name="uq_bw_book_blueprints_book_id"),
    )
    op.create_index("ix_bw_book_blueprints_book_id", "bw_book_blueprints", ["book_id"])

    op.create_table(
        "bw_chapters",
        sa.Column("book_id", GUID(), sa.ForeignKey("bw_books.id"), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("outline", sa.Text(), nullable=True),
        sa.Column("outline_sections", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="planned"),
        sa.Column("target_word_count", sa.Integer(), nullable=True),
        sa.Column("actual_word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bw_chapters_book_id", "bw_chapters", ["book_id"])
    op.create_index("ix_bw_chapters_status", "bw_chapters", ["status"])
    op.create_index("ix_bw_chapters_book_number", "bw_chapters", ["book_id", "chapter_number"])

    op.create_table(
        "bw_chapter_versions",
        sa.Column("chapter_id", GUID(), sa.ForeignKey("bw_chapters.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version_type", sa.String(length=40), nullable=False, server_default="ai_generated"),
        sa.Column("generation_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_by", GUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chapter_id", "version_number", name="uq_bw_chapter_versions_chapter_version"
        ),
    )
    op.create_index("ix_bw_chapter_versions_chapter_id", "bw_chapter_versions", ["chapter_id"])

    op.create_table(
        "bw_manuscripts",
        sa.Column("book_id", GUID(), sa.ForeignKey("bw_books.id"), nullable=False, unique=True),
        sa.Column("full_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chapter_order", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_id", name="uq_bw_manuscripts_book_id"),
    )
    op.create_index("ix_bw_manuscripts_book_id", "bw_manuscripts", ["book_id"])

    op.create_table(
        "bw_writing_sessions",
        sa.Column("book_id", GUID(), sa.ForeignKey("bw_books.id"), nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chapter_id", GUID(), sa.ForeignKey("bw_chapters.id"), nullable=True),
        sa.Column("session_type", sa.String(length=40), nullable=False, server_default="autosave"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_saved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resume_context", sa.JSON(), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bw_writing_sessions_book_id", "bw_writing_sessions", ["book_id"])
    op.create_index("ix_bw_writing_sessions_user_id", "bw_writing_sessions", ["user_id"])

    op.create_table(
        "bw_book_settings",
        sa.Column("book_id", GUID(), sa.ForeignKey("bw_books.id"), nullable=False, unique=True),
        sa.Column("tone", sa.String(length=160), nullable=True),
        sa.Column("formality", sa.String(length=160), nullable=True),
        sa.Column("sentence_complexity", sa.String(length=80), nullable=True),
        sa.Column("paragraph_length", sa.String(length=80), nullable=True),
        sa.Column("use_examples", sa.String(length=40), nullable=True, server_default="medium"),
        sa.Column("use_stories", sa.String(length=40), nullable=True, server_default="medium"),
        sa.Column("use_analogies", sa.String(length=40), nullable=True, server_default="low"),
        sa.Column("use_humor", sa.String(length=40), nullable=True, server_default="low"),
        sa.Column("use_practical_exercises", sa.String(length=40), nullable=True, server_default="medium"),
        sa.Column("point_of_view", sa.String(length=40), nullable=True, server_default="second_person"),
        sa.Column("reading_level", sa.String(length=80), nullable=True, server_default="general"),
        sa.Column("preferred_provider", sa.String(length=80), nullable=True),
        sa.Column("preferred_model", sa.String(length=160), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("stream_responses", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("style_notes", sa.Text(), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("book_id", name="uq_bw_book_settings_book_id"),
    )
    op.create_index("ix_bw_book_settings_book_id", "bw_book_settings", ["book_id"])


def downgrade() -> None:
    """Drop the Phase 6 book-writing tables (reverse order)."""
    bind = op.get_bind()
    if not _has_table(bind, "bw_books"):
        return

    op.drop_index("ix_bw_book_settings_book_id", table_name="bw_book_settings")
    op.drop_table("bw_book_settings")
    op.drop_index("ix_bw_writing_sessions_user_id", table_name="bw_writing_sessions")
    op.drop_index("ix_bw_writing_sessions_book_id", table_name="bw_writing_sessions")
    op.drop_table("bw_writing_sessions")
    op.drop_index("ix_bw_manuscripts_book_id", table_name="bw_manuscripts")
    op.drop_table("bw_manuscripts")
    op.drop_index("ix_bw_chapter_versions_chapter_id", table_name="bw_chapter_versions")
    op.drop_table("bw_chapter_versions")
    op.drop_index("ix_bw_chapters_book_number", table_name="bw_chapters")
    op.drop_index("ix_bw_chapters_status", table_name="bw_chapters")
    op.drop_index("ix_bw_chapters_book_id", table_name="bw_chapters")
    op.drop_table("bw_chapters")
    op.drop_index("ix_bw_book_blueprints_book_id", table_name="bw_book_blueprints")
    op.drop_table("bw_book_blueprints")
    op.drop_index("ix_bw_book_briefs_book_id", table_name="bw_book_briefs")
    op.drop_table("bw_book_briefs")
    op.drop_index("ix_bw_books_current_step", table_name="bw_books")
    op.drop_index("ix_bw_books_status", table_name="bw_books")
    op.drop_index("ix_bw_books_user_id", table_name="bw_books")
    op.drop_table("bw_books")
