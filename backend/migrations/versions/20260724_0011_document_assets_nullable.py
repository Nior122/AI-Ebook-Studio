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


def upgrade() -> None:
    with op.batch_alter_table("document_assets", recreate="always") as batch_op:
        batch_op.alter_column("project_id", existing_type=sa.CHAR(length=32), nullable=True)
        batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=True)
    with op.batch_alter_table("book_settings", recreate="always") as batch_op:
        batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=False)
    with op.batch_alter_table("kdp_validation_reports", recreate="always") as batch_op:
        batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=False)
    with op.batch_alter_table("marketing_assets", recreate="always") as batch_op:
        batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=False)
    with op.batch_alter_table("image_assets", recreate="always") as batch_op:
        batch_op.alter_column("project_id", existing_type=sa.CHAR(length=32), nullable=True)
        batch_op.alter_column("book_id", existing_type=sa.CHAR(length=32), nullable=True)
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
