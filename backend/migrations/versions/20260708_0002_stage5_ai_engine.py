"""stage5 ai engine telemetry and project ai settings

Revision ID: 20260708_0002
Revises: 20260707_0001
Create Date: 2026-07-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

from database.base import GUID

revision: str = "20260708_0002"
down_revision: str | None = "20260707_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind: Connection, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(bind: Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _add_column_if_missing(
    bind: Connection,
    table_name: str,
    column_name: str,
    column: sa.Column[object],
) -> None:
    if not _has_column(bind, table_name, column_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    """Add Stage 5 AI engine settings and usage telemetry."""
    bind = op.get_bind()

    _add_column_if_missing(
        bind,
        "project_settings",
        "preferred_ai_provider",
        sa.Column(
            "preferred_ai_provider",
            sa.String(length=80),  # type: ignore[arg-type]
            nullable=False,
            server_default="openai",
        ),
    )
    _add_column_if_missing(
        bind,
        "project_settings",
        "preferred_ai_model",
        sa.Column(
            "preferred_ai_model",
            sa.String(length=160),  # type: ignore[arg-type]
            nullable=False,
            server_default="openai/gpt-4o-mini",
        ),
    )
    _add_column_if_missing(
        bind,
        "project_settings",
        "ai_temperature",
        sa.Column(
            "ai_temperature",
            sa.Float(),  # type: ignore[arg-type]
            nullable=False,
            server_default="0.7",
        ),
    )
    _add_column_if_missing(
        bind,
        "project_settings",
        "ai_max_tokens",
        sa.Column("ai_max_tokens", sa.Integer(), nullable=True),  # type: ignore[arg-type]
    )

    if not _has_table(bind, "ai_usage_records"):
        op.create_table(
            "ai_usage_records",
            sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=True),
            sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id"), nullable=True),
            sa.Column("provider", sa.String(length=80), nullable=False),
            sa.Column("model", sa.String(length=120), nullable=False),
            sa.Column("request_type", sa.String(length=40), nullable=False),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False),
            sa.Column("completion_tokens", sa.Integer(), nullable=False),
            sa.Column("total_tokens", sa.Integer(), nullable=False),
            sa.Column("estimated_cost_usd", sa.Float(), nullable=False),
            sa.Column("latency_ms", sa.Float(), nullable=False),
            sa.Column("finish_reason", sa.String(length=80), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("retries", sa.Integer(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("id", GUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ai_usage_user_id", "ai_usage_records", ["user_id"])
        op.create_index("ix_ai_usage_project_id", "ai_usage_records", ["project_id"])
        op.create_index("ix_ai_usage_workspace_id", "ai_usage_records", ["workspace_id"])
        op.create_index("ix_ai_usage_provider", "ai_usage_records", ["provider"])
        op.create_index("ix_ai_usage_created_at", "ai_usage_records", ["created_at"])


def downgrade() -> None:
    """Remove Stage 5 AI engine settings and usage telemetry."""
    bind = op.get_bind()
    if _has_table(bind, "ai_usage_records"):
        op.drop_index("ix_ai_usage_created_at", table_name="ai_usage_records")
        op.drop_index("ix_ai_usage_provider", table_name="ai_usage_records")
        op.drop_index("ix_ai_usage_workspace_id", table_name="ai_usage_records")
        op.drop_index("ix_ai_usage_project_id", table_name="ai_usage_records")
        op.drop_index("ix_ai_usage_user_id", table_name="ai_usage_records")
        op.drop_table("ai_usage_records")

    for column_name in (
        "ai_max_tokens",
        "ai_temperature",
        "preferred_ai_model",
        "preferred_ai_provider",
    ):
        if _has_column(bind, "project_settings", column_name):
            op.drop_column("project_settings", column_name)
