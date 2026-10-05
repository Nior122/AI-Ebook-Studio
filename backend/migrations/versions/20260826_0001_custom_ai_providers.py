"""custom AI providers — bring-your-own endpoint / model / API key

Revision ID: 20260826_0001
Revises: 20260819_0001
Create Date: 2026-08-26

Adds the ``custom_ai_providers`` table so each user can register their own AI
provider (OpenAI-compatible endpoint, native Anthropic, or native Gemini) with
an encrypted API key and a list of model ids.

The table creation is guarded so the migration is safe on fresh databases
(where ``Base.metadata.create_all`` already materialised the full schema) and
on databases migrated incrementally.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import models  # noqa: F401
from database.base import Base

revision: str = "20260826_0001"
down_revision: str | None = "20260819_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the custom_ai_providers table if it does not exist."""
    bind = op.get_bind()
    # create_all only creates tables that are missing, so this is a no-op when
    # the schema already includes custom_ai_providers.
    Base.metadata.create_all(bind=bind)

    inspector = sa.inspect(bind)
    if "custom_ai_providers" not in set(inspector.get_table_names()):
        op.create_table(
            "custom_ai_providers",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("provider_type", sa.String(length=20), nullable=False),
            sa.Column("base_url", sa.String(length=500), nullable=True),
            sa.Column("encrypted_api_key", sa.Text(), nullable=True),
            sa.Column("model_ids", sa.JSON(), nullable=False),
            sa.Column("default_model", sa.String(length=200), nullable=True),
            sa.Column("supports_structured_output", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id", name="pk_custom_ai_providers"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_custom_ai_providers_user_id_users"),
        )
        op.create_index("ix_custom_ai_providers_user_id", "custom_ai_providers", ["user_id"])


def downgrade() -> None:
    """Drop the custom_ai_providers table if present."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "custom_ai_providers" in set(inspector.get_table_names()):
        op.drop_index("ix_custom_ai_providers_user_id", table_name="custom_ai_providers")
        op.drop_table("custom_ai_providers")
