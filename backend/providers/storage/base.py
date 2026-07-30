"""Provider-agnostic storage contracts.

These types define the single interface every storage backend implements. They
intentionally use raw ``bytes`` and simple metadata so they work equally well for
manuscripts, DOCX/PDF/EPUB exports, generated images, covers, and marketing files.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class StorageError(Exception):
    """Base storage exception."""

    def __init__(self, message: str, provider: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider


class StorageObjectNotFoundError(StorageError):
    """Raised when an object key does not exist."""


@dataclass(frozen=True)
class StorageObject:
    """An object to be written to storage.

    ``key`` is the logical path within the bucket, e.g. ``"covers/book-123.png"``.
    """

    key: str
    data: bytes
    content_type: str = "application/octet-stream"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class StoredObject:
    """The result of a successful storage write."""

    key: str
    url: str
    size_bytes: int
    content_type: str
    provider: str


class StorageProviderProtocol(ABC):
    """Interface every storage backend must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical provider name, e.g. ``local`` or ``r2``."""

    @abstractmethod
    async def save(self, obj: StorageObject) -> StoredObject:
        """Persist an object and return its stored metadata."""

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Return the raw bytes for ``key`` or raise ``StorageObjectNotFoundError``."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete the object at ``key`` (no error if it is already absent)."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return ``True`` if an object exists at ``key``."""

    @abstractmethod
    async def url_for(self, key: str) -> str:
        """Return a resolvable URL for ``key`` (public or signed, per backend)."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the storage backend is reachable/writable."""
