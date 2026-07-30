"""phase 5 ai provider user preferences

Revision ID: 20260720_0007
Revises: 20260711_0006
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

from database.base import GUID

revision: str = "20260720_0007"
down_revision: str | None = "20260711_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind: Connection, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Create the per-user AI provider preferences table."""
    bind = op.get_bind()
    if _has_table(bind, "ai_provider_preferences"):
        return

    op.create_table(
        "ai_provider_preferences",
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("preferred_provider", sa.String(length=80), nullable=True),
        sa.Column("preferred_model", sa.String(length=120), nullable=True),
        sa.Column("fallback_provider", sa.String(length=80), nullable=True),
        sa.Column("fallback_model", sa.String(length=120), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("default_writing_style", sa.String(length=80), nullable=True),
        sa.Column("default_language", sa.String(length=40), nullable=True, server_default="en"),
        sa.Column("stream_responses", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("uses_custom_key", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("key_nonce", sa.Text(), nullable=True),
        sa.Column("key_provider", sa.String(length=40), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_provider_prefs_user_id", "ai_provider_preferences", ["user_id"], unique=True
    )


def downgrade() -> None:
    """Drop the per-user AI provider preferences table."""
    bind = op.get_bind()
    if _has_table(bind, "ai_provider_preferences"):
        op.drop_index("ix_ai_provider_prefs_user_id", table_name="ai_provider_preferences")
        op.drop_table("ai_provider_preferences")
