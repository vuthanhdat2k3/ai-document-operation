"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys

import structlog

from app.config import get_settings


def setup_logging(log_level: str | None = None, debug: bool | None = None) -> None:
    """Configure structlog and stdlib logging for the application.

    Sets up JSON rendering in production and colored console rendering
    in development. Merges structlog contextvars (request_id, user_id)
    into every log entry automatically.

    Args:
        log_level: Logging level string (e.g. "INFO", "DEBUG"). Defaults to settings.
        debug: Whether to use console renderer. Defaults to settings.DEBUG.
    """
    settings = get_settings()
    level = (log_level or settings.LOG_LEVEL).upper()
    is_debug = debug if debug is not None else settings.DEBUG

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if is_debug:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for noisy in ("uvicorn.access", "uvicorn.error", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
