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




def _column_nullable(table: str, column: str) -> bool | None:
    """Nullability of a column, or None when the column is missing.

    Migrations run after Base.metadata.create_all() has already materialised
    the full current schema, so batch rebuilds of already-current tables crash
    SQLite (circular column-order dependency). These guards make each migration
    a no-op when its target state already exists.
    """
    inspector = sa.inspect(op.get_bind())
    for col in inspector.get_columns(table):
        if col["name"] == column:
            return bool(col["nullable"])
    return None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    # SQLite stores datetimes as string, so dropping the old String(40) column
    # and recreating as DateTime preserves the same column shape but gives proper
    # ORM semantics and works seamlessly on PostgreSQL.
    if not _has_column("translation_records", "completed_at"):
        with op.batch_alter_table("translation_records", recreate="always") as batch_op:
            batch_op.drop_column("completed_at")
            batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("translation_records", recreate="always") as batch_op:
        batch_op.drop_column("completed_at")
        batch_op.add_column(sa.Column("completed_at", sa.String(length=40), nullable=True))
