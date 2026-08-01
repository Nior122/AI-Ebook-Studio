"""Request body size enforcement for API routes (HTTP 413).

Protects against oversized payloads on every ``/api/v1`` route. The cap is
configurable via ``MAX_REQUEST_BODY_MB`` (default 20 MB) — generous for this
app since images are stored as URLs, not uploaded bodies.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class BodyLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds the configured cap."""

    def __init__(self, app, max_bytes: int = 20 * 1024 * 1024) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/v1"):
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > self.max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "success": False,
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": (
                                f"Request body is too large "
                                f"(max {self.max_bytes // (1024 * 1024)} MB)."
                            ),
                            "details": {},
                        },
                    },
                )
        return await call_next(request)
