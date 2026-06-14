# Observability Plan — AI Document Operations Agent

## 1. Observability Overview

The AI Document Operations Agent requires full-stack observability across three pillars:

| Pillar | Purpose | Tool |
|--------|---------|------|
| **Traces** | Follow a single request end-to-end through parsing, retrieval, LLM calls, and tool execution | OpenTelemetry + Langfuse |
| **Logs** | Capture structured events at every decision point for debugging and audit | Structured JSON logging (Python `structlog`) |
| **Metrics** | Aggregate counters and histograms for latency, cost, throughput, and error rates | Prometheus |

All three pillars are correlated via `request_id` and `trace_id`, enabling a engineer to jump from a metric spike to the exact log line or trace span that caused it.

---

## 2. Trace Design

Every inbound request produces a single root trace. Child spans represent discrete processing stages.

### 2.1 Span Inventory

| # | Span Name | Description |
|---|-----------|-------------|
| 1 | `request_received` | HTTP/gRPC entry point; captures headers, user context |
| 2 | `file_uploaded` | File bytes received and staged to object storage |
| 3 | `document_parsed` | PDF/DOCX/image parsed into raw text or structured blocks |
| 4 | `document_classified` | Document type classified (invoice, contract, report, etc.) |
| 5 | `fields_extracted` | Key-value fields extracted from the document |
| 6 | `validation_completed` | Extracted fields validated against schema/business rules |
| 7 | `embedding_created` | Document chunks embedded into vector store |
| 8 | `retrieval_started` | Vector similarity search initiated |
| 9 | `reranking_completed` | Cross-encoder reranker applied to retrieval results |
| 10 | `context_pack_compiled` | Final context window assembled for the LLM |
| 11 | `llm_called` | LLM generation request sent and response received |
| 12 | `tool_called` | Agent invoked an external tool (API, database, file system) |
| 13 | `tool_validated` | Tool input/output validated against schema |
| 14 | `tool_executed` | Tool execution completed |
| 15 | `answer_generated` | Final answer synthesized from LLM output + tool results |
| 16 | `response_returned` | Response sent back to client |

### 2.2 Span Hierarchy Example

```
request_received (root)
├── file_uploaded
├── document_parsed
│   ├── [ocr_span] (conditional)
│   └── [table_extraction_span] (conditional)
├── document_classified
├── fields_extracted
├── validation_completed
├── embedding_created
├── retrieval_started
├── reranking_completed
├── context_pack_compiled
├── llm_called (generation)
│   ├── tool_called
│   │   ├── tool_validated
│   │   └── tool_executed
│   └── llm_called (follow-up, if tool use)
├── answer_generated
└── response_returned
```

---

## 3. Trace Attributes (Required on Every Span)

Every span MUST carry the following attributes. Attributes are set at span creation and propagated to child spans via context.

| Attribute | Type | Description |
|-----------|------|-------------|
| `request_id` | UUID | Unique identifier for the inbound request |
| `user_id` | string | Authenticated user or service account |
| `document_id` | string | Document identifier (set after upload) |
| `session_id` | string | Agent conversation session identifier |
| `task_type` | enum | `parse`, `extract`, `classify`, `embed`, `retrieve`, `generate`, `validate`, `tool_use` |
| `latency_ms` | float | Duration of this span in milliseconds |
| `token_input` | int | Input tokens consumed (on `llm_called` spans) |
| `token_output` | int | Output tokens produced (on `llm_called` spans) |
| `model_name` | string | LLM model identifier (e.g., `gpt-4o`, `claude-sonnet-4-20250514`) |
| `tool_name` | string | Tool identifier (on `tool_*` spans) |
| `tool_status` | enum | `success`, `failure`, `timeout`, `skipped` |
| `retrieval_top_k` | int | Number of results requested from vector store |
| `rerank_scores` | list[float] | Relevance scores from reranker |
| `validation_errors` | list[string] | Schema/rule violations found during validation |
| `cost_estimate` | float | Estimated USD cost for this span (primarily LLM) |

### 3.1 Cost Calculation

```
cost_estimate = (token_input / 1_000_000) * input_price_per_million
              + (token_output / 1_000_000) * output_price_per_million
```

Prices are maintained in a YAML config:

```yaml
models:
  gpt-4o:
    input_price_per_million: 2.50
    output_price_per_million: 10.00
  claude-sonnet-4-20250514:
    input_price_per_million: 3.00
    output_price_per_million: 15.00
  text-embedding-3-small:
    input_price_per_million: 0.02
    output_price_per_million: 0.00
```

---

## 4. Tooling Stack

| Component | Tool | Role |
|-----------|------|------|
| LLM Observability | **Langfuse** | Trace LLM generations, token usage, cost, user feedback, evaluation scores |
| Distributed Tracing | **OpenTelemetry SDK** | Instrument all services, propagate context, export traces |
| Structured Logging | **structlog** (Python) | JSON log output with correlation IDs |
| Metrics | **Prometheus** | Scrape `/metrics` endpoint; store time-series data |
| Dashboard | **Grafana** | Visualize metrics, logs, and traces |
| Alerting | **Prometheus Alertmanager** | Fire alerts on threshold breaches |

---

## 5. Langfuse Integration

### 5.1 Initialization

```python
from langfuse import Langfuse

langfuse = Langfuse(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)
```

### 5.2 Trace Creation

```python
trace = langfuse.trace(
    id=request_id,
    name="document_operation",
    user_id=user_id,
    session_id=session_id,
    metadata={"document_id": document_id, "task_type": task_type},
)
```

### 5.3 Span Tracking

```python
span = trace.span(
    name="document_parsed",
    input={"raw_text_length": len(raw_text)},
    output={"page_count": page_count, "parse_method": method},
    metadata={"latency_ms": latency_ms},
)
span.end()
```

### 5.4 Generation Tracking (LLM Calls)

```python
generation = trace.generation(
    name="llm_called",
    model=model_name,
    input=messages,
    output=completion,
    usage={"input": token_input, "output": token_output},
    metadata={"cost_estimate": cost_usd},
)
```

### 5.5 Cost Tracking

Langfuse automatically calculates cost when model pricing is configured in the UI. For custom models, pass `cost_estimate` in metadata and set up a Langfuse model price entry.

### 5.6 User Feedback Tracking

```python
trace.score(
    name="user_feedback",
    value=1,  # 1 = positive, 0 = negative
    comment="Extracted fields were accurate",
)
```

### 5.7 Evaluation Scoring

```python
trace.score(
    name="field_accuracy",
    value=0.95,  # 0.0 to 1.0
    comment="Auto-evaluated against ground truth",
    source="eval-pipeline",
)
```

---

## 6. OpenTelemetry Integration

### 6.1 Initialization

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

resource = Resource.create({
    "service.name": "doc-ops-agent",
    "service.version": "1.0.0",
    "deployment.environment": os.environ.get("ENV", "development"),
})

provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)
```

### 6.2 Trace Propagation

Context is propagated via W3C Trace Context headers:

```python
from opentelemetry.propagate import inject, extract

# Outbound HTTP requests
headers = {}
inject(headers)
requests.get(url, headers=headers)

# Inbound requests
context = extract(request.headers)
```

### 6.3 Span Attributes

```python
with tracer.start_as_current_span("document_parsed") as span:
    span.set_attribute("request_id", request_id)
    span.set_attribute("document_id", document_id)
    span.set_attribute("task_type", "parse")
    span.set_attribute("latency_ms", latency)
    span.set_attribute("token_input", 0)
    span.set_attribute("token_output", 0)
```

### 6.4 Baggage

Use OpenTelemetry Baggage to propagate user context across service boundaries:

```python
from opentelemetry import baggage, context

ctx = baggage.set_baggage("user_id", user_id)
ctx = baggage.set_baggage("session_id", session_id, context=ctx)
context.attach(ctx)
```

### 6.5 Exporters

| Exporter | Protocol | Use Case |
|----------|----------|----------|
| OTLP | gRPC | Production — export to collector or directly to Langfuse |
| Jaeger | Thrift/HTTP | Development — local Jaeger UI for trace visualization |
| Console | stdout | Debugging — print spans to terminal |

Configure via environment variables:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector:4317
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
```

---

## 7. Structured Logging

### 7.1 Log Format (JSON)

Every log entry is a single-line JSON object:

```json
{
  "timestamp": "2026-06-11T08:02:50.123Z",
  "level": "INFO",
  "logger": "doc_ops_agent.parser",
  "message": "Document parsed successfully",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "trace_id": "abc123def456",
  "span_id": "789ghi012",
  "user_id": "user_42",
  "document_id": "doc_987",
  "session_id": "sess_654",
  "task_type": "parse",
  "latency_ms": 234.5,
  "extra": {}
}
```

### 7.2 Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Detailed internal state: chunk boundaries, embedding dimensions, raw API payloads |
| `INFO` | Normal operations: request received, document parsed, answer generated |
| `WARNING` | Recoverable issues: retry on transient error, fallback to default model, cache miss |
| `ERROR` | Failures: tool execution failed, validation error, LLM rate limit hit |
| `CRITICAL` | System-level: database unreachable, vector store down, out of memory |

### 7.3 Required Fields Per Log Entry

Every log entry MUST include:

- `timestamp` — ISO 8601 with timezone
- `level` — one of the five levels above
- `logger` — dotted module path
- `message` — human-readable summary
- `request_id` — UUID (empty string if outside request context)
- `trace_id` — W3C trace ID (empty string if outside trace context)

### 7.4 Sensitive Data Masking

The following fields are automatically redacted before logging:

| Field | Masking Rule |
|-------|-------------|
| API keys | Replace with `***REDACTED***` |
| User PII (name, email, phone) | Partial mask: `j***@***.com` |
| Document content | Log byte length only, not content |
| Tokens/secrets | Full redaction |

Implementation via a `structlog` processor:

```python
import re

SENSITIVE_PATTERNS = [
    (re.compile(r'(api[_-]?key["\s:=]+)\S+', re.IGNORECASE), r'\1***REDACTED***'),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'), lambda m: m.group()[0] + "***@***.***"),
]

def mask_sensitive_data(logger, method_name, event_dict):
    msg = event_dict.get("message", "")
    for pattern, replacement in SENSITIVE_PATTERNS:
        msg = pattern.sub(replacement, msg)
    event_dict["message"] = msg
    return event_dict
```

### 7.5 Log Correlation

Logs are correlated to traces via `request_id` and `trace_id`. These values are injected into the log context at request entry and propagated through all downstream calls.

```python
import structlog

structlog.contextvars.bind_contextvars(
    request_id=request_id,
    trace_id=trace.get_current_span().get_span_context().trace_id,
    user_id=user_id,
)
```

---

## 8. Metrics

All metrics are exposed on `/metrics` in Prometheus format.

### 8.1 Request Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_requests_total` | Counter | `endpoint`, `method`, `status` | Total HTTP requests |
| `http_request_duration_seconds` | Histogram | `endpoint`, `method` | Request latency distribution |
| `active_sessions` | Gauge | — | Number of active agent sessions |

### 8.2 LLM Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `llm_tokens_input_total` | Counter | `model` | Total input tokens consumed |
| `llm_tokens_output_total` | Counter | `model` | Total output tokens produced |
| `llm_cost_usd_total` | Counter | `model`, `endpoint` | Cumulative LLM cost in USD |
| `llm_request_duration_seconds` | Histogram | `model` | LLM call latency |
| `llm_errors_total` | Counter | `model`, `error_type` | LLM call failures |

### 8.3 Tool Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `tool_executions_total` | Counter | `tool_name`, `status` | Total tool invocations |
| `tool_execution_duration_seconds` | Histogram | `tool_name` | Tool execution latency |
| `tool_failures_total` | Counter | `tool_name`, `error_type` | Tool failures by type |

### 8.4 Retrieval Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `retrieval_top_k` | Histogram | — | Distribution of top_k values |
| `retrieval_latency_seconds` | Histogram | — | Vector search latency |
| `rerank_latency_seconds` | Histogram | — | Reranker latency |
| `cache_hit_total` | Counter | `cache_name` | Cache hits |
| `cache_miss_total` | Counter | `cache_name` | Cache misses |

### 8.5 Agent Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `agent_loop_total` | Counter | `session_id` | Number of agent loops per session |
| `error_rate` | Gauge | `error_type` | Rolling error rate (5m window) |
| `queue_depth` | Gauge | `queue_name` | Background task queue depth |

### 8.6 Prometheus Configuration

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "doc-ops-agent"
    static_configs:
      - targets: ["app:8000"]
    metrics_path: /metrics
```

---

## 9. Alerting Rules

### 9.1 Prometheus Alert Rules

```yaml
groups:
  - name: doc_ops_agent
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Error rate exceeds 5%"
          description: "Current error rate: {{ $value | humanizePercentage }}"

      - alert: HighP95Latency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P95 latency exceeds 10 seconds"
          description: "Current P95: {{ $value | humanizeDuration }}"

      - alert: HighCostPerRequest
        expr: rate(llm_cost_usd_total[1h]) / rate(http_requests_total[1h]) > 0.10
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Average cost per request exceeds $0.10"
          description: "Current avg cost: ${{ $value }}"

      - alert: HighToolFailureRate
        expr: rate(tool_failures_total[5m]) / rate(tool_executions_total[5m]) > 0.10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Tool failure rate exceeds 10%"

      - alert: AgentLoopRate
        expr: rate(agent_loop_total[5m]) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Agent loop rate exceeds 5 per second"
          description: "Possible infinite agent loop detected"

      - alert: DatabasePoolExhausted
        expr: db_connection_pool_active >= db_connection_pool_max
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool exhausted"
```

### 9.2 Alert Routing

| Severity | Channel | Response Time |
|----------|---------|---------------|
| `critical` | PagerDuty + Slack #incidents | < 15 min |
| `warning` | Slack #alerts | < 1 hour |
| `info` | Email digest | Next business day |

---

## 10. Dashboard Design

### 10.1 Real-Time Request Flow

Panel: Sankey diagram showing request flow through stages:
- Requests received → Parsed → Classified → Embedded → Retrieved → LLM → Response
- Color-coded by status (success = green, error = red)
- Clickable nodes drill into relevant traces

### 10.2 Error Tracking

| Panel | Visualization | Query |
|-------|---------------|-------|
| Error rate over time | Time series | `rate(http_requests_total{status=~"5.."}[5m])` |
| Errors by endpoint | Bar chart | `sum by (endpoint) (rate(http_requests_total{status=~"5.."}[5m]))` |
| Top error messages | Table | Log query: `level:ERROR` grouped by `message` |
| Tool failure breakdown | Pie chart | `sum by (tool_name) (rate(tool_failures_total[5m]))` |

### 10.3 Cost Breakdown

| Panel | Visualization | Query |
|-------|---------------|-------|
| Total cost over time | Time series | `rate(llm_cost_usd_total[1h])` |
| Cost by model | Stacked area | `sum by (model) (rate(llm_cost_usd_total[1h]))` |
| Cost per request | Gauge | `rate(llm_cost_usd_total[1h]) / rate(http_requests_total[1h])` |
| Daily cost projection | Stat | Extrapolate from last 1h to 24h |

### 10.4 Performance Trends

| Panel | Visualization | Query |
|-------|---------------|-------|
| Request latency percentiles | Time series (p50, p95, p99) | `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` |
| LLM latency by model | Time series | `histogram_quantile(0.95, rate(llm_request_duration_seconds_bucket[5m]))` |
| Retrieval latency | Time series | `histogram_quantile(0.95, rate(retrieval_latency_seconds_bucket[5m]))` |
| Cache hit rate | Gauge | `rate(cache_hit_total[5m]) / (rate(cache_hit_total[5m]) + rate(cache_miss_total[5m]))` |

### 10.5 Agent Session Timeline

For a given `session_id`, display a timeline view:

```
[00:00] request_received ── 12ms
[00:00] file_uploaded ── 45ms
[00:01] document_parsed ── 230ms
[00:01] document_classified ── 89ms
[00:01] fields_extracted ── 156ms
[00:02] validation_completed ── 34ms
[00:02] embedding_created ── 412ms
[00:03] retrieval_started ── 67ms
[00:03] reranking_completed ── 203ms
[00:03] context_pack_compiled ── 12ms
[00:03] llm_called ── 2,345ms (gpt-4o, 1,234 in / 567 out, $0.018)
[00:06] tool_called: search_db ── 89ms
[00:06] tool_validated ── 3ms
[00:06] tool_executed ── 45ms
[00:06] llm_called ── 1,890ms (gpt-4o, 2,100 in / 890 out, $0.031)
[00:08] answer_generated ── 8ms
[00:08] response_returned ── 2ms
Total: 5,549ms | Cost: $0.049
```

---

## 11. Debug Workflow

### 11.1 How to Trace a Failed Request

1. Find the error in Grafana → Error Tracking panel → click the error log entry.
2. Copy the `request_id` from the log entry.
3. Open Langfuse → Search traces by `request_id`.
4. Inspect the trace timeline to find which span errored.
5. Click the failing span to see `input`, `output`, `error_message`, and `stack_trace`.
6. Cross-reference with logs: search for `request_id:<value>` in the log viewer.

### 11.2 How to Find Slow Requests

1. Grafana → Performance Trends → identify time window where p95 latency spiked.
2. Query traces in Langfuse with `latency_ms > 5000` filter.
3. Sort by latency descending.
4. Open the slowest trace and inspect the span waterfall.
5. Identify the bottleneck span (usually `llm_called` or `retrieval_started`).
6. Check if the slowness is model-related (high token count) or system-related (queue delay).

### 11.3 How to Investigate High Costs

1. Grafana → Cost Breakdown → identify which model or endpoint is driving cost.
2. Query Langfuse: filter traces by date range, sort by `cost_estimate` descending.
3. Inspect top-cost traces for:
   - Unusually high token counts (prompt engineering issue)
   - Excessive agent loops (multiple LLM calls per request)
   - Redundant tool calls
4. Check if caching is effective: Grafana → Cache Hit Rate panel.
5. Action: adjust prompt, reduce context window, add caching, or switch to cheaper model.

### 11.4 How to Debug Agent Loops

1. Grafana → Agent Metrics → `agent_loop_total` shows sessions with high loop counts.
2. Identify the `session_id` with excessive loops.
3. Open Langfuse → filter by `session_id`.
4. Review the session timeline to see repeating patterns:
   - LLM → Tool → LLM → Tool → ... (tool not returning expected results)
   - LLM → LLM → LLM → ... (LLM not deciding to use tools or answer)
5. Check `tool_validated` spans for validation errors causing retries.
6. Check LLM `output` for signs of confusion or hallucination.
7. Action: improve tool descriptions, add max-loop guards, or adjust system prompt.

---

## 12. Implementation Checklist

- [ ] **Phase 1: Foundation**
  - [ ] Install OpenTelemetry SDK and configure `TracerProvider`
  - [ ] Install `structlog` and configure JSON processor chain
  - [ ] Add `request_id` middleware to generate UUID per request
  - [ ] Add `trace_id` and `span_id` to all log entries
  - [ ] Set up sensitive data masking processor
  - [ ] Expose `/metrics` endpoint with Prometheus client

- [ ] **Phase 2: Tracing**
  - [ ] Create `request_received` and `response_returned` root spans
  - [ ] Instrument each processing stage with its named span
  - [ ] Set all required span attributes (Section 3)
  - [ ] Configure OTLP exporter to collector
  - [ ] Set up Jaeger for local development
  - [ ] Verify trace propagation across async boundaries

- [ ] **Phase 3: Langfuse**
  - [ ] Initialize Langfuse SDK with environment credentials
  - [ ] Create traces aligned with `request_id`
  - [ ] Track all LLM calls as Langfuse generations with token usage
  - [ ] Track tool calls as Langfuse spans
  - [ ] Configure model pricing in Langfuse UI
  - [ ] Add user feedback endpoint to submit scores
  - [ ] Set up evaluation pipeline for automated scoring

- [ ] **Phase 4: Metrics**
  - [ ] Implement all request metrics (Section 8.1)
  - [ ] Implement all LLM metrics (Section 8.2)
  - [ ] Implement all tool metrics (Section 8.3)
  - [ ] Implement all retrieval metrics (Section 8.4)
  - [ ] Implement all agent metrics (Section 8.5)
  - [ ] Configure Prometheus scrape config

- [ ] **Phase 5: Alerting & Dashboards**
  - [ ] Write Prometheus alert rules (Section 9.1)
  - [ ] Configure Alertmanager routing (Section 9.2)
  - [ ] Build Grafana dashboard: Real-Time Request Flow
  - [ ] Build Grafana dashboard: Error Tracking
  - [ ] Build Grafana dashboard: Cost Breakdown
  - [ ] Build Grafana dashboard: Performance Trends
  - [ ] Build Grafana dashboard: Agent Session Timeline

- [ ] **Phase 6: Validation**
  - [ ] Verify end-to-end trace propagation in staging
  - [ ] Verify log-trace correlation works across all services
  - [ ] Verify cost estimates match within 5% of actual billing
  - [ ] Load test and confirm metrics accuracy under high QPS
  - [ ] Run through all four debug workflows (Section 11) and document findings
  - [ ] Team training on dashboards and debug workflows

---

## 13. Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| 1 | Every request produces a trace with all 16 spans (or applicable subset) | Langfuse trace inspection |
| 2 | All required attributes are present on every span | OTel collector validation |
| 3 | `request_id` appears in every log line for the request | Log query returns 100% coverage |
| 4 | `trace_id` links logs to OpenTelemetry traces | Click-through from log to trace works |
| 5 | LLM token counts match within 1% of provider billing | Compare Langfuse totals vs provider dashboard |
| 6 | Cost estimates match within 5% of actual billing | Monthly reconciliation |
| 7 | P50, P95, P99 latency metrics are accurate | Synthetic load test comparison |
| 8 | Alerts fire within 2 minutes of threshold breach | Chaos test: inject errors and verify alert |
| 9 | Debug workflow for failed request completes in < 5 minutes | Timed exercise by team member |
| 10 | Debug workflow for slow request completes in < 10 minutes | Timed exercise by team member |
| 11 | Debug workflow for high cost completes in < 10 minutes | Timed exercise by team member |
| 12 | Sensitive data never appears in logs | Automated scan with `grep` for patterns |
| 13 | Dashboard panels load in < 3 seconds | Grafana performance test |
| 14 | No observability overhead exceeds 5% of request latency | Benchmark with/without instrumentation |
