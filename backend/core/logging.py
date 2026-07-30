"""Structured logging configuration."""

import logging
import sys

import structlog

from core.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure development-friendly structured console logging."""
    # On Windows, uvicorn/click may have already wrapped sys.stdout with
    # colorama.AnsiToWin32. When stdout is redirected (piped, service, IDE),
    # that wrapper can OSError on flush().  Unwrap it so raw print() works.
    _stdout_valid = False
    try:
        _stdout_valid = sys.stdout is not None and hasattr(sys.stdout, "write")
        if _stdout_valid:
            sys.stdout.write("")
    except (OSError, AttributeError):
        _stdout_valid = False

    if _stdout_valid and not sys.stdout.isatty():
        try:
            import colorama  # type: ignore[import-untyped]
            colorama.deinit()
        except ImportError:
            pass

    log_stream = sys.stdout if _stdout_valid else sys.stderr

    logging.basicConfig(
        format="%(message)s",
        stream=log_stream,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    use_colors = settings.app_env == "development" and _stdout_valid and sys.stdout.isatty()
    if settings.app_env == "development":
        processors.append(structlog.dev.ConsoleRenderer(colors=use_colors))
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO),
        ),
        logger_factory=structlog.PrintLoggerFactory(file=log_stream),
        cache_logger_on_first_use=True,
    )
