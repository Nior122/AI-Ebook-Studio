"""Cover API endpoints."""

from uuid import UUID

from fastapi import APIRouter, status

from api.dependencies import AIServiceDep, CurrentUser, DatabaseSession
from schemas.cover import CoverComponentResponse, CoverAllResponse
from services.cover.engine import get_cover_engine

router = APIRouter(prefix="/book-writing/books", tags=["cover"])


@router.post(
    "/{book_id}/cover/front",
    response_model=CoverComponentResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate front cover design",
)
async def generate_front_cover(
    book_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    ai_service: AIServiceDep,
) -> CoverComponentResponse:
    engine = get_cover_engine(ai_service)
    result = await engine.generate_front_cover(session, user, book_id)
    return CoverComponentResponse(**result)


@router.post(
    "/{book_id}/cover/back",
    response_model=CoverComponentResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate back cover design",
)
async def generate_back_cover(
    book_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    ai_service: AIServiceDep,
) -> CoverComponentResponse:
    engine = get_cover_engine(ai_service)
    result = await engine.generate_back_cover(session, user, book_id)
    return CoverComponentResponse(**result)


@router.post(
    "/{book_id}/cover/spine",
    response_model=CoverComponentResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate spine design",
)
async def generate_spine(
    book_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    ai_service: AIServiceDep,
) -> CoverComponentResponse:
    engine = get_cover_engine(ai_service)
    result = await engine.generate_spine(session, user, book_id)
    return CoverComponentResponse(**result)


@router.post(
    "/{book_id}/cover/all",
    response_model=CoverAllResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate all cover components",
)
async def generate_full_cover(
    book_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    ai_service: AIServiceDep,
) -> CoverAllResponse:
    engine = get_cover_engine(ai_service)
    result = await engine.generate_all(session, user, book_id)
    return CoverAllResponse(
        front=CoverComponentResponse(**result["front"]),
        back=CoverComponentResponse(**result["back"]),
        spine=CoverComponentResponse(**result["spine"]),
    )