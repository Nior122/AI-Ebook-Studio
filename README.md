# AI Ebook Studio

AI Ebook Studio is a production SaaS foundation for planning, writing, editing, illustrating, validating, and exporting ebooks with AI assistance.

The core user flow is now fully implemented and wired end-to-end:

```
Dashboard → New Book wizard (5 sections) → Generate Book
  → background generation (floating progress panel: %, ETA, current task)
  → unified workspace opens automatically (editor + AI tools)
  → autosave, versions, search, notifications → validate → export
```

## What works today

- **New Book wizard** — title/subtitle/author/topic/audience/language/tone/style/
  purpose, word-count presets with live chapter estimates (+ override), full
  formatting section (page size, margins, fonts, spacing, images), AI settings
  (provider, encrypted API key, creativity, quality, reading level, citations,
  exercises, summaries), special instructions, and smart-AI pre-checks that ask
  follow-up questions when something is ambiguous.
- **One-click generation** — one button launches the whole pipeline (brief →
  blueprint → chapters → formatting → validation) in the background with live
  progress, ETA, and per-chapter status; the editor opens automatically when it
  finishes.
- **Unified workspace** (`/workspace/[projectId]`) — three panels:
  - Left: chapters, outline, bookmarks, version history (restore points), activity timeline
  - Center: rich text editor with autosave ("Saving… / Saved / Last saved"), AI quick actions
  - Right: AI assistant, proofreader, images, cover, marketing, translation, KDP validator, export
- **Live updates** — WebSocket stream for progress, notifications, activities,
  and version events; floating minimizable progress panel; notification center
  with retry/open actions.
- **Project stages** — Draft → Generating → Review → Ready for Export → Published.
- **Version history** — automatic restore points after generation/proofreading/
  formatting/translation plus manual snapshots, with one-click restore.
- **Manuscript search** (Ctrl+F) — chapters, headings, and image captions.
- **Keyboard shortcuts** — Ctrl+S (save), Ctrl+F (search), Ctrl+Z / Ctrl+Shift+Z.
- **Export & validation** — real DOCX/PDF/EPUB generation and KDP validation as
  background jobs with notifications.
- **Zero-key operation** — a built-in local engine (see
  [docs/Studio_UX.md](docs/Studio_UX.md)) keeps every feature working without API
  keys; real OpenAI / Anthropic / Gemini / OpenRouter / Groq providers take over
  automatically when keys are configured.

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
- Neon PostgreSQL (SQLite works for local dev)
- GitHub repository
- Future frontend deployment to Cloudflare Pages
- Future backend deployment to Render

Provider strategy:
- AI providers are abstracted behind a provider interface.
- Supported providers: OpenAI, Anthropic, Google Gemini, OpenRouter, Groq,
  NVIDIA NIM, Ollama, and a built-in offline Local engine.
- Image providers are separate from text AI providers; Pollinations is the
  default image provider (free, no key).

## Project Structure

```text
AI-Ebook-Studio/
  frontend/       Next.js application
  backend/        FastAPI application
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

Install backend dependencies and run it (SQLite works out of the box for local
development — no Docker or Postgres required):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
set DATABASE_URL=sqlite+aiosqlite:///./var/dev.db   # or export DATABASE_URL=...
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Run the frontend:

```bash
cd frontend
npm run dev
```

Open http://localhost:3000, sign in, and click **New Book**.

## Tests

```bash
cd backend
python -m pytest tests/ -q
```

The suite includes an end-to-end test (`tests/test_studio_flow.py`) covering the
complete user journey: wizard setup → background generation → autosave →
versions/restore → activities → notifications → search → bookmarks → stages →
DOCX export → KDP validation → assistant → images.

See [docs/Studio_UX.md](docs/Studio_UX.md) for the full architecture of the
unified workspace.
