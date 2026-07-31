"""studio ux — activities, notifications, versions, bookmarks, project stage

Revision ID: 20260731_0001
Revises: 20260724_0013
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import models  # noqa: F401
from database.base import Base

revision: str = "20260731_0001"
down_revision: str | None = "20260724_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the Studio UX tables and add the project lifecycle stage.

    Earlier migrations already materialised the full current schema (including
    these tables and the ``projects.stage`` column) via
    ``Base.metadata.create_all()``, so both operations are guarded to be safe
    on fresh databases and on databases migrated incrementally.
    """
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("projects")}
    if "stage" not in columns:
        op.add_column(
            "projects",
            sa.Column("stage", sa.String(length=40), nullable=False, server_default="draft"),
        )


def downgrade() -> None:
    """Drop the Studio UX schema."""
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("projects")}
    if "stage" in columns:
        op.drop_column("projects", "stage")
    op.drop_table("studio_bookmarks")
    op.drop_table("studio_versions")
    op.drop_table("studio_notifications")
    op.drop_table("studio_activities")
