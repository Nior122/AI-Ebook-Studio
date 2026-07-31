"""add metadata_json to books, bridge legacy to phase6

Revision ID: 20260724_0012
Revises: 20260724_0011
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0012"
down_revision: str | None = "20260724_0011"
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
    if not _has_column("books", "metadata_json"):
        with op.batch_alter_table("books", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))
        op.execute("UPDATE books SET metadata_json = '{}'")
        with op.batch_alter_table("books") as batch_op:
            batch_op.alter_column("metadata_json", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("books", recreate="always") as batch_op:
        batch_op.drop_column("metadata_json")