"""FastAPI router for Stage 8 image intelligence."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from api.dependencies import CurrentUser, DatabaseSession
from app.modules.images.schemas.api import (
    GeneratedImageResponse,
    ImageAnalysisResponse,
    ImageAnalyzeRequest,
    ImageGenerateRequest,
    ImageGenerateResponse,
    ImagePlanRequest,
    ImagePlanResponse,
    ImageRegenerateRequest,
    ImageReplaceRequest,
    ImageUpdateRequest,
)
from app.modules.images.services.engine import get_image_engine
from schemas.auth import MessageResponse

router = APIRouter(prefix="/images", tags=["images"])
ProjectIdQuery = Annotated[UUID | None, Query()]
BookIdQuery = Annotated[UUID | None, Query()]


@router.post(
    "/analyze", response_model=ImageAnalysisResponse, summary="Analyze manuscript for images"
)
async def analyze_images(
    payload: ImageAnalyzeRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> ImageAnalysisResponse:
    """Analyze the full structured manuscript and suggest image locations."""
    engine = get_image_engine()
    return await engine.analyze_book(
        session,
        user,
        book_id=payload.book_id,
        mode=payload.mode,
        custom_count=payload.custom_count,
    )


@router.post("/plan", response_model=list[ImagePlanResponse], summary="Persist image plans")
async def plan_images(
    payload: ImagePlanRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> list[ImagePlanResponse]:
    """Persist analyzed image plans for a book."""
    engine = get_image_engine()
    plans = await engine.create_plan(
        session,
        user,
        book_id=payload.book_id,
        mode=payload.mode,
        custom_count=payload.custom_count,
        replace_existing=payload.replace_existing,
    )
    return [ImagePlanResponse.model_validate(plan) for plan in plans]


@router.post(
    "/generate", response_model=ImageGenerateResponse, summary="Generate an image from a plan"
)
async def generate_image(
    payload: ImageGenerateRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> ImageGenerateResponse:
    """Generate an image and create its first version."""
    if payload.plan_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="plan_id is required."
        )
    engine = get_image_engine()
    image, job = await engine.generate(
        session,
        user,
        plan_id=payload.plan_id,
        provider_name=payload.provider,
        model=payload.model,
        title=payload.title,
        style=payload.style,
        aspect_ratio=payload.aspect_ratio,
        quality=payload.quality,
        prompt_override=payload.prompt_override,
        negative_prompt_override=payload.negative_prompt_override,
        seed=payload.seed,
    )
    return ImageGenerateResponse(
        image=GeneratedImageResponse.model_validate(image),
        job=job,
    )


@router.post("/regenerate", response_model=ImageGenerateResponse, summary="Regenerate an image")
async def regenerate_image(
    payload: ImageRegenerateRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> ImageGenerateResponse:
    """Create a fresh image version with the same placement."""
    engine = get_image_engine()
    image, job = await engine.regenerate(
        session,
        user,
        image_id=payload.image_id,
        provider_name=payload.provider,
        model=payload.model,
        style=payload.style,
        aspect_ratio=payload.aspect_ratio,
        quality=payload.quality,
        prompt_override=payload.prompt_override,
        negative_prompt_override=payload.negative_prompt_override,
        seed=payload.seed,
    )
    return ImageGenerateResponse(
        image=GeneratedImageResponse.model_validate(image),
        job=job,
    )


@router.post(
    "/replace",
    response_model=ImageGenerateResponse,
    summary="Replace an image with an external asset",
)
async def replace_image(
    payload: ImageReplaceRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> ImageGenerateResponse:
    """Replace the current image while preserving version history."""
    engine = get_image_engine()
    image, job = await engine.replace(
        session,
        user,
        image_id=payload.image_id,
        image_url=payload.image_url,
        prompt=payload.prompt,
        negative_prompt=payload.negative_prompt,
        model=payload.model,
    )
    return ImageGenerateResponse(
        image=GeneratedImageResponse.model_validate(image),
        job=job,
    )


@router.get("", response_model=list[GeneratedImageResponse], summary="List images")
async def list_images(
    session: DatabaseSession,
    user: CurrentUser,
    project_id: ProjectIdQuery = None,
    book_id: BookIdQuery = None,
) -> list[GeneratedImageResponse]:
    """List generated images for a project or book."""
    engine = get_image_engine()
    images = await engine.list_images(session, user, project_id=project_id, book_id=book_id)
    return [GeneratedImageResponse.model_validate(image) for image in images]


@router.get("/{image_id}", response_model=GeneratedImageResponse, summary="Get one image")
async def get_image(
    image_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> GeneratedImageResponse:
    """Retrieve one generated image with placement and version history."""
    engine = get_image_engine()
    image = await engine.get_image_entity(session, user, image_id)
    return GeneratedImageResponse.model_validate(image)


@router.put(
    "/{image_id}",
    response_model=GeneratedImageResponse,
    summary="Update image metadata or restore version",
)
async def update_image(
    image_id: UUID,
    payload: ImageUpdateRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> GeneratedImageResponse:
    """Update image metadata or restore a previous version."""
    engine = get_image_engine()
    image = await engine.update_image(
        session,
        user,
        image_id=image_id,
        title=payload.title,
        alt_text=payload.alt_text,
        status_value=payload.status,
        restore_version_number=payload.restore_version_number,
    )
    return GeneratedImageResponse.model_validate(image)


@router.delete(
    "/{image_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete image",
)
async def delete_image(
    image_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> MessageResponse:
    """Soft delete an image record."""
    engine = get_image_engine()
    await engine.delete_image(session, user, image_id=image_id)
    return MessageResponse(message="Image deleted.")
