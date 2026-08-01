"""Production-hardening QA tests.

Covers the new hardening layer:

- monitoring: /health, /ready, /system/health (DB + storage + jobs)
- correlation: X-Request-Id header + request_id in error payloads
- request limits: 413 for oversized bodies
- job endpoint security: auth required, ownership enforced, generic enqueue removed
- persistence: GET /jobs/{id} falls back to the DB row after restart
- stale job recovery: RUNNING rows become FAILED with an actionable message
- secret hygiene: /me never exposes password material
"""

from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from database.base import Base
from database.session import AsyncSessionLocal, dispose_engine
from models.operations import Job
from services.jobs.runner import recover_stale_jobs

TEST_DB = "./var/test_studio.db"


@pytest.fixture()
async def hc() -> Any:
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    async with AsyncSessionLocal() as session:
        await session.run_sync(lambda sync: Base.metadata.create_all(sync.bind))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await dispose_engine()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


async def _register(client: AsyncClient) -> tuple[str, str, dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"hardening-{uuid4().hex[:10]}@test.dev",
            "password": "SecurePass123",
            "display_name": "Hardening QA",
        },
    )
    assert response.status_code in (200, 201), response.text
    data = response.json()
    token = data["tokens"]["access_token"]
    return token, str(data["user"]["id"]), {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------
async def test_liveness_ready_and_full_health(hc: AsyncClient) -> None:
    response = await hc.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    response = await hc.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    response = await hc.get("/api/v1/system/health")
    assert response.status_code == 200
    body = response.json()
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["storage"] == "ok"
    assert body["checks"]["jobs"] == "ok"
    assert body["version"]
    assert body["uptime_seconds"] >= 0


# ---------------------------------------------------------------------------
# Correlation ids
# ---------------------------------------------------------------------------
async def test_request_id_header_and_error_payload(hc: AsyncClient) -> None:
    response = await hc.get("/api/v1/health")
    assert response.headers.get("x-request-id")

    _, _, headers = await _register(hc)
    response = await hc.get("/api/v1/projects/00000000-0000-0000-0000-000000000000", headers=headers)
    assert response.status_code == 404
    body = response.json()
    assert body["request_id"], "error payload should carry the correlation id"
    assert body["error"]["message"]


# ---------------------------------------------------------------------------
# Request size limit
# ---------------------------------------------------------------------------
async def test_oversized_body_rejected(hc: AsyncClient) -> None:
    big_password = "x" * (21 * 1024 * 1024)  # > 20 MB default cap
    response = await hc.post(
        "/api/v1/auth/login",
        json={"email": "someone@test.dev", "password": big_password},
    )
    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


# ---------------------------------------------------------------------------
# Job endpoint security + persistence
# ---------------------------------------------------------------------------
async def test_job_endpoints_require_auth_and_generic_enqueue_removed(hc: AsyncClient) -> None:
    assert (await hc.get("/api/v1/jobs")).status_code == 401
    assert (await hc.get(f"/api/v1/jobs/{uuid4()}")).status_code == 401
    assert (await hc.post(f"/api/v1/jobs/{uuid4()}/cancel")).status_code == 401
    # The generic enqueue endpoint was removed (it allowed arbitrary job types
    # and payloads without authentication).
    response = await hc.post(
        "/api/v1/jobs", json={"job_type": "BOOK_GENERATION", "payload": {}}
    )
    # Route is gone: 404 on a fresh router, 405 if another method is registered.
    assert response.status_code in (404, 405)


async def test_job_get_falls_back_to_db_with_ownership(hc: AsyncClient) -> None:
    _, user_id, headers = await _register(hc)
    job_id = uuid4()
    async with AsyncSessionLocal() as session:
        session.add(
            Job(
                id=job_id,
                user_id=UUID(user_id),
                job_type="DOCX_BUILD",
                status="COMPLETED",
                progress=100,
                result_data={"ok": True},
            )
        )
        await session.commit()

    # Owner sees the persisted job even though the in-memory queue lost it.
    response = await hc.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["result"] == {"ok": True}

    # Another user must not see it.
    _, _, other_headers = await _register(hc)
    response = await hc.get(f"/api/v1/jobs/{job_id}", headers=other_headers)
    assert response.status_code == 404


async def test_stale_job_recovery(hc: AsyncClient) -> None:
    _, user_id, headers = await _register(hc)
    job_id = uuid4()
    async with AsyncSessionLocal() as session:
        session.add(
            Job(
                id=job_id,
                user_id=UUID(user_id),
                job_type="KDP_VALIDATION",
                status="RUNNING",
            )
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        recovered = await recover_stale_jobs(session)
    assert recovered >= 1

    response = await hc.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "FAILED"
    assert "Interrupted by server restart" in (body["error_message"] or "")


# ---------------------------------------------------------------------------
# Secret hygiene
# ---------------------------------------------------------------------------
async def test_me_does_not_leak_password_material(hc: AsyncClient) -> None:
    _, _, headers = await _register(hc)
    response = await hc.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    payload = response.text.lower()
    assert "password" not in payload
    assert "hash" not in payload
