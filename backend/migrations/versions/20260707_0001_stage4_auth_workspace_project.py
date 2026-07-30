"""stage4 auth workspace project schema

Revision ID: 20260707_0001
Revises:
Create Date: 2026-07-07
"""

from collections.abc import Sequence

from alembic import op

import models  # noqa: F401
from database.base import Base

revision: str = "20260707_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the Stage 4 authentication, workspace, and project schema."""
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Drop the Stage 4 schema."""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
