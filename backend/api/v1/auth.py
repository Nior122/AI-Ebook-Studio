"""Authentication and profile endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.dependencies import AppSettings, CurrentUser, DatabaseSession
from models.accounts import User
from schemas.auth import (
    AuthResponse,
    EmailVerificationRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    ProfileUpdateRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPairResponse,
    UserResponse,
)
from services.auth_service import (
    authenticate_user,
    logout,
    register_user,
    rotate_refresh_token,
)

router = APIRouter(prefix="", tags=["authentication"])


@router.post(
    "/auth/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register user",
)
async def register(
    payload: RegisterRequest,
    session: DatabaseSession,
    settings: AppSettings,
    request: Request,
) -> AuthResponse:
    """Create a user account, default workspace, and initial token pair."""
    return await register_user(session, payload, settings, request)


@router.post("/auth/login", response_model=AuthResponse, summary="Login")
async def login(
    payload: LoginRequest,
    session: DatabaseSession,
    settings: AppSettings,
    request: Request,
) -> AuthResponse:
    """Authenticate with email/password and issue tokens."""
    return await authenticate_user(session, payload.email, payload.password, settings, request)


@router.post("/auth/refresh", response_model=TokenPairResponse, summary="Refresh token")
async def refresh_token(
    payload: RefreshRequest,
    session: DatabaseSession,
    settings: AppSettings,
    request: Request,
) -> TokenPairResponse:
    """Rotate refresh token and return a new token pair."""
    return await rotate_refresh_token(session, payload.refresh_token, settings, request)


@router.post("/auth/logout", response_model=MessageResponse, summary="Logout")
async def logout_endpoint(
    payload: LogoutRequest | None = None,
    session: DatabaseSession = None,
) -> MessageResponse:
    """Revoke the supplied refresh token (if any)."""
    if payload and payload.refresh_token:
        await logout(session, payload.refresh_token)
    return MessageResponse(message="Logged out.")


async def _load_user_with_profile(session: DatabaseSession, user: CurrentUser) -> User:
    result = await session.execute(
        select(User).options(selectinload(User.profile)).where(User.id == user.id),
    )
    return result.scalar_one()


@router.get("/me", response_model=UserResponse, summary="Current user")
@router.get("/auth/me", response_model=UserResponse, include_in_schema=False)
async def me(user: Annotated[User, Depends(_load_user_with_profile)]) -> User:
    """Return the authenticated user profile."""
    return user


@router.put("/me", response_model=UserResponse, summary="Update profile")
async def update_me(
    payload: ProfileUpdateRequest,
    session: DatabaseSession,
    user: Annotated[User, Depends(_load_user_with_profile)],
) -> User:
    """Update the current user's profile."""
    if payload.display_name is not None:
        user.profile.display_name = payload.display_name
    if payload.avatar_url is not None:
        user.profile.avatar_url = payload.avatar_url
    if payload.bio is not None:
        user.profile.bio = payload.bio
    if payload.timezone is not None:
        user.profile.timezone = payload.timezone
    await session.commit()
    await session.refresh(user)
    return await _load_user_with_profile(session, user)


@router.post("/auth/forgot-password", response_model=MessageResponse, summary="Forgot password")
async def forgot_password(_payload: ForgotPasswordRequest) -> MessageResponse:
    """Prepare password reset flow without sending email in this stage."""
    return MessageResponse(
        message="If the email exists, password reset instructions will be prepared.",
    )


@router.post("/auth/reset-password", response_model=MessageResponse, summary="Reset password")
async def reset_password(_payload: ResetPasswordRequest) -> MessageResponse:
    """Prepare reset password endpoint structure for future email flow."""
    return MessageResponse(
        message="Password reset structure is available; email flow is not enabled yet.",
    )


@router.post("/auth/verify-email", response_model=MessageResponse, summary="Verify email")
async def verify_email(_payload: EmailVerificationRequest) -> MessageResponse:
    """Prepare email verification endpoint structure."""
    return MessageResponse(
        message="Email verification structure is available; email sending is not enabled yet.",
    )
