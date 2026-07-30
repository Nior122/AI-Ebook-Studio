"""Workspace and project management tests."""

import pytest
from httpx import AsyncClient


async def register_and_token(client: AsyncClient, email: str) -> str:
    """Register a user and return an access token."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 201
    return str(response.json()["tokens"]["access_token"])


@pytest.mark.asyncio
async def test_workspace_crud(client: AsyncClient) -> None:
    """User can create, list, update, archive, and delete workspaces."""
    token = await register_and_token(client, "workspace@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post("/api/v1/workspaces", json={"name": "Studio"}, headers=headers)
    assert created.status_code == 201
    workspace_id = created.json()["id"]

    listed = await client.get("/api/v1/workspaces", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    updated = await client.put(
        f"/api/v1/workspaces/{workspace_id}",
        json={"name": "Studio Renamed"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Studio Renamed"

    archived = await client.post(f"/api/v1/workspaces/{workspace_id}/archive", headers=headers)
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    deleted = await client.delete(f"/api/v1/workspaces/{workspace_id}", headers=headers)
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_project_crud_and_settings(client: AsyncClient) -> None:
    """User can create, update, favorite, archive, and delete projects."""
    token = await register_and_token(client, "project@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    workspaces = await client.get("/api/v1/workspaces", headers=headers)
    workspace_id = workspaces.json()[0]["id"]

    created = await client.post(
        "/api/v1/projects",
        json={"workspace_id": workspace_id, "name": "Book Project"},
        headers=headers,
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert created.json()["title"] == "Book Project"

    listed = await client.get("/api/v1/projects", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == project_id

    updated = await client.put(
        f"/api/v1/projects/{project_id}",
        json={"title": "Updated Book Title"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated Book Title"

    settings = await client.get(f"/api/v1/projects/{project_id}/settings", headers=headers)
    assert settings.status_code == 200
    assert settings.json()["book_size"] == "6x9"

    updated_settings = await client.put(
        f"/api/v1/projects/{project_id}/settings",
        json={"book_size": "8x10", "image_ratio": "square"},
        headers=headers,
    )
    assert updated_settings.status_code == 200
    assert updated_settings.json()["book_size"] == "8x10"

    favorite = await client.post(f"/api/v1/projects/{project_id}/favorite", headers=headers)
    assert favorite.status_code == 200
    assert favorite.json()["is_favorite"] is True

    archived = await client.post(f"/api/v1/projects/{project_id}/archive", headers=headers)
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    deleted = await client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_project_authorization_between_users(client: AsyncClient) -> None:
    """Users cannot access projects in another user's workspace."""
    owner_token = await register_and_token(client, "owner@example.com")
    outsider_token = await register_and_token(client, "outsider@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

    workspaces = await client.get("/api/v1/workspaces", headers=owner_headers)
    workspace_id = workspaces.json()[0]["id"]
    project = await client.post(
        "/api/v1/projects",
        json={"workspace_id": workspace_id, "name": "Private", "title": "Private"},
        headers=owner_headers,
    )
    project_id = project.json()["id"]

    forbidden = await client.get(f"/api/v1/projects/{project_id}", headers=outsider_headers)
    assert forbidden.status_code == 403
