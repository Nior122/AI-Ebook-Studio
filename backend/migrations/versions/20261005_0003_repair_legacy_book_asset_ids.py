"""Repair unambiguous project-asset IDs written in the writing-book namespace.

Revision ID: 20261005_0003
Revises: 20261005_0002
Create Date: 2026-10-05

Older SQLite deployments did not enforce foreign keys and could persist a
WritingBook.id in tables whose ``book_id`` references ``books.id``. After the
canonical link is backfilled, repair only rows whose old ID is not already a
project Book ID and whose writing book has exactly one explicit project link.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from database.base import GUID

revision: str = "20261005_0003"
down_revision: str | None = "20261005_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ASSET_TABLES = (
    "kdp_validation_reports",
    "marketing_assets",
    "document_assets",
    "jobs",
)


def _repair_legacy_book_ids(bind: sa.Connection) -> None:
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "books" not in existing_tables or "bw_books" not in existing_tables:
        return

    project_books = sa.table("books", sa.column("id", GUID()))
    writing_books = sa.table(
        "bw_books",
        sa.column("id", GUID()),
        sa.column("project_book_id", GUID()),
    )

    for table_name in _ASSET_TABLES:
        if table_name not in existing_tables:
            continue
        column_names = {column["name"] for column in inspector.get_columns(table_name)}
        if not {"id", "book_id"}.issubset(column_names):
            continue

        asset_table = sa.Table(table_name, sa.MetaData(), autoload_with=bind)
        linked_project_book_id = (
            sa.select(writing_books.c.project_book_id)
            .where(
                writing_books.c.id == asset_table.c.book_id,
                writing_books.c.project_book_id.is_not(None),
            )
            .scalar_subquery()
        )
        has_canonical_book = sa.exists(
            sa.select(1).where(project_books.c.id == asset_table.c.book_id)
        )
        has_linked_writing_book = sa.exists(
            sa.select(1).where(
                writing_books.c.id == asset_table.c.book_id,
                writing_books.c.project_book_id.is_not(None),
            )
        )

        conditions = [
            asset_table.c.book_id.is_not(None),
            ~has_canonical_book,
            has_linked_writing_book,
        ]

        # Preserve the unique (book, type, version) export constraint if an
        # old row would collide with an already-canonical export record.
        if table_name == "document_assets" and {"asset_type", "version"}.issubset(column_names):
            existing_asset = asset_table.alias("existing_document_asset")
            collision = sa.exists(
                sa.select(1)
                .select_from(existing_asset)
                .where(
                    existing_asset.c.id != asset_table.c.id,
                    existing_asset.c.book_id == linked_project_book_id,
                    existing_asset.c.asset_type == asset_table.c.asset_type,
                    existing_asset.c.version == asset_table.c.version,
                )
            )
            conditions.append(~collision)

        bind.execute(
            sa.update(asset_table)
            .where(*conditions)
            .values(book_id=linked_project_book_id)
        )


def upgrade() -> None:
    """Repair only rows with a valid, unambiguous canonical parent."""
    _repair_legacy_book_ids(op.get_bind())


def downgrade() -> None:
    """No-op: repaired IDs cannot be safely distinguished from canonical IDs."""
