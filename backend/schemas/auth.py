"""Authentication and profile schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProfileResponse(BaseModel):
    """Profile response schema."""

    id: UUID
    display_name: str
    avatar_url: str | None = None
    bio: str | None = None
    timezone: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    """Authenticated user response schema."""

    id: UUID
    email: EmailStr
    status: str
    is_email_verified: bool
    created_at: datetime
    profile: ProfileResponse

    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    """Registration request."""

    email: EmailStr = Field(examples=["author@example.com"])
    password: str = Field(min_length=8, examples=["SecurePass123"])
    display_name: str = Field(min_length=1, max_length=160, examples=["Example Author"])


class LoginRequest(BaseModel):
    """Login request."""

    email: EmailStr
    password: str


class TokenPairResponse(BaseModel):
    """Access and refresh token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime


class AuthResponse(BaseModel):
    """Authentication response with user and token pair."""

    user: UserResponse
    tokens: TokenPairResponse


class RefreshRequest(BaseModel):
    """Refresh token rotation request."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout request."""

    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Password reset request."""

    token: str
    new_password: str = Field(min_length=8)


class EmailVerificationRequest(BaseModel):
    """Email verification request."""

    token: str


class ProfileUpdateRequest(BaseModel):
    """Profile update request."""

    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    avatar_url: str | None = None
    bio: str | None = None
    timezone: str | None = None


class MessageResponse(BaseModel):
    """Generic API message response."""

    message: str


class ForgotPasswordResponse(BaseModel):
    """Forgot-password response with an optional dev-only reset link."""

    message: str
    dev_link: str | None = None
