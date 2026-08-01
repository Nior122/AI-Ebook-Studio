"""System monitoring endpoints — liveness, readiness, full health.

- ``GET /api/v1/health``         — liveness: the process is up (no deps).
- ``GET /api/v1/ready``          — readiness: database reachable (SELECT 1).
- ``GET /api/v1/system/health``  — full health: DB + storage write probe +
                                   job queue + version + uptime.
- ``GET /api/v1/version``        — version info.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from api.dependencies import DatabaseSession
from core.config import get_settings
from schemas.system import HealthResponse, VersionResponse

router = APIRouter(tags=["system"])

_STARTED_AT = datetime.now(UTC)


def _now() -> datetime:
    return datetime.now(UTC)


def _health_payload(status_value: str, response: Response | None = None) -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status=status_value,
        service=settings.service_name,
        version=settings.app_version,
        app=settings.app_name,
        environment=settings.app_env,
        timestamp=_now(),
    )


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def liveness() -> HealthResponse:
    """Return 200 whenever the process is running (no dependencies checked)."""
    return _health_payload("ok")


@router.get("/ready", response_model=HealthResponse, summary="Readiness probe")
async def readiness(session: DatabaseSession, response: Response) -> HealthResponse:
    """Return 200 when the database is reachable, otherwise 503.

    This is the endpoint Render uses as the health check path.
    """
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return _health_payload("unavailable", response)
    return _health_payload("ok", response)


@router.get("/system/health", summary="Full health: DB, storage, jobs, version")
async def full_health(session: DatabaseSession) -> dict[str, object]:
    """Deep health check with per-dependency status (database, storage, jobs)."""
    settings = get_settings()
    checks: dict[str, str] = {}

    # --- database ---
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    # --- storage write probe (local storage backend) ---
    try:
        root = settings.storage_local_root
        os.makedirs(root, exist_ok=True)
        probe = os.path.join(root, f".health-{uuid4().hex}.tmp")
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write("ok")
        os.remove(probe)
        checks["storage"] = "ok"
    except Exception:
        checks["storage"] = "error"

    # --- job queue ---
    try:
        from services.jobs import get_job_queue

        checks["jobs"] = "ok" if await get_job_queue().health_check() else "error"
    except Exception:
        checks["jobs"] = "error"

    healthy = all(value == "ok" for value in checks.values())
    return {
        "status": "ok" if healthy else "degraded",
        "service": settings.service_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "uptime_seconds": int((_now() - _STARTED_AT).total_seconds()),
        "checks": checks,
        "timestamp": _now().isoformat(),
    }


@router.get("/version", response_model=VersionResponse, summary="Version info")
async def version_info() -> VersionResponse:
    settings = get_settings()
    return VersionResponse(
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
    )
