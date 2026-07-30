"""Local filesystem storage provider.

Stores objects under a configurable root directory. Suitable for local
development and tests. Production deployments should switch ``STORAGE_PROVIDER``
to an object store (R2/S3) without any change to feature code.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from providers.storage.base import (
    StorageObject,
    StorageObjectNotFoundError,
    StorageProviderProtocol,
    StoredObject,
)


class LocalStorageProvider(StorageProviderProtocol):
    """Filesystem-backed implementation of :class:`StorageProviderProtocol`."""

    def __init__(self, root: str = "./var/storage", public_base_url: str | None = None) -> None:
        self._root = Path(root).resolve()
        self._public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        """Return the canonical provider name."""
        return "local"

    def _path_for(self, key: str) -> Path:
        """Resolve a safe absolute path for ``key`` inside the storage root."""
        # Normalize and prevent path traversal outside the root.
        candidate = (self._root / key.lstrip("/")).resolve()
        if not str(candidate).startswith(str(self._root)):
            raise StorageObjectNotFoundError(f"Invalid storage key: {key}", provider=self.name)
        return candidate

    async def save(self, obj: StorageObject) -> StoredObject:
        """Write ``obj`` to disk and return stored metadata."""

        def _write() -> int:
            path = self._path_for(obj.key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(obj.data)
            return len(obj.data)

        size = await asyncio.to_thread(_write)
        return StoredObject(
            key=obj.key,
            url=await self.url_for(obj.key),
            size_bytes=size,
            content_type=obj.content_type,
            provider=self.name,
        )

    async def get(self, key: str) -> bytes:
        """Return the raw bytes for ``key``."""

        def _read() -> bytes:
            path = self._path_for(key)
            if not path.is_file():
                raise StorageObjectNotFoundError(f"Object not found: {key}", provider=self.name)
            return path.read_bytes()

        return await asyncio.to_thread(_read)

    async def delete(self, key: str) -> None:
        """Delete the object at ``key`` if present."""

        def _delete() -> None:
            path = self._path_for(key)
            path.unlink(missing_ok=True)

        await asyncio.to_thread(_delete)

    async def exists(self, key: str) -> bool:
        """Return ``True`` if an object exists at ``key``."""
        return await asyncio.to_thread(lambda: self._path_for(key).is_file())

    async def url_for(self, key: str) -> str:
        """Return a URL for ``key`` (public base URL if set, else a file URI)."""
        normalized = key.lstrip("/")
        if self._public_base_url:
            return f"{self._public_base_url}/{normalized}"
        return self._path_for(key).as_uri()

    async def health_check(self) -> bool:
        """Return ``True`` if the storage root is writable."""
        return await asyncio.to_thread(lambda: self._root.is_dir())
