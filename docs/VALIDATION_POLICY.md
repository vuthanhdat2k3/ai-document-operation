# Validation Policy — AI Document Operations Agent

> **Version:** 1.0.0
> **Last Updated:** 2026-06-11
> **Status:** Active

This document defines the complete validation strategy for the AI Document Operations Agent. Every request, tool call, LLM output, and side-effecting action must pass through the applicable validation layers before execution.

---

## Table of Contents

1. [Input Validation](#1-input-validation)
2. [File Validation](#2-file-validation)
3. [Tool Call Validation](#3-tool-call-validation)
4. [LLM Output Validation](#4-llm-output-validation)
5. [JSON Schema Validation](#5-json-schema-validation)
6. [Pydantic Validation](#6-pydantic-validation)
7. [Citation Validation](#7-citation-validation)
8. [Groundedness Validation](#8-groundedness-validation)
9. [Idempotency Validation](#9-idempotency-validation)
10. [Retry Validation](#10-retry-validation)
11. [Human-in-the-Loop Policy](#11-human-in-the-loop-policy)
12. [Agent Safety Constraints](#12-agent-safety-constraints)
13. [Validation Error Response Format](#13-validation-error-response-format)
14. [Implementation Checklist](#14-implementation-checklist)
15. [Acceptance Criteria](#15-acceptance-criteria)

---

## 1. Input Validation

All inbound API requests must be validated before any business logic executes.

### 1.1 API Request Validation (Pydantic)

- Every endpoint must declare a Pydantic request model.
- Requests that fail schema validation return `422 Unprocessable Entity` with field-level errors.
- Strict mode is enabled on all request models (`model_config = ConfigDict(strict=True)`).

### 1.2 Query Parameter Validation

| Parameter | Rule |
|-----------|------|
| `page` | `int`, `ge=1`, default `1` |
| `page_size` | `int`, `ge=1`, `le=100`, default `20` |
| `sort_by` | `str`, must be in allowed field whitelist |
| `order` | `Literal["asc", "desc"]`, default `"asc"` |

- Unknown query parameters are rejected (not silently ignored).

### 1.3 Path Parameter Validation

- All path parameters are parsed and validated by Pydantic before handler execution.
- UUID parameters must match the UUID v4 format.
- Document IDs are validated against existence in the database before proceeding.

### 1.4 File Upload Validation

| Check | Rule |
|-------|------|
| Max file size | 50 MB |
| Allowed MIME types | Whitelist only (see §2) |
| Content-Type header | Must match detected MIME type |
| Filename | Sanitized, no path traversal characters |
| Upload timeout | 30 seconds |

### 1.5 Request Body Size Limits

| Endpoint Category | Max Body Size |
|-------------------|---------------|
| Single document upload | 50 MB |
| Bulk upload (batch) | 200 MB |
| Query/search endpoints | 1 MB |
| Configuration endpoints | 256 KB |

Requests exceeding limits receive `413 Payload Too Large`.

---

## 2. File Validation

Files are validated through a multi-stage pipeline before processing.

### 2.1 MIME Type Verification

- MIME type is detected via **magic bytes** (libmagic / python-magic), NOT from the file extension or `Content-Type` header alone.
- If the detected MIME type does not match the declared type, the file is rejected.
- Example: a `.pdf` file whose magic bytes indicate `application/zip` is rejected.

```python
import magic

def detect_mime(file_bytes: bytes) -> str:
    return magic.from_buffer(file_bytes, mime=True)
```

### 2.2 File Size Limits

| Limit | Value |
|-------|-------|
| Maximum file size | 50 MB |
| Minimum file size | 1 byte (empty files rejected) |
| Per-request total (batch) | 200 MB |

### 2.3 File Integrity (Checksum)

- SHA-256 checksum is computed on upload and stored alongside the file.
- On retrieval, the checksum is re-verified to detect corruption.
- Mismatch triggers re-upload; corrupted files are flagged and quarantined.

### 2.4 Virus Scanning Placeholder

All uploaded files pass through a virus scanning stage before processing.

```python
async def scan_for_viruses(file_bytes: bytes) -> ScanResult:
    # TODO: Integrate ClamAV or cloud-based scanning service
    # Currently returns CLEAN for all files
    return ScanResult(status="CLEAN", engine="placeholder")
```

- Files flagged as `INFECTED` are rejected with `422`.
- Files flagged as `SUSPICIOUS` are quarantined for manual review.
- Production deployment MUST replace the placeholder before go-live.

### 2.5 Supported Format Whitelist

| Category | Extensions | MIME Types |
|----------|-----------|------------|
| PDF | `.pdf` | `application/pdf` |
| Word | `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| Plain Text | `.txt` | `text/plain` |
| Markdown | `.md` | `text/markdown` |
| CSV | `.csv` | `text/csv` |
| Excel | `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| Images (OCR) | `.png`, `.jpg`, `.jpeg`, `.tiff` | `image/png`, `image/jpeg`, `image/tiff` |

Files not on this whitelist are rejected with a descriptive error message listing supported formats.

---

## 3. Tool Call Validation

Every tool invocation by the agent must pass validation before execution.

### 3.1 Pre-Execution Schema Validation (JSON Schema)

- Each tool defines an input JSON Schema.
- Tool inputs are validated against the schema **before** execution begins.
- Schema validation failures are caught and surfaced to the LLM for correction.

### 3.2 Input Sanitization

- All string inputs are sanitized for:
  - SQL injection patterns
  - Path traversal sequences (`../`, `..\\`)
  - Shell injection characters (`;`, `|`, `&`, `` ` ``)
  - HTML/script injection (`<script>`, `javascript:`)
- Sanitization is applied **after** schema validation, **before** tool execution.

### 3.3 Parameter Type Checking

- Type coercion is NOT allowed in strict mode; parameters must arrive in the declared type.
- Numeric parameters are range-checked against declared `minimum` / `maximum`.
- Enum parameters must match one of the declared values exactly.

### 3.4 Required Field Verification

- All fields marked `required` in the tool's JSON Schema must be present.
- Missing required fields produce a validation error, not a default value.

### 3.5 Tool Availability Check

- Before invocation, the agent confirms the tool is registered and enabled.
- Disabled or deprecated tools return a clear error with migration guidance.
- Tool version mismatches are detected and reported.

### 3.6 Rate Limiting Per Tool

| Tool Category | Rate Limit |
|---------------|------------|
| Read operations | 60/minute |
| Write operations | 20/minute |
| External API calls | 10/minute |
| LLM calls | 30/minute |
| File processing | 15/minute |

Rate limit violations return `429 Too Many Requests` with `Retry-After` header.

---

## 4. LLM Output Validation

All LLM responses are validated before being acted upon or returned to the user.

### 4.1 Response Format Validation

- If the LLM is instructed to return structured output (JSON), the response is parsed and validated.
- Non-parseable responses trigger a retry with reinforced instructions (max 2 retries).

### 4.2 JSON Output Parsing

```python
def parse_llm_json(raw: str) -> dict:
    # Strip markdown code fences if present
    cleaned = strip_code_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise LLMOutputError(f"Invalid JSON from LLM: {e}")
```

### 4.3 Required Field Extraction

- After parsing, required fields are extracted and validated against the expected schema.
- Missing fields trigger a structured retry with explicit field requirements.

### 4.4 Token Limit Checking

| Check | Limit |
|-------|-------|
| Max output tokens | 4096 |
| Max input context | 128k tokens |
| Streaming chunk timeout | 30 seconds |

Outputs exceeding token limits are truncated with an indicator, not silently dropped.

### 4.5 Content Policy Filtering

LLM outputs are checked against content policies:

- PII detection (SSN, credit card numbers, etc.)
- Profanity / hate speech filtering
- Confidential data leakage patterns
- Hallucinated URLs or credentials

Violations are logged and the output is replaced with a safe fallback.

### 4.6 Output Schema Matching

- The parsed LLM output is validated against the declared output Pydantic model.
- Extra fields not in the schema are stripped (strict mode).
- Type mismatches in structured fields trigger a retry.

---

## 5. JSON Schema Validation

### 5.1 Schema Registry

- All schemas are registered in a central `SchemaRegistry`.
- Schemas are loaded at application startup and cached in memory.
- Schema lookup is by name + version.

```python
class SchemaRegistry:
    def get(self, name: str, version: str = "latest") -> dict: ...
    def register(self, name: str, version: str, schema: dict) -> None: ...
    def validate(self, name: str, data: dict, version: str = "latest") -> list[str]: ...
```

### 5.2 Schema Versioning

- Schemas follow semantic versioning (`MAJOR.MINOR.PATCH`).
- Breaking changes require a MAJOR version bump.
- The registry supports multiple versions of the same schema simultaneously.
- Consumers specify which version they expect; defaults to `latest`.

### 5.3 Strict Mode (No Additional Properties)

All schemas use strict mode:

```json
{
  "additionalProperties": false,
  "type": "object",
  "required": ["field1", "field2"],
  "properties": {
    "field1": { "type": "string" },
    "field2": { "type": "integer", "minimum": 0 }
  }
}
```

### 5.4 Custom Format Validators

| Format | Validation |
|--------|------------|
| `uuid-v4` | UUID v4 regex + version nibble check |
| `iso-datetime` | ISO 8601 with timezone required |
| `email` | RFC 5322 simplified |
| `document-id` | Application-specific ID pattern |
| `safe-filename` | No path separators, no control characters |

---

## 6. Pydantic Validation

### 6.1 Model Validation Patterns

- All domain models inherit from a base model with strict configuration.
- `model_config = ConfigDict(strict=True, extra="forbid")` is the default.

### 6.2 Custom Validators

```python
from pydantic import field_validator, model_validator

class DocumentRequest(BaseModel):
    filename: str
    content_type: str

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        if "/" in v or "\\" in v:
            raise ValueError("Filename must not contain path separators")
        if not re.match(r"^[\w\-. ]+$", v):
            raise ValueError("Filename contains invalid characters")
        return v.strip()

    @model_validator(mode="after")
    def cross_validate(self) -> "DocumentRequest":
        # Cross-field validation logic
        return self
```

### 6.3 Field Constraints

| Constraint | Example |
|------------|---------|
| `ge`, `le` | `page_size: int = Field(ge=1, le=100)` |
| `min_length`, `max_length` | `title: str = Field(min_length=1, max_length=500)` |
| `pattern` | `code: str = Field(pattern=r"^[A-Z]{3}-\d{4}$")` |
| `Enum` | `status: Literal["active", "archived"]` |

### 6.4 Cross-Field Validation

- `@model_validator(mode="after")` is used for cross-field validation.
- Examples: `start_date` must be before `end_date`; at least one of `email` or `phone` must be provided.

### 6.5 Model Config (Strict Mode)

```python
from pydantic import ConfigDict

class StrictBaseModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_default=True,
        frozen=True,
    )
```

---

## 7. Citation Validation

Every citation in the agent's output must be validated for accuracy and completeness.

### 7.1 Citation Format Validation

Citations must follow the standard format:

```
[Source: <document_id>, Page: <page_number>, Chunk: <chunk_id>]
```

- `document_id`: valid UUID v4
- `page_number`: positive integer
- `chunk_id`: valid UUID v4

### 7.2 Citation-Source Matching

- Every cited `document_id` must exist in the document store.
- The cited content must be traceable to the actual source chunk.
- Phantom citations (citing non-existent sources) are flagged as hallucinations.

### 7.3 Page Number Verification

- Page numbers must fall within the document's actual page count.
- Out-of-range page numbers are flagged and the citation is invalidated.

### 7.4 Chunk ID Existence Check

- Every `chunk_id` in a citation is verified against the chunk index.
- Missing chunks trigger a re-retrieval; if still missing, the citation is removed.

### 7.5 Citation Completeness Scoring

Each response receives a citation completeness score:

```
score = (cited_claims / total_claims) * 100
```

| Score | Rating |
|-------|--------|
| 90-100% | Excellent |
| 70-89% | Acceptable |
| 50-69% | Warning |
| < 50% | Fail — response must be revised |

Minimum acceptable score: **70%**.

---

## 8. Groundedness Validation

All factual claims in agent output must be grounded in retrieved source material.

### 8.1 Claim Extraction from LLM Output

- The LLM output is decomposed into individual claims using a claim extraction prompt.
- Each claim is a single, verifiable factual statement.
- Subjective or hedging statements (`"may"`, `"possibly"`) are scored separately.

### 8.2 Evidence Matching Against Source

- Each extracted claim is compared against the retrieved source chunks.
- Semantic similarity (cosine similarity on embeddings) is computed.
- Claims with similarity >= 0.8 are considered "supported."
- Claims with similarity 0.5-0.8 are "partially supported."
- Claims below 0.5 are "unsupported."

### 8.3 Confidence Scoring (0-1)

```
groundedness_score = supported_claims / total_claims
```

| Score | Interpretation |
|-------|---------------|
| >= 0.9 | High confidence |
| 0.7 - 0.89 | Acceptable confidence |
| 0.5 - 0.69 | Low confidence — flag for review |
| < 0.5 | Unacceptable — must not return to user |

### 8.4 Hallucination Detection

A claim is classified as a hallucination if:

- It contains specific facts (names, dates, numbers) not present in any source chunk.
- It contradicts the source material.
- It fabricates URLs, file paths, or identifiers.

Hallucinated content is stripped from the response before delivery.

### 8.5 Minimum Groundedness Threshold

**The minimum groundedness threshold is 0.7.**

Responses scoring below 0.7 MUST NOT be returned to the user as-is.

### 8.6 "I Don't Know" Policy

When groundedness falls below the 0.7 threshold:

1. The agent MUST NOT fabricate an answer.
2. The agent returns: *"I don't have enough information in the provided documents to answer this question with confidence."*
3. The agent MAY suggest which documents the user should review.
4. The low-groundedness event is logged for quality monitoring.

---

## 9. Idempotency Validation

All mutating operations must be idempotent to prevent duplicate side effects.

### 9.1 Idempotency Key Format

- Idempotency keys MUST be UUID v4.
- Keys are provided by the client in the `Idempotency-Key` header.
- If no key is provided for a mutating endpoint, the request is rejected.

### 9.2 Key Uniqueness Check

- Keys are stored in a persistent idempotency store (Redis or database).
- Uniqueness is enforced at the storage level.
- Key collisions (same UUID from different clients) are rejected with `409 Conflict`.

### 9.3 Duplicate Request Detection

```python
async def check_idempotency(key: str) -> Optional[CachedResult]:
    cached = await idempotency_store.get(key)
    if cached is not None:
        if cached.status == "completed":
            return cached.result  # Return cached response
        if cached.status == "in_progress":
            raise IdempotencyConflictError("Request is already being processed")
    return None
```

### 9.4 Result Caching for Duplicate Keys

- Completed results are cached against the idempotency key.
- Duplicate requests with the same key receive the cached result with `200 OK` (not `201 Created`).
- The `Idempotent-Replay: true` header is set on cached responses.

### 9.5 TTL for Idempotency Keys

| Setting | Value |
|---------|-------|
| Key TTL | 24 hours |
| Cleanup interval | Every 1 hour |
| Storage | Redis with TTL or DB with scheduled purge |

After 24 hours, the same idempotency key may be reused (though this is discouraged).

---

## 10. Retry Validation

Failed operations are retried according to a controlled retry policy.

### 10.1 Maximum Retry Limits Per Operation

| Operation Type | Max Retries |
|----------------|-------------|
| LLM API calls | 3 |
| Database writes | 2 |
| External API calls | 3 |
| File processing | 2 |
| Tool execution | 2 |

### 10.2 Exponential Backoff with Jitter

```python
import random

def compute_backoff(attempt: int, base: float = 1.0, max_delay: float = 60.0) -> float:
    delay = min(base * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.5)
    return delay + jitter
```

| Attempt | Base Delay | Max Delay (with jitter) |
|---------|-----------|------------------------|
| 1 | 1s | ~1.5s |
| 2 | 2s | ~3s |
| 3 | 4s | ~6s |

### 10.3 Retryable vs Non-Retryable Errors

**Retryable:**
- `429 Too Many Requests`
- `500 Internal Server Error` (transient)
- `502 Bad Gateway`
- `503 Service Unavailable`
- `504 Gateway Timeout`
- Network timeouts
- Connection resets

**Non-Retryable:**
- `400 Bad Request`
- `401 Unauthorized`
- `403 Forbidden`
- `404 Not Found`
- `413 Payload Too Large`
- `422 Unprocessable Entity`
- Validation errors
- Authentication failures

### 10.4 Dead Letter Queue for Failed Retries

- After exhausting retries, the failed operation is placed in a Dead Letter Queue (DLQ).
- DLQ entries include: original request, error details, retry history, timestamps.
- DLQ is monitored; alerts fire when queue depth exceeds threshold.
- DLQ entries are retained for 7 days for debugging.

---

## 11. Human-in-the-Loop Policy

Certain actions require explicit human approval before execution.

### 11.1 Actions Requiring Approval

| Action | Risk Level | Approval Required |
|--------|-----------|-------------------|
| Sending real emails | HIGH | YES |
| Deleting data (documents, records) | CRITICAL | YES |
| Writing to production database | CRITICAL | YES |
| Creating external API calls | HIGH | YES |
| Modifying user permissions | CRITICAL | YES |
| Bulk operations (> 10 items) | MEDIUM | YES |

### 11.2 Approval Workflow

1. Agent identifies an action requiring approval.
2. Agent generates an approval request with:
   - Action description
   - Affected resources
   - Risk assessment
   - Reversible (yes/no)
3. Approval request is sent to the designated approver(s).
4. Approver reviews and approves/rejects.
5. Agent executes or cancels based on the decision.

### 11.3 Timeout for Approval

| Setting | Value |
|---------|-------|
| Approval timeout | 30 minutes |
| Reminder at | 20 minutes |
| Escalation at | 25 minutes |
| Auto-reject at | 30 minutes |

After timeout, the action is automatically rejected and the user is notified.

### 11.4 Fallback When No Approval

If no approver is available:

1. The action is queued, not executed.
2. The user receives a notification that their request is pending approval.
3. The agent returns a partial result excluding the unapproved action.
4. The pending action is logged and tracked.

---

## 12. Agent Safety Constraints

### 12.1 Agent MUST NEVER

| Constraint | Enforcement |
|-----------|-------------|
| Send real emails without approval | Hard block in tool layer |
| Delete data without approval | Hard block in tool layer |
| Write to critical database tables without approval | Hard block in tool layer |
| Create duplicate tasks | Idempotency enforcement |
| Return answers without evidence | Groundedness validation |
| Execute more than 10 iterations | Iteration counter with hard limit |
| Exceed cost budget per request | Cost tracker with hard limit |
| Call tools with invalid input | Pre-execution validation |

### 12.2 Iteration Limit

```
MAX_ITERATIONS = 10
```

- Each tool call + LLM reasoning cycle counts as one iteration.
- After 10 iterations, the agent MUST stop and return its best-effort answer.
- Iteration exhaustion is logged as a warning.

### 12.3 Cost Budget

| Metric | Limit per Request |
|--------|-------------------|
| LLM tokens (input + output) | 100,000 |
| Tool calls | 20 |
| External API calls | 10 |
| Estimated cost (USD) | $0.50 |

Cost tracking runs in real-time; exceeding the budget halts execution.

---

## 13. Validation Error Response Format

### 13.1 Standard Error Schema

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "page_size",
        "code": "VALUE_OUT_OF_RANGE",
        "message": "Value must be between 1 and 100",
        "received": 500
      }
    ],
    "request_id": "req_abc123",
    "timestamp": "2026-06-11T15:00:00Z"
  }
}
```

### 13.2 Error Codes Taxonomy

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | General validation failure |
| `INVALID_FILE_TYPE` | 422 | File MIME type not allowed |
| `FILE_TOO_LARGE` | 413 | File exceeds size limit |
| `TOOL_NOT_FOUND` | 404 | Requested tool does not exist |
| `TOOL_RATE_LIMITED` | 429 | Tool rate limit exceeded |
| `IDEMPOTENCY_KEY_MISSING` | 400 | Required idempotency key not provided |
| `IDEMPOTENCY_KEY_DUPLICATE` | 409 | Duplicate idempotency key detected |
| `GROUNDING_FAILED` | 422 | Response cannot be grounded in sources |
| `CITATION_INVALID` | 422 | Citation references non-existent source |
| `APPROVAL_REQUIRED` | 202 | Action requires human approval |
| `APPROVAL_TIMEOUT` | 408 | Approval not received within timeout |
| `ITERATION_LIMIT` | 500 | Agent exceeded maximum iterations |
| `COST_BUDGET_EXCEEDED` | 429 | Request exceeded cost budget |
| `CONTENT_POLICY_VIOLATION` | 422 | Output violates content policies |
| `VIRUS_DETECTED` | 422 | Uploaded file failed virus scan |
| `INTERNAL_ERROR` | 500 | Unexpected internal error |

### 13.3 Human-Readable Messages

Every error response includes a `message` field that is:

- Written in plain English
- Actionable (tells the user what to do)
- Free of internal implementation details
- Localized (future: support for multiple languages)

### 13.4 Field-Level Error Details

The `details` array contains one entry per field error:

```json
{
  "field": "filename",
  "code": "INVALID_CHARACTERS",
  "message": "Filename contains invalid characters. Use only letters, numbers, hyphens, and underscores.",
  "received": "../../../etc/passwd"
}
```

---

## 14. Implementation Checklist

### Phase 1 — Foundation

- [ ] Define all Pydantic request/response models with strict mode
- [ ] Implement JSON Schema registry with versioning
- [ ] Set up file upload pipeline with magic-byte MIME detection
- [ ] Implement checksum computation and verification
- [ ] Create standard error response format

### Phase 2 — Tool & LLM Validation

- [ ] Define JSON Schema for every tool input
- [ ] Implement pre-execution tool validation pipeline
- [ ] Add input sanitization middleware
- [ ] Build LLM output parser with retry logic
- [ ] Implement content policy filtering

### Phase 3 — Citation & Groundedness

- [ ] Build claim extraction pipeline
- [ ] Implement evidence matching with semantic similarity
- [ ] Create groundedness scoring (threshold: 0.7)
- [ ] Implement "I don't know" fallback
- [ ] Build citation completeness scorer

### Phase 4 — Safety & Idempotency

- [ ] Implement idempotency key store (Redis)
- [ ] Add duplicate request detection
- [ ] Build Human-in-the-Loop approval workflow
- [ ] Enforce iteration limits (max 10)
- [ ] Implement cost tracking and budget enforcement
- [ ] Set up retry logic with exponential backoff
- [ ] Configure Dead Letter Queue

### Phase 5 — Monitoring & Observability

- [ ] Add structured logging for all validation events
- [ ] Set up metrics for validation pass/fail rates
- [ ] Configure alerts for DLQ depth
- [ ] Build validation dashboard
- [ ] Implement virus scanning integration (replace placeholder)

---

## 15. Acceptance Criteria

The validation policy is considered successfully implemented when ALL of the following are true:

### AC-1: Input Validation
> All API endpoints reject malformed requests with `422` and field-level error details. No unvalidated input reaches business logic.

### AC-2: File Validation
> 100% of uploaded files pass MIME detection, size checks, and integrity verification. Virus scanning integration is in place (or explicitly marked as placeholder in non-production).

### AC-3: Tool Call Validation
> No tool executes with invalid input. All tool calls are schema-validated, sanitized, and rate-limited.

### AC-4: LLM Output Validation
> All structured LLM outputs are parsed, validated against output schemas, and checked for content policy violations before being returned.

### AC-5: Citation & Groundedness
> Every factual claim in agent output has a verifiable citation. No response with a groundedness score below 0.7 is returned to the user without the "I don't know" fallback.

### AC-6: Idempotency
> All mutating endpoints require an idempotency key. Duplicate requests with the same key return the cached result without re-executing the operation.

### AC-7: Human-in-the-Loop
> High-risk actions (email, delete, production writes, external API calls) are blocked until explicit approval is received. Approval timeouts auto-reject after 30 minutes.

### AC-8: Safety Constraints
> The agent never exceeds 10 iterations, never exceeds the cost budget, and never returns ungrounded answers. All safety violations are logged.

### AC-9: Error Responses
> All validation errors use the standard error schema with error codes, human-readable messages, and field-level details.

### AC-10: Observability
> All validation events are logged with structured data. Metrics and alerts are configured for monitoring.

---

*End of Validation Policy*
