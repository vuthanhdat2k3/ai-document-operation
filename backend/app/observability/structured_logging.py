"""Enhanced structured logging with observability context propagation."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.config import Settings


def setup_structured_logging(settings: Settings) -> None:
    """Configure structured logging with observability context fields.

    Extends the base structlog setup with request_id, user_id, and
    document_id context propagation via contextvars.  In production,
    output is JSON; in development, colored console output.

    Args:
        settings: Application settings.
    """
    level = settings.LOG_LEVEL.upper()
    is_debug = settings.DEBUG

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        _add_observability_context,
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


def _add_observability_context(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject observability correlation fields into every log entry.

    Reads ``request_id``, ``user_id``, and ``document_id`` from
    structlog's contextvars (set by middleware or pipeline code) and
    ensures they appear in every log line for cross-pillar correlation.

    Args:
        logger: The logger instance.
        method_name: The log method name (e.g. ``info``).
        event_dict: The current event dictionary.

    Returns:
        The enriched event dictionary.
    """
    ctx = structlog.contextvars.get_contextvars()
    for field in ("request_id", "user_id", "document_id", "trace_id", "span_id"):
        value = ctx.get(field)
        if value and field not in event_dict:
            event_dict[field] = value
    return event_dict


def bind_request_context(
    request_id: str | None = None,
    user_id: str | None = None,
    document_id: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    **extra: Any,
) -> None:
    """Bind observability context fields to the current structlog context.

    Call this from middleware or pipeline code to ensure all subsequent
    log entries include the correlation identifiers.

    Args:
        request_id: Unique request identifier.
        user_id: Authenticated user identifier.
        document_id: Document being processed.
        trace_id: OpenTelemetry trace ID.
        span_id: OpenTelemetry span ID.
        **extra: Additional context fields.
    """
    if request_id:
        structlog.contextvars.bind_contextvars(request_id=request_id)
    if user_id:
        structlog.contextvars.bind_contextvars(user_id=user_id)
    if document_id:
        structlog.contextvars.bind_contextvars(document_id=document_id)
    if trace_id:
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
    if span_id:
        structlog.contextvars.bind_contextvars(span_id=span_id)
    if extra:
        structlog.contextvars.bind_contextvars(**extra)


def clear_request_context() -> None:
    """Clear all bound observability context fields.

    Call this at the end of a request lifecycle to prevent context leaks
    across requests.
    """
    structlog.contextvars.clear_contextvars()
