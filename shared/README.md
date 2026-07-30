# `shared/` — Cross-stack contracts

This package holds types and constants that the **frontend** and the **backend**
must agree on. Importing a contract from one place — rather than re-declaring it
on both sides — prevents the two halves of the system from drifting apart.

## What lives here

| Path             | Purpose                                                      |
|------------------|--------------------------------------------------------------|
| `types/api.ts`   | REST response/request shapes + provider-id unions            |
| `types/index.ts` | Barrel re-export so consumers import from `@shared/types`   |

## How the two stacks consume it

- **Frontend (Next.js)** imports via the path alias configured in
  `frontend/tsconfig.json` and `frontend/next.config.mjs` (externalDir):
  ```ts
  import type { ApiHealth } from "@/shared/types";
  ```
- **Backend (FastAPI)** does not import TypeScript; it mirrors these contracts
  in Pydantic schemas under `backend/schemas/`. The TS types are the canonical
  description of the wire format, and the Pydantic models are kept in sync with
  them.

## Rules

1. A shape belongs here only if **both** stacks depend on it.
2. Backend-only or frontend-only types stay in their own `types/` dirs.
3. When a contract changes, update the TS type **and** the matching Pydantic
   schema in the same change. Tests in `backend/tests` should fail if they drift.
