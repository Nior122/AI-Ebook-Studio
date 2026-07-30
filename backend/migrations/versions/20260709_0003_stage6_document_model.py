"""stage6 structured document model — parts, chapters, sections, paragraphs, sentences

Revision ID: 20260709_0003
Revises: 20260708_0002
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

from database.base import GUID

revision: str = "20260709_0003"
down_revision: str | None = "20260708_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind: Connection, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    # -- document_parts --
    if not _has_table(bind, "document_parts"):
        op.create_table(
            "document_parts",
            sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("book_id", GUID(), sa.ForeignKey("books.id"), nullable=False),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("slug", sa.String(length=320), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
            sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("id", GUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("book_id", "slug", name="uq_document_parts_book_slug"),
        )
        op.create_index("ix_document_parts_book_id", "document_parts", ["book_id"])
        op.create_index("ix_document_parts_project_id", "document_parts", ["project_id"])
        op.create_index("ix_document_parts_position", "document_parts", ["book_id", "position"])

    # -- document_chapters --
    if not _has_table(bind, "document_chapters"):
        op.create_table(
            "document_chapters",
            sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("book_id", GUID(), sa.ForeignKey("books.id"), nullable=False),
            sa.Column("part_id", GUID(), sa.ForeignKey("document_parts.id"), nullable=True),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("slug", sa.String(length=320), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
            sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("id", GUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("book_id", "slug", name="uq_document_chapters_book_slug"),
        )
        op.create_index("ix_document_chapters_book_id", "document_chapters", ["book_id"])
        op.create_index("ix_document_chapters_project_id", "document_chapters", ["project_id"])
        op.create_index("ix_document_chapters_part_id", "document_chapters", ["part_id"])
        op.create_index(
            "ix_document_chapters_position", "document_chapters", ["book_id", "position"]
        )

    # -- document_sections --
    if not _has_table(bind, "document_sections"):
        op.create_table(
            "document_sections",
            sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("book_id", GUID(), sa.ForeignKey("books.id"), nullable=False),
            sa.Column("chapter_id", GUID(), sa.ForeignKey("document_chapters.id"), nullable=False),
            sa.Column("title", sa.String(length=300), nullable=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
            sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("id", GUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_document_sections_chapter_id", "document_sections", ["chapter_id"])
        op.create_index("ix_document_sections_project_id", "document_sections", ["project_id"])
        op.create_index("ix_document_sections_book_id", "document_sections", ["book_id"])
        op.create_index(
            "ix_document_sections_position", "document_sections", ["chapter_id", "position"]
        )

    # -- document_paragraphs --
    if not _has_table(bind, "document_paragraphs"):
        op.create_table(
            "document_paragraphs",
            sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("book_id", GUID(), sa.ForeignKey("books.id"), nullable=False),
            sa.Column("chapter_id", GUID(), sa.ForeignKey("document_chapters.id"), nullable=False),
            sa.Column("section_id", GUID(), sa.ForeignKey("document_sections.id"), nullable=False),
            sa.Column("kind", sa.String(length=40), nullable=False, server_default="body"),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
            sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("id", GUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_document_paragraphs_section_id", "document_paragraphs", ["section_id"])
        op.create_index("ix_document_paragraphs_chapter_id", "document_paragraphs", ["chapter_id"])
        op.create_index("ix_document_paragraphs_project_id", "document_paragraphs", ["project_id"])
        op.create_index("ix_document_paragraphs_book_id", "document_paragraphs", ["book_id"])
        op.create_index(
            "ix_document_paragraphs_position",
            "document_paragraphs",
            ["section_id", "position"],
        )

    # -- document_sentences --
    if not _has_table(bind, "document_sentences"):
        op.create_table(
            "document_sentences",
            sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("book_id", GUID(), sa.ForeignKey("books.id"), nullable=False),
            sa.Column("chapter_id", GUID(), sa.ForeignKey("document_chapters.id"), nullable=False),
            sa.Column("section_id", GUID(), sa.ForeignKey("document_sections.id"), nullable=False),
            sa.Column(
                "paragraph_id", GUID(), sa.ForeignKey("document_paragraphs.id"), nullable=False
            ),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("kind", sa.String(length=40), nullable=False, server_default="body"),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
            sa.Column("id", GUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_document_sentences_paragraph_id", "document_sentences", ["paragraph_id"]
        )
        op.create_index("ix_document_sentences_section_id", "document_sentences", ["section_id"])
        op.create_index("ix_document_sentences_chapter_id", "document_sentences", ["chapter_id"])
        op.create_index("ix_document_sentences_project_id", "document_sentences", ["project_id"])
        op.create_index("ix_document_sentences_book_id", "document_sentences", ["book_id"])
        op.create_index(
            "ix_document_sentences_position",
            "document_sentences",
            ["paragraph_id", "position"],
        )


def downgrade() -> None:
    bind = op.get_bind()

    for table_name in (
        "document_sentences",
        "document_paragraphs",
        "document_sections",
        "document_chapters",
        "document_parts",
    ):
        if _has_table(bind, table_name):
            op.drop_table(table_name)
