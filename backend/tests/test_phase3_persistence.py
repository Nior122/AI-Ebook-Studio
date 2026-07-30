"""Phase 3 persistence and book/chapter/settings API tests."""

from typing import Any

import pytest
from httpx import AsyncClient


async def register_and_token(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 201
    return str(response.json()["tokens"]["access_token"])


async def seed_book(client: AsyncClient, headers: dict[str, Any], workspace_id: str, name: str) -> str:
    project = await client.post(
        "/api/v1/projects",
        json={"workspace_id": workspace_id, "name": name, "title": name},
        headers=headers,
    )
    assert project.status_code == 201
    project_id = project.json()["id"]
    book = await client.post(
        f"/api/v1/projects/{project_id}/book",
        json={"title": name},
        headers=headers,
    )
    assert book.status_code == 201
    return str(book.json()["id"])


@pytest.mark.asyncio
async def test_book_create_and_get(client: AsyncClient) -> None:
    token = await register_and_token(client, "book-create@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    workspaces = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = workspaces.json()[0]["id"]

    project = await client.post(
        "/api/v1/projects",
        json={"workspace_id": workspace_id, "name": "My Book", "title": "My Book"},
        headers=headers,
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    created = await client.post(
        f"/api/v1/projects/{project_id}/book",
        json={
            "title": "My Book",
            "description": "A test book",
            "language": "en",
            "target_audience": "beginners",
            "writing_style": "conversational",
        },
        headers=headers,
    )
    assert created.status_code == 201
    body = created.json()
    book_id = body["id"]
    assert body["title"] == "My Book"
    assert body["description"] == "A test book"
    assert body["language"] == "en"

    fetched = await client.get(f"/api/v1/books/{book_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == book_id


@pytest.mark.asyncio
async def test_book_patch_metadata(client: AsyncClient) -> None:
    token = await register_and_token(client, "book-patch@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    workspaces = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = workspaces.json()[0]["id"]
    book_id = await seed_book(client, headers, workspace_id, "Patch Book")

    patched = await client.patch(
        f"/api/v1/books/{book_id}",
        json={"title": "Renamed", "writing_style": "formal"},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Renamed"
    assert patched.json()["writing_style"] == "formal"


@pytest.mark.asyncio
async def test_chapter_crud_and_ordering(client: AsyncClient) -> None:
    token = await register_and_token(client, "chapter-crud@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    workspaces = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = workspaces.json()[0]["id"]
    book_id = await seed_book(client, headers, workspace_id, "Chapter Book")

    c1 = await client.post(
        f"/api/v1/books/{book_id}/chapters",
        json={"title": "Intro", "content": "Hello world chapter."},
        headers=headers,
    )
    assert c1.status_code == 201
    chapter1 = c1.json()
    assert chapter1["chapter_number"] == 1
    assert chapter1["word_count"] == 3

    c2 = await client.post(
        f"/api/v1/books/{book_id}/chapters",
        json={"title": "Body", "content": "More content here for readers."},
        headers=headers,
    )
    assert c2.status_code == 201
    chapter2 = c2.json()
    assert chapter2["chapter_number"] == 2

    listed = await client.get(f"/api/v1/books/{book_id}/chapters", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    updated = await client.patch(
        f"/api/v1/chapters/{chapter1['id']}",
        json={"content": "Rewritten chapter body with several different words inside."},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["word_count"] == 8

    reorder = await client.post(
        f"/api/v1/books/{book_id}/chapters/reorder",
        json={
            "items": [
                {"chapter_id": chapter2["id"], "chapter_number": 1},
                {"chapter_id": chapter1["id"], "chapter_number": 2},
            ]
        },
        headers=headers,
    )
    assert reorder.status_code == 200
    reordered = await client.get(f"/api/v1/books/{book_id}/chapters", headers=headers)
    order = [c["id"] for c in reordered.json()]
    assert order == [chapter2["id"], chapter1["id"]]

    deleted = await client.delete(f"/api/v1/chapters/{chapter2['id']}", headers=headers)
    assert deleted.status_code == 204
    after_delete = await client.get(f"/api/v1/books/{book_id}/chapters", headers=headers)
    assert len(after_delete.json()) == 1
    assert after_delete.json()[0]["chapter_number"] == 1


@pytest.mark.asyncio
async def test_book_settings_defaults_and_update(client: AsyncClient) -> None:
    token = await register_and_token(client, "settings@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    workspaces = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = workspaces.json()[0]["id"]
    book_id = await seed_book(client, headers, workspace_id, "Settings Book")

    got = await client.get(f"/api/v1/books/{book_id}/settings", headers=headers)
    assert got.status_code == 200
    body = got.json()
    assert body["kdp_trim_size"] == "6x9"
    assert body["image_aspect_ratio"] == "16:9"

    updated = await client.patch(
        f"/api/v1/books/{book_id}/settings",
        json={"kdp_trim_size": "8x10", "body_font_size": 12.0},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["kdp_trim_size"] == "8x10"
    assert updated.json()["body_font_size"] == 12.0


@pytest.mark.asyncio
async def test_book_ownership_between_users(client: AsyncClient) -> None:
    owner_token = await register_and_token(client, "book-owner@example.com")
    outsider_token = await register_and_token(client, "book-outsider@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

    workspaces = await client.get("/api/v1/workspaces", headers=owner_headers)
    workspace_id = workspaces.json()[0]["id"]
    book_id = await seed_book(client, owner_headers, workspace_id, "Private Book")

    forbidden = await client.get(f"/api/v1/books/{book_id}", headers=outsider_headers)
    assert forbidden.status_code == 403

    forbidden_chapters = await client.get(
        f"/api/v1/books/{book_id}/chapters", headers=outsider_headers
    )
    assert forbidden_chapters.status_code == 403
