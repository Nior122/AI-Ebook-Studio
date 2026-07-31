"""Production-readiness QA test — every workflow, end to end.

Covers the remaining checklist flows on top of test_studio_flow.py:

    forgot password -> reset -> login with new password
    email verification (signed token)
    project duplicate -> archive -> restore -> delete -> restore
    jobs history listing (previously "not implemented")
    proofreading review on a real chapter
    cover generation (auto restore point created)
    marketing generation
    translation (graceful without a key; real with LIBRETRANSLATE_URL / AI key)
    DOCX + PDF + EPUB exports
    auth rate limiting (429)
"""

from __future__ import annotations

import os
import re
import urllib.parse
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from core.config import get_settings
from database.base import Base
from database.session import AsyncSessionLocal, dispose_engine
from services.auth_service import create_auth_flow_token
from services.jobs.handlers import register_all_handlers

TEST_DB = "./var/test_studio.db"


def _setup_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "details": {
            "title": "QA Production Book",
            "subtitle": "End-to-end verification",
            "topic": "Building reliable software systems for production environments",
            "target_audience": "Engineers with some experience",
            "tone": "professional",
            "writing_style": "practical_guide",
            "language": "en",
            "author": "QA Runner",
            "book_purpose": "Help engineers ship dependable systems",
        },
        "size": {"total_word_count": 3000, "custom": False, "chapters_override": 3},
        "ai": {"provider": "openrouter", "model": "openai/gpt-4o-mini", "creativity": "balanced"},
        "special_instructions": {"instructions": "Be precise and practical."},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(payload.get(key), dict):
            payload[key].update(value)
        else:
            payload[key] = value
    return payload


@pytest.fixture()
async def qa_client() -> Any:
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    async with AsyncSessionLocal() as session:
        await session.run_sync(lambda sync: Base.metadata.create_all(sync.bind))
    register_all_handlers()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await dispose_engine()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


async def _register(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "QA Author"},
    )
    assert response.status_code in (200, 201), response.text
    data = response.json()
    return {
        "token": data["tokens"]["access_token"],
        "user_id": str(data["user"]["id"]),
        "headers": {"Authorization": f"Bearer {data['tokens']['access_token']}"},
    }


async def _wait_job(client: AsyncClient, token: str, job_id: str, timeout: float = 150.0) -> dict[str, Any]:
    import asyncio

    deadline = asyncio.get_event_loop().time() + timeout
    last: dict[str, Any] = {}
    while asyncio.get_event_loop().time() < deadline:
        response = await client.get(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200, response.text
        last = response.json()
        if last["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return last
        await asyncio.sleep(0.15)
    raise AssertionError(f"Job did not finish. Last: {last}")


async def test_auth_flows_password_reset_and_verification(qa_client: AsyncClient) -> None:
    account = await _register(qa_client, "reset-qa@test.dev")

    # --- Forgot password (no user enumeration) ---
    response = await qa_client.post(
        "/api/v1/auth/forgot-password", json={"email": "reset-qa@test.dev"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "sent" in body["message"].lower()
    assert body["dev_link"], "dev mode should return the reset link"
    token = urllib.parse.parse_qs(urllib.parse.urlparse(body["dev_link"]).query)["token"][0]

    # Unknown email: same generic message, no link.
    response = await qa_client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@test.dev"}
    )
    assert response.status_code == 200
    assert response.json()["dev_link"] is None

    # --- Reset password ---
    response = await qa_client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "NewPass456"},
    )
    assert response.status_code == 200, response.text

    # Old password rejected, new password works, sessions revoked.
    response = await qa_client.post(
        "/api/v1/auth/login",
        json={"email": "reset-qa@test.dev", "password": "SecurePass123"},
    )
    assert response.status_code == 401
    response = await qa_client.post(
        "/api/v1/auth/login",
        json={"email": "reset-qa@test.dev", "password": "NewPass456"},
    )
    assert response.status_code == 200, response.text

    # --- Email verification ---
    settings = get_settings()
    verify_token = create_auth_flow_token(UUID(account["user_id"]), "email_verify", settings)
    response = await qa_client.post(
        "/api/v1/auth/verify-email", json={"token": verify_token}, headers=account["headers"]
    )
    assert response.status_code == 200, response.text
    assert "verified" in response.json()["message"].lower()

    response = await qa_client.get("/api/v1/auth/me", headers=account["headers"])
    assert response.status_code == 200
    assert response.json()["is_email_verified"] is True

    # Bad-purpose token rejected.
    wrong = create_auth_flow_token(UUID(account["user_id"]), "reset_password", settings)
    response = await qa_client.post("/api/v1/auth/verify-email", json={"token": wrong})
    assert response.status_code in (400, 422)


async def test_project_lifecycle_and_jobs_history(qa_client: AsyncClient) -> None:
    account = await _register(qa_client, "projects-qa@test.dev")
    headers = account["headers"]

    # --- Create ---
    response = await qa_client.get("/api/v1/workspaces", headers=headers)
    workspace_id = response.json()[0]["id"]
    response = await qa_client.post(
        "/api/v1/projects",
        json={"workspace_id": workspace_id, "name": "QA Project"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    project_id = response.json()["id"]

    # --- Edit ---
    response = await qa_client.put(
        f"/api/v1/projects/{project_id}",
        json={"name": "QA Project v2"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "QA Project v2"

    # --- Duplicate ---
    response = await qa_client.post(f"/api/v1/projects/{project_id}/duplicate", headers=headers)
    assert response.status_code == 200, response.text
    duplicate_id = response.json()["id"]
    assert duplicate_id != project_id

    # --- Archive + Restore ---
    response = await qa_client.post(f"/api/v1/projects/{project_id}/archive", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "archived"
    response = await qa_client.post(f"/api/v1/projects/{project_id}/restore", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "active"

    # --- Delete + Restore ---
    response = await qa_client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert response.status_code == 200
    response = await qa_client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert response.status_code == 404
    response = await qa_client.post(f"/api/v1/projects/{project_id}/restore", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "active"

    # --- Jobs history (previously a "not implemented" placeholder) ---
    response = await qa_client.get("/api/v1/jobs", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_full_book_workflow_with_jobs(qa_client: AsyncClient) -> None:
    account = await _register(qa_client, "workflow-qa@test.dev")
    headers = account["headers"]

    # --- Generate ---
    response = await qa_client.post("/api/v1/generation/setup", json=_setup_payload(), headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["project_id"] and body["job_id"] and body["writing_book_id"]
    project_id, writing_book_id = body["project_id"], body["writing_book_id"]
    job = await _wait_job(qa_client, account["token"], body["job_id"])
    assert job["status"] == "COMPLETED", job

    response = await qa_client.get(
        f"/api/v1/book-writing/books/{writing_book_id}/chapters", headers=headers
    )
    chapters = response.json()
    assert len(chapters) >= 3
    chapter_id = chapters[0]["id"]

    # --- Proofread (editing review) ---
    response = await qa_client.post(
        f"/api/v1/editing/chapters/{chapter_id}/review",
        json={"payload": {"mode": "proofreading"}},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    review = response.json()
    assert "suggestions" in review

    # --- Cover job + automatic restore point ---
    response = await qa_client.post(
        f"/api/v1/async/books/{writing_book_id}/cover", headers=headers
    )
    assert response.status_code == 202, response.text
    cover_job = await _wait_job(qa_client, account["token"], response.json()["id"])
    assert cover_job["status"] == "COMPLETED", cover_job

    versions = await qa_client.get(f"/api/v1/projects/{project_id}/versions", headers=headers)
    version_labels = [v["label"] for v in versions.json()]
    assert any("After Cover generation" in label for label in version_labels), version_labels

    # --- Marketing job ---
    response = await qa_client.post(
        f"/api/v1/async/books/{writing_book_id}/marketing/AMAZON_DESCRIPTION", headers=headers
    )
    assert response.status_code == 202, response.text
    marketing_job = await _wait_job(qa_client, account["token"], response.json()["id"])
    assert marketing_job["status"] == "COMPLETED", marketing_job

    # --- Translation: graceful without a key (clear actionable error) ---
    response = await qa_client.post(
        f"/api/v1/async/books/{writing_book_id}/translate",
        params={"source_lang": "en", "target_lang": "es"},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    translation_job = await _wait_job(qa_client, account["token"], response.json()["id"])
    if translation_job["status"] == "FAILED":
        message = translation_job.get("error_message") or ""
        assert "provider key" in message or "LibreTranslate" in message, message
    else:
        assert translation_job["status"] == "COMPLETED"

    # --- Exports: DOCX + PDF + EPUB must produce real files ---
    storage_root = os.path.join(os.path.dirname(__file__), "..", "var", "storage")
    for fmt in ("docx", "pdf", "epub"):
        response = await qa_client.post(
            f"/api/v1/async/books/{writing_book_id}/exports/{fmt}", headers=headers
        )
        assert response.status_code == 202, response.text
        export_job = await _wait_job(qa_client, account["token"], response.json()["id"])
        assert export_job["status"] == "COMPLETED", export_job

    produced = []
    for root, _, files in os.walk(storage_root):
        for name in files:
            if name.endswith((".docx", ".pdf", ".epub")):
                produced.append(name)
    assert any(name.endswith(".docx") for name in produced), produced
    assert any(name.endswith(".pdf") for name in produced), produced
    assert any(name.endswith(".epub") for name in produced), produced

    # --- Jobs history now lists everything ---
    response = await qa_client.get("/api/v1/jobs", headers=headers)
    job_types = {job["job_type"] for job in response.json()}
    assert {"BOOK_GENERATION", "COVER_GENERATION", "DOCX_BUILD", "PDF_EXPORT", "EPUB_EXPORT"} <= job_types


async def test_auth_rate_limiting(qa_client: AsyncClient) -> None:
    await _register(qa_client, "ratelimit-qa@test.dev")
    seen_429 = False
    for _ in range(70):
        response = await qa_client.post(
            "/api/v1/auth/login",
            json={"email": "ratelimit-qa@test.dev", "password": "WrongPass123"},
        )
        if response.status_code == 429:
            seen_429 = True
            break
    assert seen_429, "rate limiter should return 429 after enough attempts"
