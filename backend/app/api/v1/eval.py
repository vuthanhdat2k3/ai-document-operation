"""Evaluation API endpoints."""

from __future__ import annotations

import logging
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.schemas.eval import (
    EvalResultResponse,
    EvalResultsListResponse,
    EvalRunRequest,
    EvalRunTriggeredResponse,
    PerSampleResultResponse,
)
from app.eval.datasets import load_gold_dataset_as_dicts
from app.eval.evaluator import Evaluator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eval", tags=["evaluation"])

_eval_results: OrderedDict[str, dict[str, Any]] = OrderedDict()
_MAX_STORED_RESULTS = 20


def _get_pipeline_fn(pipeline_name: str) -> Any:
    """Return a pipeline function for the given name.

    In a production system this would dispatch to the actual pipeline
    (QAService, ExtractionService, etc.).  For now it returns a stub
    that produces a minimal result dict so the evaluator can run.

    Args:
        pipeline_name: Pipeline identifier.

    Returns:
        A callable that accepts a sample dict and returns a result dict.
    """

    def _stub_pipeline(sample: dict[str, Any]) -> dict[str, Any]:
        return {
            "answer": sample.get("expected_answer", ""),
            "retrieved_ids": sample.get("context_chunks", []),
            "supported_claims": 0,
            "total_claims": 0,
        }

    return _stub_pipeline


@router.post("/run", response_model=EvalRunTriggeredResponse)
async def run_evaluation(body: EvalRunRequest) -> EvalRunTriggeredResponse:
    """Trigger an evaluation run against a gold dataset.

    Loads the dataset from the specified path, executes the pipeline
    function for each sample, computes metrics, and stores the results.
    """
    run_id = str(uuid.uuid4())

    dataset_path = body.dataset_path or "evals/gold_dataset_sample.jsonl"

    try:
        dataset = load_gold_dataset_as_dicts(dataset_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pipeline_fn = _get_pipeline_fn(body.pipeline_name)

    evaluator = Evaluator()
    eval_result = evaluator.run_evaluation(
        dataset=dataset,
        pipeline_fn=pipeline_fn,
        dataset_name=body.pipeline_name,
    )

    result_data: dict[str, Any] = {
        **eval_result.to_dict(),
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    _eval_results[run_id] = result_data
    if len(_eval_results) > _MAX_STORED_RESULTS:
        _eval_results.popitem(last=False)

    logger.info("Evaluation run %s completed: %s", run_id, eval_result.summary)

    return EvalRunTriggeredResponse(
        run_id=run_id,
        status="completed",
        message=f"Evaluation completed. {eval_result.successful_samples}/{eval_result.total_samples} samples succeeded.",
    )


@router.get("/results", response_model=EvalResultsListResponse)
async def list_evaluation_results() -> EvalResultsListResponse:
    """List all stored evaluation results, most recent first."""
    results: list[EvalResultResponse] = []
    for data in reversed(list(_eval_results.values())):
        per_sample = [
            PerSampleResultResponse(**s) for s in data.get("per_sample_results", [])
        ]
        created = data.get("created_at")
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        results.append(
            EvalResultResponse(
                dataset_name=data.get("dataset_name", ""),
                total_samples=data.get("total_samples", 0),
                successful_samples=data.get("successful_samples", 0),
                failed_samples=data.get("failed_samples", 0),
                aggregate_metrics=data.get("aggregate_metrics", {}),
                per_sample_results=per_sample,
                total_latency_ms=data.get("total_latency_ms", 0.0),
                summary=data.get("summary", ""),
                run_id=data.get("run_id", ""),
                created_at=created,
            )
        )

    return EvalResultsListResponse(results=results, total=len(results))


@router.get("/results/{run_id}", response_model=EvalResultResponse)
async def get_evaluation_result(run_id: str) -> EvalResultResponse:
    """Retrieve a specific evaluation result by run ID."""
    data = _eval_results.get(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Evaluation result {run_id} not found.")

    per_sample = [
        PerSampleResultResponse(**s) for s in data.get("per_sample_results", [])
    ]
    created = data.get("created_at")
    if isinstance(created, str):
        created = datetime.fromisoformat(created)

    return EvalResultResponse(
        dataset_name=data.get("dataset_name", ""),
        total_samples=data.get("total_samples", 0),
        successful_samples=data.get("successful_samples", 0),
        failed_samples=data.get("failed_samples", 0),
        aggregate_metrics=data.get("aggregate_metrics", {}),
        per_sample_results=per_sample,
        total_latency_ms=data.get("total_latency_ms", 0.0),
        summary=data.get("summary", ""),
        run_id=data.get("run_id", ""),
        created_at=created,
    )
