# Coding Standards

## General

- Keep modules small and purpose-specific.
- Prefer explicit names over clever abstractions.
- Keep provider code isolated from product services.
- Add tests near the behavior being changed.

## TypeScript

- Use strict TypeScript.
- Prefer named exports for shared modules.
- Keep server state in dedicated services/hooks.
- Keep UI components presentational when possible.

## Python

- Use type hints for public functions.
- Use Pydantic schemas at API boundaries.
- Use SQLAlchemy models only in persistence layers.
- Keep FastAPI routers thin.

## Formatting

- Frontend: ESLint, TypeScript, Prettier-compatible formatting
- Backend: Ruff, mypy, pytest
