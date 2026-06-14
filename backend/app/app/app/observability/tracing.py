"""OpenTelemetry distributed tracing for the document operations pipeline."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

if TYPE_CHECKING:
    from fastapi import FastAPI
    from opentelemetry.sdk.trace.export import SpanExporter
    from opentelemetry.trace import Span

    from app.config import Settings

logger = logging.getLogger(__name__)

_TRACER_PROVIDER: TracerProvider | None = None


class TracingManager:
    """Manages OpenTelemetry tracing lifecycle and span operations."""

    def __init__(self, tracer_provider: TracerProvider) -> None:
        self._provider = tracer_provider
        self._tracer = trace.get_tracer("app.document_ops", tracer_provider=tracer_provider)

    @property
    def tracer(self) -> trace.Tracer:
        return self._tracer

    def create_span(
        self,
        name: str,
        attributes: dict[str, str | int | float | bool] | None = None,
    ) -> Span:
        """Create a new span with optional attributes.

        Args:
            name: Span name (use the span inventory from the observability plan).
            attributes: Key-value pairs to attach to the span.

        Returns:
            An OpenTelemetry Span context manager.
        """
        span = self._tracer.start_span(name)
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        return span

    @staticmethod
    def add_event(
        span: Span,
        name: str,
        attributes: dict[str, str | int | float | bool] | None = None,
    ) -> None:
        """Add a timed event to an existing span.

        Args:
            span: The span to annotate.
            name: Event name.
            attributes: Key-value pairs for the event.
        """
        span.add_event(name, attributes=attributes or {})

    @staticmethod
    def set_error(span: Span, exc: BaseException) -> None:
        """Record an exception on a span and mark it as errored.

        Args:
            span: The span to record the error on.
            exc: The exception that occurred.
        """
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
        span.record_exception(exc)

    @staticmethod
    def get_current_trace_id() -> str | None:
        """Return the hex trace ID of the currently active span, or None."""
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, "032x")
        return None


def _build_resource(settings: Settings) -> Resource:
    """Build an OpenTelemetry Resource identifying this service."""
    return Resource.create(
        {
            "service.name": settings.APP_NAME,
            "service.version": "1.0.0",
            "deployment.environment": "development" if settings.DEBUG else "production",
        }
    )


def _create_exporter(settings: Settings) -> SpanExporter:
    """Create the appropriate span exporter based on configuration.

    In debug mode, exports to the console. Otherwise uses OTLP HTTP export
    if an endpoint is configured, falling back to a no-op logger.
    """
    if settings.DEBUG:
        return ConsoleSpanExporter()

    otlp_endpoint = getattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            return OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
        except ImportError:
            logger.warning("OTLP exporter not installed; falling back to console exporter")
            return ConsoleSpanExporter()

    return ConsoleSpanExporter()


def setup_tracing(app: FastAPI, settings: Settings) -> TracingManager:
    """Configure OpenTelemetry tracing and instrument the FastAPI app.

    Args:
        app: The FastAPI application instance.
        settings: Application settings.

    Returns:
        A TracingManager instance attached to the configured provider.
    """
    global _TRACER_PROVIDER

    resource = _build_resource(settings)
    exporter = _create_exporter(settings)

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    _TRACER_PROVIDER = provider

    trace.set_tracer_provider(provider)

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        logger.info("FastAPI OpenTelemetry instrumentation enabled")
    except ImportError:
        logger.warning(
            "opentelemetry-instrumentation-fastapi not installed; "
            "automatic FastAPI tracing disabled"
        )

    logger.info("OpenTelemetry tracing initialized (service=%s)", settings.APP_NAME)
    return TracingManager(provider)


def get_tracing_manager() -> TracingManager | None:
    """Return the global TracingManager if tracing has been set up."""
    if _TRACER_PROVIDER is None:
        return None
    return TracingManager(_TRACER_PROVIDER)
