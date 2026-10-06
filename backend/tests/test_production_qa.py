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
import urllib.parse
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text

from app.main import app
from core.config import get_settings
from database.base import Base
from database.session import AsyncSessionLocal, dispose_engine
from database.session import engine as database_engine
from models.operations import Job
from services.auth_service import create_auth_flow_token
from services.jobs.handlers import register_all_handlers

TEST_DB = "./var/test_studio.db"


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    """Make the persistent SQLite QA database enforce PostgreSQL-like FKs."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


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
        "layout": {
            "page_size": "8x10",
            "margins": {"top": 1.0, "bottom": 1.0, "left": 1.25, "right": 1.25},
        },
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
    enforce_sqlite_fks = database_engine.dialect.name == "sqlite"
    if enforce_sqlite_fks:
        event.listen(database_engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    try:
        async with AsyncSessionLocal() as session:
            await session.run_sync(lambda sync: Base.metadata.create_all(sync.bind))
        register_all_handlers()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"X-Forwarded-For": str(uuid4())},
        ) as client:
            yield client
    finally:
        await dispose_engine()
        if enforce_sqlite_fks:
            event.remove(database_engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
        try:
            if os.path.exists(TEST_DB):
                os.remove(TEST_DB)
        except PermissionError:
            # Windows: a lingering job-runner connection may still hold the file.
            pass


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


async def _wait_job(
    client: AsyncClient, token: str, job_id: str, timeout: float = 150.0
) -> dict[str, Any]:
    import asyncio

    deadline = asyncio.get_event_loop().time() + timeout
    last: dict[str, Any] = {}
    while asyncio.get_event_loop().time() < deadline:
        response = await client.get(
            f"/api/v1/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
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
    response = await qa_client.post(
        "/api/v1/generation/setup",
        json=_setup_payload(),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["project_id"] and body["job_id"] and body["writing_book_id"]
    project_id = body["project_id"]
    project_book_id = body["book_id"]
    writing_book_id = body["writing_book_id"]
    assert project_book_id and writing_book_id
    assert project_book_id != writing_book_id
    if database_engine.dialect.name == "sqlite":
        async with AsyncSessionLocal() as session:
            foreign_keys = await session.execute(text("PRAGMA foreign_keys"))
            assert foreign_keys.scalar_one() == 1
    # Multi-stage generation (spec → blueprint → outlines → sections →
    # validation per chapter) legitimately takes several minutes on a real
    # provider.
    job = await _wait_job(qa_client, account["token"], body["job_id"], timeout=900.0)
    assert job["status"] == "COMPLETED", job
    async with AsyncSessionLocal() as session:
        persisted_job = await session.get(Job, UUID(body["job_id"]))
        assert persisted_job is not None
        assert str(persisted_job.book_id) == project_book_id

    format_settings = await qa_client.get(
        f"/api/v1/books/{project_book_id}/settings", headers=headers
    )
    assert format_settings.status_code == 200, format_settings.text
    assert format_settings.json()["kdp_trim_size"] == "8x10"
    assert format_settings.json()["margin_left"] == 1.25

    response = await qa_client.get(
        f"/api/v1/book-writing/books/{writing_book_id}/chapters", headers=headers
    )
    chapters = response.json()
    body_chapters = [
        chapter for chapter in chapters
        if chapter["chapter_number"] > 0 and chapter["title"].lower() != "conclusion"
    ]
    assert len(body_chapters) == 3
    assert all(chapter["content"].strip() for chapter in body_chapters)
    manuscript_text = "\n".join(chapter["content"] for chapter in chapters).lower()
    total_words = sum(chapter["actual_word_count"] for chapter in chapters)
    # This assertion specifically guards the reproduced 24,038-word result
    # for a 3,000-word request; content quantity is measured from persisted text.
    chapter_lengths = [
        (c["chapter_number"], c["title"], c["actual_word_count"], c["target_word_count"])
        for c in chapters
    ]
    assert 2400 <= total_words <= 3600, (total_words, chapter_lengths)
    assert "production" in manuscript_text or "software systems" in manuscript_text
    assert "the book starts with a clear map" not in manuscript_text
    chapter_id = chapters[0]["id"]

    kdp_response = await qa_client.post(
        f"/api/v1/book-writing/books/{writing_book_id}/validate-kdp",
        headers=headers,
    )
    assert kdp_response.status_code == 200, kdp_response.text
    kdp_report = kdp_response.json()
    assert kdp_report["book_id"] == project_book_id
    assert any(
        check["check"] == "page_size" and "8x10" in check["message"]
        for check in kdp_report["passed_checks"]
    ), kdp_report
    latest_kdp_report = await qa_client.get(
        f"/api/v1/book-writing/books/{writing_book_id}/validate-kdp", headers=headers
    )
    assert latest_kdp_report.status_code == 200, latest_kdp_report.text
    assert latest_kdp_report.json()["id"] == kdp_report["id"]

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
    marketing_job_id = response.json()["id"]
    marketing_job = await _wait_job(qa_client, account["token"], marketing_job_id)
    assert marketing_job["status"] == "COMPLETED", marketing_job
    async with AsyncSessionLocal() as session:
        persisted_marketing_job = await session.get(Job, UUID(marketing_job_id))
        assert persisted_marketing_job is not None
        assert str(persisted_marketing_job.book_id) == project_book_id
    marketing_assets = await qa_client.get(
        f"/api/v1/book-writing/books/{writing_book_id}/marketing", headers=headers
    )
    assert marketing_assets.status_code == 200, marketing_assets.text
    assert marketing_assets.json()["items"]
    assert all(
        asset["book_id"] == project_book_id
        for asset in marketing_assets.json()["items"]
    )
    marketing_asset_id = marketing_assets.json()["items"][0]["id"]
    wrong_book_delete = await qa_client.delete(
        f"/api/v1/book-writing/books/{uuid4()}/marketing/{marketing_asset_id}",
        headers=headers,
    )
    assert wrong_book_delete.status_code == 404

    # --- Translation: graceful without a key (clear actionable error) ---
    response = await qa_client.post(
        f"/api/v1/async/books/{writing_book_id}/translate",
        params={"source_lang": "en", "target_lang": "es"},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    # Full books translate chapter-by-chapter through the AI provider; a
    # substantive manuscript takes a few minutes.
    translation_job = await _wait_job(
        qa_client, account["token"], response.json()["id"], timeout=420.0
    )
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

    listed_exports = await qa_client.get(
        f"/api/v1/book-writing/books/{writing_book_id}/exports", headers=headers
    )
    assert listed_exports.status_code == 200, listed_exports.text
    export_assets = listed_exports.json()["items"]
    assert len(export_assets) == 3
    assert all(asset["book_id"] == project_book_id for asset in export_assets)
    docx_asset = next(asset for asset in export_assets if asset["asset_type"] == "DOCX")
    downloaded = await qa_client.get(
        f"/api/v1/book-writing/books/{writing_book_id}/exports/{docx_asset['id']}",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"PK")
    wrong_book_download = await qa_client.get(
        f"/api/v1/book-writing/books/{uuid4()}/exports/{docx_asset['id']}",
        headers=headers,
    )
    assert wrong_book_download.status_code == 404

    book_export_root = os.path.join(storage_root, "exports", writing_book_id)
    produced = os.listdir(book_export_root)
    assert any(name.endswith(".docx") for name in produced), produced
    assert any(name.endswith(".pdf") for name in produced), produced
    assert any(name.endswith(".epub") for name in produced), produced

    docx_path = os.path.join(
        book_export_root,
        next(name for name in produced if name.endswith(".docx")),
    )
    from docx import Document

    docx = Document(docx_path)
    section = docx.sections[0]
    assert section.page_width.inches == pytest.approx(8.0, abs=0.01)
    assert section.page_height.inches == pytest.approx(10.0, abs=0.01)
    assert section.left_margin.inches == pytest.approx(1.25, abs=0.01)

    # --- Jobs history now lists everything ---
    response = await qa_client.get("/api/v1/jobs", headers=headers)
    job_types = {job["job_type"] for job in response.json()}
    assert {
        "BOOK_GENERATION",
        "COVER_GENERATION",
        "DOCX_BUILD",
        "PDF_EXPORT",
        "EPUB_EXPORT",
    } <= job_types


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
