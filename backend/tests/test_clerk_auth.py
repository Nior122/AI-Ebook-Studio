"""Test Clerk auth integration — legacy JWT backward compat + Clerk user auto-creation."""

import uuid

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from core.config import Settings, get_settings
from core.security import verify_clerk_token, create_access_token
from models.accounts import Profile, User, UserRole


@pytest.mark.asyncio
async def test_legacy_jwt_still_works(client: AsyncClient) -> None:
    """Backward compatibility: old custom JWTs still authenticate."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "legacy@test.com", "password": "SecurePass123", "display_name": "Legacy"},
    )
    assert reg.status_code == 201
    token = reg.json()["tokens"]["access_token"]

    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "legacy@test.com"


@pytest.mark.asyncio
async def test_protected_route_requires_auth(client: AsyncClient) -> None:
    """No token → 401."""
    resp = await client.get("/api/v1/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_clerk_jwt_missing_kid_rejected() -> None:
    """A Clerk-formatted JWT without a 'kid' header is rejected."""
    settings = get_settings()
    settings.clerk_jwks_url = "https://example.com/.well-known/jwks.json"

    no_kid = jwt.encode({"sub": "user_test", "email": "t@t.com"}, "wrong-key", algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError, match="Missing kid"):
        await verify_clerk_token(no_kid, settings)


@pytest.mark.asyncio
async def test_user_auto_created_via_clerk(db_session) -> None:
    """Verify the Clerk user auto-creation flow."""
    from api.dependencies import _create_clerk_user

    clerk_id = f"user_test_{uuid.uuid4().hex[:8]}"
    email = f"{clerk_id}@clerk.test"

    user = await _create_clerk_user(db_session, clerk_id, email)
    assert user.clerk_id == clerk_id
    assert user.email == email
    assert user.password_hash is None

    # Profile was created
    prof = (await db_session.execute(
        select(Profile).where(Profile.user_id == user.id),
    )).scalar_one_or_none()
    assert prof is not None

    # Role is optional (no "user" role in test DB)
    ur = (await db_session.execute(
        select(UserRole).where(UserRole.user_id == user.id),
    )).scalar_one_or_none()
    # Role may be None if no "user" role exists


@pytest.mark.asyncio
async def test_clerk_user_can_use_legacy_jwt(client: AsyncClient, db_session) -> None:
    """A Clerk-created user can authenticate via legacy JWT too."""
    from api.dependencies import _create_clerk_user

    clerk_id = f"user_test_{uuid.uuid4().hex[:8]}"
    user = await _create_clerk_user(db_session, clerk_id, f"{clerk_id}@test.com")

    token, _ = create_access_token(user.id, get_settings())
    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == f"{clerk_id}@test.com"
