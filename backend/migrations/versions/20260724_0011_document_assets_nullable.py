"""make document_assets.project_id and book_id nullable for phase6 exports

Revision ID: 20260724_0011
Revises: 20260722_0010
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0011"
down_revision: str | None = "20260722_0010"
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
    if _column_nullable("document_assets", "project_id") is not True:
        with op.batch_alter_table("document_assets", recreate="always") as batch_op:
            batch_op.alter_column("project_id", existing_type=sa.CHAR(length=32), nullable=True)
            batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=True)
    if _column_nullable("book_settings", "book_id") is not False:
        with op.batch_alter_table("book_settings", recreate="always") as batch_op:
            batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=False)
    if _column_nullable("kdp_validation_reports", "book_id") is not False:
        with op.batch_alter_table("kdp_validation_reports", recreate="always") as batch_op:
            batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=False)
    if _column_nullable("marketing_assets", "book_id") is not False:
        with op.batch_alter_table("marketing_assets", recreate="always") as batch_op:
            batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=False)
    if _column_nullable("image_assets", "project_id") is not True:
        with op.batch_alter_table("image_assets", recreate="always") as batch_op:
            batch_op.alter_column("project_id", existing_type=sa.CHAR(length=32), nullable=True)
            batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=True)
    if _column_nullable("translation_records", "book_id") is not False:
        with op.batch_alter_table("translation_records", recreate="always") as batch_op:
            batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("document_assets", recreate="always") as batch_op:
        batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=False)
        batch_op.alter_column("project_id", existing_type=sa.CHAR(length=32), nullable=False)
    with op.batch_alter_table("book_settings", recreate="always") as batch_op:
        batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=False)
    with op.batch_alter_table("kdp_validation_reports", recreate="always") as batch_op:
        batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=False)
    with op.batch_alter_table("marketing_assets", recreate="always") as batch_op:
        batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=False)
    with op.batch_alter_table("image_assets", recreate="always") as batch_op:
        batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=False)
        batch_op.alter_column("project_id", existing_type=sa.CHAR(length=32), nullable=False)
    with op.batch_alter_table("translation_records", recreate="always") as batch_op:
        batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=False)
