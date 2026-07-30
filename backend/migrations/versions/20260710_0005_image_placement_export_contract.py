"""image placement export contract fields

Revision ID: 20260710_0005
Revises: 20260710_0004
Create Date: 2026-07-10 06:20:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260710_0005"
down_revision = "20260710_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("image_placements")}

    if "alignment" not in existing_columns:
        op.add_column(
            "image_placements",
            sa.Column("alignment", sa.String(length=40), nullable=False, server_default="center"),
        )
    if "caption" not in existing_columns:
        op.add_column("image_placements", sa.Column("caption", sa.Text(), nullable=True))
    if "display_width" not in existing_columns:
        op.add_column("image_placements", sa.Column("display_width", sa.Integer(), nullable=True))
    if "display_height" not in existing_columns:
        op.add_column("image_placements", sa.Column("display_height", sa.Integer(), nullable=True))
    if "aspect_ratio" not in existing_columns:
        op.add_column(
            "image_placements",
            sa.Column("aspect_ratio", sa.String(length=20), nullable=False, server_default="16:9"),
        )
    if "position" not in existing_columns:
        op.add_column(
            "image_placements",
            sa.Column(
                "position",
                sa.String(length=80),
                nullable=False,
                server_default="after_paragraph",
            ),
        )

    if "alignment" not in existing_columns:
        op.alter_column("image_placements", "alignment", server_default=None)
    if "aspect_ratio" not in existing_columns:
        op.alter_column("image_placements", "aspect_ratio", server_default=None)
    if "position" not in existing_columns:
        op.alter_column("image_placements", "position", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("image_placements")}

    if "position" in existing_columns:
        op.drop_column("image_placements", "position")
    if "aspect_ratio" in existing_columns:
        op.drop_column("image_placements", "aspect_ratio")
    if "display_height" in existing_columns:
        op.drop_column("image_placements", "display_height")
    if "display_width" in existing_columns:
        op.drop_column("image_placements", "display_width")
    if "caption" in existing_columns:
        op.drop_column("image_placements", "caption")
    if "alignment" in existing_columns:
        op.drop_column("image_placements", "alignment")
