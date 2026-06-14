"""Prometheus-compatible metrics collection for the document operations pipeline."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class _Counter:
    """Lightweight counter compatible with the Prometheus data model."""

    def __init__(self, name: str, documentation: str, labelnames: tuple[str, ...] = ()) -> None:
        self.name = name
        self.documentation = documentation
        self.labelnames = labelnames
        self._values: dict[tuple[str, ...], float] = {}

    def labels(self, *label_values: str) -> _CounterChild:
        key = tuple(label_values)
        if key not in self._values:
            self._values[key] = 0.0
        return _CounterChild(self, key)

    def inc(self, amount: float = 1.0) -> None:
        self._values[("",)] = self._values.get(("",), 0.0) + amount

    def collect(self) -> list[tuple[tuple[str, ...], float]]:
        return list(self._values.items())


class _CounterChild:
    """A label-set specific counter handle."""

    __slots__ = ("_parent", "_key")

    def __init__(self, parent: _Counter, key: tuple[str, ...]) -> None:
        self._parent = parent
        self._key = key

    def inc(self, amount: float = 1.0) -> None:
        self._parent._values[self._key] = self._parent._values.get(self._key, 0.0) + amount


class _Histogram:
    """Lightweight histogram compatible with the Prometheus data model."""

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: tuple[str, ...] = (),
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        self.name = name
        self.documentation = documentation
        self.labelnames = labelnames
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._observations: dict[tuple[str, ...], list[float]] = {}

    def labels(self, *label_values: str) -> _HistogramChild:
        key = tuple(label_values)
        if key not in self._observations:
            self._observations[key] = []
        return _HistogramChild(self, key)

    def observe(self, value: float) -> None:
        self._observations.setdefault(("",), []).append(value)

    def collect(self) -> dict[tuple[str, ...], list[float]]:
        return dict(self._observations)


class _HistogramChild:
    """A label-set specific histogram handle."""

    __slots__ = ("_parent", "_key")

    def __init__(self, parent: _Histogram, key: tuple[str, ...]) -> None:
        self._parent = parent
        self._key = key

    def observe(self, value: float) -> None:
        self._parent._observations.setdefault(self._key, []).append(value)


class _Gauge:
    """Lightweight gauge compatible with the Prometheus data model."""

    def __init__(self, name: str, documentation: str, labelnames: tuple[str, ...] = ()) -> None:
        self.name = name
        self.documentation = documentation
        self.labelnames = labelnames
        self._values: dict[tuple[str, ...], float] = {}

    def labels(self, *label_values: str) -> _GaugeChild:
        key = tuple(label_values)
        if key not in self._values:
            self._values[key] = 0.0
        return _GaugeChild(self, key)

    def set(self, value: float) -> None:
        self._values[("",)] = value

    def inc(self, amount: float = 1.0) -> None:
        self._values[("",)] = self._values.get(("",), 0.0) + amount

    def dec(self, amount: float = 1.0) -> None:
        self._values[("",)] = self._values.get(("",), 0.0) - amount

    def collect(self) -> list[tuple[tuple[str, ...], float]]:
        return list(self._values.items())


class _GaugeChild:
    """A label-set specific gauge handle."""

    __slots__ = ("_parent", "_key")

    def __init__(self, parent: _Gauge, key: tuple[str, ...]) -> None:
        self._parent = parent
        self._key = key

    def set(self, value: float) -> None:
        self._parent._values[self._key] = value

    def inc(self, amount: float = 1.0) -> None:
        self._parent._values[self._key] = self._parent._values.get(self._key, 0.0) + amount

    def dec(self, amount: float = 1.0) -> None:
        self._parent._values[self._key] = self._parent._values.get(self._key, 0.0) - amount


class MetricsCollector:
    """Central metrics registry for the document operations pipeline.

    Exposes counters, histograms, and gauges that can be scraped by Prometheus
    via the ``/metrics`` endpoint.  Also provides a helper context manager for
    timing arbitrary operations.
    """

    def __init__(self) -> None:
        # --- HTTP request metrics ---
        self.request_count = _Counter(
            "docops_http_requests_total",
            "Total number of HTTP requests.",
            labelnames=("method", "endpoint", "status_code"),
        )
        self.request_latency = _Histogram(
            "docops_http_request_duration_seconds",
            "HTTP request latency in seconds.",
            labelnames=("method", "endpoint"),
        )

        # --- LLM metrics ---
        self.llm_request_count = _Counter(
            "docops_llm_requests_total",
            "Total number of LLM generation requests.",
            labelnames=("model", "status"),
        )
        self.llm_tokens = _Counter(
            "docops_llm_tokens_total",
            "Total LLM tokens consumed.",
            labelnames=("model", "direction"),
        )
        self.llm_latency = _Histogram(
            "docops_llm_request_duration_seconds",
            "LLM request latency in seconds.",
            labelnames=("model",),
        )
        self.llm_cost = _Counter(
            "docops_llm_cost_usd_total",
            "Estimated LLM cost in USD.",
            labelnames=("model",),
        )

        # --- Tool / pipeline metrics ---
        self.tool_calls = _Counter(
            "docops_tool_calls_total",
            "Total tool invocations.",
            labelnames=("tool_name", "status"),
        )
        self.tool_latency = _Histogram(
            "docops_tool_duration_seconds",
            "Tool execution latency in seconds.",
            labelnames=("tool_name",),
        )

        # --- Document processing metrics ---
        self.documents_processed = _Counter(
            "docops_documents_processed_total",
            "Total documents processed.",
            labelnames=("document_type", "status"),
        )
        self.retrieval_queries = _Counter(
            "docops_retrieval_queries_total",
            "Total retrieval queries executed.",
            labelnames=("retrieval_type",),
        )

        # --- Active request gauge ---
        self.active_requests = _Gauge(
            "docops_active_requests",
            "Number of in-flight requests.",
        )

        self._start_time = time.monotonic()

    def record_request(self, method: str, endpoint: str, status_code: int, duration: float) -> None:
        """Record an HTTP request with its latency.

        Args:
            method: HTTP method.
            endpoint: Request path.
            status_code: HTTP response status code.
            duration: Request duration in seconds.
        """
        self.request_count.labels(method, endpoint, str(status_code)).inc()
        self.request_latency.labels(method, endpoint).observe(duration)

    def record_llm_call(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        duration: float,
        cost: float = 0.0,
        status: str = "success",
    ) -> None:
        """Record an LLM generation call.

        Args:
            model: Model identifier.
            tokens_in: Input tokens consumed.
            tokens_out: Output tokens produced.
            duration: Call latency in seconds.
            cost: Estimated USD cost.
            status: ``success`` or ``error``.
        """
        self.llm_request_count.labels(model, status).inc()
        self.llm_tokens.labels(model, "input").inc(float(tokens_in))
        self.llm_tokens.labels(model, "output").inc(float(tokens_out))
        self.llm_latency.labels(model).observe(duration)
        if cost > 0:
            self.llm_cost.labels(model).inc(cost)

    def record_tool_call(self, tool_name: str, duration: float, status: str = "success") -> None:
        """Record a tool invocation.

        Args:
            tool_name: Tool identifier.
            duration: Execution duration in seconds.
            status: ``success`` or ``error``.
        """
        self.tool_calls.labels(tool_name, status).inc()
        self.tool_latency.labels(tool_name).observe(duration)

    def record_document_processed(self, document_type: str, status: str = "success") -> None:
        """Record a processed document.

        Args:
            document_type: Classified document type.
            status: ``success`` or ``error``.
        """
        self.documents_processed.labels(document_type, status).inc()

    def record_retrieval(self, retrieval_type: str = "hybrid") -> None:
        """Record a retrieval query.

        Args:
            retrieval_type: Type of retrieval performed.
        """
        self.retrieval_queries.labels(retrieval_type).inc()

    def to_prometheus_text(self) -> str:
        """Render all metrics in Prometheus text exposition format.

        Returns:
            A string suitable for a ``/metrics`` HTTP response.
        """
        lines: list[str] = []
        uptime = time.monotonic() - self._start_time
        lines.append(f"# HELP docops_uptime_seconds Application uptime in seconds.")
        lines.append(f"# TYPE docops_uptime_seconds gauge")
        lines.append(f"docops_uptime_seconds {uptime:.6f}")

        self._render_counter(lines, self.request_count)
        self._render_histogram(lines, self.request_latency)
        self._render_counter(lines, self.llm_request_count)
        self._render_counter(lines, self.llm_tokens)
        self._render_histogram(lines, self.llm_latency)
        self._render_counter(lines, self.llm_cost)
        self._render_counter(lines, self.tool_calls)
        self._render_histogram(lines, self.tool_latency)
        self._render_counter(lines, self.documents_processed)
        self._render_counter(lines, self.retrieval_queries)
        self._render_gauge(lines, self.active_requests)

        return "\n".join(lines) + "\n"

    @staticmethod
    def _format_labels(labelnames: tuple[str, ...], label_values: tuple[str, ...]) -> str:
        if not labelnames:
            return ""
        pairs = ",".join(f'{n}="{v}"' for n, v in zip(labelnames, label_values))
        return "{" + pairs + "}"

    def _render_counter(self, lines: list[str], counter: _Counter) -> None:
        lines.append(f"# HELP {counter.name} {counter.documentation}")
        lines.append(f"# TYPE {counter.name} counter")
        for label_values, value in counter.collect():
            lbl = self._format_labels(counter.labelnames, label_values)
            lines.append(f"{counter.name}{lbl} {value}")

    def _render_gauge(self, lines: list[str], gauge: _Gauge) -> None:
        lines.append(f"# HELP {gauge.name} {gauge.documentation}")
        lines.append(f"# TYPE {gauge.name} gauge")
        for label_values, value in gauge.collect():
            lbl = self._format_labels(gauge.labelnames, label_values)
            lines.append(f"{gauge.name}{lbl} {value}")

    def _render_histogram(self, lines: list[str], histogram: _Histogram) -> None:
        lines.append(f"# HELP {histogram.name} {histogram.documentation}")
        lines.append(f"# TYPE {histogram.name} histogram")
        observations_by_labels = histogram.collect()
        for label_values, observations in observations_by_labels.items():
            lbl = self._format_labels(histogram.labelnames, label_values)
            cumulative = 0.0
            for bucket in histogram.buckets:
                count = sum(1 for o in observations if o <= bucket)
                cumulative += count
                bucket_lbl = lbl.rstrip("}") + ("," if lbl.endswith("}") else "{")
                bucket_lbl += f'le="{bucket}"}}' if lbl.endswith("}") else f'le="{bucket}"}}'
                lines.append(f"{histogram.name}_bucket{bucket_lbl} {cumulative}")
            inf_lbl = lbl.rstrip("}") + ("," if lbl.endswith("}") else "{")
            inf_lbl += 'le="+Inf"}}' if lbl.endswith("}") else 'le="+Inf"}}'
            lines.append(f"{histogram.name}_bucket{inf_lbl} {len(observations)}")
            lines.append(f"{histogram.name}_sum{lbl} {sum(observations):.6f}")
            lines.append(f"{histogram.name}_count{lbl} {len(observations)}")


_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Return the global MetricsCollector singleton."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
