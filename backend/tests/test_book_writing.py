"""Phase 6 — Book Writing & Manuscript Management tests.

Uses a mock AI service so no external/paid API calls are made. The AI service is
injected by overriding the ``get_ai_service`` dependency on the app, returning a
deterministic fake that returns structured JSON matching the engine's schemas.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# AI mock
# ---------------------------------------------------------------------------
class FakeAIService:
    """Deterministic stand-in for AIService returning canned structured output."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_structured_output(self, *, messages, schema, **kwargs):
        self.calls.append({"kind": "struct", "task": kwargs.get("task"), "model": kwargs.get("model")})
        system = messages[0].content if messages else ""
        task = kwargs.get("task", "")
        if "generate_book_brief" in task:
            return {
                "working_title": "AI Tools for Teachers",
                "subtitle": "A Practical Guide",
                "book_purpose": "Help teachers save time with AI.",
                "target_reader": "Teachers with limited technical experience.",
                "reader_problems": ["workload", "repetitive tasks"],
                "promised_transformation": "Confident AI users.",
                "tone": "Friendly",
                "writing_style": "Practical",
                "key_themes": ["productivity", "pedagogy"],
                "major_concepts": ["automation", "assistants"],
                "topics_to_avoid": ["advanced coding"],
                "suggested_structure": "Intro, chapters, conclusion.",
                "estimated_chapter_count": 10,
                "estimated_word_count": 40000,
            }
        if "generate_book_blueprint" in task:
            return {
                "introduction_purpose": "Set the stage for AI in teaching.",
                "chapters": [
                    {
                        "title": "Why Teachers Need AI",
                        "objective": "Explain changing role of technology.",
                        "summary": "Motivation and mindset.",
                        "key_lessons": ["workload", "assistance"],
                        "important_examples": ["grading"],
                        "practical_exercises": ["audit your week"],
                        "estimated_word_count": 3000,
                        "connects_to_previous": "",
                        "connects_to_future": "Next: tools.",
                    },
                    {
                        "title": "Getting Started",
                        "objective": "First steps with AI tools.",
                        "summary": "Setup and safety.",
                        "key_lessons": ["accounts", "privacy"],
                        "important_examples": ["chatbot"],
                        "practical_exercises": ["try a prompt"],
                        "estimated_word_count": 3000,
                        "connects_to_previous": "Why",
                        "connects_to_future": "Classroom",
                    },
                ],
            }
        if "generate_chapter_outline" in task:
            return {
                "title": "Why Teachers Need AI",
                "sections": [
                    {"title": "The Workload Problem", "purpose": "Context", "key_points": ["time", "tasks"]},
                    {"title": "AI as Assistant", "purpose": "Reframe", "key_points": ["support", "safe"]},
                ],
            }
        # Default: a content blob.
        return {"content": "This is generated chapter content for testing purposes."}

    async def generate_text(self, *, messages, **kwargs):
        self.calls.append({"kind": "text", "task": kwargs.get("task")})
        return type("R", (), {"content": "Mock generated text."})()


@pytest.fixture()
async def fake_ai():
    """Inject a fake AI service for the whole app (both DI and direct calls)."""
    fake = FakeAIService()
    from services import book_writing as bw_pkg
    from services.ai_service import get_ai_service

    # The service layer calls ``get_ai_service()`` directly inside ``_engine()``,
    # so we patch the symbol it imported.
    original = bw_pkg.service.get_ai_service
    bw_pkg.service.get_ai_service = lambda: fake
    app.dependency_overrides[get_ai_service] = lambda: fake
    yield fake
    bw_pkg.service.get_ai_service = original
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
async def register_and_token(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["tokens"]["access_token"])


async def create_book(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {
        "title": "AI Tools for Teachers",
        "description": "A practical guide for teachers.",
        "author_name": "Jane Doe",
        "target_audience": "Teachers",
        "language": "en",
        "tone": "Friendly",
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/book-writing/books", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Book creation + ownership
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_book_creation_and_listing(client: AsyncClient, fake_ai: FakeAIService) -> None:
    token = await register_and_token(client, "bw1@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    book = await create_book(client, headers)
    assert book["title"] == "AI Tools for Teachers"
    assert book["user_id"]  # assigned

    listed = await client.get("/api/v1/book-writing/books", headers=headers)
    assert listed.status_code == 200
    assert any(b["id"] == book["id"] for b in listed.json())


@pytest.mark.asyncio
async def test_book_requires_auth(client: AsyncClient, fake_ai: FakeAIService) -> None:
    resp = await client.post(
        "/api/v1/book-writing/books",
        json={"title": "X", "language": "en"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_idor_protection(client: AsyncClient, fake_ai: FakeAIService) -> None:
    """User A cannot access User B's book."""
    token_a = await register_and_token(client, "bw-a@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    book = await create_book(client, headers_a)

    token_b = await register_and_token(client, "bw-b@example.com")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    resp = await client.get(f"/api/v1/book-writing/books/{book['id']}", headers=headers_b)
    assert resp.status_code == 404
    patch = await client.patch(
        f"/api/v1/book-writing/books/{book['id']}", json={"payload": {"title": "Hacked"}}, headers=headers_b
    )
    assert patch.status_code == 404


# ---------------------------------------------------------------------------
# Brief + Blueprint
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_brief_generation_and_edit(client: AsyncClient, fake_ai: FakeAIService) -> None:
    token = await register_and_token(client, "bw2@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    book = await create_book(client, headers)

    gen = await client.post(
        f"/api/v1/book-writing/books/{book['id']}/brief/generate",
        json={"payload": {"provider": "openai", "model": "openai/gpt-4o-mini"}},
        headers=headers,
    )
    assert gen.status_code == 201, gen.text
    brief = gen.json()
    assert brief["working_title"] == "AI Tools for Teachers"
    assert brief["key_themes"] == ["productivity", "pedagogy"]

    # Edit and verify persistence.
    edited = await client.patch(
        f"/api/v1/book-writing/books/{book['id']}/brief",
        json={"payload": {"working_title": "AI for Educators"}},
        headers=headers,
    )
    assert edited.status_code == 200
    assert edited.json()["working_title"] == "AI for Educators"


@pytest.mark.asyncio
async def test_blueprint_generation_and_edit(client: AsyncClient, fake_ai: FakeAIService) -> None:
    token = await register_and_token(client, "bw3@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    book = await create_book(client, headers)
    await client.post(f"/api/v1/book-writing/books/{book['id']}/brief/generate", json={"payload": {}}, headers=headers)

    gen = await client.post(
        f"/api/v1/book-writing/books/{book['id']}/blueprint/generate",
        json={"payload": {}},
        headers=headers,
    )
    assert gen.status_code == 201, gen.text
    bp = gen.json()
    assert len(bp["chapters"]) == 2
    assert bp["chapters"][0]["title"] == "Why Teachers Need AI"

    # Add a chapter to the blueprint via PATCH.
    bp["chapters"].append({"title": "Classroom in Practice", "objective": "Apply."})
    edited = await client.patch(
        f"/api/v1/book-writing/books/{book['id']}/blueprint",
        json={"payload": {"chapters": bp["chapters"]}},
        headers=headers,
    )
    assert edited.status_code == 200, edited.text
    assert len(edited.json()["chapters"]) == 3


# ---------------------------------------------------------------------------
# Chapters + versioning
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chapter_create_outline_generate(client: AsyncClient, fake_ai: FakeAIService) -> None:
    token = await register_and_token(client, "bw4@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    book = await create_book(client, headers)

    ch = await client.post(
        f"/api/v1/book-writing/books/{book['id']}/chapters",
        json={"title": "Why Teachers Need AI", "target_word_count": 3000},
        headers=headers,
    )
    assert ch.status_code == 201, ch.text
    chapter = ch.json()
    chapter_id = chapter["id"]

    outline = await client.post(
        f"/api/v1/book-writing/chapters/{chapter_id}/outline/generate",
        json={"payload": {}},
        headers=headers,
    )
    assert outline.status_code == 200, outline.text
    assert outline.json()["status"] == "outlining"
    assert len(outline.json()["outline_sections"]) == 2

    content = await client.post(
        f"/api/v1/book-writing/chapters/{chapter_id}/generate",
        json={"payload": {}},
        headers=headers,
    )
    assert content.status_code == 200, content.text
    assert "generated chapter content" in content.json()["content"]
    assert content.json()["actual_word_count"] > 0


@pytest.mark.asyncio
async def test_chapter_versioning_and_restore(client: AsyncClient, fake_ai: FakeAIService) -> None:
    token = await register_and_token(client, "bw5@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    book = await create_book(client, headers)
    ch = await client.post(
        f"/api/v1/book-writing/books/{book['id']}/chapters",
        json={"title": "Ch1"},
        headers=headers,
    )
    chapter_id = ch.json()["id"]

    # Generate content (this creates version 1).
    await client.post(
        f"/api/v1/book-writing/chapters/{chapter_id}/generate", json={"payload": {}}, headers=headers
    )
    versions = await client.get(
        f"/api/v1/book-writing/chapters/{chapter_id}/versions", headers=headers
    )
    assert versions.status_code == 200
    assert len(versions.json()) == 1
    v1_id = versions.json()[0]["id"]

    # Manual autosave update (version 2).
    save = await client.put(
        f"/api/v1/book-writing/books/{book['id']}/chapters/{chapter_id}/autosave",
        json={"payload": {"chapter_id": chapter_id, "content": "My edited version."}},
        headers=headers,
    )
    assert save.status_code == 200
    assert save.json()["content"] == "My edited version."

    # Restore version 1.
    restore = await client.post(
        f"/api/v1/book-writing/chapters/{chapter_id}/versions/{v1_id}/restore",
        headers=headers,
    )
    assert restore.status_code == 200
    assert "generated chapter content" in restore.json()["content"]

    versions_after = await client.get(
        f"/api/v1/book-writing/chapters/{chapter_id}/versions", headers=headers
    )
    assert len(versions_after.json()) == 3  # v1, v2 (autosave), v3 (restore)


@pytest.mark.asyncio
async def test_chapter_reorder_and_delete(client: AsyncClient, fake_ai: FakeAIService) -> None:
    token = await register_and_token(client, "bw6@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    book = await create_book(client, headers)
    c1 = await client.post(
        f"/api/v1/book-writing/books/{book['id']}/chapters", json={"title": "A"}, headers=headers
    )
    c2 = await client.post(
        f"/api/v1/book-writing/books/{book['id']}/chapters", json={"title": "B"}, headers=headers
    )
    id1, id2 = c1.json()["id"], c2.json()["id"]

    reorder = await client.post(
        f"/api/v1/book-writing/books/{book['id']}/chapters/reorder",
        json={"chapter_ids": [id2, id1]},
        headers=headers,
    )
    assert reorder.status_code == 200
    nums = {c["id"]: c["chapter_number"] for c in reorder.json()}
    assert nums[id2] == 1 and nums[id1] == 2

    deleted = await client.delete(f"/api/v1/book-writing/chapters/{id2}", headers=headers)
    assert deleted.status_code == 204
    after = await client.get(f"/api/v1/book-writing/books/{book['id']}/chapters", headers=headers)
    assert len(after.json()) == 1
    assert after.json()[0]["id"] == id1
    assert after.json()[0]["chapter_number"] == 1


# ---------------------------------------------------------------------------
# Editing actions
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rewrite_and_expand_actions(client: AsyncClient, fake_ai: FakeAIService) -> None:
    token = await register_and_token(client, "bw7@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    book = await create_book(client, headers)
    ch = await client.post(
        f"/api/v1/book-writing/books/{book['id']}/chapters",
        json={"title": "Ch"},
        headers=headers,
    )
    chapter_id = ch.json()["id"]

    rewrite = await client.post(
        f"/api/v1/book-writing/chapters/{chapter_id}/rewrite",
        json={"payload": {"instruction": "make punchier", "selected_text": "AI can help."}},
        headers=headers,
    )
    assert rewrite.status_code == 200
    assert rewrite.json()["content"] == "This is generated chapter content for testing purposes."

    expand = await client.post(
        f"/api/v1/book-writing/chapters/{chapter_id}/expand",
        json={"payload": {"selected_text": "AI can help."}},
        headers=headers,
    )
    assert expand.status_code == 200


# ---------------------------------------------------------------------------
# Autosave + settings + manuscript
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_autosave_settings_and_manuscript(client: AsyncClient, fake_ai: FakeAIService) -> None:
    token = await register_and_token(client, "bw8@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    book = await create_book(client, headers)
    ch = await client.post(
        f"/api/v1/book-writing/books/{book['id']}/chapters",
        json={"title": "Ch"},
        headers=headers,
    )
    chapter_id = ch.json()["id"]

    # Autosave.
    save = await client.put(
        f"/api/v1/book-writing/books/{book['id']}/chapters/{chapter_id}/autosave",
        json={"payload": {"chapter_id": chapter_id, "content": "Persisted draft."}},
        headers=headers,
    )
    assert save.status_code == 200
    assert save.json()["content"] == "Persisted draft."

    # Settings / style profile.
    settings = await client.patch(
        f"/api/v1/book-writing/books/{book['id']}/settings",
        json={"payload": {"tone": "Encouraging", "use_examples": "high", "reading_level": "simple"}},
        headers=headers,
    )
    assert settings.status_code == 200
    assert settings.json()["tone"] == "Encouraging"

    # Manuscript refresh.
    man = await client.post(
        f"/api/v1/book-writing/books/{book['id']}/manuscript/refresh", headers=headers
    )
    assert man.status_code == 200
    assert "Persisted draft." in man.json()["full_text"]


# ---------------------------------------------------------------------------
# AI failure safety (provider error preserves existing content)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ai_failure_does_not_destroy_content(client: AsyncClient, fake_ai: FakeAIService) -> None:
    token = await register_and_token(client, "bw9@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    book = await create_book(client, headers)
    ch = await client.post(
        f"/api/v1/book-writing/books/{book['id']}/chapters",
        json={"title": "Ch"},
        headers=headers,
    )
    chapter_id = ch.json()["id"]
    # Seed content via autosave.
    await client.put(
        f"/api/v1/book-writing/books/{book['id']}/chapters/{chapter_id}/autosave",
        json={"payload": {"chapter_id": chapter_id, "content": "Original safe content."}},
        headers=headers,
    )

    # Make the AI service raise on the next generation.
    async def _boom(*args, **kwargs):
        from providers.ai.base import ProviderUnavailableError

        raise ProviderUnavailableError("simulated outage", provider="openai")

    fake_ai.generate_structured_output = _boom  # type: ignore[method-assign]

    gen = await client.post(
        f"/api/v1/book-writing/chapters/{chapter_id}/generate", json={"payload": {}}, headers=headers
    )
    # Generation fails but the existing content must remain intact.
    assert gen.status_code in (500, 502, 503, 504)
    after = await client.get(f"/api/v1/book-writing/chapters/{chapter_id}", headers=headers)
    assert after.json()["content"] == "Original safe content."
