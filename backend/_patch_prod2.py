"""One-off patch (v2): production-readiness backend fixes — idempotent."""
import re

ROOT = "/home/user/repos/AI-Ebook-Studio/backend"


def edit(path, fn):
    p = f"{ROOT}/{path}"
    s = open(p, encoding="utf-8").read()
    fn(s, p)


# ---------------------------------------------------------------- config.py
def config(s, p):
    if "app_base_url" in s:
        print("config already patched")
        return
    old = """    clerk_publishable_key: str | None = None
    clerk_secret_key: str | None = None
    clerk_jwks_url: str | None = None"""
    new = old + """

    # --- Email / auth flows ---
    app_base_url: str = "http://localhost:3000"
    email_from: str = "AI Ebook Studio <no-reply@ai-ebook.studio>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    require_email_verification: bool = False

    # --- Security / rate limiting ---
    rate_limit_enabled: bool = True"""
    assert old in s, "config anchor"
    open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("patched config")


edit("core/config.py", config)


# ------------------------------------------------------- services/auth_service.py
AUTH_FLOWS = '''

# ---------------------------------------------------------------------------
# Auth flow tokens (password reset / email verification)
# ---------------------------------------------------------------------------
def create_auth_flow_token(user_id, kind: str, settings) -> str:
    """Sign a short-lived JWT with a purpose claim."""
    import jwt as pyjwt

    now = datetime.now(UTC)
    if kind == "reset_password":
        ttl = timedelta(minutes=settings.password_reset_token_expire_minutes)
    else:
        ttl = timedelta(hours=settings.email_verification_token_expire_hours)
    payload = {
        "sub": str(user_id),
        "purpose": kind,
        "iat": now,
        "exp": now + ttl,
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_auth_flow_token(token: str, kind: str, settings):
    """Return the user id for a valid purpose-matching token, else None."""
    import jwt as pyjwt

    try:
        payload = pyjwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception:
        return None
    if payload.get("purpose") != kind:
        return None
    try:
        return uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError):
        return None


async def start_password_reset(session: AsyncSession, email: str, settings) -> dict:
    """Issue a password-reset token + link. Never reveals whether the email exists."""
    from services.email_service import send_auth_email

    result = await session.execute(
        select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    message = "If that email exists, password reset instructions have been sent."
    dev_link = None
    if user is not None:
        token = create_auth_flow_token(user.id, "reset_password", settings)
        link = f"{settings.app_base_url.rstrip('/')}/reset-password?token={token}"
        if settings.app_env != "production":
            dev_link = link
        send_auth_email(user.email, "Reset your AI Ebook Studio password", link, settings)
    return {"message": message, "dev_link": dev_link}


async def complete_password_reset(session: AsyncSession, token: str, new_password: str, settings) -> str:
    """Validate the reset token, set the new password, revoke all sessions."""
    from core.exceptions import ValidationAppError
    from sqlalchemy import update as sa_update

    user_id = decode_auth_flow_token(token, "reset_password", settings)
    if user_id is None:
        raise ValidationAppError("This reset link is invalid or has expired. Request a new one.")
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise ValidationAppError("This reset link is invalid or has expired. Request a new one.")
    user.password_hash = hash_password(new_password)
    await session.execute(
        sa_update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()
    return "Password updated. All existing sessions have been signed out."


async def verify_email_flow(session: AsyncSession, token: str, settings) -> str:
    """Mark the user email as verified with a signed token."""
    from core.exceptions import ValidationAppError

    user_id = decode_auth_flow_token(token, "email_verify", settings)
    if user_id is None:
        raise ValidationAppError("This verification link is invalid or has expired.")
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise ValidationAppError("This verification link is invalid or has expired.")
    user.is_email_verified = True
    user.email_verified_at = datetime.now(UTC)
    await session.commit()
    return "Email verified. You are all set."
'''


def auth_service(s, p):
    if "create_auth_flow_token" in s:
        print("auth_service already patched")
        return
    old = """    tokens = await issue_token_pair(session, user, settings, request)
    await session.commit()
    return await build_auth_response(session, user.id, tokens)"""
    new = """    tokens = await issue_token_pair(session, user, settings, request)
    await session.commit()

    if getattr(settings, "require_email_verification", False):
        from services.email_service import send_auth_email

        token = create_auth_flow_token(user.id, "email_verify", settings)
        link = f"{settings.app_base_url.rstrip('/')}/verify-email?token={token}"
        send_auth_email(user.email, "Verify your email address", link, settings)

    return await build_auth_response(session, user.id, tokens)"""
    assert old in s, "auth_service register anchor"
    open(p, "w", encoding="utf-8").write(s.replace(old, new, 1) + AUTH_FLOWS)
    print("patched auth_service")


edit("services/auth_service.py", auth_service)


# ---------------------------------------------------------------- schemas/auth.py
def auth_schemas(s, p):
    if "ForgotPasswordResponse" in s:
        print("auth schemas already patched")
        return
    old = """class MessageResponse(BaseModel):
    \"\"\"Generic API message response.\"\"\"

    message: str"""
    new = old + '''


class ForgotPasswordResponse(BaseModel):
    """Forgot-password response with an optional dev-only reset link."""

    message: str
    dev_link: str | None = None'''
    assert old in s, "auth schemas anchor"
    open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("patched auth schemas")


edit("schemas/auth.py", auth_schemas)


# ---------------------------------------------------------------- api/v1/auth.py
def auth_router(s, p):
    if "start_password_reset" in s:
        print("auth router already patched")
        return
    match = re.search(r"from schemas.auth import \([\s\S]*?\)", s)
    if match:
        s = s[: match.end()] + "\n    ForgotPasswordResponse," + s[match.end() :]
    elif "from schemas.auth import " in s:
        s = s.replace(
            "from schemas.auth import ",
            "from schemas.auth import ForgotPasswordResponse, ",
            1,
        )

    old = '''@router.post("/auth/forgot-password", response_model=MessageResponse, summary="Forgot password")
async def forgot_password(_payload: ForgotPasswordRequest) -> MessageResponse:
    """Prepare password reset flow without sending email in this stage."""
    return MessageResponse(
        message="If the email exists, password reset instructions will be prepared.",
    )'''
    new = '''@router.post(
    "/auth/forgot-password", response_model=ForgotPasswordResponse, summary="Forgot password"
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: DatabaseSession,
    settings: AppSettings,
) -> ForgotPasswordResponse:
    """Issue a password-reset link (sent by email; also returned as dev_link outside production)."""
    from services.auth_service import start_password_reset

    result = await start_password_reset(session, payload.email, settings)
    return ForgotPasswordResponse(**result)'''
    assert old in s, "forgot anchor"
    s = s.replace(old, new, 1)

    old = '''@router.post("/auth/reset-password", response_model=MessageResponse, summary="Reset password")
async def reset_password(_payload: ResetPasswordRequest) -> MessageResponse:
    """Prepare reset password endpoint structure for future email flow."""
    return MessageResponse(
        message="Password reset structure is available; email flow is not enabled yet.",
    )'''
    new = '''@router.post("/auth/reset-password", response_model=MessageResponse, summary="Reset password")
async def reset_password(
    payload: ResetPasswordRequest,
    session: DatabaseSession,
    settings: AppSettings,
) -> MessageResponse:
    """Complete a password reset with the emailed token."""
    from services.auth_service import complete_password_reset

    message = await complete_password_reset(session, payload.token, payload.new_password, settings)
    return MessageResponse(message=message)'''
    assert old in s, "reset anchor"
    s = s.replace(old, new, 1)

    old = '''@router.post("/auth/verify-email", response_model=MessageResponse, summary="Verify email")
async def verify_email(_payload: EmailVerificationRequest) -> MessageResponse:
    """Prepare email verification endpoint structure."""
    return MessageResponse(
        message="Email verification structure is available; email sending is not enabled yet.",
    )'''
    new = '''@router.post("/auth/verify-email", response_model=MessageResponse, summary="Verify email")
async def verify_email(
    payload: EmailVerificationRequest,
    session: DatabaseSession,
    settings: AppSettings,
) -> MessageResponse:
    """Verify the user email with the emailed token."""
    from services.auth_service import verify_email_flow

    message = await verify_email_flow(session, payload.token, settings)
    return MessageResponse(message=message)'''
    assert old in s, "verify anchor"
    s = s.replace(old, new, 1)
    open(p, "w", encoding="utf-8").write(s)
    print("patched auth router")


edit("api/v1/auth.py", auth_router)


# ------------------------------------------------------- services/project_service.py
RESTORE_SVC = '''

async def restore_project(session: AsyncSession, user: User, project_id: UUID) -> Project:
    """Restore an archived or soft-deleted project back to active."""
    from datetime import UTC, datetime

    from core.exceptions import ResourceNotFoundError

    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.owner_user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise ResourceNotFoundError("Project not found.")
    project.status = "active"
    project.deleted_at = None
    project.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(project)
    return project
'''


def project_service(s, p):
    if "async def restore_project" in s:
        print("project_service already patched")
        return
    open(p, "w", encoding="utf-8").write(s.rstrip() + "\n" + RESTORE_SVC)
    print("patched project_service")


edit("services/project_service.py", project_service)


# ---------------------------------------------------------------- api/v1/projects.py
def projects_router(s, p):
    if "restore_project_svc" in s:
        print("projects router already patched")
        return
    match = re.search(r"from services.project_service import \([\s\S]*?\)", s)
    if match:
        s = s[: match.end()] + "\n    restore_project," + s[match.end() :]

    old = '''@router.post(
    "/{project_id}/favorite",'''
    new = '''@router.post(
    "/{project_id}/restore",
    response_model=ProjectResponse,
    summary="Restore an archived or deleted project",
)
async def restore_project(
    project_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> ProjectResponse:
    """Restore a project to active (unarchive / undelete)."""
    project = await restore_project_svc(session, user, project_id)
    return project


@router.post(
    "/{project_id}/favorite",'''
    assert old in s, "projects favorite anchor"
    s = s.replace(old, new, 1)
    s = s.replace(
        "    restore_project,\n",
        "    restore_project as restore_project_svc,\n",
        1,
    )
    open(p, "w", encoding="utf-8").write(s)
    print("patched projects router")


edit("api/v1/projects.py", projects_router)


# ---------------------------------------------------------------- api/v1/jobs.py
def jobs_router(s, p):
    if "List my jobs" in s:
        print("jobs router already patched")
        return
    s = s.replace(
        "from fastapi import APIRouter, status",
        "from fastapi import APIRouter, Query, status",
        1,
    )
    s = s.replace(
        "from core.exceptions import ResourceNotFoundError",
        "from core.exceptions import ResourceNotFoundError\n"
        "from api.dependencies import CurrentUser, DatabaseSession\n"
        "from models.operations import Job\n"
        "from sqlalchemy import select",
        1,
    )
    old = '''@router.get("", summary="List jobs (not implemented)")
async def list_jobs() -> dict[str, str]:
    """Placeholder: a future endpoint will list persisted jobs for the caller."""
    return {"message": "Endpoint not implemented yet"}'''
    new = '''@router.get("", response_model=list[JobResponse], summary="List my jobs")
async def list_jobs(
    session: DatabaseSession,
    user: CurrentUser,
    job_type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[JobResponse]:
    """List the caller jobs from the persisted job table (newest first)."""
    query = (
        select(Job)
        .where(Job.user_id == user.id)
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    if job_type:
        query = query.where(Job.job_type == job_type)
    if status:
        query = query.where(Job.status == status)
    result = await session.execute(query)
    rows = list(result.scalars())
    response: list[JobResponse] = []
    for job in rows:
        try:
            response.append(
                JobResponse(
                    id=job.id,
                    job_type=JobType(job.job_type),
                    status=JobStatus(job.status),
                    progress=job.progress or 0,
                    current_step=job.current_step,
                    result=job.result_data or job.result,
                    error_message=job.error_message,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                )
            )
        except ValueError:
            continue
    return response'''
    assert old in s, "jobs list anchor"
    open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("patched jobs router")


edit("api/v1/jobs.py", jobs_router)


# ---------------------------------------------------------------- services/jobs/runner.py
def runner(s, p):
    if "AUTO_VERSION_JOB_TYPES" in s:
        print("runner already patched")
        return
    old = '''    JobType.COVER_GENERATION: "Cover generation",
}'''
    new = '''    JobType.COVER_GENERATION: "Cover generation",
}

# Job types that should leave an automatic project restore point behind.
AUTO_VERSION_JOB_TYPES = {
    JobType.PROOFREADING,
    JobType.TRANSLATION,
    JobType.COVER_GENERATION,
    JobType.MARKETING_GENERATION,
    JobType.IMAGE_GENERATION,
    JobType.IMAGE_ANALYSIS,
    JobType.DOCX_BUILD,
    JobType.PDF_EXPORT,
    JobType.EPUB_EXPORT,
}'''
    assert old in s, "runner labels anchor"
    s = s.replace(old, new, 1)

    old = '''            if project_id is not None and handle.status == JobStatus.COMPLETED:
                await record_activity(
                    session, user_id, project_id, "job_completed", f"{label} complete",
                    {"job_id": str(handle.id), "job_type": handle.job_type.value},
                )'''
    new = '''            if project_id is not None and handle.status == JobStatus.COMPLETED:
                await record_activity(
                    session, user_id, project_id, "job_completed", f"{label} complete",
                    {"job_id": str(handle.id), "job_type": handle.job_type.value},
                )
            if (
                project_id is not None
                and handle.status == JobStatus.COMPLETED
                and handle.job_type in AUTO_VERSION_JOB_TYPES
            ):
                from models.accounts import User
                from services.studio_service import create_version

                user = await session.get(User, user_id)
                if user is not None:
                    await create_version(
                        session, user, project_id,
                        label=f"After {label}",
                        reason=f"Automatic restore point created after {label}.",
                        created_by="auto",
                        announce=True,
                    )'''
    assert old in s, "runner notify anchor"
    open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("patched runner")


edit("services/jobs/runner.py", runner)


# ---------------------------------------------------------------- app/main.py
def main_app(s, p):
    if "RateLimitMiddleware" in s:
        print("main already patched")
        return
    old = "    app.add_middleware(SecurityHeadersMiddleware)"
    new = """    from middleware.rate_limit import RateLimitMiddleware

    app.add_middleware(
        RateLimitMiddleware,
        enabled=resolved_settings.rate_limit_enabled,
    )
    app.add_middleware(SecurityHeadersMiddleware)"""
    assert old in s, "main anchor"
    open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
    print("patched main")


edit("app/main.py", main_app)


# ---------------------------------------------------------------- requirements.txt
def requirements(s, p):
    if "reportlab" not in s:
        open(p, "w", encoding="utf-8").write(s + "\nreportlab>=4.2.0\nebooklib>=0.18\n")
        print("patched requirements")


edit("requirements.txt", requirements)

print("ALL PATCHES APPLIED")
