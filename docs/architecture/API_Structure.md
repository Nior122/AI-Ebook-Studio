# API Structure

_Last updated: Phase 2._

## Conventions

- **Base prefix**: all endpoints are versioned under `/api/v1`
  (`API_V1_PREFIX`).
- **Routers**: each domain has its own `APIRouter` in `api/v1/` and is included by
  `api/v1/router.py`, which is mounted by the root router in `api/router.py`.
- **Response envelope**:
  - Success: `{ "success": true, "data": ... }`
  - List: `{ "success": true, "data": [...], "pagination": { "page", "page_size", "total" } }`
  - Error: `{ "success": false, "error": { "code", "message", "details" } }`
  - Helpers/schemas live in `schemas/responses.py`.
- **Placeholders**: unbuilt endpoints return `{ "message": "Endpoint not implemented yet" }`.
- **Interactive docs**: Swagger UI at `/docs`, ReDoc at `/redoc`, schema at `/openapi.json`.

## Router map

| Router | Prefix | Status |
|---|---|---|
| system | `/api/v1` | active (`/health`, `/version`) |
| auth | `/api/v1/auth` | active (existing) |
| workspaces | `/api/v1/workspaces` | active (existing) |
| projects | `/api/v1/projects` | active (existing, incl. project-scoped books) |
| books | `/api/v1/books` | placeholder (Phase 2) |
| jobs | `/api/v1/jobs` | job status + cancel (Phase 2) |
| ai | `/api/v1/ai` | active (existing) |
| images | `/api/v1/images` | active (existing) |

## Adding a new endpoint

1. Create `api/v1/<domain>.py` with an `APIRouter(prefix="/<domain>", tags=[...])`.
2. Return typed Pydantic responses; wrap collections with `ListResponse`.
3. Raise typed errors from `core/exceptions.py` (e.g. `ResourceNotFoundError`).
4. Include the router in `api/v1/router.py`.
5. Add tests under `backend/tests/`.
