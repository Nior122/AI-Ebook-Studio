# AI Ebook Studio — Database Schema

PostgreSQL (Neon) is the system of record. SQLAlchemy 2.0 async models live in
`models/`; relationships are explicit and cascade through workspace → project →
book → chapters/assets.

## Namespaces

| Namespace | Models | Purpose |
|-----------|--------|---------|
| Auth (`models/user.py`) | `User` | Email/password (bcrypt) accounts, JWT + refresh tokens. |
| Workspaces (`models/workspace.py`) | `Workspace`, `WorkspaceMembership` | Multi-tenant ownership and RBAC. |
| Projects (`models/project.py`) | `Project`, `Book`, `ProjectAISettings` | Top-level writing projects and their primary book. |
| Documents (`models/document.py`) | `DocumentNode` (base), `Part`, `Section`, `Chapter`, `Paragraph`, `Sentence` | Structured manuscript tree. `Chapter` also carries a flat `content` body for fast access. |
| Operations (`models/operations.py`) | `Job`, `DocumentAsset`-adjacent | Async AI jobs with lifecycle tracking. |
| Assets (`models/assets.py`) | `BookSettings`, `ImageAsset`, `DocumentAsset`, `TranslationRecord`, `MarketingAsset`, `KDPValidationReport` | Per-book generated assets and formatting. |
| Enums (`models/enums.py`) | status + type enums, `TRIM_SIZES` | Shared vocabularies. |

## Phase 3 additions

### `Book` (extended in `models/project.py`)
New columns: `description`, `language` (default `en`), `target_audience`,
`writing_style`. Relationships to `Chapter` and the six asset models.

### `Chapter` (extended in `models/document.py`)
New flat column `content` (TEXT) — the prose body. The structured tree
(Part/Section/Paragraph/Sentence) remains the source of truth for layout; `content`
is a convenience accessor kept in sync via the chapter service. `word_count` is
derived from `content`.

### `Job` (extended in `models/operations.py`)
New columns: `book_id` (FK → books), `progress` (int 0–100), `current_step`,
`result_data` (JSON), `started_at`, `completed_at`.

### New tables (`models/assets.py`)

| Table | Key columns | Notes |
|-------|-------------|-------|
| `book_settings` | `book_id` (unique FK), `kdp_trim_size`, margins, fonts, `image_aspect_ratio`, caption/heading config | One per book. Defaults: 6×9 trim, 16:9 images. |
| `image_assets` | `project_id`, `book_id`, `chapter_id`, `prompt`, `provider`, `width/height`, `status`, `position` | Generated illustrations. |
| `document_assets` | `project_id`, `book_id`, `asset_type`, `version` (uq per book/type/version) | Manuscript exports (DOCX/EPUB/PDF). |
| `translation_records` | `book_id`, `source_language`, `target_language`, `status`, `document_asset_id` | Translation jobs. |
| `marketing_assets` | `book_id`, `asset_type`, `content` | Blurbs, ads, social copy. |
| `kdp_validation_reports` | `book_id`, `status`, `score`, `issues`, `warnings`, `passed_checks` | KDP readiness checks. |

## Ownership & access control
Ownership is derived: `Book → Project → Workspace`. All Phase 3 endpoints resolve
the authenticated user via `get_current_user` and call
`services/rbac_service.require_workspace_permission`, which raises `403` for
cross-user access.

## Migrations
Managed by Alembic. Phase 3 is revision `20260711_0006` (down_revision
`20260710_0005`). It is idempotent: column additions guard on existing columns,
and table creation guards on existing tables, so re-running `alembic upgrade head`
is safe.
