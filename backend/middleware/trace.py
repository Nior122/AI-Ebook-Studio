"""Temporary request trace middleware — logs every request/response for debugging."""
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class TraceMiddleware(BaseHTTPMiddleware):
    """Log every request path, method, auth header presence, and response status."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.monotonic()
        auth = request.headers.get("authorization", "none")[:60]
        body_data = None
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body_bytes = await request.body()
                body_data = body_bytes.decode("utf-8", errors="replace")[:500]
            except Exception:
                body_data = "[unreadable]"

        response = await call_next(request)
        elapsed = (time.monotonic() - start) * 1000

        log_line = (
            f"TRACE {request.method} {request.url.path} "
            f"auth={'yes' if 'bearer' in auth.lower() else 'no'} "
            f"status={response.status_code} "
            f"ms={elapsed:.0f}"
        )
        if body_data:
            log_line += f" body={body_data}"

        try:
            with open("backend_trace.log", "a") as f:
                f.write(log_line + "\n")
        except OSError:
            pass

        return response