"""Request correlation IDs — X-Request-Id header + context var for logs/errors.

Every response carries an ``X-Request-Id`` (client-supplied or generated), and
the id is available to exception handlers via :func:`get_request_id` so error
payloads and log lines can be correlated by support.
"""

from __future__ import annotations

import contextvars
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def get_request_id() -> str | None:
    """Return the correlation id of the current request, if any."""
    return _request_id.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign (or forward) a request id and expose it on the response."""

    async def dispatch(self, request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = _request_id.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _request_id.reset(token)
        response.headers["X-Request-Id"] = request_id
        return response
