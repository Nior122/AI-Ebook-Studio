# Deployment guide and current status

## Current status — 2026-10-06

Deployment has **not** been verified end to end. GitHub Actions passed on the last inspected commit, but the Cloudflare Workers Builds check failed and its detailed log requires Cloudflare Dashboard access. The OpenNext worker build and Wrangler dry-run pass locally; a dry-run is not a deployment. See [Production Readiness Report](PRODUCTION_READINESS_REPORT.md) for the latest check IDs and remaining gates.

## Target platforms

- Frontend: Cloudflare Workers Builds using Next.js through `@opennextjs/cloudflare`.
- Backend: Render web service using FastAPI.
- Database: Neon PostgreSQL (non-pooling `asyncpg` connection string).
- Source and CI: GitHub; PR CI runs backend tests/migrations/scoped Ruff plus frontend tests/typecheck/lint/OpenNext build.

## Cloudflare frontend

The frontend package root is `frontend/`. The checked-in configuration expects:

- Build command: `npm run build` (produces `.open-next/worker.js`).
- Deploy command: `npx wrangler deploy`.
- Production branch: `master` (verify this matches the Cloudflare dashboard).
- Wrangler config: `frontend/wrangler.toml`; it declares the OpenNext asset directory, `ASSETS` binding, `WORKER_SELF_REFERENCE`, `nodejs_compat`, and `global_fetch_strictly_public`.
- `frontend/open-next.config.ts` selects `npm run build:next` for OpenNext's nested Next.js build to prevent recursion.

Set the following in the Cloudflare Workers Builds environment. Public/build-time values should be available when Next.js bundles the frontend; secrets must also be configured as Worker secrets for runtime:

- `NEXT_PUBLIC_API_BASE_URL=https://<backend-host>.onrender.com/api/v1`
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<Clerk publishable key>`
- `CLERK_SECRET_KEY=<Clerk secret>` (secret; never commit it)
- `BACKEND_URL=https://<backend-host>.onrender.com` is optional when the public API base is set; when provided, use the origin without `/api/v1`.

Do not upload a Worker until the remote Workers Builds check passes and the required domain/environment values are configured. The actual domain and Cloudflare account settings are not available in this repository.

## Render backend and Neon database

The root `render.yaml` defines the FastAPI service and intentionally requires the deployment owner to provide:

- `DATABASE_URL` using the Neon **non-pooling** endpoint;
- production frontend `CORS_ORIGINS` (the exact HTTPS Worker/custom-domain origin, with no path);
- `APP_BASE_URL` (the same public HTTPS frontend URL, used for auth/email links);
- Clerk keys/JWKS URL and email SMTP values as appropriate.

Render generates distinct `SECRET_KEY` and `JWT_SECRET`. The service runs `alembic upgrade head` in a pre-deploy command before starting Uvicorn. The backend rejects unsafe production secret/debug/CORS settings and now requires a public HTTPS `APP_BASE_URL`; unset or development values must be fixed before startup.

After configuring the blueprint, verify `/api/v1/ready` against the live database. Do not treat SQLite migration success as PostgreSQL validation; use a staging Neon database first and inspect migration effects before production.

## Release sequence

1. Push only to the session branch and wait for required GitHub Actions checks.
2. Resolve any failing Cloudflare Workers Builds check from its Dashboard log; do not infer the cause from a local build alone.
3. Configure Cloudflare build/runtime variables and Render/Neon environment values without committing secrets.
4. Deploy backend migrations and verify the readiness endpoint.
5. Deploy the Worker and smoke-test static assets, Clerk sign-in, frontend-to-backend calls, and project ownership.
6. Run the authenticated browser workflow and provider-quality checks when their test infrastructure/credentials are available.

## Local preflight (does not deploy)

```bash
cd frontend
npm ci
npm test -- --reporter=dot
npm run typecheck
npm run lint
npm run build
npx wrangler deploy --dry-run
```

Secrets belong in platform dashboards or local ignored `.env` files, never Git. Video generation/rendering is out of scope.
