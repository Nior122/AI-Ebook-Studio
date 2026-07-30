"""Phase 3: book metadata, chapter content, job lifecycle, and per-book assets

Revision ID: 20260711_0006
Revises: 20260710_0005
Create Date: 2026-07-11 09:00:00
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

from database.base import GUID

revision = "20260711_0006"
down_revision = "20260710_0005"
branch_labels = None
depends_on = None


def _add_column_if_missing(inspector: sa.Inspector, table: str, column: sa.Column[Any]) -> None:
    existing = {col["name"] for col in inspector.get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # --- books: Phase 3 metadata ---
    _add_column_if_missing(inspector, "books", sa.Column("description", sa.Text(), nullable=True))
    _add_column_if_missing(
        inspector,
        "books",
        sa.Column("language", sa.String(length=20), nullable=False, server_default="en"),
    )
    _add_column_if_missing(
        inspector, "books", sa.Column("target_audience", sa.String(length=220), nullable=True)
    )
    _add_column_if_missing(
        inspector, "books", sa.Column("writing_style", sa.String(length=220), nullable=True)
    )

    # --- document_chapters: flat content body ---
    _add_column_if_missing(
        inspector,
        "document_chapters",
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
    )

    # --- jobs: richer lifecycle tracking ---
    _add_column_if_missing(inspector, "jobs", sa.Column("book_id", GUID(), nullable=True))
    _add_column_if_missing(
        inspector,
        "jobs",
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        inspector, "jobs", sa.Column("current_step", sa.String(length=200), nullable=True)
    )
    _add_column_if_missing(inspector, "jobs", sa.Column("result_data", sa.JSON(), nullable=True))
    _add_column_if_missing(
        inspector, "jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
    )
    _add_column_if_missing(
        inspector, "jobs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
    )

    existing_tables = set(inspector.get_table_names())

    # --- book_settings ---
    if "book_settings" not in existing_tables:
        op.create_table(
            "book_settings",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("book_id", GUID(), nullable=False),
            sa.Column("kdp_trim_size", sa.String(length=40), nullable=False, server_default="6x9"),
            sa.Column(
                "custom_format_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column("page_width", sa.Float(), nullable=False, server_default="6.0"),
            sa.Column("page_height", sa.Float(), nullable=False, server_default="9.0"),
            sa.Column("margin_top", sa.Float(), nullable=False, server_default="0.75"),
            sa.Column("margin_bottom", sa.Float(), nullable=False, server_default="0.75"),
            sa.Column("margin_left", sa.Float(), nullable=False, server_default="0.75"),
            sa.Column("margin_right", sa.Float(), nullable=False, server_default="0.75"),
            sa.Column("body_font", sa.String(length=120), nullable=False, server_default="Georgia"),
            sa.Column("body_font_size", sa.Float(), nullable=False, server_default="11.0"),
            sa.Column(
                "heading_font", sa.String(length=120), nullable=False, server_default="Georgia"
            ),
            sa.Column("line_spacing", sa.Float(), nullable=False, server_default="1.15"),
            sa.Column("paragraph_spacing", sa.Float(), nullable=False, server_default="6.0"),
            sa.Column("image_width", sa.Float(), nullable=False, server_default="5.0"),
            sa.Column(
                "image_alignment", sa.String(length=40), nullable=False, server_default="center"
            ),
            sa.Column(
                "image_aspect_ratio", sa.String(length=40), nullable=False, server_default="16:9"
            ),
            sa.Column(
                "image_style", sa.String(length=80), nullable=False, server_default="realistic"
            ),
            sa.Column("caption_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("caption_font_size", sa.Float(), nullable=False, server_default="9.0"),
            sa.Column(
                "chapter_page_breaks", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column("toc_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["book_id"], ["books.id"], name=op.f("fk_book_settings_book_id_books")
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_book_settings")),
        )
        op.create_index(
            "ix_book_settings_book_id", "book_settings", ["book_id"], unique=True
        )

    # --- image_assets ---
    if "image_assets" not in existing_tables:
        op.create_table(
            "image_assets",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("project_id", GUID(), nullable=False),
            sa.Column("book_id", GUID(), nullable=False),
            sa.Column("chapter_id", GUID(), nullable=True),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("negative_prompt", sa.Text(), nullable=True),
            sa.Column(
                "provider", sa.String(length=80), nullable=False, server_default="pollinations"
            ),
            sa.Column("model", sa.String(length=160), nullable=True),
            sa.Column("width", sa.Integer(), nullable=False, server_default="1600"),
            sa.Column("height", sa.Integer(), nullable=False, server_default="900"),
            sa.Column("aspect_ratio", sa.String(length=40), nullable=False, server_default="16:9"),
            sa.Column("file_url", sa.Text(), nullable=True),
            sa.Column("storage_key", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="PENDING"),
            sa.Column("position", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["project_id"], ["projects.id"], name=op.f("fk_image_assets_project_id_projects")
            ),
            sa.ForeignKeyConstraint(
                ["book_id"], ["books.id"], name=op.f("fk_image_assets_book_id_books")
            ),
            sa.ForeignKeyConstraint(
                ["chapter_id"],
                ["document_chapters.id"],
                name=op.f("fk_image_assets_chapter_id_document_chapters"),
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_image_assets")),
        )
        op.create_index("ix_image_assets_project_id", "image_assets", ["project_id"])
        op.create_index("ix_image_assets_book_id", "image_assets", ["book_id"])
        op.create_index("ix_image_assets_chapter_id", "image_assets", ["chapter_id"])
        op.create_index("ix_image_assets_status", "image_assets", ["status"])

    # --- document_assets ---
    if "document_assets" not in existing_tables:
        op.create_table(
            "document_assets",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("project_id", GUID(), nullable=False),
            sa.Column("book_id", GUID(), nullable=False),
            sa.Column("asset_type", sa.String(length=60), nullable=False),
            sa.Column("file_name", sa.String(length=300), nullable=False),
            sa.Column("file_url", sa.Text(), nullable=True),
            sa.Column("storage_key", sa.Text(), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column("mime_type", sa.String(length=160), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["project_id"],
                ["projects.id"],
                name=op.f("fk_document_assets_project_id_projects"),
            ),
            sa.ForeignKeyConstraint(
                ["book_id"], ["books.id"], name=op.f("fk_document_assets_book_id_books")
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_document_assets")),
            sa.UniqueConstraint(
                "book_id", "asset_type", "version", name="uq_document_assets_book_type_version"
            ),
        )
        op.create_index("ix_document_assets_project_id", "document_assets", ["project_id"])
        op.create_index("ix_document_assets_book_id", "document_assets", ["book_id"])
        op.create_index("ix_document_assets_asset_type", "document_assets", ["asset_type"])

    # --- translation_records ---
    if "translation_records" not in existing_tables:
        op.create_table(
            "translation_records",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("book_id", GUID(), nullable=False),
            sa.Column("source_language", sa.String(length=20), nullable=False),
            sa.Column("target_language", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="PENDING"),
            sa.Column("document_asset_id", GUID(), nullable=True),
            sa.Column("completed_at", sa.String(length=40), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["book_id"], ["books.id"], name=op.f("fk_translation_records_book_id_books")
            ),
            sa.ForeignKeyConstraint(
                ["document_asset_id"],
                ["document_assets.id"],
                name=op.f("fk_translation_records_document_asset_id_document_assets"),
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_translation_records")),
        )
        op.create_index("ix_translation_records_book_id", "translation_records", ["book_id"])
        op.create_index("ix_translation_records_status", "translation_records", ["status"])

    # --- marketing_assets ---
    if "marketing_assets" not in existing_tables:
        op.create_table(
            "marketing_assets",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("book_id", GUID(), nullable=False),
            sa.Column("asset_type", sa.String(length=60), nullable=False),
            sa.Column("content", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["book_id"], ["books.id"], name=op.f("fk_marketing_assets_book_id_books")
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_marketing_assets")),
        )
        op.create_index("ix_marketing_assets_book_id", "marketing_assets", ["book_id"])
        op.create_index("ix_marketing_assets_asset_type", "marketing_assets", ["asset_type"])

    # --- kdp_validation_reports ---
    if "kdp_validation_reports" not in existing_tables:
        op.create_table(
            "kdp_validation_reports",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("book_id", GUID(), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="PENDING"),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("issues", sa.JSON(), nullable=False),
            sa.Column("warnings", sa.JSON(), nullable=False),
            sa.Column("passed_checks", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["book_id"], ["books.id"], name=op.f("fk_kdp_validation_reports_book_id_books")
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_kdp_validation_reports")),
        )
        op.create_index(
            "ix_kdp_validation_reports_book_id", "kdp_validation_reports", ["book_id"]
        )
        op.create_index(
            "ix_kdp_validation_reports_status", "kdp_validation_reports", ["status"]
        )


def downgrade() -> None:
    op.drop_table("kdp_validation_reports")
    op.drop_table("marketing_assets")
    op.drop_table("translation_records")
    op.drop_table("document_assets")
    op.drop_table("image_assets")
    op.drop_table("book_settings")

    for column in (
        "completed_at",
        "started_at",
        "result_data",
        "current_step",
        "progress",
        "book_id",
    ):
        op.drop_column("jobs", column)
    op.drop_column("document_chapters", "content")
    for column in ("writing_style", "target_audience", "language", "description"):
        op.drop_column("books", column)
