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


def upgrade() -> None:
    with op.batch_alter_table("books", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))
    op.execute("UPDATE books SET metadata_json = '{}'")
    with op.batch_alter_table("books") as batch_op:
        batch_op.alter_column("metadata_json", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("books", recreate="always") as batch_op:
        batch_op.drop_column("metadata_json")