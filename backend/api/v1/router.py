"""Version 1 infrastructure routes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request, status

from api.v1.ai import router as ai_router
from api.v1.async_jobs import router as async_jobs_router
from api.v1.auth import router as auth_router
from api.v1.book_writing import router as book_writing_router
from api.v1.books import router as books_router
from api.v1.editing import router as editing_router
from api.v1.cover import router as cover_router
from api.v1.generation import router as generation_router
from api.v1.exports import router as exports_router
from api.v1.images import router as images_router
from api.v1.jobs import router as jobs_router
from api.v1.kdp import router as kdp_router
from api.v1.marketing import router as marketing_router
from api.v1.projects import router as projects_router
from api.v1.studio import router as studio_router
from api.v1.system import router as system_router
from api.v1.translation import router as translation_router
from api.v1.workspaces import router as workspaces_router
from schemas.system import HealthResponse, VersionResponse

router = APIRouter(tags=["system"])
router.include_router(auth_router)
router.include_router(workspaces_router)
router.include_router(projects_router)
router.include_router(studio_router)
router.include_router(system_router)
router.include_router(books_router)
router.include_router(book_writing_router)
router.include_router(editing_router)
router.include_router(generation_router)
router.include_router(jobs_router)
router.include_router(async_jobs_router)
router.include_router(ai_router)
router.include_router(images_router)
router.include_router(exports_router)
router.include_router(kdp_router)
router.include_router(cover_router)
router.include_router(marketing_router)
router.include_router(translation_router)


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health(request: Request) -> HealthResponse:
    """Return service health for load balancers and smoke tests."""
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.app_version,
        app=settings.app_name,
        environment=settings.app_env,
        timestamp=datetime.now(UTC),
    )


@router.get("/version", response_model=VersionResponse, status_code=status.HTTP_200_OK)
async def version(request: Request) -> VersionResponse:
    """Return API version metadata."""
    settings = request.app.state.settings
    return VersionResponse(
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
    )
