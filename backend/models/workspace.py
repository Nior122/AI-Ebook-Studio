"""Workspace and membership models."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-like workspace that groups projects and members."""

    __tablename__ = "workspaces"
    __table_args__ = (
        Index("ix_workspaces_owner_user_id", "owner_user_id"),
        Index("ix_workspaces_status", "status"),
    )

    owner_user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(220), nullable=False)
    slug: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    members: Mapped[list[WorkspaceMember]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    projects: Mapped[list[Project]] = relationship(back_populates="workspace")


class WorkspaceMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Membership and role assignment inside a workspace."""

    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
        Index("ix_workspace_members_workspace_id", "workspace_id"),
        Index("ix_workspace_members_user_id", "user_id"),
        Index("ix_workspace_members_role_id", "role_id"),
    )

    workspace_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("workspaces.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    role_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("roles.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    invitation_email: Mapped[str | None] = mapped_column(String(320))

    workspace: Mapped[Workspace] = relationship(back_populates="members")
    role: Mapped[Role] = relationship(back_populates="workspace_members")


from models.accounts import Role  # noqa: E402
from models.project import Project  # noqa: E402
