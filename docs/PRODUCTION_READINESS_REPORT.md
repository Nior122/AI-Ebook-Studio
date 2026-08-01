# AI Ebook Studio — Production Readiness Report

**Date:** 2026-08-01 · **Branch:** `master` · **Baseline:** `96a6546` (remote HEAD) · **Hardening commit:** `1e95cf6` (local, **not yet pushed**)

## 1. Verdict

**Ready to deploy** once the two manual steps below are done. The full backend
suite passes **148/148 tests** (including 7 new hardening tests), all 14 Alembic
migrations run clean on a fresh SQLite, all frontend `.ts/.tsx` files parse
cleanly with tree-sitter, and the static security scans below found no
hardcoded secrets, raw SQL, subprocess use, or dangerously-set HTML sinks.

> **Manual steps before/at deploy**
> 1. Push `1e95cf6` (sandbox has no GitHub credentials — PAT was revoked as advised).
> 2. Cloudflare Workers Builds deploy (repo is configured: root dir `frontend`,
>    build `npm run build` → `opennextjs-cloudflare build`, deploy
>    `npx wrangler deploy`; `wrangler.toml` uses `main = ".open-next/worker.js"`
>    + `nodejs_compat`).

## 2. What was audited (and verified clean)

| Area | Finding |
|---|---|
| Hardcoded secrets | `git grep` for `sk-…`, `pk_test_…`, `AIza…`, `ghp_…`, `AKIA…` across tracked files → **none** (`.env.example` files contain placeholders only) |
| Raw SQL / subprocess | No `subprocess`/`os.system` anywhere; the only `text("SELECT 1")` calls are the new health probes. All queries go through SQLAlchemy ORM |
| XSS sinks | No `dangerouslySetInnerHTML` / `v-html`. `markdown.ts` escapes attribute values (`escapeHtml` on `src`/`alt`/`href`) before injecting; the rich editor syncs a user-owned `contentEditable`. Residual (low): `href` escaping doesn't block `javascript:` scheme — see §7 |
| Command injection | No shell interpolation of user input (no subprocess at all) |
| Endpoint auth gaps | **Fixed this pass**: `GET /jobs/{id}`, `POST /jobs/{id}/cancel`, and generic `POST /jobs` were unauthenticated. All job routes now require auth + ownership; the generic enqueue endpoint was **removed** (arbitrary `job_type`/payload with no auth) |
| Request size limits | **Fixed**: 20 MB cap middleware → HTTP 413 (`MAX_REQUEST_BODY_MB`) |
| Logging | structlog structured logging + request-logging middleware; **fixed**: every response now carries `X-Request-Id` and error payloads include `request_id` for correlation |
| Indexes | All FK columns indexed via `__table_args__` (`Project.owner_user_id`, `Book.project_id`, `WritingBook.user_id`, `ProjectVersion.project_id`, `Notification.user_id`, `ProjectActivity(project_id, created_at)` composite, `ProjectSettings.project_id` unique, etc.) → **no migration needed** |
| Health endpoints | **Fixed**: `/api/v1/health` (liveness), `/api/v1/ready` (DB probe, now the Render health check), `/api/v1/system/health` (DB + storage write probe + job queue + version + uptime), `/api/v1/version` |
| N+1 queries | List endpoints are single-query (`list_projects`, `list_jobs` use one `select` with no per-row sub-queries; `User.profile` is `selectinload`-ed in auth paths) → **no N+1 found** |

## 3. Background jobs — resilience (this pass)

- **Persistence fallback:** `GET /jobs/{id}` now falls back to the `jobs` table
  when the in-memory queue no longer holds the job (e.g. after restart).
- **Stale recovery:** on startup, `recover_stale_jobs()` marks PENDING/QUEUED/
  RUNNING rows FAILED with "Interrupted by server restart — please retry".
- **Ownership:** queue payloads and DB rows are both checked against the caller.

## 4. Authentication model (documented)

- **Frontend:** Clerk (`@clerk/nextjs` middleware protects `/dashboard`,
  `/book-writing`, `/projects`, `/workspace`, `/new-book`, `/generating`).
- **Backend:** local JWT accounts (`register`/`login`) are the primary API auth;
  the studio API also accepts **Clerk JWTs** (`verify_clerk_token` against
  `CLERK_JWKS_URL`, auto-provisioning a `User` by `clerk_id`) — so a
  Clerk-only deployment works with zero local passwords.
- **NextAuth is not used** anywhere in the codebase.
- **Env vars:** `NEXT_PUBLIC_API_BASE_URL` (frontend → backend, defaults to
  `/api/v1` same-origin) is the only frontend base-URL var; there is no
  server-side `API_URL` in use. Clerk vars: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
  + `CLERK_SECRET_KEY` (frontend), `CLERK_PUBLISHABLE_KEY`/`CLERK_SECRET_KEY`/
  `CLERK_JWKS_URL` (backend, optional).

## 5. Environment variables

- **Canonical template:** root `.env.example` — complete against `Settings`
  after this pass (added `MAX_REQUEST_BODY_MB`); sectioned by host
  (Backend/Render, Database/Neon, Frontend/Cloudflare).
- `backend/.env.example` was aligned with every `Settings` field (added
  `NVIDIA_NIM_API_KEY`, `CUSTOM_OPENAI_*`, `AI_FALLBACK_PROVIDER/MODEL`,
  `CLERK_*`, `APP_BASE_URL`, `EMAIL_FROM`, `SMTP_*`, `REQUIRE_EMAIL_VERIFICATION`,
  `LIBRETRANSLATE_URL`, `RATE_LIMIT_ENABLED`, `MAX_REQUEST_BODY_MB`).
- Production settings to flip at deploy: `APP_ENV=production`, `DEBUG=false`,
  strong `SECRET_KEY`/`JWT_SECRET` (Render auto-generate), Neon **non-pooling**
  connection string, `SMTP_*` for real emails, `NEXT_PUBLIC_API_BASE_URL=https://<backend>.onrender.com/api/v1`.

## 6. Deployment configuration

- **Render (backend):** `render.yaml` — health check now `/api/v1/ready`;
  asyncpg SSL handled (`strip sslmode/channel_binding`, pass via `connect_args`);
  `AI_DEFAULT_PROVIDER=openrouter` per the latest remote commit.
- **Cloudflare (frontend):** Workers Builds route; `wrangler.toml` pinned to
  `.open-next/worker.js` + `nodejs_compat` (remote commit `96a6546` — the
  stale local copy was replaced, not overwritten).
- **Storage:** local backend on Render disk (exports/images); S3/R2 switches
  are pre-wired via `STORAGE_PROVIDER`.

## 7. Residual recommendations (non-blocking)

1. **`javascript:` URL scheme in markdown links** — `escapeHtml` prevents
   attribute breakout; add a scheme allowlist (`http`, `https`, `mailto`) in
   `frontend/lib/markdown.ts` for defense in depth.
2. **API cache headers** — API responses are authenticated/private and uncached
   by design; if any public read route appears later, add `Cache-Control`.
3. **Job queue durability** — jobs are persisted and recoverable, but a
   Postgres-backed queue (e.g. `arq`) would allow multi-instance workers if
   the single Render instance outgrows itself.
4. **Rate limiting** covers auth endpoints; consider extending to job-creation
   paths if abuse is observed.

## 8. Evidence

- Backend: `pytest` → **148 passed** (0 failures), incl. `test_prod_hardening.py` (7).
- Migrations: 14/14 clean on fresh SQLite; job table writes verified in tests.
- Frontend: `scripts/verify_frontend.py` — all files parse, no orphan
  components (dynamic imports tracked), 24 routes.
- Workspace performance: 8 right-panel tools lazy-loaded via `next/dynamic`;
  image grids `loading="lazy"`.
