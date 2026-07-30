"""Identity, RBAC, token, session, and API key models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Registered account used for authentication and ownership."""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_clerk_id", "clerk_id", unique=True),
        Index("ix_users_status", "status"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    clerk_id: Mapped[str | None] = mapped_column(String(256), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped[Profile] = relationship(back_populates="user", cascade="all, delete-orphan")
    roles: Mapped[list[UserRole]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(back_populates="user")
    sessions: Mapped[list[Session]] = relationship(back_populates="user")
    api_keys: Mapped[list[APIKey]] = relationship(back_populates="user")


class Profile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User-facing account profile separate from authentication data."""

    __tablename__ = "profiles"
    __table_args__ = (Index("ix_profiles_user_id", "user_id", unique=True),)

    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str | None] = mapped_column(String(80))

    user: Mapped[User] = relationship(back_populates="profile")


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Database-driven RBAC role."""

    __tablename__ = "roles"
    __table_args__ = (Index("ix_roles_name", "name", unique=True),)

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    permissions: Mapped[list[Permission]] = relationship(
        secondary="role_permissions",
        back_populates="roles",
    )
    user_roles: Mapped[list[UserRole]] = relationship(back_populates="role")
    workspace_members: Mapped[list[WorkspaceMember]] = relationship(back_populates="role")


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Atomic permission that can be attached to roles."""

    __tablename__ = "permissions"
    __table_args__ = (Index("ix_permissions_key", "key", unique=True),)

    key: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    roles: Mapped[list[Role]] = relationship(
        secondary="role_permissions",
        back_populates="permissions",
    )


class RolePermission(TimestampMixin, Base):
    """Join table connecting roles to permissions."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_pair"),
        Index("ix_role_permissions_role_id", "role_id"),
        Index("ix_role_permissions_permission_id", "permission_id"),
    )

    role_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("permissions.id"),
        primary_key=True,
    )


class UserRole(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Global role assignment for a user."""

    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
        Index("ix_user_roles_user_id", "user_id"),
        Index("ix_user_roles_role_id", "role_id"),
    )

    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    role_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("roles.id"), nullable=False)

    user: Mapped[User] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship(back_populates="user_roles")


class Session(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Login session metadata for active and historical sessions."""

    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )

    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    token_family: Mapped[str] = mapped_column(String(120), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(80))
    user_agent: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sessions")


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hashed refresh token with rotation and revocation tracking."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_token_hash", "token_hash", unique=True),
        Index("ix_refresh_tokens_family", "token_family"),
    )

    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    session_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("sessions.id"))
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    token_family: Mapped[str] = mapped_column(String(120), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_token_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("refresh_tokens.id"),
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class APIKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hashed API keys for future integrations."""

    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_api_keys_user_id", "user_id"),
        Index("ix_api_keys_key_hash", "key_hash", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="api_keys")


from models.workspace import WorkspaceMember  # noqa: E402
