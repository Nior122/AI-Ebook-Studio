# Studio UX — the unified book workspace

This document describes the redesigned user experience: one continuous flow from
dashboard to finished, validated, exportable book — instead of ten separate
module pages.

## The flow

```
Dashboard  →  New Book (5-section wizard)  →  Generate Book (one button)
    →  background generation with floating progress panel (%, ETA, current task)
    →  editor opens automatically  →  review with AI tools  →  export
```

Everything stays in **one workspace** (`/workspace/[projectId]`):

| Area | What it does |
| --- | --- |
| Left panel | Chapters, outline, bookmarks, version history (restore points), activity timeline |
| Center | Rich text editor (markdown-backed) with autosave, AI quick actions, keyboard shortcuts |
| Right panel | AI Assistant, Proofreader, Images, Cover, Marketing, Translation, KDP Validator, Export |
| Floating panel | Live generation progress (overall %, ETA, current task/chapter), minimizable |
| Header | Project stage badge (Draft → Generating → Review → Ready for Export → Published), manuscript search (Ctrl+F), notifications bell, save status ("Saving… / Saved / Last saved HH:MM") |

Legacy URLs (`/projects/[id]/writing`, `/proofreader`, …) now redirect into the
workspace with the right tool open, so old links and bookmarks keep working.

## Backend additions (all additive)

- `models/studio.py` — `ProjectActivity` (timeline), `StudioNotification`,
  `ProjectVersion` (restore points), `Bookmark`; `projects.stage` lifecycle column.
- `services/studio_service.py` — autosave, snapshots + restore, activities,
  notifications, manuscript search (chapters/headings/image captions), bookmarks,
  stage transitions, per-user encrypted AI provider keys, in-workspace assistant.
- `services/events.py` + WebSocket `GET /api/v1/ws/projects/{project_id}` — live
  progress/activity/notification/version events.
- `api/v1/studio.py` — the REST surface for all of the above (+ images via
  Pollinations, no key required).
- Job runner now publishes progress events and creates notifications/activities
  when any job finishes (success or failure, with actionable messages).
- The generation orchestrator drives the project through
  `draft → generating → review`, records timeline entries per phase, saves an
  automatic restore point, and notifies on completion.

### The Local engine (zero-key operation)

`providers/ai/local_provider.py` is an always-available fallback provider, so the
entire flow works **without any API keys**:

- Book brief / blueprint / chapter generation (structured JSON + real prose)
- Proofreading (deterministic language heuristics)
- Marketing copy and cover design briefs (template-based)
- Assistant chat and edit actions (grammar fix, shorten, expand, continue, rewrite)
- Translation via the free LibreTranslate public endpoint

The moment a real key is configured (env var or per-user key in the wizard),
real LLM providers take over automatically.

## Running locally

Backend (Python 3.12+, SQLite for zero-config local dev):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# optional, for the SQLite dev database:
set DATABASE_URL=sqlite+aiosqlite:///./var/dev.db   # or export DATABASE_URL=...
alembic upgrade head                                 # creates all tables incl. studio_* tables
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1` (default) and Clerk
keys for auth (existing setup).

## Verification

The end-to-end flow is covered by `backend/tests/test_studio_flow.py`:

register → smart-AI clarification path → one-click generation (local engine) →
chapters written → autosave → version snapshot + restore → activity timeline →
notifications → manuscript search → bookmarks → stage transitions → DOCX export
(a real `.docx` file) → KDP validation → assistant chat + edit actions → image
generation → encrypted provider-key storage.

```bash
cd backend && python -m pytest tests/ -q
```
