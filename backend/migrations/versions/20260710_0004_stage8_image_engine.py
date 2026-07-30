"""stage8 image intelligence engine tables and project image preferences

Revision ID: 20260710_0004
Revises: 20260709_0003
Create Date: 2026-07-10 05:30:00
"""
# ruff: noqa: E501

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260710_0004"
down_revision = "20260709_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("project_settings")}
    existing_tables = set(inspector.get_table_names())

    if "image_color_theme" not in existing_columns:
        op.add_column(
            "project_settings",
            sa.Column("image_color_theme", sa.String(length=120), nullable=True),
        )
    if "illustration_style" not in existing_columns:
        op.add_column(
            "project_settings",
            sa.Column(
                "illustration_style",
                sa.String(length=80),
                nullable=False,
                server_default="Photorealistic",
            ),
        )
    if "image_quality" not in existing_columns:
        op.add_column(
            "project_settings",
            sa.Column("image_quality", sa.String(length=40), nullable=False, server_default="high"),
        )

    if {
        "image_providers",
        "image_plans",
        "generated_images",
        "image_placements",
        "image_versions",
    }.issubset(existing_tables):
        if "illustration_style" not in existing_columns:
            op.alter_column("project_settings", "illustration_style", server_default=None)
        if "image_quality" not in existing_columns:
            op.alter_column("project_settings", "image_quality", server_default=None)
        return

    op.create_table(
        "image_providers",
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("api_base_url", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("last_health_status", sa.Boolean(), nullable=True),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.CHAR(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_providers")),
    )
    op.create_index("ix_image_providers_enabled", "image_providers", ["is_enabled"], unique=False)
    op.create_index("ix_image_providers_name", "image_providers", ["name"], unique=True)

    op.create_table(
        "image_plans",
        sa.Column("project_id", sa.CHAR(length=32), nullable=False),
        sa.Column("book_id", sa.CHAR(length=32), nullable=False),
        sa.Column("chapter_id", sa.CHAR(length=32), nullable=False),
        sa.Column("section_id", sa.CHAR(length=32), nullable=False),
        sa.Column("paragraph_id", sa.CHAR(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.CHAR(length=32), nullable=True),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("importance_score", sa.Float(), nullable=False),
        sa.Column("visual_complexity_score", sa.Float(), nullable=False),
        sa.Column("educational_value_score", sa.Float(), nullable=False),
        sa.Column("narrative_value_score", sa.Float(), nullable=False),
        sa.Column("recommended_order", sa.Integer(), nullable=False),
        sa.Column("aspect_ratio", sa.String(length=20), nullable=False),
        sa.Column("style", sa.String(length=80), nullable=False),
        sa.Column("color_theme", sa.String(length=120), nullable=True),
        sa.Column("quality", sa.String(length=40), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.CHAR(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["book_id"], ["books.id"], name=op.f("fk_image_plans_book_id_books")
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["document_chapters.id"],
            name=op.f("fk_image_plans_chapter_id_document_chapters"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_image_plans_created_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["paragraph_id"],
            ["document_paragraphs.id"],
            name=op.f("fk_image_plans_paragraph_id_document_paragraphs"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_image_plans_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["document_sections.id"],
            name=op.f("fk_image_plans_section_id_document_sections"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_plans")),
    )
    op.create_index("ix_image_plans_book_id", "image_plans", ["book_id"], unique=False)
    op.create_index("ix_image_plans_chapter_id", "image_plans", ["chapter_id"], unique=False)
    op.create_index("ix_image_plans_project_id", "image_plans", ["project_id"], unique=False)
    op.create_index("ix_image_plans_status", "image_plans", ["status"], unique=False)

    op.create_table(
        "generated_images",
        sa.Column("project_id", sa.CHAR(length=32), nullable=False),
        sa.Column("book_id", sa.CHAR(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.CHAR(length=32), nullable=True),
        sa.Column("plan_id", sa.CHAR(length=32), nullable=True),
        sa.Column("provider_id", sa.CHAR(length=32), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("alt_text", sa.Text(), nullable=True),
        sa.Column("aspect_ratio", sa.String(length=20), nullable=False),
        sa.Column("style", sa.String(length=80), nullable=False),
        sa.Column("quality", sa.String(length=40), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("provider_name", sa.String(length=80), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("current_version_number", sa.Integer(), nullable=False),
        sa.Column("current_image_url", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.CHAR(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["book_id"], ["books.id"], name=op.f("fk_generated_images_book_id_books")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_generated_images_created_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["image_plans.id"], name=op.f("fk_generated_images_plan_id_image_plans")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_generated_images_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["image_providers.id"],
            name=op.f("fk_generated_images_provider_id_image_providers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generated_images")),
    )
    op.create_index("ix_generated_images_book_id", "generated_images", ["book_id"], unique=False)
    op.create_index(
        "ix_generated_images_project_id", "generated_images", ["project_id"], unique=False
    )
    op.create_index("ix_generated_images_status", "generated_images", ["status"], unique=False)

    op.create_table(
        "image_placements",
        sa.Column("project_id", sa.CHAR(length=32), nullable=False),
        sa.Column("book_id", sa.CHAR(length=32), nullable=False),
        sa.Column("chapter_id", sa.CHAR(length=32), nullable=False),
        sa.Column("section_id", sa.CHAR(length=32), nullable=False),
        sa.Column("paragraph_id", sa.CHAR(length=32), nullable=False),
        sa.Column("plan_id", sa.CHAR(length=32), nullable=True),
        sa.Column("generated_image_id", sa.CHAR(length=32), nullable=True),
        sa.Column("placement_order", sa.Integer(), nullable=False),
        sa.Column("placement_label", sa.String(length=80), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.CHAR(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["book_id"], ["books.id"], name=op.f("fk_image_placements_book_id_books")
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["document_chapters.id"],
            name=op.f("fk_image_placements_chapter_id_document_chapters"),
        ),
        sa.ForeignKeyConstraint(
            ["generated_image_id"],
            ["generated_images.id"],
            name=op.f("fk_image_placements_generated_image_id_generated_images"),
        ),
        sa.ForeignKeyConstraint(
            ["paragraph_id"],
            ["document_paragraphs.id"],
            name=op.f("fk_image_placements_paragraph_id_document_paragraphs"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["image_plans.id"], name=op.f("fk_image_placements_plan_id_image_plans")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_image_placements_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["document_sections.id"],
            name=op.f("fk_image_placements_section_id_document_sections"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_placements")),
    )
    op.create_index("ix_image_placements_book_id", "image_placements", ["book_id"], unique=False)
    op.create_index(
        "ix_image_placements_image_id", "image_placements", ["generated_image_id"], unique=False
    )
    op.create_index(
        "ix_image_placements_project_id", "image_placements", ["project_id"], unique=False
    )

    op.create_table(
        "image_versions",
        sa.Column("generated_image_id", sa.CHAR(length=32), nullable=False),
        sa.Column("provider_id", sa.CHAR(length=32), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False),
        sa.Column("provider_name", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("aspect_ratio", sa.String(length=20), nullable=False),
        sa.Column("generation_time_ms", sa.Float(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.CHAR(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["generated_image_id"],
            ["generated_images.id"],
            name=op.f("fk_image_versions_generated_image_id_generated_images"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["image_providers.id"],
            name=op.f("fk_image_versions_provider_id_image_providers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_versions")),
    )
    op.create_index(
        "ix_image_versions_image_id", "image_versions", ["generated_image_id"], unique=False
    )
    op.create_index(
        "ix_image_versions_version_number",
        "image_versions",
        ["generated_image_id", "version_number"],
        unique=False,
    )

    if "illustration_style" not in existing_columns:
        op.alter_column("project_settings", "illustration_style", server_default=None)
    if "image_quality" not in existing_columns:
        op.alter_column("project_settings", "image_quality", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_image_versions_version_number", table_name="image_versions")
    op.drop_index("ix_image_versions_image_id", table_name="image_versions")
    op.drop_table("image_versions")
    op.drop_index("ix_image_placements_project_id", table_name="image_placements")
    op.drop_index("ix_image_placements_image_id", table_name="image_placements")
    op.drop_index("ix_image_placements_book_id", table_name="image_placements")
    op.drop_table("image_placements")
    op.drop_index("ix_generated_images_status", table_name="generated_images")
    op.drop_index("ix_generated_images_project_id", table_name="generated_images")
    op.drop_index("ix_generated_images_book_id", table_name="generated_images")
    op.drop_table("generated_images")
    op.drop_index("ix_image_plans_status", table_name="image_plans")
    op.drop_index("ix_image_plans_project_id", table_name="image_plans")
    op.drop_index("ix_image_plans_chapter_id", table_name="image_plans")
    op.drop_index("ix_image_plans_book_id", table_name="image_plans")
    op.drop_table("image_plans")
    op.drop_index("ix_image_providers_name", table_name="image_providers")
    op.drop_index("ix_image_providers_enabled", table_name="image_providers")
    op.drop_table("image_providers")
    op.drop_column("project_settings", "image_quality")
    op.drop_column("project_settings", "illustration_style")
    op.drop_column("project_settings", "image_color_theme")
