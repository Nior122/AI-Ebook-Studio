"""Storage provider abstraction.

Business logic must never write files directly to disk or call boto3. It depends
only on :class:`StorageProviderProtocol`, so the underlying backend (local disk,
Cloudflare R2, AWS S3, or any S3-compatible store) can change without touching
feature code.

    from providers.storage import get_storage_provider

    storage = get_storage_provider()
    stored = await storage.save(StorageObject(key="covers/x.png", data=..., ...))
"""

from providers.storage.base import (
    StorageError,
    StorageObject,
    StorageObjectNotFoundError,
    StorageProviderProtocol,
    StoredObject,
)
from providers.storage.factory import get_storage_provider
from providers.storage.local_provider import LocalStorageProvider

__all__ = [
    "LocalStorageProvider",
    "StorageError",
    "StorageObject",
    "StorageObjectNotFoundError",
    "StorageProviderProtocol",
    "StoredObject",
    "get_storage_provider",
]
