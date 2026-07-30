"""fix translation_records.completed_at to DateTime and add chapter card info

Revision ID: 20260724_0013
Revises: 20260724_0012
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0013"
down_revision: str | None = "20260724_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite stores datetimes as string, so dropping the old String(40) column
    # and recreating as DateTime preserves the same column shape but gives proper
    # ORM semantics and works seamlessly on PostgreSQL.
    with op.batch_alter_table("translation_records", recreate="always") as batch_op:
        batch_op.drop_column("completed_at")
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("translation_records", recreate="always") as batch_op:
        batch_op.drop_column("completed_at")
        batch_op.add_column(sa.Column("completed_at", sa.String(length=40), nullable=True))
