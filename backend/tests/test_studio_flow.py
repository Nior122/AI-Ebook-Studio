"""End-to-end Studio UX flow test.

Covers the full user journey against the real app (no DB overrides, so
background jobs and request handlers share the same SQLite file):

    register -> setup (wizard payload) -> background generation job
    -> chapters written -> autosave -> version snapshot -> restore
    -> activities timeline -> notifications -> manuscript search
    -> bookmarks -> stage transitions -> DOCX export -> KDP validation
    -> assistant edit -> image generation -> smart-AI clarification path
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from database.base import Base
from database.session import AsyncSessionLocal, dispose_engine
from services.jobs.handlers import register_all_handlers

TEST_DB = "./var/test_studio.db"


def _setup_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "details": {
            "title": "The Startup Field Guide",
            "subtitle": "A practical path from idea to first customers",
            "topic": "Launching and growing a small software business from zero",
            "target_audience": "First-time founders with no technical background",
            "tone": "friendly",
            "writing_style": "practical_guide",
            "language": "en",
            "author": "Test Author",
            "book_purpose": "Help readers launch a side business in 90 days",
        },
        "size": {"total_word_count": 3000, "custom": False, "chapters_override": 3},
        "layout": {
            "page_size": "6x9",
            "body_font": "Georgia",
            "body_size": 12,
            "line_spacing": 1.5,
            "image_ratio": "16:9",
            "default_image_style": "realistic",
        },
        "ai": {
            "provider": "openrouter",
            "model": "openai/gpt-4o-mini",
            "creativity": "balanced",
            "reading_level": "basic",
            "generate_exercises": True,
            "generate_summaries": True,
        },
        "special_instructions": {
            "instructions": "Avoid jargon. Use short paragraphs and concrete examples."
        },
    }
    return _deep_merge(payload, overrides)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@pytest.fixture()
async def studio_client() -> AsyncIterator[AsyncClient]:
    """Real app client sharing the file-backed DB with the job runner."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    async with AsyncSessionLocal() as session:
        await session.run_sync(lambda sync: Base.metadata.create_all(sync.bind))

    # ASGITransport does not run the app lifespan, so register job handlers
    # explicitly (production registers them on startup).
    register_all_handlers()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await dispose_engine()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


async def _register(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "author@test.dev", "password": "SecurePass123", "display_name": "Test Author"},
    )
    assert response.status_code in (200, 201), response.text
    return str(response.json()["tokens"]["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _wait_job(client: AsyncClient, token: str, job_id: str, timeout: float = 120.0) -> dict[str, Any]:
    """Poll a job until terminal, yielding to the loop so the task can run."""
    deadline = asyncio.get_event_loop().time() + timeout
    last: dict[str, Any] = {}
    while asyncio.get_event_loop().time() < deadline:
        response = await client.get(f"/api/v1/jobs/{job_id}", headers=_auth(token))
        assert response.status_code == 200, response.text
        last = response.json()
        if last["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return last
        await asyncio.sleep(0.15)
    raise AssertionError(f"Job did not finish in time. Last state: {last}")


async def test_studio_full_flow(studio_client: AsyncClient) -> None:
    token = await _register(studio_client)
    headers = _auth(token)

    # ---- Smart-AI clarification path ---------------------------------------
    vague = _setup_payload(details={"topic": "Cooking"})
    response = await studio_client.post("/api/v1/generation/setup", json=vague, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["clarification_questions"], "vague setup should ask questions"
    assert body["project_id"] is None

    # ---- One-click generation ----------------------------------------------
    response = await studio_client.post("/api/v1/generation/setup", json=_setup_payload(), headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["clarification_questions"] is None, body
    assert body["project_id"] and body["job_id"] and body["writing_book_id"]
    project_id, job_id, writing_book_id = body["project_id"], body["job_id"], body["writing_book_id"]
    UUID(project_id)

    # ---- Generation runs in the background with progress -------------------
    job = await _wait_job(studio_client, token, job_id)
    assert job["status"] == "COMPLETED", job
    assert job["progress"] == 100

    # Project moved to Review stage.
    response = await studio_client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert response.status_code == 200, response.text
    project = response.json()
    assert project["stage"] == "review", project

    # Chapters were written with real content.
    response = await studio_client.get(
        f"/api/v1/book-writing/books/{writing_book_id}/chapters", headers=headers
    )
    assert response.status_code == 200, response.text
    chapters = response.json()
    assert len(chapters) >= 3, chapters
    for chapter in chapters:
        assert chapter["content"].strip(), chapter
        assert chapter["actual_word_count"] > 50, chapter
    first_chapter = chapters[0]

    # ---- Autosave -----------------------------------------------------------
    new_content = "# Edited draft\n\nThis chapter was edited by the author during the test run."
    response = await studio_client.put(
        f"/api/v1/projects/{project_id}/autosave",
        json={"chapters": {first_chapter["id"]: new_content}},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["saved_chapters"] == 1
    response = await studio_client.get(
        f"/api/v1/book-writing/books/{writing_book_id}/chapters", headers=headers
    )
    edited = next(c for c in response.json() if c["id"] == first_chapter["id"])
    assert "edited by the author" in edited["content"]

    # ---- Version snapshot + restore -----------------------------------------
    response = await studio_client.post(
        f"/api/v1/projects/{project_id}/versions",
        json={"label": "Before my edits", "reason": "test snapshot"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    version_id = response.json()["id"]

    response = await studio_client.put(
        f"/api/v1/projects/{project_id}/autosave",
        json={"chapters": {first_chapter["id"]: "# Scrapped\n\nThis content will be restored away."}},
        headers=headers,
    )
    assert response.status_code == 200

    response = await studio_client.post(f"/api/v1/versions/{version_id}/restore", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["restored"] is True

    response = await studio_client.get(
        f"/api/v1/book-writing/books/{writing_book_id}/chapters", headers=headers
    )
    restored = next(c for c in response.json() if c["id"] == first_chapter["id"])
    assert "edited by the author" in restored["content"], "restore should revert the last save"

    # ---- Activity timeline ---------------------------------------------------
    response = await studio_client.get(f"/api/v1/projects/{project_id}/activities", headers=headers)
    assert response.status_code == 200, response.text
    activities = response.json()
    kinds = {a["kind"] for a in activities}
    assert "outline_created" in kinds, kinds
    assert "chapter_generated" in kinds, kinds
    assert "generation_complete" in kinds, kinds
    assert "version_restored" in kinds, kinds

    # ---- Notifications -------------------------------------------------------
    response = await studio_client.get("/api/v1/notifications", headers=headers)
    assert response.status_code == 200, response.text
    notifications = response.json()
    assert notifications["unread"] >= 1
    assert any("Book generation complete" in n["title"] for n in notifications["items"])
    unread_id = next(n["id"] for n in notifications["items"] if n["read_at"] is None)
    response = await studio_client.post(f"/api/v1/notifications/{unread_id}/read", headers=headers)
    assert response.status_code == 200
    response = await studio_client.get("/api/v1/notifications/unread-count", headers=headers)
    assert response.json()["unread"] >= 0

    # ---- Manuscript search ---------------------------------------------------
    response = await studio_client.get(
        f"/api/v1/projects/{project_id}/search", params={"q": "founder"}, headers=headers
    )
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert results, "search should hit generated chapters"

    # ---- Bookmarks -----------------------------------------------------------
    response = await studio_client.post(
        f"/api/v1/projects/{project_id}/bookmarks",
        json={"chapter_id": first_chapter["id"], "title": "Important chapter", "note": "revisit"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    bookmark_id = response.json()["id"]
    response = await studio_client.get(f"/api/v1/projects/{project_id}/bookmarks", headers=headers)
    assert response.status_code == 200
    assert any(b["id"] == bookmark_id for b in response.json())
    response = await studio_client.delete(f"/api/v1/bookmarks/{bookmark_id}", headers=headers)
    assert response.status_code == 204

    # ---- Stage transitions ---------------------------------------------------
    response = await studio_client.put(
        f"/api/v1/projects/{project_id}/stage",
        json={"stage": "ready_for_export"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["stage"] == "ready_for_export"

    # ---- DOCX export job -----------------------------------------------------
    response = await studio_client.post(
        f"/api/v1/async/books/{writing_book_id}/exports/docx", headers=headers
    )
    assert response.status_code == 202, response.text
    export_job = await _wait_job(studio_client, token, response.json()["id"])
    assert export_job["status"] == "COMPLETED", export_job

    # ---- KDP validation job --------------------------------------------------
    response = await studio_client.post(
        f"/api/v1/async/books/{writing_book_id}/kdp-validate", headers=headers
    )
    assert response.status_code == 202, response.text
    kdp_job = await _wait_job(studio_client, token, response.json()["id"])
    assert kdp_job["status"] == "COMPLETED", kdp_job

    # ---- Assistant (chat + edit actions, works without API keys) -------------
    response = await studio_client.post(
        f"/api/v1/projects/{project_id}/assistant",
        json={"message": "How should I improve the first chapter?"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["reply"].strip()

    response = await studio_client.post(
        f"/api/v1/projects/{project_id}/assistant",
        json={"chapter_id": first_chapter["id"], "message": "Tighten it up", "action": "shorten"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assistant = response.json()
    assert assistant["applied"] is True
    assert assistant["new_content"], assistant

    # ---- Image generation (Pollinations URL provider) ------------------------
    response = await studio_client.post(
        f"/api/v1/projects/{project_id}/images",
        json={"prompt": "A cozy home office with an open laptop and morning light", "aspect_ratio": "16:9"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    image = response.json()
    assert image["file_url"].startswith("https://image.pollinations.ai/"), image

    # ---- Provider key storage (encrypted) ------------------------------------
    response = await studio_client.put(
        "/api/v1/settings/ai/key",
        json={"provider": "openai", "api_key": "sk-test-1234567890"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["has_key"] is True
    response = await studio_client.get("/api/v1/settings/ai/key-status", headers=headers)
    assert response.json()["provider"] == "openai"
