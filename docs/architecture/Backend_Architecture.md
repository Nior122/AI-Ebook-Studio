# Backend Architecture

_Last updated: Phase 2 (Backend Foundation & API Core)._

## Overview

The AI Ebook Studio backend is a modular, async-friendly FastAPI application
prepared for Neon PostgreSQL, background jobs, AI/image provider integrations,
and the Next.js frontend. Phase 2 established the foundation that every future
feature depends on. **No ebook feature logic is built in this phase.**

## Layout (flat top-level packages)

The backend uses flat, top-level Python packages (not nested under `app/`). This
was preserved from Phase 1 to avoid rewriting ~100 files and every import.

```text
backend/
  app/
    main.py              # FastAPI app factory + lifespan
    modules/images/      # (existing) image intelligence module
  api/
    router.py            # root API router
    dependencies.py      # shared FastAPI dependencies (auth, db session)
    v1/
      router.py          # v1 aggregation + /health, /version
      auth.py            # authentication endpoints (existing)
      workspaces.py      # workspace endpoints (existing)
      projects.py        # project + project-scoped book endpoints (existing)
      books.py           # NEW: top-level /books placeholders
      jobs.py            # NEW: /jobs status + cancel
      ai.py              # AI engine endpoints (existing)
      images.py          # image endpoints (existing)
  core/
    config.py            # Pydantic Settings (env-driven)
    security.py          # password hashing + JWT utilities
    logging.py           # structlog configuration
    exceptions.py        # domain errors + global handlers
  database/
    base.py              # DeclarativeBase, GUID type, mixins
    session.py           # async engine + session dependency (pooled)
  models/                # SQLAlchemy models (incl. Job)
  schemas/               # Pydantic schemas
    responses.py         # NEW: success/list/pagination/error envelopes
    jobs.py              # NEW: job API schemas
    system.py            # health/version schemas
  services/
    jobs/                # NEW: job type/status enums + queue abstraction
    ai_engine.py         # provider-independent AI engine (existing)
    ...
  providers/
    ai/                  # AI provider adapters (existing)
    images/              # image provider placeholder (canonical impl in app/modules/images)
    storage/             # NEW: storage abstraction (base/local/factory)
  workers/               # reserved for worker entrypoints
  utils/
  tests/
  migrations/            # Alembic
  alembic.ini
  pyproject.toml         # ruff + mypy(strict) + pytest config
  requirements.txt
```

## Application lifecycle

`app/main.py` exposes `create_app(settings)` (an app factory) and a module-level
`app` instance for `uvicorn app.main:app`. It configures:

- **Lifespan**: structured startup/shutdown logging.
- **Middleware**: security headers, request logging, CORS.
- **Exception handlers**: consistent error envelope (see Error Handling).
- **Routing**: mounts the versioned router under `API_V1_PREFIX` (`/api/v1`).

## Configuration

`core/config.py` uses `pydantic-settings`. All configuration is environment-driven
and cached via `get_settings()`. Secrets are never hardcoded. Notable groups:
application metadata, API versioning, database + pool tuning, security/JWT, AI
provider keys, image provider key, storage backend selection, Redis. See
`.env.example` for the full list.

## Error handling

`core/exceptions.py` defines typed domain errors (`AppError` and subclasses like
`ResourceNotFoundError`, `AuthenticationError`, `AuthorizationError`,
`ValidationAppError`, `ConflictError`, `NotImplementedFeatureError`) plus global
handlers for HTTP, request-validation, Pydantic, SQLAlchemy, and unexpected
exceptions. Every error returns:

```json
{ "success": false, "error": { "code": "RESOURCE_NOT_FOUND", "message": "...", "details": {} } }
```

Stack traces and SQL details are logged, never returned to clients.

## Security foundation

`core/security.py` provides bcrypt password hashing/verification, opaque token
hashing, and JWT create/decode helpers (HS256). Full auth flows already exist
from a prior stage; Phase 2 only confirms and documents these utilities.

## Running locally

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1      # PowerShell
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- Health: `GET http://localhost:8000/api/v1/health`
- Docs: `http://localhost:8000/docs`

## Quality gates

- `ruff check .` — lint
- `mypy .` — strict type checking
- `pytest` — tests
