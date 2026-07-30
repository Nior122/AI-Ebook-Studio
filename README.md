# AI Ebook Studio

AI Ebook Studio is a production SaaS foundation for planning, writing, editing, illustrating, validating, and exporting ebooks with AI assistance.

This repository is currently in **Stage 1: Project Foundation**. It intentionally does not implement ebook writing, editing, image generation, authentication, export, KDP validation, marketing, or translation features yet. The goal of this stage is a clean architecture that future features can follow safely.

## Technology Stack

Frontend:
- Next.js with App Router
- TypeScript
- Tailwind CSS
- shadcn/ui

Backend:
- Python
- FastAPI
- SQLAlchemy
- Alembic

Infrastructure:
- Neon PostgreSQL
- GitHub repository
- Future frontend deployment to Cloudflare Pages
- Future backend deployment to Render

Provider strategy:
- AI providers are abstracted behind a provider interface.
- Supported planned providers: OpenAI, Anthropic, Google Gemini, OpenRouter, and future providers.
- Image providers are separate from text AI providers.
- Pollinations is the first planned image provider.

## Project Structure

```text
AI-Ebook-Studio/
  frontend/       Next.js application foundation
  backend/        FastAPI application foundation
  shared/         Cross-stack contracts and shared types
  docs/           Product, architecture, API, database, UI, security, and workflow docs
  prompts/        Prompt templates grouped by domain
  database/       Migration, schema, seed, and diagram placeholders
  scripts/        Developer and deployment automation placeholders
  assets/         Brand, reference, and future product assets
  public/         Root-level public assets
  .github/        CI workflow foundation
```

## Installation

Copy the environment template:

```bash
cp .env.example .env
```

Install frontend dependencies:

```bash
cd frontend
npm install
```

Install backend dependencies:

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Running Locally

Frontend:

```bash
cd frontend
npm run dev
```

Backend setup will be activated in Stage 2 when the FastAPI app shell and first API boundaries are introduced.

Optional local infrastructure:

```bash
docker compose up postgres redis -d
```

## Stage 1 Scope

Included:
- Professional monorepo layout
- Frontend folder architecture
- Backend folder architecture
- Documentation starter set
- Prompt template starter set
- Environment variable template
- Provider abstraction design
- UI design system documentation
- Deployment direction for Cloudflare Pages, Render, and Neon

Not included yet:
- Authentication
- Ebook writing
- Editing
- Image generation
- DOCX, PDF, EPUB, or KDP export
- Marketing tools
- Translation
- Billing
- Production deployments

## Roadmap

Stage 2 should add the first runnable backend app shell, API versioning conventions, database connection plumbing, Alembic baseline, frontend route groups, and authentication design decisions without implementing the full auth flow.

See [Development_Roadmap.md](docs/Development_Roadmap.md) for the staged delivery plan.
