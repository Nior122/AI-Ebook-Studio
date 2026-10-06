"""Tests for the conservative repair of legacy asset FK values."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

from sqlalchemy import JSON, Column, Integer, MetaData, String, Table, create_engine

from database.base import GUID

_LINK_MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20261005_0002_canonical_project_book_link.py"
)
_LINK_SPEC = spec_from_file_location("canonical_project_book_link", _LINK_MIGRATION_PATH)
assert _LINK_SPEC is not None and _LINK_SPEC.loader is not None
_LINK_MIGRATION = module_from_spec(_LINK_SPEC)
_LINK_SPEC.loader.exec_module(_LINK_MIGRATION)

_MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20261005_0003_repair_legacy_book_asset_ids.py"
)
_SPEC = spec_from_file_location("repair_legacy_book_asset_ids", _MIGRATION_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MIGRATION = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MIGRATION)


def test_backfill_sets_only_unique_metadata_links() -> None:
    metadata = MetaData()
    books = Table(
        "books",
        metadata,
        Column("id", GUID(), primary_key=True),
        Column("metadata_json", JSON()),
    )
    writing_books = Table(
        "bw_books",
        metadata,
        Column("id", GUID(), primary_key=True),
        Column("project_book_id", GUID()),
    )
    writing_book_id = uuid4()
    uniquely_linked_writing_book_id = uuid4()
    unique_project_book_id = uuid4()
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            books.insert(),
            [
                {
                    "id": uuid4(),
                    "metadata_json": {"writing_book_id": str(writing_book_id)},
                },
                {
                    "id": uuid4(),
                    "metadata_json": {"writing_book_id": str(writing_book_id)},
                },
                {
                    "id": unique_project_book_id,
                    "metadata_json": {"writing_book_id": str(uniquely_linked_writing_book_id)},
                },
            ],
        )
        connection.execute(
            writing_books.insert(),
            [
                {"id": writing_book_id, "project_book_id": None},
                {"id": uniquely_linked_writing_book_id, "project_book_id": None},
            ],
        )

    with engine.begin() as connection:
        _LINK_MIGRATION._backfill_unambiguous_links(connection)

    with engine.connect() as connection:
        links = {
            row["id"]: row["project_book_id"]
            for row in connection.execute(writing_books.select()).mappings()
        }
        assert links[writing_book_id] is None
        assert links[uniquely_linked_writing_book_id] == unique_project_book_id

    engine.dispose()


def test_repair_only_maps_unambiguous_legacy_ids_and_avoids_export_collision() -> None:
    metadata = MetaData()
    books = Table("books", metadata, Column("id", GUID(), primary_key=True))
    writing_books = Table(
        "bw_books",
        metadata,
        Column("id", GUID(), primary_key=True),
        Column("project_book_id", GUID()),
    )
    marketing_assets = Table(
        "marketing_assets",
        metadata,
        Column("id", GUID(), primary_key=True),
        Column("book_id", GUID(), nullable=False),
    )
    reports = Table(
        "kdp_validation_reports",
        metadata,
        Column("id", GUID(), primary_key=True),
        Column("book_id", GUID(), nullable=False),
    )
    exports = Table(
        "document_assets",
        metadata,
        Column("id", GUID(), primary_key=True),
        Column("book_id", GUID()),
        Column("asset_type", String(60), nullable=False),
        Column("version", Integer, nullable=False),
    )
    jobs = Table(
        "jobs",
        metadata,
        Column("id", GUID(), primary_key=True),
        Column("book_id", GUID()),
    )

    project_book_id = uuid4()
    writing_book_id = uuid4()
    unlinked_writing_book_id = uuid4()
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(books.insert(), [{"id": project_book_id}])
        connection.execute(
            writing_books.insert(),
            [
                {"id": writing_book_id, "project_book_id": project_book_id},
                {"id": unlinked_writing_book_id, "project_book_id": None},
            ],
        )
        connection.execute(
            marketing_assets.insert(),
            [
                {"id": uuid4(), "book_id": writing_book_id},
                {"id": uuid4(), "book_id": unlinked_writing_book_id},
                {"id": uuid4(), "book_id": project_book_id},
            ],
        )
        connection.execute(
            reports.insert(), [{"id": uuid4(), "book_id": writing_book_id}]
        )
        connection.execute(
            exports.insert(),
            [
                {"id": uuid4(), "book_id": writing_book_id, "asset_type": "DOCX", "version": 1},
                {"id": uuid4(), "book_id": writing_book_id, "asset_type": "DOCX", "version": 2},
                {"id": uuid4(), "book_id": project_book_id, "asset_type": "DOCX", "version": 2},
            ],
        )
        connection.execute(jobs.insert(), [{"id": uuid4(), "book_id": writing_book_id}])

    with engine.begin() as connection:
        _MIGRATION._repair_legacy_book_ids(connection)

    with engine.connect() as connection:
        marketing_rows = connection.execute(marketing_assets.select()).mappings().all()
        assert {row["book_id"] for row in marketing_rows} == {
            project_book_id,
            unlinked_writing_book_id,
        }
        assert connection.execute(reports.select()).mappings().one()["book_id"] == project_book_id
        export_rows = connection.execute(exports.select()).mappings().all()
        assert any(
            row["book_id"] == project_book_id and row["version"] == 1
            for row in export_rows
        )
        # Version 2 would collide with the canonical record, so keep the
        # legacy row untouched rather than destroying or merging either.
        assert any(
            row["book_id"] == writing_book_id and row["version"] == 2
            for row in export_rows
        )
        assert any(
            row["book_id"] == project_book_id and row["version"] == 2
            for row in export_rows
        )
        assert connection.execute(jobs.select()).mappings().one()["book_id"] == project_book_id
    engine.dispose()
