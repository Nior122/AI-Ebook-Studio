"""Standard API response envelopes.

Every future endpoint can return data using these consistent wrappers so the
Next.js frontend has a single, predictable response contract:

* :class:`SuccessResponse`   -> ``{"success": true, "data": {...}}``
* :class:`ListResponse`      -> ``{"success": true, "data": [...], "pagination": {...}}``
* :class:`ErrorResponse`     -> ``{"success": false, "error": {...}}``

These are intentionally generic (``Generic[T]``) so they can wrap any payload
type without duplicating schema code.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Machine-readable error body shared by all failure responses."""

    code: str = Field(description="Stable, uppercase error code, e.g. RESOURCE_NOT_FOUND.")
    message: str = Field(description="Human-readable error message safe to show to users.")
    details: object | None = Field(
        default=None,
        description="Optional structured context (never a stack trace in production).",
    )


class ErrorResponse(BaseModel):
    """Consistent failure envelope: ``{"success": false, "error": {...}}``."""

    success: bool = False
    error: ErrorDetail


class SuccessResponse(BaseModel, Generic[T]):
    """Consistent success envelope: ``{"success": true, "data": {...}}``."""

    success: bool = True
    data: T


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    page: int = Field(ge=1, description="Current 1-indexed page.")
    page_size: int = Field(ge=1, description="Number of items requested per page.")
    total: int = Field(ge=0, description="Total number of items across all pages.")

    @property
    def total_pages(self) -> int:
        """Return the total number of pages given the current page size."""
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


class ListResponse(BaseModel, Generic[T]):
    """Consistent paginated list envelope.

    ``{"success": true, "data": [...], "pagination": {...}}``
    """

    success: bool = True
    data: list[T]
    pagination: PaginationMeta


def success(data: T) -> SuccessResponse[T]:
    """Helper to build a :class:`SuccessResponse` in route handlers."""
    return SuccessResponse[T](data=data)


def paginated(
    data: list[T],
    *,
    page: int,
    page_size: int,
    total: int,
) -> ListResponse[T]:
    """Helper to build a :class:`ListResponse` with pagination metadata."""
    return ListResponse[T](
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
    )
