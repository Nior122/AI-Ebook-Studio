"""Storage provider factory.

Selects and constructs the active storage backend from application settings.
Adding a new backend (e.g. R2/S3) means adding a branch here plus a new provider
class — no feature code changes required.
"""

from __future__ import annotations

from functools import lru_cache

from core.config import Settings, get_settings
from providers.storage.base import StorageError, StorageProviderProtocol
from providers.storage.local_provider import LocalStorageProvider


def build_storage_provider(settings: Settings) -> StorageProviderProtocol:
    """Construct a storage provider instance for the configured backend."""
    provider = (settings.storage_provider or "local").lower()

    if provider == "local":
        return LocalStorageProvider(
            root=settings.storage_local_root,
            public_base_url=settings.storage_public_base_url,
        )

    # S3 / R2 share an S3-compatible client; the concrete adapter is added in a
    # later phase. Until then, fail loudly rather than silently using local disk.
    if provider in {"s3", "r2"}:
        raise StorageError(
            f"Storage provider '{provider}' is configured but its adapter is not "
            "implemented yet. Set STORAGE_PROVIDER=local for now.",
            provider=provider,
        )

    raise StorageError(f"Unknown storage provider: '{provider}'.", provider=provider)


@lru_cache
def get_storage_provider() -> StorageProviderProtocol:
    """Return a cached storage provider built from application settings."""
    return build_storage_provider(get_settings())
