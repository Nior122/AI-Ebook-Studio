"""Global exception handling and reusable domain exceptions.

This module gives the application a single, consistent error contract:

    {
        "success": false,
        "error": {"code": "RESOURCE_NOT_FOUND", "message": "...", "details": {}}
    }

Feature code should raise the typed :class:`AppError` subclasses below instead of
constructing raw ``HTTPException`` objects, so the HTTP status, stable error code,
and message stay in one place. Internal details and stack traces are never leaked
to clients; unexpected exceptions are logged and returned as a generic 500.
"""

from typing import cast

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.types import ExceptionHandler

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Reusable domain exceptions
# ---------------------------------------------------------------------------
class AppError(Exception):
    """Base application error carrying an HTTP status and stable error code."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"
    message: str = "The request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: object | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details
        super().__init__(self.message)


class ValidationAppError(AppError):
    """Raised when input fails business validation (distinct from request parsing)."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"
    message = "The submitted data is invalid."


class AuthenticationError(AppError):
    """Raised when a request is unauthenticated or credentials are invalid."""

    status_code = status.HTTP_401_UNAUTHORIZED
    code = "AUTHENTICATION_REQUIRED"
    message = "Authentication is required."


class AuthorizationError(AppError):
    """Raised when an authenticated user lacks permission for an action."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "PERMISSION_DENIED"
    message = "You do not have permission to perform this action."


class ResourceNotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    status_code = status.HTTP_404_NOT_FOUND
    code = "RESOURCE_NOT_FOUND"
    message = "The requested resource was not found."


class ConflictError(AppError):
    """Raised when an action conflicts with existing state."""

    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"
    message = "The request conflicts with the current state."


class NotImplementedFeatureError(AppError):
    """Raised by placeholder endpoints for features not yet built."""

    status_code = status.HTTP_501_NOT_IMPLEMENTED
    code = "NOT_IMPLEMENTED"
    message = "Endpoint not implemented yet."


class ServiceUnavailableError(AppError):
    """Raised when an upstream/AI provider is unavailable or fails."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "SERVICE_UNAVAILABLE"
    message = "The requested service is temporarily unavailable."


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------
def error_response(code: str, message: str, details: object | None = None) -> dict[str, object]:
    """Build the standard API error envelope.

    Shape: ``{"success": false, "error": {"code", "message", "details"}}``.
    """
    from middleware.request_id import get_request_id

    return {
        "success": False,
        "error": {"code": code, "message": message, "details": details or {}},
        "request_id": get_request_id(),
    }


def _safe_error_details(errors: list[dict]) -> list[dict]:
    """Sanitize pydantic error details so JSONResponse never crashes.

    Pydantic v2 embeds the offending ``input`` value in every error; for
    ORM-backed inputs that object is not JSON serializable. Convert any
    non-primitive input to a truncated repr.
    """
    safe: list[dict] = []
    for error in errors:
        item = dict(error)
        raw = item.get("input")
        if raw is not None and not isinstance(raw, (str, int, float, bool, list, dict)):
            item["input"] = repr(raw)[:500]
        safe.append(item)
    return safe


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    """Handle typed application/domain errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(code=exc.code, message=exc.message, details=exc.details),
    )


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI/Starlette HTTP exceptions with a mapped error code."""
    code = _HTTP_STATUS_TO_CODE.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            code=code,
            message=str(exc.detail),
            details={"status_code": exc.status_code},
        ),
    )


async def validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle request validation exceptions."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            details=_safe_error_details(exc.errors()),
        ),
    )


async def pydantic_validation_exception_handler(
    _request: Request,
    exc: ValidationError,
) -> JSONResponse:
    """Handle internal Pydantic validation exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            code="INTERNAL_VALIDATION_ERROR",
            message="Internal validation failed.",
            details=_safe_error_details(exc.errors()),
        ),
    )


async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle database errors without leaking SQL details to clients."""
    logger.exception(
        "database_error",
        path=str(request.url.path),
        method=request.method,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            code="DATABASE_ERROR",
            message="The database is temporarily unavailable. Please try again in a moment.",
        ),
    )


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions without leaking internals to clients."""
    import traceback
    logger.exception(
        "unexpected_exception",
        path=str(request.url.path),
        method=request.method,
        exc_info=exc,
    )
    # Write full traceback to a log file for debugging purposes.
    try:
        with open("backend_exceptions.log", "a") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"PATH: {request.method} {request.url.path}\n")
            f.write(f"ERROR: {type(exc).__name__}: {exc}\n")
            f.write(traceback.format_exc())
            f.write(f"{'='*80}\n\n")
    except OSError:
        pass
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            code="INTERNAL_ERROR",
            message="Something went wrong on our side. Please try again — your work is auto-saved.",
        ),
    )


_HTTP_STATUS_TO_CODE: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "AUTHENTICATION_REQUIRED",
    status.HTTP_403_FORBIDDEN: "PERMISSION_DENIED",
    status.HTTP_404_NOT_FOUND: "RESOURCE_NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_ERROR",
    status.HTTP_501_NOT_IMPLEMENTED: "NOT_IMPLEMENTED",
}


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""
    app.add_exception_handler(AppError, cast(ExceptionHandler, app_error_handler))
    app.add_exception_handler(HTTPException, cast(ExceptionHandler, http_exception_handler))
    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, validation_exception_handler),
    )
    app.add_exception_handler(
        ValidationError,
        cast(ExceptionHandler, pydantic_validation_exception_handler),
    )
    app.add_exception_handler(SQLAlchemyError, cast(ExceptionHandler, database_exception_handler))
    app.add_exception_handler(Exception, unexpected_exception_handler)
