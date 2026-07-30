# AI Ebook Studio Backend

FastAPI backend infrastructure for AI Ebook Studio.

This backend now includes Stage 3 infrastructure, Stage 4 authentication,
workspace/project management, and Stage 5 provider-independent AI engine foundations.

Stage 3 included:
- FastAPI app shell
- Pydantic Settings configuration
- Structured logging
- SQLAlchemy async engine and session management
- Alembic migration preparation
- Global error handling
- CORS, request logging, and security headers middleware
- Health and version endpoints
- Pytest health checks
- Dockerfile

Stage 4 adds:
- User registration and login
- JWT access tokens
- Refresh token rotation
- Logout
- Current user and profile update endpoints
- RBAC roles and permissions
- Workspace CRUD and invite structure
- Project CRUD, archive, duplicate, favorite, recent, search, filter
- Project settings
- Book container foundation
- Alembic schema migration

Stage 5 adds:
- Provider-independent `AIEngine.generate()` abstraction
- Provider interface for OpenAI, Anthropic, Gemini, OpenRouter, Groq, Ollama, and future providers
- Prompt template rendering and prompt versioning foundation
- Model registry with context, streaming, JSON mode, image, and cost metadata
- Project AI settings for provider, model, temperature, and max tokens
- AI usage telemetry model
- Provider health, model discovery, test, chat, and completion endpoints
- Mocked pytest coverage for provider switching, fallback, streaming, health, and endpoints

AI writing, editing, translation, marketing, image generation, cover generation,
ebook generation, DOCX/PDF/EPUB export, billing, and publishing workflows are not
implemented in this stage.

## Requirements

- Python 3.12+
- PostgreSQL-compatible database, such as Neon or local Docker PostgreSQL

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with local or Neon-compatible values.

## Run

```bash
uvicorn app.main:app --reload
```

Default URLs:
- API: `http://localhost:8000`
- Health: `http://localhost:8000/api/v1/health`
- Version: `http://localhost:8000/api/v1/version`
- Docs: `http://localhost:8000/docs`

## Migrations

```bash
alembic upgrade head
```

Use `DATABASE_URL` for Neon/PostgreSQL:

```bash
set DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
alembic upgrade head
```

## Test

```bash
pytest
```

## Core API

Authentication:
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/me`
- `PUT /api/v1/me`

Workspaces:
- `POST /api/v1/workspaces`
- `GET /api/v1/workspaces`
- `PUT /api/v1/workspaces/{workspace_id}`
- `POST /api/v1/workspaces/{workspace_id}/archive`
- `DELETE /api/v1/workspaces/{workspace_id}`

Projects:
- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `GET /api/v1/projects/recent`
- `PUT /api/v1/projects/{project_id}`
- `DELETE /api/v1/projects/{project_id}`
- `GET /api/v1/projects/{project_id}/settings`
- `PUT /api/v1/projects/{project_id}/settings`

AI Engine:
- `GET /api/v1/ai/providers`
- `GET /api/v1/ai/models`
- `GET /api/v1/ai/status`
- `POST /api/v1/ai/test`
- `POST /api/v1/ai/chat`
- `POST /api/v1/ai/complete`

`/api/v1/ai/chat` and `/api/v1/ai/complete` accept an explicit `payload` object
in the JSON body.

See `../docs/Stage_4_Backend_Auth_Workspaces.md` and
`../docs/Stage_5_AI_Engine.md` for architecture notes.
