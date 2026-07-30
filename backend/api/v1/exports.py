"""Export API — DOCX, PDF, EPUB generation and download endpoints."""

import io
from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from api.dependencies import CurrentUser, DatabaseSession
from providers.storage.factory import get_storage_provider
from schemas.exports import ExportFormatInfo, ExportListResponse, ExportRequest, ExportResponse
from services.export.engine import get_export_engine

router = APIRouter(prefix="/book-writing/books", tags=["exports"])


@router.get(
    "/{book_id}/exports/formats",
    response_model=list[ExportFormatInfo],
    summary="List available export formats",
)
async def list_formats() -> list[ExportFormatInfo]:
    """Return metadata for all supported export formats."""
    engine = get_export_engine()
    return [ExportFormatInfo(**f) for f in engine.available_formats()]


@router.post(
    "/{book_id}/exports",
    response_model=ExportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Export book to a format",
)
async def export_book(
    book_id: UUID,
    payload: ExportRequest,
    session: DatabaseSession,
    user: CurrentUser,
) -> ExportResponse:
    """Generate a DOCX, PDF, or EPUB file from the book's chapters."""
    engine = get_export_engine()
    asset = await engine.export_book(
        session=session,
        user=user,
        book_id=book_id,
        fmt=payload.format,
        include_front_matter=payload.include_front_matter,
        include_toc=payload.include_toc,
        include_back_matter=payload.include_back_matter,
    )
    return ExportResponse.model_validate(asset)


@router.get(
    "/{book_id}/exports",
    response_model=ExportListResponse,
    summary="List exports for a book",
)
async def list_exports(
    book_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> ExportListResponse:
    """List all generated export files for a book."""
    engine = get_export_engine()
    exports = await engine.list_exports(session, user, book_id)
    return ExportListResponse(items=[ExportResponse.model_validate(e) for e in exports])


@router.get(
    "/{book_id}/exports/{asset_id}",
    summary="Download an export file",
)
async def download_export(
    book_id: UUID,
    asset_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> StreamingResponse:
    """Download a previously generated export file."""
    engine = get_export_engine()
    asset = await engine.get_export(session, user, asset_id)
    storage = get_storage_provider()
    file_bytes = await storage.get(asset.storage_key)

    headers = {
        "Content-Disposition": f'attachment; filename="{asset.file_name}"',
    }

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=asset.mime_type,
        headers=headers,
    )


@router.delete(
    "/{book_id}/exports/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an export file",
)
async def delete_export(
    book_id: UUID,
    asset_id: UUID,
    session: DatabaseSession,
    user: CurrentUser,
) -> None:
    """Delete a previously generated export file."""
    engine = get_export_engine()
    await engine.delete_export(session, user, asset_id)
