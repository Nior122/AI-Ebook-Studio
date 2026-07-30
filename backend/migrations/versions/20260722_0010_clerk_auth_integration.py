"""add clerk_id to users, make password_hash nullable

Revision ID: 20260722_0010
Revises: 20260721_0009
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_0010"
down_revision: str | None = "20260721_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("clerk_id", sa.String(length=256), nullable=True))
        batch_op.alter_column("password_hash", existing_type=sa.Text(), nullable=True)
        batch_op.create_index("ix_users_clerk_id", ["clerk_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.drop_index("ix_users_clerk_id")
        batch_op.drop_column("clerk_id")
        batch_op.alter_column("password_hash", existing_type=sa.Text(), nullable=False)
