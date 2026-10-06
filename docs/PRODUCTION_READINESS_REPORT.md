# AI Ebook Studio — Production Readiness Report

**Snapshot date:** 2026-10-06
**Branch:** `arena/01a10cb1-ai-ebook-studio`
**Pull request:** [#1](https://github.com/Nior122/AI-Ebook-Studio/pull/1) (draft, targets `master`)
**Audit source:** `docs/PROJECT_AUDIT.md` and `docs/IMPLEMENTATION_ROADMAP.md`

## Verdict

**Not yet confirmed ready for production deployment.** The product has useful, locally verified deployment artifacts, but a remote Cloudflare Workers Builds check is failing and its account-side error log is not accessible from GitHub. No production Worker or Render service was deployed from this checkout.

### Latest remote evidence

- GitHub Actions run `37408649550` passed both backend and frontend jobs on pushed commit `c1af346`.
- The Cloudflare Workers Builds check for that commit failed with build ID `51c9ff4a-2c55-4aa2-af24-42b75be46633`. GitHub's check summary contains only a link to the private Cloudflare Dashboard. The failure reason is therefore **unknown**, not assumed to be fixed by local reproduction.
- Local reproduction found a recursive OpenNext command and fixed it; the remote Cloudflare check still failed afterward. A further local review found missing OpenNext `ASSETS` and `WORKER_SELF_REFERENCE` bindings. Those follow-up changes have now been locally validated and require a fresh remote check.

## Local deployment checks

On the current working tree:

| Check | Result | Notes |
|---|---|---|
| Clean frontend install | **PASS** | `npm ci`; npm currently reports 12 advisories (4 moderate, 8 high, 0 critical). |
| Frontend tests | **PASS** | 14 tests across 6 files. |
| Frontend TypeScript | **PASS** | `npm run typecheck`. |
| Frontend lint | **PASS with existing warnings** | `npm run lint`; includes deprecated `next lint`, `any`, unused state, and `<img>` warnings. |
| OpenNext production build | **PASS** | `CI=1 npm run build` produces `.open-next/worker.js`. |
| Wrangler packaging validation | **PASS (dry run only)** | `npx wrangler deploy --dry-run` read 89 static assets and reported both `WORKER_SELF_REFERENCE` and `ASSETS`; no upload was performed. |
| API rewrite configuration | **PASS** | Three cases verified: local port-8000 fallback, `NEXT_PUBLIC_API_BASE_URL` origin derivation, and `BACKEND_URL` precedence. |

The Next.js standalone trace root is package-local during the OpenNext build so its expected `.next/standalone/.next` layout is preserved. OpenNext's nested Next build is explicitly `npm run build:next`, preventing the previous `npm run build` recursion. CI now runs the actual OpenNext Worker build rather than only `next build`.

## Cloudflare Workers setup

`frontend/wrangler.toml` now declares:

- `main = ".open-next/worker.js"` and `nodejs_compat`;
- `global_fetch_strictly_public` for public server-side fetches;
- the required OpenNext `ASSETS` binding for `.open-next/assets`;
- the `WORKER_SELF_REFERENCE` service binding.

These settings follow the [OpenNext Cloudflare getting-started guide](https://opennext.js.org/cloudflare/get-started). Local `wrangler deploy --dry-run` accepts the config, but only the connected Cloudflare Workers Builds check can verify the account's build/deploy environment. Cloudflare Dashboard environment variables and deployment logs are not accessible in this checkout.

### Required dashboard values

Set the following in the Cloudflare Workers Builds environment, as appropriate for both **build time** and **Worker runtime**:

- `NEXT_PUBLIC_API_BASE_URL=https://<backend>.onrender.com/api/v1`
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<Clerk publishable key>`
- `CLERK_SECRET_KEY=<Clerk secret>` (store as a secret; never commit it)
- `BACKEND_URL=https://<backend>.onrender.com` is optional when the public API base URL is set; when provided, it should be the backend origin without `/api/v1`.

Actual values are not present in the repository and must be configured by the deployment owner. The repository's `wrangler.toml` comments document the dashboard build command (`npm run build`) and deploy command (`npx wrangler deploy`).

## Remaining release blockers

1. Push the locally tested Cloudflare binding and environment-proxy changes on `arena/01a10cb1-ai-ebook-studio`; wait for the new GitHub and Cloudflare checks.
2. If Workers Builds still fails, inspect its Dashboard log or share a **redacted error excerpt**. Do not share passwords, API tokens, or secret values.
3. Verify Render startup with production secrets and the actual Neon/PostgreSQL connection; run and validate the production migration lifecycle.
4. Configure the Cloudflare runtime/build variables above and perform a deployed smoke test for frontend asset loading, Clerk auth, and calls to the backend health/API routes.
5. Run an authenticated browser workflow and provider-backed quality checks when the required test sessions and provider credentials are available.

The backend suite passes **203 tests**, and a fresh SQLite database reached migration `20261005_0003` across 19 revisions. `render.yaml` now runs `alembic upgrade head` as a pre-deploy command and requires the deployment owner to supply the real HTTPS CORS origin and `APP_BASE_URL`; these checks do not establish populated PostgreSQL behavior, deployed startup, browser authentication, or live AI quality. Keep PR #1 in draft and do not describe the application as deployed or fully production-ready until the blockers above are resolved.
