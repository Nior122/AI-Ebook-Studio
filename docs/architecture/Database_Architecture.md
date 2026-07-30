# Database Architecture

## Stack

- **SQLAlchemy 2.x** (declarative, typed `Mapped[...]` columns), async engine.
- **Alembic** for migrations (`backend/migrations/`, `alembic.ini`).
- **Neon PostgreSQL** in hosted environments; SQLite (aiosqlite) for tests.

## Engine & sessions (`database/session.py`)

- Async engine created from `DATABASE_URL`.
- **Connection pooling** driven by settings: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`,
  `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`, plus `pool_pre_ping=True`. Pool sizing is
  applied only to PostgreSQL (SQLite does not support it).
- `get_db_session()` is the FastAPI dependency yielding a request-scoped
  `AsyncSession`. `dispose_engine()` cleans up on shutdown/tests.

## Base & conventions (`database/base.py`)

- `Base(DeclarativeBase)` with a consistent constraint **naming convention**
  (indexes, unique, check, foreign key, primary key) for clean migrations.
- `GUID` — a platform-independent UUID type: native `UUID` on PostgreSQL,
  `CHAR(32)` on SQLite (keeps tests light, production Neon-compatible).
- Mixins: `UUIDPrimaryKeyMixin` (UUID PK) and `TimestampMixin`
  (`created_at`, `updated_at`, soft-delete `deleted_at`).

## Model registration

`models/__init__.py` imports every model so Alembic autogenerate and
`Base.metadata` see the full schema. This includes the `Job` model used by the
job architecture.

## Migrations

```bash
cd backend
alembic revision --autogenerate -m "message"
alembic upgrade head
```

Migrations are reviewed before merge; the naming convention keeps generated
constraint names stable across environments.

## Phase 2 scope

Phase 2 provides the **database foundation** (engine, pooling, base, mixins,
session lifecycle). It does not add new business tables beyond what already
exists; the `jobs` table already exists to back the job architecture.
