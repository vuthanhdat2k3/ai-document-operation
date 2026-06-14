"""Langfuse client for LLM observability with graceful fallback."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

try:
    from langfuse import Langfuse

    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    Langfuse = None  # type: ignore[assignment,misc]


class _NoOpTrace:
    """No-op trace returned when Langfuse is unavailable."""

    def span(self, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()

    def generation(self, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()

    def score(self, **kwargs: Any) -> None:
        pass


class _NoOpSpan:
    """No-op span returned when Langfuse is unavailable."""

    def end(self) -> None:
        pass


class LangfuseClient:
    """Wrapper around the Langfuse Python SDK with graceful degradation.

    If the ``langfuse`` package is not installed or credentials are missing,
    every method silently no-ops so that the rest of the application is
    unaffected.
    """

    def __init__(self) -> None:
        self._client: Any | None = None
        self._enabled: bool = False

    def init(self, settings: Settings) -> None:
        """Initialize the Langfuse client from application settings.

        Args:
            settings: Application settings containing Langfuse credentials.
        """
        if not LANGFUSE_AVAILABLE:
            logger.info("langfuse package not installed; LLM tracing disabled")
            return

        public_key = getattr(settings, "LANGFUSE_PUBLIC_KEY", None)
        secret_key = getattr(settings, "LANGFUSE_SECRET_KEY", None)
        host = getattr(settings, "LANGFUSE_HOST", "https://cloud.langfuse.com")

        if not public_key or not secret_key:
            logger.info("Langfuse credentials not configured; LLM tracing disabled")
            return

        try:
            self._client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
            self._enabled = True
            logger.info("Langfuse client initialized (host=%s)", host)
        except Exception:
            logger.warning("Failed to initialize Langfuse client", exc_info=True)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def create_trace(
        self,
        name: str,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
    ) -> Any:
        """Create a new Langfuse trace.

        Args:
            name: Trace name (e.g. ``document_operation``).
            user_id: Authenticated user identifier.
            metadata: Additional key-value metadata.
            session_id: Conversation session identifier.
            trace_id: Optional explicit trace ID (UUID string).

        Returns:
            A Langfuse Trace object or a no-op stub.
        """
        if not self._enabled or self._client is None:
            return _NoOpTrace()

        try:
            return self._client.trace(
                id=trace_id or str(uuid.uuid4()),
                name=name,
                user_id=user_id,
                session_id=session_id,
                metadata=metadata or {},
            )
        except Exception:
            logger.debug("Langfuse trace creation failed", exc_info=True)
            return _NoOpTrace()

    def trace_generation(
        self,
        trace_id: str,
        name: str,
        model: str,
        input: Any,
        output: Any,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an LLM generation event on an existing trace.

        Args:
            trace_id: The trace ID this generation belongs to.
            name: Generation name (e.g. ``llm_called``).
            model: Model identifier (e.g. ``gpt-4o``).
            input: The prompt / messages sent to the LLM.
            output: The completion returned by the LLM.
            tokens_input: Number of input tokens consumed.
            tokens_output: Number of output tokens produced.
            cost: Estimated USD cost for this call.
            metadata: Additional metadata.
        """
        if not self._enabled or self._client is None:
            return

        try:
            trace_obj = self._client.trace(id=trace_id)
            trace_obj.generation(
                name=name,
                model=model,
                input=input,
                output=output,
                usage={"input": tokens_input, "output": tokens_output},
                metadata={
                    **(metadata or {}),
                    **({"cost_estimate": cost} if cost is not None else {}),
                },
            )
        except Exception:
            logger.debug("Langfuse generation tracking failed", exc_info=True)

    def score(
        self,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
        source: str = "app",
    ) -> None:
        """Attach an evaluation score to a trace.

        Args:
            trace_id: Target trace ID.
            name: Score name (e.g. ``field_accuracy``, ``user_feedback``).
            value: Numeric score value.
            comment: Optional textual comment.
            source: Score source identifier.
        """
        if not self._enabled or self._client is None:
            return

        try:
            self._client.score(
                trace_id=trace_id,
                name=name,
                value=value,
                comment=comment,
                source=source,
            )
        except Exception:
            logger.debug("Langfuse score submission failed", exc_info=True)

    def flush(self) -> None:
        """Flush pending events to Langfuse."""
        if self._enabled and self._client is not None:
            try:
                self._client.flush()
            except Exception:
                logger.debug("Langfuse flush failed", exc_info=True)


_langfuse_client: LangfuseClient | None = None


def get_langfuse_client() -> LangfuseClient:
    """Return the global LangfuseClient singleton, creating one if needed."""
    global _langfuse_client
    if _langfuse_client is None:
        _langfuse_client = LangfuseClient()
    return _langfuse_client


def init_langfuse(settings: Settings) -> LangfuseClient:
    """Initialize and return the global LangfuseClient.

    Args:
        settings: Application settings.

    Returns:
        The initialized LangfuseClient.
    """
    client = get_langfuse_client()
    client.init(settings)
    return client
