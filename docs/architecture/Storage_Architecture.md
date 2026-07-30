# Storage Architecture

## Principle

The application never writes files directly to disk or hardcodes an object store.
All persistence of binary artifacts (manuscripts, DOCX/PDF/EPUB exports, generated
images, covers, marketing files, translated books) goes through a storage
provider interface, so the backend can be swapped without changing feature code.

## Components

```text
StorageProviderProtocol (providers/storage/base.py)
  ├── LocalStorageProvider   (dev / tests)
  ├── R2 / S3 provider       (later phase, S3-compatible)
  └── FutureProvider

get_storage_provider()  (providers/storage/factory.py)
```

### Interface

`StorageProviderProtocol` defines:

- `save(StorageObject) -> StoredObject`
- `get(key) -> bytes`
- `delete(key) -> None`
- `exists(key) -> bool`
- `url_for(key) -> str`
- `health_check() -> bool`
- `name` (property)

### Data types

- `StorageObject(key, data, content_type, metadata)` — an object to write.
- `StoredObject(key, url, size_bytes, content_type, provider)` — write result.
- Errors: `StorageError`, `StorageObjectNotFoundError`.

## Backend selection

`STORAGE_PROVIDER` selects the backend (`local` | `s3` | `r2`). The factory
constructs the correct provider from settings:

- `local` — `LocalStorageProvider` under `STORAGE_LOCAL_ROOT`, optional
  `STORAGE_PUBLIC_BASE_URL` for public URLs. Path traversal is prevented.
- `s3` / `r2` — reserved; the adapter is added in a later phase and fails loudly
  until then rather than silently using local disk.

## Adding a backend

Implement `StorageProviderProtocol`, then add a branch in
`providers/storage/factory.py`. No feature code changes required.
