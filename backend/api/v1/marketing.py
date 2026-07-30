"""Marketing API endpoints."""

from uuid import UUID

from fastapi import APIRouter, status

from api.dependencies import AIServiceDep, CurrentUser, DatabaseSession
from schemas.marketing import MarketingAssetResponse, MarketingAssetTypeInfo, MarketingListResponse
from services.marketing import MARKETING_ASSET_CONFIGS
from services.marketing.engine import get_marketing_engine

router = APIRouter(prefix="/book-writing/books", tags=["marketing"])


@router.get(
    "/{book_id}/marketing/types",
    response_model=list[MarketingAssetTypeInfo],
    summary="List available marketing asset types",
)
async def list_marketing_types() -> list[MarketingAssetTypeInfo]:
    """Return metadata for all supported marketing asset types."""
    return [
        MarketingAssetTypeInfo(
            type_id=atype.value,
            label=config["label"],
            description=config["description"],
        )
        for atype, config in MARKETING_ASSET_CONFIGS.items()
    ]


@router.post(
    "/{book_id}/marketing/{asset_type}",
    response_model=MarketingAssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a marketing asset",
)
async def generate_marketing(
    book_id: UUID,
    asset_type: str,
    session: DatabaseSession,
    user: CurrentUser,
    ai_service: AIServiceDep,
) -> MarketingAssetResponse:
    """Generate a marketing asset (Amazon desc, social post, etc.) using AI."""
    engine = get_marketing_engine(ai_service)
    asset = await engine.generate(session, user, book_id, asset_type)
    return MarketingAssetResponse.model_validate(asset)


@router.get(
    "/{book_id}/marketing",
    response_model=MarketingListResponse,
    summary="List marketing assets for a book",
)
async def list_marketing(
    book_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    ai_service: AIServiceDep,
) -> MarketingListResponse:
    """List all generated marketing assets for a book."""
    engine = get_marketing_engine(ai_service)
    assets = await engine.list_assets(session, user, book_id)
    return MarketingListResponse(items=[MarketingAssetResponse.model_validate(a) for a in assets])


@router.delete(
    "/{book_id}/marketing/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a marketing asset",
)
async def delete_marketing(
    book_id: UUID,
    asset_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
    ai_service: AIServiceDep,
) -> None:
    """Delete a generated marketing asset."""
    engine = get_marketing_engine(ai_service)
    await engine.delete_asset(session, user, asset_id)