# Architecture

AI Ebook Studio uses a modular monorepo with independent frontend and backend applications.

## Principles

- Feature code depends on interfaces, not vendors.
- Business services do not call external providers directly.
- Text AI and image AI are separate provider systems.
- Database access flows through repositories.
- API contracts are explicit and versioned.
- Configuration is environment-driven.

## High-Level Flow

```text
Next.js frontend -> FastAPI API -> services -> repositories/providers -> Neon PostgreSQL/external vendors
```

## Provider Abstraction

Text AI providers will implement a shared interface for completion, structured output, and streaming support. Planned providers include OpenAI, Anthropic, Google Gemini, OpenRouter, and future providers.

Image providers will use a separate interface. Pollinations is the first planned provider.

## Backend Layers

- `api/`: FastAPI routers and request boundary
- `services/`: use-case orchestration
- `providers/`: vendor adapters
- `repositories/`: persistence abstraction
- `models/`: SQLAlchemy models
- `schemas/`: Pydantic schemas
- `database/`: engine, sessions, migrations support
- `jobs/` and `workers/`: asynchronous processing
