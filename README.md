# AI Ebook Studio

AI Ebook Studio is an ebook-production application in active development. It combines a Next.js/TypeScript frontend with a FastAPI/SQLAlchemy backend and provider-independent AI services.

> **Status: not yet a complete or production-verified product.** Feature code and API routes do not imply that every end-to-end workflow is complete. Read the current [project audit](docs/PROJECT_AUDIT.md), [implementation roadmap](docs/IMPLEMENTATION_ROADMAP.md), and [production-readiness report](docs/PRODUCTION_READINESS_REPORT.md) before evaluating or deploying it.

## Implemented foundations

The repository currently includes:

- User accounts and Clerk integration, project/book APIs, a dashboard, and a unified workspace.
- A staged book-generation pipeline with saved chapters, background-job progress, retry/resume support, and manuscript quality/review state.
- Chapter editing, autosave, versions/restore points, and proofreading suggestions.
- Separate, source-preserving translated editions for synchronous and background translation.
- DOCX, PDF, and EPUB export paths, formatting settings, and an advisory KDP readiness check.
- Provider interfaces for text and image generation, custom text-provider configuration, and a local fallback for development/testing.

These are implementation foundations, not a guarantee that every workflow is publishable. In particular, offline generation must remain visibly degraded and in review; semantic quality with live providers is not verified. Image planning/placement, export fidelity, cover generation, marketing flows, durable jobs, and browser-level authentication still have known gaps documented in the audit.

## Verification snapshot

The latest local verification recorded for this branch includes:

- Backend: **203 tests passed**; a fresh SQLite migration chain reached `20261005_0003` across 19 revisions.
- Frontend: **14 tests passed across 6 files**, with typecheck and lint passing (lint emits existing warnings).
- Cloudflare artifact: the OpenNext Worker build and Wrangler dry-run pass locally; the dry-run confirms the `ASSETS` and `WORKER_SELF_REFERENCE` bindings without uploading a Worker.
- Remote: GitHub Actions passed on commit `c1af346`, but the Cloudflare Workers Builds check failed. The account-side failure details are unavailable from this checkout, and follow-up configuration changes require a new remote check.

Production Cloudflare/Render startup, populated PostgreSQL migrations, browser auth/E2E, and live-provider quality have not been verified. Do not use this snapshot as a deployment approval; see the production-readiness report for blockers and required environment variables.

## Technology stack

- **Frontend:** Next.js App Router, TypeScript, React, Tailwind CSS, Clerk.
- **Backend:** Python, FastAPI, SQLAlchemy, Alembic.
- **Persistence:** SQLite for local tests/development; PostgreSQL/Neon is the intended hosted database.
- **Deployment targets:** Cloudflare Workers Builds with OpenNext for the frontend; Render for the backend. Neither service is confirmed deployed from this checkout.
- **AI:** swappable text-provider adapters (including OpenAI-compatible, Anthropic, Gemini, OpenRouter, Groq, NVIDIA NIM, Ollama, and a local provider); image providers are independent of text providers.

## Repository structure

```text
AI-Ebook-Studio/
  frontend/       Next.js application and Cloudflare Worker configuration
  backend/        FastAPI application, models, services, migrations, tests
  shared/         Cross-stack contracts and shared types
  docs/           Audit, roadmap, deployment, architecture, and product docs
  prompts/        Prompt templates grouped by domain
  database/       Schema, seed, migration, and diagram material
  scripts/        Developer and deployment automation
  assets/         Brand, reference, and product assets
  .github/        CI workflow
```

## Local development

Copy the root environment template for reference and local backend settings:

```bash
cp .env.example .env
```

Install and run the frontend. Next.js reads frontend variables from `frontend/.env.local`; set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1` and test Clerk keys there when exercising authenticated flows.

```bash
cd frontend
npm ci
# Create .env.local with the local frontend variables described above.
npm run dev
```

In another shell, create the backend environment file, install dependencies, upgrade a local SQLite database, and start FastAPI:

```bash
cd backend
cp .env.example .env
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
DATABASE_URL=sqlite+aiosqlite:///./var/dev.db .venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open <http://localhost:3000>. Local fallback behavior is useful for development, but it is not evidence of production-quality generated prose.

## Tests

```bash
# Backend
cd backend && .venv/bin/python -m pytest tests/ -q

# Frontend (from frontend/)
npm test -- --reporter=dot
npm run typecheck
npm run lint
npm run build
npx wrangler deploy --dry-run
```

The backend suite contains broad API/service tests and a persisted workflow regression; it is not a real browser E2E suite. The frontend tests are component-level. `wrangler deploy --dry-run` packages the Worker locally and does not upload it or verify Cloudflare account configuration.
