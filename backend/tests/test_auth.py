"""Authentication tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_registration_login_jwt_and_me(client: AsyncClient) -> None:
    """User can register, log in, and access protected current-user endpoint."""
    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "author@example.com",
            "password": "SecurePass123",
            "display_name": "Example Author",
        },
    )
    assert registration.status_code == 201
    registration_body = registration.json()
    assert registration_body["user"]["email"] == "author@example.com"
    assert registration_body["tokens"]["access_token"]
    assert registration_body["tokens"]["refresh_token"]

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "author@example.com", "password": "SecurePass123"},
    )
    assert login.status_code == 200
    access_token = login.json()["tokens"]["access_token"]

    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "author@example.com"


@pytest.mark.asyncio
async def test_protected_route_requires_jwt(client: AsyncClient) -> None:
    """Protected endpoints reject anonymous requests."""
    response = await client.get("/api/v1/workspaces")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient) -> None:
    """Refresh token endpoint rotates refresh tokens."""
    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rotate@example.com",
            "password": "SecurePass123",
            "display_name": "Rotate User",
        },
    )
    refresh_token = registration.json()["tokens"]["refresh_token"]

    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != refresh_token

    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reused.status_code == 401
