"""Add source-preserving translated editions for writing books.

Revision ID: 20261005_0001
Revises: 20260826_0001
Create Date: 2026-10-05

Translated text belongs to a WritingBook edition and must never replace the
source WritingChapter.content. Existing legacy ``translation_records`` remain
available for project-level books; new WritingBook translation workflows use
``bw_translations`` and ``bw_translation_chapters``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import models  # noqa: F401
from database.base import Base

revision: str = "20261005_0001"
down_revision: str | None = "20260826_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the WritingBook translation tables if they are missing."""
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop only the two tables introduced by this revision."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "bw_translation_chapters" in tables:
        op.drop_table("bw_translation_chapters")
    if "bw_translations" in tables:
        op.drop_table("bw_translations")
