# AI Ebook Studio — API Reference

Base URL (local): `http://localhost:8000`
API prefix: `/api/v1`
Interactive docs: `/docs` (Swagger) · `/redoc` (ReDoc) · `/openapi.json`

> Phase 2 note: several endpoints below already existed before Phase 2. Phase 2
> added the `books` and `jobs` routers, standardized the response envelope, and
> extended configuration/storage/job foundations. Endpoints marked **placeholder**
> return `{ "message": "Endpoint not implemented yet" }`.

## Response format

Success:
```json
{ "success": true, "data": {} }
```
List:
```json
{ "success": true, "data": [], "pagination": { "page": 1, "page_size": 20, "total": 0 } }
```
Error:
```json
{ "success": false, "error": { "code": "RESOURCE_NOT_FOUND", "message": "The requested resource was not found.", "details": {} } }
```

Common error codes: `VALIDATION_ERROR`, `AUTHENTICATION_REQUIRED`,
`PERMISSION_DENIED`, `RESOURCE_NOT_FOUND`, `CONFLICT`, `RATE_LIMITED`,
`DATABASE_ERROR`, `NOT_IMPLEMENTED`, `INTERNAL_ERROR`.

## System

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Service health: `{ status, service, version, app, environment, timestamp }` |
| GET | `/api/v1/version` | API version metadata |

Example:
```bash
curl http://localhost:8000/api/v1/health
```
```json
{ "status": "ok", "service": "ai-ebook-studio-api", "version": "1.0.0", "app": "AI Ebook Studio API", "environment": "development", "timestamp": "..." }
```

## Jobs (Phase 2)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/jobs` | **placeholder** — persisted job listing (later phase) |
| GET | `/api/v1/jobs/{job_id}` | Get job status (`JobResponse`) |
| POST | `/api/v1/jobs/{job_id}/cancel` | Cancel a non-terminal job |

`JobResponse`: `{ id, job_type, status, progress, result, error_message, created_at, updated_at }`
Job types: `BOOK_GENERATION`, `PROOFREADING`, `IMAGE_ANALYSIS`, `IMAGE_GENERATION`,
`DOCX_BUILD`, `PDF_EXPORT`, `EPUB_EXPORT`, `TRANSLATION`, `MARKETING_GENERATION`, `KDP_VALIDATION`.
Statuses: `PENDING`, `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`.

## Books (Phase 2)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/books` | **placeholder** — cross-project book listing |
| GET | `/api/v1/books/{book_id}` | **placeholder** — direct book access |

> Project-scoped book creation/listing already exists under `/projects` (below).

## Auth (existing)

| Method | Path |
|---|---|
| POST | `/api/v1/auth/register` |
| POST | `/api/v1/auth/login` |
| POST | `/api/v1/auth/refresh` |
| POST | `/api/v1/auth/logout` |
| GET | `/api/v1/auth/me` |
| POST | `/api/v1/auth/forgot-password` |
| POST | `/api/v1/auth/reset-password` |
| POST | `/api/v1/auth/verify-email` |

## Workspaces (existing)

| Method | Path |
|---|---|
| GET/POST | `/api/v1/workspaces` |
| PUT/DELETE | `/api/v1/workspaces/{workspace_id}` |
| POST | `/api/v1/workspaces/{workspace_id}/archive` |
| POST | `/api/v1/workspaces/{workspace_id}/invites` |

## Projects (existing)

| Method | Path |
|---|---|
| GET/POST | `/api/v1/projects` |
| GET | `/api/v1/projects/recent` |
| GET/PUT/DELETE | `/api/v1/projects/{project_id}` |
| GET/PUT | `/api/v1/projects/{project_id}/settings` |
| GET/POST | `/api/v1/projects/{project_id}/books` |
| POST | `/api/v1/projects/{project_id}/archive` · `/duplicate` · `/favorite` |

## AI (existing)

| Method | Path |
|---|---|
| GET | `/api/v1/ai/providers` · `/ai/models` · `/ai/status` |
| POST | `/api/v1/ai/chat` · `/ai/complete` · `/ai/test` |

## Images (existing)

| Method | Path |
|---|---|
| GET | `/api/v1/images` · `/images/{image_id}` |
| POST | `/api/v1/images/analyze` · `/plan` · `/generate` · `/regenerate` · `/replace` |
| PUT/DELETE | `/api/v1/images/{image_id}` |
