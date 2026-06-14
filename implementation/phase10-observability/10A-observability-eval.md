# Phase 10: Observability + Evaluation — Implementation Plan

## Task
Instrument system with tracing, metrics, logging and build evaluation framework.

## Dependencies
Phase 5 (RAG pipeline), Phase 6 (agent)

## Files Created

### Observability

#### 1. `backend/app/observability/__init__.py`
#### 2. `backend/app/observability/tracing.py`
- TracingManager class
- setup_tracing(app, settings) — OpenTelemetry + FastAPI auto-instrumentation
- create_span, add_event, set_error, get_current_trace_id

#### 3. `backend/app/observability/langfuse_client.py`
- LangfuseClient class
- init, create_trace, trace_generation, score, flush
- No-op fallback when langfuse not installed

#### 4. `backend/app/observability/metrics.py`
- MetricsCollector class
- Lightweight Counter/Histogram/Gauge
- record_request, record_llm_call, record_tool_call, record_document_processed, record_retrieval
- Prometheus text exposition

#### 5. `backend/app/observability/structured_logging.py`
- setup_structured_logging(settings)
- JSON formatter for production
- request_id, user_id, document_id, trace_id context propagation

### Evaluation

#### 6. `backend/app/eval/__init__.py`
#### 7. `backend/app/eval/metrics.py`
- RetrievalMetrics: recall@k, precision@k, mrr, ndcg@k, hit_rate
- GenerationMetrics: answer_relevance, context_relevance, groundedness, citation_accuracy
- ClassificationMetrics: accuracy, precision, recall, f1, macro_f1, confusion_matrix

#### 8. `backend/app/eval/evaluator.py`
- Evaluator.run_evaluation(dataset, pipeline_fn) -> EvalResult
- Per-sample metrics, latency percentiles, summary

#### 9. `backend/app/eval/datasets.py`
- GoldSample dataclass
- load_gold_dataset(path) — JSONL loader with validation

### API

#### 10. `backend/app/api/v1/eval.py`
- POST /eval/run — trigger evaluation
- GET /eval/results — list results
- GET /eval/results/{run_id} — specific result

#### 11. `backend/app/api/schemas/eval.py`
- EvalRunRequest, EvalResultResponse, MetricResultResponse

### Data

#### 12. `evals/gold_dataset_sample.jsonl`
- 20 Vietnamese business document Q&A pairs

## Acceptance Criteria
- [x] OpenTelemetry traces cover full request lifecycle
- [x] Langfuse traces LLM calls with token counts
- [x] Structured JSON logs with correlation IDs
- [x] Evaluation framework computes RAG metrics
- [x] Gold dataset with 20+ Vietnamese samples

## Test Requirements
- Tests for metrics computation (retrieval, generation, classification)
- Tests for evaluator pipeline
- Tests for dataset loading
