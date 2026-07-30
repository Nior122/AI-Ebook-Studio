"""Authentication service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import Settings
from core.security import (
    create_access_token,
    create_opaque_token,
    hash_password,
    hash_token,
    password_policy_errors,
    verify_password,
)
from models.accounts import Profile, RefreshToken, Session, User
from models.workspace import Workspace, WorkspaceMember
from schemas.auth import AuthResponse, RegisterRequest, TokenPairResponse
from services.rbac_service import ensure_rbac_seeded, get_role_by_name


def _as_aware_utc(value: datetime) -> datetime:
    """Normalize stored datetimes for PostgreSQL and SQLite test compatibility."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


async def register_user(
    session: AsyncSession,
    payload: RegisterRequest,
    settings: Settings,
    request: Request | None = None,
) -> AuthResponse:
    """Register a new user and create a default workspace."""
    errors = password_policy_errors(payload.password)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

    existing = await session.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        )

    await ensure_rbac_seeded(session)
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    session.add(user)
    await session.flush()

    session.add(Profile(user_id=user.id, display_name=payload.display_name))

    owner_role = await get_role_by_name(session, "owner")
    workspace = Workspace(
        owner_user_id=user.id,
        name=f"{payload.display_name}'s Workspace",
        slug=f"workspace-{user.id.hex[:12]}",
        status="active",
    )
    session.add(workspace)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role_id=owner_role.id))

    tokens = await issue_token_pair(session, user, settings, request)
    await session.commit()
    return await build_auth_response(session, user.id, tokens)


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
    settings: Settings,
    request: Request | None = None,
) -> AuthResponse:
    """Authenticate a user with email and password."""
    result = await session.execute(
        select(User).options(selectinload(User.profile)).where(User.email == email.lower()),
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    if user.deleted_at is not None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active.")

    user.last_login_at = datetime.now(UTC)
    tokens = await issue_token_pair(session, user, settings, request)
    await session.commit()
    return await build_auth_response(session, user.id, tokens)


async def issue_token_pair(
    session: AsyncSession,
    user: User,
    settings: Settings,
    request: Request | None = None,
) -> TokenPairResponse:
    """Issue JWT access token and opaque refresh token."""
    access_token, access_expires_at = create_access_token(user.id, settings)
    refresh_token = create_opaque_token()
    token_family = uuid4().hex
    refresh_expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)

    auth_session = Session(
        user_id=user.id,
        token_family=token_family,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        expires_at=refresh_expires_at,
    )
    session.add(auth_session)
    await session.flush()

    session.add(
        RefreshToken(
            user_id=user.id,
            session_id=auth_session.id,
            token_hash=hash_token(refresh_token),
            token_family=token_family,
            expires_at=refresh_expires_at,
        ),
    )
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=access_expires_at,
    )


async def rotate_refresh_token(
    session: AsyncSession,
    refresh_token: str,
    settings: Settings,
    request: Request | None = None,
) -> TokenPairResponse:
    """Rotate a refresh token and issue a new token pair."""
    token_hash = hash_token(refresh_token)
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.deleted_at.is_(None),
        ),
    )
    stored = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if stored is None or stored.revoked_at is not None or _as_aware_utc(stored.expires_at) <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    user_result = await session.execute(select(User).where(User.id == stored.user_id))
    user = user_result.scalar_one()
    access_token, access_expires_at = create_access_token(user.id, settings)
    new_refresh_token = create_opaque_token()
    new_stored = RefreshToken(
        user_id=user.id,
        session_id=stored.session_id,
        token_hash=hash_token(new_refresh_token),
        token_family=stored.token_family,
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(new_stored)
    await session.flush()
    stored.revoked_at = now
    stored.replaced_by_token_id = new_stored.id

    if request is not None and stored.session_id is not None:
        auth_session = await session.get(Session, stored.session_id)
        if auth_session is not None:
            auth_session.ip_address = (
                request.client.host if request.client else auth_session.ip_address
            )
            auth_session.user_agent = request.headers.get("user-agent")

    await session.commit()
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_at=access_expires_at,
    )


async def logout(session: AsyncSession, refresh_token: str | None) -> None:
    """Revoke a refresh token if supplied."""
    if refresh_token is None:
        return
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token)),
    )
    stored = result.scalar_one_or_none()
    if stored is not None:
        stored.revoked_at = datetime.now(UTC)
        await session.commit()


async def build_auth_response(
    session: AsyncSession,
    user_id: object,
    tokens: TokenPairResponse,
) -> AuthResponse:
    """Load a user with profile and build an auth response."""
    result = await session.execute(
        select(User).options(selectinload(User.profile)).where(User.id == user_id),
    )
    user = result.scalar_one()
    return AuthResponse(user=user, tokens=tokens)
