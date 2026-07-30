"""API dependencies for authentication and authorization."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings, get_settings
from core.security import decode_access_token, verify_clerk_token
from database.session import get_db_session
from models.accounts import Profile, Role, User, UserRole
from services.ai_engine import AIEngine, get_ai_engine
from services.ai_service import AIService, get_ai_service
from services.book_writing.engine import BookWritingEngine

AIServiceDep = Annotated[AIService, Depends(get_ai_service)]
BookWritingEngineDep = Annotated[
    BookWritingEngine, Depends(lambda: BookWritingEngine(get_ai_service()))
]

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Resolve the authenticated user from a Bearer token.

    Supports both Clerk session JWTs and legacy custom JWTs.
    """
    import structlog
    logger = structlog.get_logger(__name__)

    if credentials is None:
        logger.warning("auth_failed_no_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    token = credentials.credentials

    # Try Clerk JWT first, fall back to legacy custom JWT.
    clerk_user_id: str | None = None
    clerk_email: str | None = None
    use_clerk = False

    if settings.clerk_jwks_url:
        try:
            payload = await verify_clerk_token(token, settings)
            clerk_user_id = payload.get("sub")
            clerk_email = payload.get("email")
            use_clerk = True
            logger.info("clerk_token_verified", clerk_user_id=clerk_user_id, has_email=bool(clerk_email))
        except (jwt.PyJWTError, ValueError) as e:
            logger.debug("clerk_token_verification_failed", error=str(e))

    if use_clerk and clerk_user_id:
        result = await session.execute(
            select(User).where(User.clerk_id == clerk_user_id, User.deleted_at.is_(None)),
        )
        user = result.scalar_one_or_none()

        if user is None:
            logger.info("clerk_user_not_found_creating", clerk_user_id=clerk_user_id)
            try:
                user = await _create_clerk_user(session, clerk_user_id, clerk_email)
                logger.info("clerk_user_created", user_id=str(user.id))
            except Exception as e:
                logger.exception("clerk_user_creation_failed", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create user account: {e}",
                ) from e
        return user

    # Fall back to legacy custom JWT
    try:
        user_id = decode_access_token(token, settings)
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        ) from exc

    result = await session.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None), User.status == "active"),
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")
    return user


async def _create_clerk_user(
    session: AsyncSession,
    clerk_user_id: str,
    email: str | None,
) -> User:
    """Create a local user record for a Clerk-authenticated user.

    Also creates a default workspace and workspace membership so the user can
    immediately start creating projects without an explicit onboarding step.
    """
    import uuid
    from datetime import datetime, timezone

    from models.workspace import Workspace, WorkspaceMember
    from services.rbac_service import get_role_by_name

    now = datetime.now(timezone.utc)

    user = User(
        id=uuid.uuid4(),
        email=email or f"{clerk_user_id}@clerk.local",
        password_hash=None,
        clerk_id=clerk_user_id,
        status="active",
        is_email_verified=bool(email),
        email_verified_at=now if email else None,
        last_login_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    await session.flush()

    profile = Profile(
        id=uuid.uuid4(),
        user_id=user.id,
        display_name=email or clerk_user_id[:12],
        created_at=now,
        updated_at=now,
    )
    session.add(profile)

    result = await session.execute(select(Role).where(Role.name == "user"))
    role = result.scalar_one_or_none()
    if role:
        session.add(
            UserRole(
                id=uuid.uuid4(),
                user_id=user.id,
                role_id=role.id,
                created_at=now,
                updated_at=now,
            )
        )

    # Create a default workspace + owner membership so the user can create projects.
    owner_role = await get_role_by_name(session, "owner")
    import re

    slug_base = re.sub(r"[^a-z0-9]+", "-", (email or "workspace").lower()).strip("-") or "workspace"
    workspace = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user.id,
        name=f"{email or clerk_user_id[:12]}'s Workspace",
        slug=f"{slug_base}-{user.id.hex[:8]}",
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            user_id=user.id,
            role_id=owner_role.id,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )

    await session.commit()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]
AIEngineDep = Annotated[AIEngine, Depends(get_ai_engine)]
AIServiceDep = Annotated[AIService, Depends(get_ai_service)]
