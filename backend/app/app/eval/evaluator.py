"""Evaluation harness for running pipelines against gold datasets."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.eval.metrics import (
    ClassificationMetrics,
    GenerationMetrics,
    RetrievalMetrics,
)

logger = logging.getLogger(__name__)


@dataclass
class PerSampleResult:
    """Result for a single evaluation sample."""

    sample_id: str
    question: str
    predicted_answer: str
    expected_answer: str
    metrics: dict[str, float] = field(default_factory=dict)
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class EvalResult:
    """Aggregated evaluation results across all samples."""

    dataset_name: str
    total_samples: int
    successful_samples: int
    failed_samples: int
    aggregate_metrics: dict[str, float] = field(default_factory=dict)
    per_sample_results: list[PerSampleResult] = field(default_factory=list)
    total_latency_ms: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result to a JSON-serializable dictionary."""
        return {
            "dataset_name": self.dataset_name,
            "total_samples": self.total_samples,
            "successful_samples": self.successful_samples,
            "failed_samples": self.failed_samples,
            "aggregate_metrics": self.aggregate_metrics,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "summary": self.summary,
            "per_sample_results": [
                {
                    "sample_id": r.sample_id,
                    "question": r.question,
                    "predicted_answer": r.predicted_answer,
                    "expected_answer": r.expected_answer,
                    "metrics": r.metrics,
                    "latency_ms": round(r.latency_ms, 2),
                    "error": r.error,
                }
                for r in self.per_sample_results
            ],
        }


class Evaluator:
    """Run evaluation pipelines against gold-standard datasets.

    The evaluator iterates over a dataset, calls the provided pipeline
    function for each sample, collects per-sample metrics, and aggregates
    them into a final ``EvalResult``.
    """

    def __init__(
        self,
        retrieval_ks: tuple[int, ...] = (5, 10, 20),
    ) -> None:
        self._retrieval_ks = retrieval_ks

    def run_evaluation(
        self,
        dataset: list[dict[str, Any]],
        pipeline_fn: Any,
        dataset_name: str = "default",
    ) -> EvalResult:
        """Execute the evaluation pipeline on the full dataset.

        Args:
            dataset: List of gold samples.  Each sample is a dict with at
                least ``question`` and ``expected_answer`` keys.  Optional
                keys: ``document_id``, ``context_chunks``,
                ``relevance_scores``, ``expected_label``.
            pipeline_fn: A callable that takes a sample dict and returns a
                result dict with at least ``answer`` (and optionally
                ``retrieved_ids``, ``supported_claims``, ``total_claims``,
                ``context_chunks``, ``scores``).
            dataset_name: Name of the dataset for reporting.

        Returns:
            An ``EvalResult`` with aggregated and per-sample metrics.
        """
        per_sample_results: list[PerSampleResult] = []
        total_start = time.monotonic()

        for idx, sample in enumerate(dataset):
            sample_id = sample.get("id", f"sample_{idx}")
            question = sample.get("question", "")
            expected_answer = sample.get("expected_answer", "")

            start = time.monotonic()
            try:
                output = pipeline_fn(sample)
                latency_ms = (time.monotonic() - start) * 1000

                sample_metrics = self._compute_sample_metrics(sample, output)
                per_sample_results.append(
                    PerSampleResult(
                        sample_id=sample_id,
                        question=question,
                        predicted_answer=output.get("answer", ""),
                        expected_answer=expected_answer,
                        metrics=sample_metrics,
                        latency_ms=latency_ms,
                    )
                )
            except Exception as exc:
                latency_ms = (time.monotonic() - start) * 1000
                logger.warning("Evaluation sample %s failed: %s", sample_id, exc)
                per_sample_results.append(
                    PerSampleResult(
                        sample_id=sample_id,
                        question=question,
                        predicted_answer="",
                        expected_answer=expected_answer,
                        latency_ms=latency_ms,
                        error=str(exc),
                    )
                )

        total_latency_ms = (time.monotonic() - total_start) * 1000

        aggregate = self._aggregate_metrics(per_sample_results)
        successful = sum(1 for r in per_sample_results if r.error is None)
        failed = len(per_sample_results) - successful

        summary = self._build_summary(aggregate, len(dataset), successful, failed)

        result = EvalResult(
            dataset_name=dataset_name,
            total_samples=len(dataset),
            successful_samples=successful,
            failed_samples=failed,
            aggregate_metrics=aggregate,
            per_sample_results=per_sample_results,
            total_latency_ms=total_latency_ms,
            summary=summary,
        )

        logger.info(
            "Evaluation complete: %d/%d succeeded, avg_latency=%.1fms",
            successful,
            len(dataset),
            total_latency_ms / max(len(dataset), 1),
        )

        return result

    def _compute_sample_metrics(
        self,
        sample: dict[str, Any],
        output: dict[str, Any],
    ) -> dict[str, float]:
        """Compute metrics for a single sample."""
        metrics: dict[str, float] = {}

        retrieved_ids = output.get("retrieved_ids", [])
        relevant_ids = set(sample.get("context_chunks", []))
        relevance_scores = sample.get("relevance_scores", {})

        if retrieved_ids and relevant_ids:
            retrieval = RetrievalMetrics.compute_all(
                retrieved=retrieved_ids,
                relevant=relevant_ids,
                relevance_scores=relevance_scores or None,
                ks=self._retrieval_ks,
            )
            metrics.update(retrieval)

        supported = output.get("supported_claims", 0)
        total = output.get("total_claims", 0)
        if total > 0:
            metrics["groundedness"] = GenerationMetrics.groundedness_score(supported, total)

        predicted = sample.get("expected_label")
        actual = output.get("predicted_label")
        if predicted is not None and actual is not None:
            metrics["classification_correct"] = 1.0 if predicted == actual else 0.0

        return metrics

    @staticmethod
    def _aggregate_metrics(results: list[PerSampleResult]) -> dict[str, float]:
        """Average per-sample metrics across all successful results."""
        successful = [r for r in results if r.error is None]
        if not successful:
            return {}

        all_keys: set[str] = set()
        for r in successful:
            all_keys.update(r.metrics.keys())

        aggregated: dict[str, float] = {}
        for key in sorted(all_keys):
            values = [r.metrics[key] for r in successful if key in r.metrics]
            if values:
                aggregated[key] = sum(values) / len(values)

        latencies = [r.latency_ms for r in successful]
        aggregated["avg_latency_ms"] = sum(latencies) / len(latencies)
        aggregated["p50_latency_ms"] = sorted(latencies)[len(latencies) // 2]
        aggregated["p95_latency_ms"] = sorted(latencies)[int(len(latencies) * 0.95)]
        aggregated["p99_latency_ms"] = sorted(latencies)[int(len(latencies) * 0.99)]

        return aggregated

    @staticmethod
    def _build_summary(
        aggregate: dict[str, float],
        total: int,
        successful: int,
        failed: int,
    ) -> str:
        """Build a human-readable summary of the evaluation."""
        lines = [
            f"Evaluated {total} samples ({successful} succeeded, {failed} failed).",
            "",
            "Aggregate Metrics:",
        ]
        for key, value in sorted(aggregate.items()):
            if "latency" in key:
                lines.append(f"  {key}: {value:.1f}ms")
            else:
                lines.append(f"  {key}: {value:.4f}")
        return "\n".join(lines)
