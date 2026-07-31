"""In-process sliding-window rate limiter for authentication endpoints.

Protects register / login / forgot-password / reset-password from brute-force
and credential-stuffing attempts. Per (client, path) window of 60 seconds;
configurable via ``RATE_LIMIT_ENABLED``. Uses ``X-Forwarded-For`` when present
(behind Vercel/Render proxies). State is per-process — fine for single-instance
deployments; a Redis-backed limiter can replace this later without changing
callers.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# path -> max requests per 60s window
AUTH_LIMITS: dict[str, int] = {
    "/api/v1/auth/register": 40,
    "/api/v1/auth/login": 60,
    "/api/v1/auth/forgot-password": 20,
    "/api/v1/auth/reset-password": 20,
}
WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter (best effort, in-memory)."""

    def __init__(self, app, enabled: bool = True) -> None:
        super().__init__(app)
        self.enabled = enabled
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        limit = AUTH_LIMITS.get(request.url.path)
        if limit is None:
            return await call_next(request)

        key = (self._client_key(request), request.url.path)
        now = time.monotonic()
        window = self._hits[key]
        while window and now - window[0] > WINDOW_SECONDS:
            window.popleft()

        if len(window) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many attempts. Please wait a minute and try again.",
                    "code": "RATE_LIMITED",
                },
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )
        window.append(now)
        return await call_next(request)
