"""SQLAlchemy declarative base, shared column types, and model mixins."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData
from sqlalchemy.dialects.postgresql import UUID as POSTGRES_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import CHAR, TypeDecorator

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class GUID(TypeDecorator[UUID]):
    """Platform-independent UUID type.

    PostgreSQL uses its native UUID type. SQLite stores UUID values as 32-character
    strings, which keeps tests lightweight while production remains Neon-compatible.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        """Return the dialect-specific UUID column implementation."""
        if dialect.name == "postgresql":
            return dialect.type_descriptor(POSTGRES_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value: UUID | str | None, dialect: Any) -> str | UUID | None:
        """Convert Python UUID values for database storage."""
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, UUID) else UUID(str(value))
        return uuid_value.hex if isinstance((uuid_value := value), UUID) else UUID(str(value)).hex

    def process_result_value(self, value: UUID | str | None, dialect: Any) -> UUID | None:
        """Convert database UUID values back to Python UUIDs."""
        if value is None:
            return None
        return value if isinstance(value, UUID) else UUID(str(value))


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    """Mixin that adds a UUID primary key."""

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)


class TimestampMixin:
    """Mixin that adds created, updated, and soft-delete timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
