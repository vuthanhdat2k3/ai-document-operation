# AI Document Operations Agent — Tool Contracts

> **Version:** 1.0.0
> **Last Updated:** 2026-06-11
> **Status:** Draft

This document defines the formal contracts for every tool available to the AI Document Operations Agent. Each contract specifies purpose, schemas, preconditions, postconditions, failure modes, retry policy, idempotency, and testing requirements.

---

## Table of Contents

1. [Global Conventions](#global-conventions)
2. [Tool Registry](#tool-registry)
3. [Tool Schema Validation](#tool-schema-validation)
4. [Tool Execution Sandbox](#tool-execution-sandbox)
5. [Tool Timeout Configuration](#tool-timeout-configuration)
6. [Tool Result Caching Policy](#tool-result-caching-policy)
7. [Tool Error Handling Pattern](#tool-error-handling-pattern)
8. [Tool Contracts](#tool-contracts)
   - 8.1 [parse_document](#1-parse_document)
   - 8.2 [classify_document](#2-classify_document)
   - 8.3 [extract_fields](#3-extract_fields)
   - 8.4 [search_documents](#4-search_documents)
   - 8.5 [rerank_evidence](#5-rerank_evidence)
   - 8.6 [compile_context_pack](#6-compile_context_pack)
   - 8.7 [detect_risks](#7-detect_risks)
   - 8.8 [generate_checklist](#8-generate_checklist)
   - 8.9 [create_task](#9-create_task)
   - 8.10 [save_extracted_fields](#10-save_extracted_fields)
   - 8.11 [generate_report](#11-generate_report)
   - 8.12 [export_report](#12-export_report)

---

## Global Conventions

- All schemas are defined as Pydantic v2 `BaseModel` subclasses.
- All `Optional` fields default to `None` unless stated otherwise.
- All datetime fields use ISO 8601 format with timezone.
- All ID fields are UUID v4 strings unless stated otherwise.
- All tool functions are `async def` and return their result schema wrapped in a `ToolResponse`.
- Error responses follow the unified `ToolError` schema.

```python
from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime

class ToolError(BaseModel):
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    retryable: bool = Field(default=False, description="Whether the caller should retry")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

class ToolResponse(BaseModel):
    success: bool
    data: Any = None
    error: ToolError | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

---

## Tool Registry

All tools are registered in a central registry that maps tool names to their implementation, schema, and metadata.

```python
from typing import Callable, Any
from pydantic import BaseModel

class ToolMeta(BaseModel):
    name: str
    version: str
    description: str
    timeout_seconds: int
    max_retries: int
    cache_ttl_seconds: int | None
    requires_sandbox: bool
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]

class ToolRegistry:
    _tools: dict[str, tuple[Callable, ToolMeta]] = {}

    @classmethod
    def register(cls, meta: ToolMeta):
        def decorator(fn: Callable):
            cls._tools[meta.name] = (fn, meta)
            return fn
        return decorator

    @classmethod
    def get(cls, name: str) -> tuple[Callable, ToolMeta]:
        if name not in cls._tools:
            raise KeyError(f"Tool '{name}' is not registered")
        return cls._tools[name]

    @classmethod
    def list_tools(cls) -> list[ToolMeta]:
        return [meta for _, meta in cls._tools.values()]

    @classmethod
    async def execute(cls, name: str, **kwargs) -> ToolResponse:
        fn, meta = cls.get(name)
        validated_input = meta.input_schema(**kwargs)
        return await fn(validated_input)
```

**Rules:**
- Every tool MUST be registered before it can be called.
- Duplicate tool names MUST raise `ValueError` at registration time.
- The registry MUST be immutable after the agent bootstrap phase.

---

## Tool Schema Validation

All tool inputs and outputs are validated against their Pydantic schemas at the boundary.

```python
import jsonschema

def generate_json_schema(model: type[BaseModel]) -> dict:
    return model.model_json_schema()

def validate_input_against_schema(data: dict, schema: type[BaseModel]):
    schema_dict = generate_json_schema(schema)
    jsonschema.validate(instance=data, schema=schema_dict)
```

**Rules:**
- Input validation happens BEFORE tool execution.
- Output validation happens AFTER tool execution.
- Validation failures produce a `ToolError` with code `VALIDATION_ERROR` and are NOT retryable.

---

## Tool Execution Sandbox

Tools that interact with external systems or execute untrusted code MUST run inside a sandbox.

```python
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def tool_sandbox(meta: ToolMeta):
    env = {
        "TOOL_NAME": meta.name,
        "TIMEOUT": meta.timeout_seconds,
        "SANDBOXED": meta.requires_sandbox,
    }
    try:
        yield env
    except asyncio.TimeoutError:
        raise ToolExecutionError(f"Tool '{meta.name}' timed out after {meta.timeout_seconds}s")
    finally:
        pass  # cleanup temp files, close connections
```

**Rules:**
- File system access is restricted to a dedicated `/tmp/tool_sandbox/<tool_name>/` directory.
- Network access is restricted to an allowlist of endpoints.
- Memory usage is capped at 512 MB per execution.
- CPU time is capped at the tool's configured timeout.

---

## Tool Timeout Configuration

| Tool | Timeout (seconds) |
|---|---|
| `parse_document` | 120 |
| `classify_document` | 30 |
| `extract_fields` | 60 |
| `search_documents` | 15 |
| `rerank_evidence` | 20 |
| `compile_context_pack` | 10 |
| `detect_risks` | 45 |
| `generate_checklist` | 30 |
| `create_task` | 10 |
| `save_extracted_fields` | 10 |
| `generate_report` | 60 |
| `export_report` | 120 |

Timeouts are enforced via `asyncio.wait_for()` and produce a `TIMEOUT_ERROR` which is retryable.

---

## Tool Result Caching Policy

| Tool | Cacheable | TTL (seconds) | Cache Key |
|---|---|---|---|
| `parse_document` | Yes | 86400 | `file_id` |
| `classify_document` | Yes | 86400 | `document_id` |
| `extract_fields` | Yes | 86400 | `document_id + schema_name` |
| `search_documents` | Yes | 300 | `query + filters + top_k` |
| `rerank_evidence` | No | — | — |
| `compile_context_pack` | No | — | — |
| `detect_risks` | Yes | 3600 | `document_id + evidence_hash` |
| `generate_checklist` | Yes | 3600 | `document_id + risk_items_hash` |
| `create_task` | No | — | — |
| `save_extracted_fields` | No | — | — |
| `generate_report` | Yes | 3600 | `document_id + report_type` |
| `export_report` | Yes | 3600 | `report_id + format` |

Cache implementation uses Redis with namespaced keys: `tool_cache:<tool_name>:<cache_key>`.

```python
import hashlib
import json

def make_cache_key(tool_name: str, **kwargs) -> str:
    raw = json.dumps(kwargs, sort_keys=True)
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"tool_cache:{tool_name}:{h}"
```

**Rules:**
- Cache invalidation is triggered when the underlying document is mutated.
- Cache hits skip tool execution entirely and return the stored result.
- Cache misses proceed with normal execution and store the result on success.

---

## Tool Error Handling Pattern

All errors are wrapped in a unified `ToolError` model. The error handling pipeline:

1. **Catch** the raw exception.
2. **Classify** the error into a known error code.
3. **Enrich** with context (tool name, input summary, timestamp).
4. **Decide** retryability based on the error code.
5. **Return** `ToolResponse(success=False, error=ToolError(...))`.

```python
class ErrorCodes:
    VALIDATION_ERROR = "VALIDATION_ERROR"        # not retryable
    NOT_FOUND = "NOT_FOUND"                      # not retryable
    PERMISSION_DENIED = "PERMISSION_DENIED"       # not retryable
    TIMEOUT_ERROR = "TIMEOUT_ERROR"               # retryable
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"         # retryable (with backoff)
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"  # retryable
    INTERNAL_ERROR = "INTERNAL_ERROR"             # retryable (once)
    PARSE_ERROR = "PARSE_ERROR"                   # not retryable
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT" # not retryable
```

---

## Tool Contracts

### 1. parse_document

**Purpose:** Ingests a raw file (PDF, DOCX, TXT, image) and produces structured text content with metadata. Handles OCR for image-based documents.

#### Input Schema

```python
class ParseDocumentInput(BaseModel):
    file_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique identifier for the file in the document store"
    )
    ocr_enabled: bool = Field(
        default=True,
        description="Whether to run OCR on image-based content"
    )
    language: str = Field(
        default="en",
        pattern=r"^[a-z]{2}(-[A-Z]{2})?$",
        description="ISO 639-1 language code for OCR engine hint"
    )
```

#### Output Schema

```python
class ParsedPage(BaseModel):
    page_number: int = Field(..., ge=1)
    text: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    tables: list[dict] = Field(default_factory=list)
    images: list[dict] = Field(default_factory=list)

class ParseResult(BaseModel):
    file_id: str
    document_type: str = Field(..., description="Detected file format: pdf, docx, txt, image")
    pages: list[ParsedPage]
    total_pages: int = Field(..., ge=1)
    total_characters: int = Field(..., ge=0)
    language_detected: str
    parse_duration_ms: int = Field(..., ge=0)
    created_at: datetime
```

#### Preconditions
- `file_id` must reference an existing file in the document store.
- The file must not be corrupted or zero-length.
- The file format must be in the supported set: PDF, DOCX, TXT, PNG, JPG, TIFF.

#### Postconditions
- A `ParseResult` with at least one page is returned.
- The parsed text is persisted in the document store under `file_id`.
- The file's status is updated to `PARSED`.

#### Failure Modes
| Error Code | Condition | Retryable |
|---|---|---|
| `NOT_FOUND` | `file_id` does not exist | No |
| `PARSE_ERROR` | File is corrupted or unsupported format | No |
| `TIMEOUT_ERROR` | Parsing exceeds 120 seconds | Yes |
| `EXTERNAL_SERVICE_ERROR` | OCR service unavailable | Yes |

#### Retry Policy
- **Max retries:** 2
- **Backoff:** Exponential, base=2s, max=30s
- **Retryable errors:** `TIMEOUT_ERROR`, `EXTERNAL_SERVICE_ERROR`

#### Idempotency
- **Idempotent:** Yes, by `file_id`.
- Re-parsing the same `file_id` returns the cached `ParseResult` if it exists and the file has not been modified.
- Idempotency is enforced by checking `file_id` + `file_hash` in the cache.

#### Unit Test Requirements
- Verify parsing of each supported file format (PDF, DOCX, TXT, PNG).
- Verify OCR toggle (`ocr_enabled=False` skips OCR).
- Verify language hint is passed to OCR engine.
- Verify `NOT_FOUND` for invalid `file_id`.
- Verify `PARSE_ERROR` for corrupted file.
- Verify timeout triggers `TIMEOUT_ERROR`.

#### Integration Test Requirements
- End-to-end: upload file → parse → verify text stored in document store.
- Verify OCR integration with real image file.
- Verify cache hit on second parse of same file.
- Verify file status transitions to `PARSED`.

---

### 2. classify_document

**Purpose:** Classifies a parsed document into a predefined category (e.g., invoice, contract, report, letter) using an ML model.

#### Input Schema

```python
class ClassifyDocumentInput(BaseModel):
    document_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique identifier for the parsed document"
    )
    candidate_labels: list[str] | None = Field(
        default=None,
        description="Optional list of candidate labels. If None, uses default taxonomy."
    )
```

#### Output Schema

```python
class ClassificationResult(BaseModel):
    document_id: str
    predicted_label: str = Field(..., description="Top predicted category")
    confidence: float = Field(..., ge=0.0, le=1.0)
    label_scores: dict[str, float] = Field(..., description="Score for each candidate label")
    model_version: str
    classified_at: datetime
```

#### Preconditions
- `document_id` must reference a document with status `PARSED` or `CLASSIFIED`.
- The document must have non-empty text content.

#### Postconditions
- A `ClassificationResult` is returned with scores summing to approximately 1.0.
- The document's `classification` field is updated in the store.

#### Failure Modes
| Error Code | Condition | Retryable |
|---|---|---|
| `NOT_FOUND` | `document_id` does not exist | No |
| `VALIDATION_ERROR` | Document has no parsed text | No |
| `EXTERNAL_SERVICE_ERROR` | ML model service unavailable | Yes |
| `TIMEOUT_ERROR` | Classification exceeds 30 seconds | Yes |

#### Retry Policy
- **Max retries:** 3
- **Backoff:** Exponential, base=1s, max=15s
- **Retryable errors:** `EXTERNAL_SERVICE_ERROR`, `TIMEOUT_ERROR`

#### Idempotency
- **Idempotent:** Yes, by `document_id`.
- Re-classifying the same document returns the cached result.
- Cache is invalidated if the document content changes.

#### Unit Test Requirements
- Verify classification with default taxonomy.
- Verify classification with custom `candidate_labels`.
- Verify `NOT_FOUND` for invalid `document_id`.
- Verify `VALIDATION_ERROR` for document with empty text.
- Verify confidence is in [0, 1] range.

#### Integration Test Requirements
- End-to-end: parse document → classify → verify label stored.
- Verify ML model service integration.
- Verify cache hit on second classification.

---

### 3. extract_fields

**Purpose:** Extracts structured fields from a document based on a named schema (e.g., invoice schema extracts vendor, amount, date; contract schema extracts parties, terms, effective date).

#### Input Schema

```python
class ExtractFieldsInput(BaseModel):
    document_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique identifier for the document"
    )
    schema_name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Name of the extraction schema to apply"
    )
    strict: bool = Field(
        default=False,
        description="If True, fails when a required field cannot be extracted"
    )
```

#### Output Schema

```python
class ExtractedField(BaseModel):
    name: str
    value: Any
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_location: dict | None = Field(default=None, description="Page and bounding box of source")

class ExtractionResult(BaseModel):
    document_id: str
    schema_name: str
    fields: list[ExtractedField]
    extraction_model_version: str
    extracted_at: datetime
    completeness: float = Field(..., ge=0.0, le=1.0, description="Fraction of schema fields extracted")
```

#### Preconditions
- `document_id` must reference a parsed document.
- `schema_name` must exist in the schema registry.
- The document must have text content.

#### Postconditions
- An `ExtractionResult` is returned with at least one field (unless `strict=True` and a required field is missing, which is a failure).
- Extracted fields are persisted in the document store.

#### Failure Modes
| Error Code | Condition | Retryable |
|---|---|---|
| `NOT_FOUND` | `document_id` or `schema_name` not found | No |
| `VALIDATION_ERROR` | `strict=True` and required field missing | No |
| `PARSE_ERROR` | Document text is unextractable | No |
| `EXTERNAL_SERVICE_ERROR` | Extraction model unavailable | Yes |
| `TIMEOUT_ERROR` | Extraction exceeds 60 seconds | Yes |

#### Retry Policy
- **Max retries:** 2
- **Backoff:** Exponential, base=2s, max=20s
- **Retryable errors:** `EXTERNAL_SERVICE_ERROR`, `TIMEOUT_ERROR`

#### Idempotency
- **Idempotent:** Yes, by `document_id` + `schema_name`.
- Re-extraction with the same parameters returns the cached result.

#### Unit Test Requirements
- Verify extraction with each registered schema.
- Verify `strict=True` raises `VALIDATION_ERROR` when required field is missing.
- Verify `source_location` is populated.
- Verify `completeness` calculation.

#### Integration Test Requirements
- End-to-end: parse → extract → verify fields stored.
- Verify schema registry lookup.
- Verify extraction with real ML model.

---

### 4. search_documents

**Purpose:** Performs semantic search over the document corpus, returning the most relevant documents or chunks for a given query.

#### Input Schema

```python
class SearchDocumentsInput(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language search query"
    )
    filters: dict = Field(
        default_factory=dict,
        description="Metadata filters: {field: value} or {field: {operator: value}}"
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of results to return"
    )
```

#### Output Schema

```python
class SearchChunk(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    metadata: dict = Field(default_factory=dict)

class SearchResults(BaseModel):
    query: str
    results: list[SearchChunk]
    total_matches: int = Field(..., ge=0)
    search_duration_ms: int = Field(..., ge=0)
    searched_at: datetime
```

#### Preconditions
- The vector index must be available and populated.
- `filters` keys must be valid metadata fields.

#### Postconditions
- A `SearchResults` with up to `top_k` results is returned.
- Results are sorted by `score` descending.

#### Failure Modes
| Error Code | Condition | Retryable |
|---|---|---|
| `VALIDATION_ERROR` | Invalid filter field | No |
| `EXTERNAL_SERVICE_ERROR` | Vector index unavailable | Yes |
| `TIMEOUT_ERROR` | Search exceeds 15 seconds | Yes |

#### Retry Policy
- **Max retries:** 3
- **Backoff:** Exponential, base=0.5s, max=5s
- **Retryable errors:** `EXTERNAL_SERVICE_ERROR`, `TIMEOUT_ERROR`

#### Idempotency
- **Idempotent:** Yes, by `query` + `filters` + `top_k`.
- Cached results are returned if the index has not been updated since the last search.

#### Unit Test Requirements
- Verify search returns correct number of results.
- Verify results are sorted by score.
- Verify filters narrow results.
- Verify `top_k` boundary (1 and 100).

#### Integration Test Requirements
- End-to-end: index documents → search → verify relevant results.
- Verify vector index integration.
- Verify cache hit on repeated search.

---

### 5. rerank_evidence

**Purpose:** Re-scores a set of candidate chunks against a query using a cross-encoder model for higher precision ranking.

#### Input Schema

```python
class RerankEvidenceInput(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The original user query"
    )
    candidate_chunks: list[SearchChunk] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Candidate chunks from search_documents to rerank"
    )
```

#### Output Schema

```python
class RerankedChunk(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    original_score: float = Field(..., ge=0.0, le=1.0)
    reranked_score: float = Field(..., ge=0.0, le=1.0)
    rank: int = Field(..., ge=1)

class RerankResults(BaseModel):
    query: str
    results: list[RerankedChunk]
    rerank_model_version: str
    rerank_duration_ms: int = Field(..., ge=0)
    reranked_at: datetime
```

#### Preconditions
- `candidate_chunks` must contain at least 1 chunk.
- Cross-encoder model service must be available.

#### Postconditions
- A `RerankResults` with the same chunks re-ordered by `reranked_score` is returned.
- Each chunk has both `original_score` and `reranked_score`.

#### Failure Modes
| Error Code | Condition | Retryable |
|---|---|---|
| `VALIDATION_ERROR` | Empty candidate list | No |
| `EXTERNAL_SERVICE_ERROR` | Cross-encoder model unavailable | Yes |
| `TIMEOUT_ERROR` | Reranking exceeds 20 seconds | Yes |

#### Retry Policy
- **Max retries:** 2
- **Backoff:** Exponential, base=1s, max=10s
- **Retryable errors:** `EXTERNAL_SERVICE_ERROR`, `TIMEOUT_ERROR`

#### Idempotency
- **Not idempotent** in the strict sense — model state may change.
- No caching applied.

#### Unit Test Requirements
- Verify reranking reorders chunks.
- Verify `reranked_score` is in [0, 1].
- Verify `rank` is sequential starting at 1.
- Verify `VALIDATION_ERROR` for empty input.

#### Integration Test Requirements
- End-to-end: search → rerank → verify ordering improves relevance.
- Verify cross-encoder model integration.

---

### 6. compile_context_pack

**Purpose:** Assembles the top evidence chunks into a structured context pack suitable for LLM consumption, with source attribution and deduplication.

#### Input Schema

```python
class CompileContextPackInput(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The original user query"
    )
    evidence_chunks: list[RerankedChunk] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Top evidence chunks after reranking"
    )
    max_tokens: int = Field(
        default=4000,
        ge=500,
        le=32000,
        description="Maximum token budget for the context pack"
    )
```

#### Output Schema

```python
class ContextChunk(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    source_reference: str = Field(..., description="Human-readable source citation")
    relevance_score: float = Field(..., ge=0.0, le=1.0)

class ContextPack(BaseModel):
    query: str
    chunks: list[ContextChunk]
    total_tokens: int = Field(..., ge=0, le=32000)
    documents_represented: list[str] = Field(..., description="Unique document IDs included")
    compiled_at: datetime
```

#### Preconditions
- `evidence_chunks` must contain at least 1 chunk.
- Token counter must be available.

#### Postconditions
- A `ContextPack` with deduplicated, token-budgeted chunks is returned.
- `total_tokens` does not exceed `max_tokens`.
- Source references are formatted and included.

#### Failure Modes
| Error Code | Condition | Retryable |
|---|---|---|
| `VALIDATION_ERROR` | Empty evidence list | No |
| `INTERNAL_ERROR` | Token counter failure | Yes |

#### Retry Policy
- **Max retries:** 1
- **Backoff:** Fixed, 1s
- **Retryable errors:** `INTERNAL_ERROR`

#### Idempotency
- **Idempotent:** Yes, given the same input.
- No caching applied (cheap operation).

#### Unit Test Requirements
- Verify token budget is respected.
- Verify deduplication of chunks from the same document.
- Verify source reference formatting.
- Verify `VALIDATION_ERROR` for empty input.

#### Integration Test Requirements
- End-to-end: rerank → compile → verify context pack is LLM-ready.
- Verify token counting accuracy.

---

### 7. detect_risks

**Purpose:** Analyzes a document and its evidence to identify potential risks, compliance issues, or red flags.

#### Input Schema

```python
class DetectRisksInput(BaseModel):
    document_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique identifier for the document"
    )
    evidence: list[ContextChunk] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Evidence chunks for risk analysis"
    )
    risk_categories: list[str] | None = Field(
        default=None,
        description="Optional filter: only detect risks in these categories"
    )
```

#### Output Schema

```python
class RiskItem(BaseModel):
    risk_id: str = Field(..., description="Unique risk identifier")
    category: str = Field(..., description="Risk category: financial, legal, compliance, operational")
    severity: str = Field(..., pattern=r"^(low|medium|high|critical)$")
    description: str = Field(..., min_length=1)
    evidence_chunk_ids: list[str] = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    recommendation: str | None = None

class RiskDetectionResult(BaseModel):
    document_id: str
    risks: list[RiskItem]
    total_risks: int = Field(..., ge=0)
    severity_counts: dict[str, int] = Field(..., description="Count per severity level")
    detection_model_version: str
    detected_at: datetime
```

#### Preconditions
- `document_id` must reference a parsed document.
- `evidence` must contain at least one chunk.
- If `risk_categories` is provided, each must be a valid category.

#### Postconditions
- A `RiskDetectionResult` with zero or more risks is returned.
- Each risk is linked to at least one evidence chunk.
- Severity counts are consistent with the risks list.

#### Failure Modes
| Error Code | Condition | Retryable |
|---|---|---|
| `NOT_FOUND` | `document_id` not found | No |
| `VALIDATION_ERROR` | Empty evidence or invalid category | No |
| `EXTERNAL_SERVICE_ERROR` | Risk detection model unavailable | Yes |
| `TIMEOUT_ERROR` | Detection exceeds 45 seconds | Yes |

#### Retry Policy
- **Max retries:** 2
- **Backoff:** Exponential, base=2s, max=20s
- **Retryable errors:** `EXTERNAL_SERVICE_ERROR`, `TIMEOUT_ERROR`

#### Idempotency
- **Idempotent:** Yes, by `document_id` + evidence hash.
- Cache invalidated when evidence changes.

#### Unit Test Requirements
- Verify risk detection returns valid `RiskItem` objects.
- Verify severity counts match risks list.
- Verify `evidence_chunk_ids` reference actual chunks.
- Verify `risk_categories` filter works.
- Verify `VALIDATION_ERROR` for empty evidence.

#### Integration Test Requirements
- End-to-end: parse → search → rerank → compile → detect risks → verify risks stored.
- Verify risk model integration.

---

### 8. generate_checklist

**Purpose:** Generates an actionable checklist from detected risks, suitable for human review and task tracking.

#### Input Schema

```python
class GenerateChecklistInput(BaseModel):
    document_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique identifier for the document"
    )
    risk_items: list[RiskItem] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Risk items to convert into checklist actions"
    )
    priority_order: str = Field(
        default="severity",
        pattern=r"^(severity|confidence|category)$",
        description="How to order checklist items"
    )
```

#### Output Schema

```python
class ChecklistItem(BaseModel):
    checklist_id: str = Field(..., description="Unique checklist item identifier")
    risk_id: str = Field(..., description="Source risk ID")
    action: str = Field(..., min_length=1, description="Actionable task description")
    priority: str = Field(..., pattern=r"^(low|medium|high|critical)$")
    assignee_role: str | None = Field(default=None, description="Suggested role for assignment")
    due_days: int | None = Field(default=None, ge=1, description="Suggested days until due")
    status: str = Field(default="pending", pattern=r"^(pending|in_progress|completed|dismissed)$")

class ChecklistResult(BaseModel):
    document_id: str
    checklist: list[ChecklistItem]
    total_items: int = Field(..., ge=1)
    priority_order: str
    generated_at: datetime
```

#### Preconditions
- `document_id` must reference an existing document.
- `risk_items` must contain at least one valid `RiskItem`.
- `priority_order` must be one of the allowed values.

#### Postconditions
- A `ChecklistResult` with one checklist item per risk is returned.
- Checklist items are ordered according to `priority_order`.
- Each checklist item links back to its source `risk_id`.

#### Failure Modes
| Error Code | Condition | Retryable |
|---|---|---|
| `NOT_FOUND` | `document_id` not found | No |
| `VALIDATION_ERROR` | Empty risk_items or invalid priority_order | No |
| `INTERNAL_ERROR` | Checklist generation logic failure | Yes |

#### Retry Policy
- **Max retries:** 1
- **Backoff:** Fixed, 2s
- **Retryable errors:** `INTERNAL_ERROR`

#### Idempotency
- **Idempotent:** Yes, by `document_id` + risk items hash.
- Same risks always produce the same checklist.

#### Unit Test Requirements
- Verify one checklist item per risk item.
- Verify ordering by each `priority_order` option.
- Verify `status` defaults to `pending`.
- Verify `VALIDATION_ERROR` for empty risk_items.

#### Integration Test Requirements
- End-to-end: detect risks → generate checklist → verify checklist stored.
- Verify checklist items are actionable and well-formed.

---

### 9. create_task

**Purpose:** Creates a task in the task management system, typically triggered by a checklist item or manual agent action.

#### Input Schema

```python
class CreateTaskInput(BaseModel):
    task_payload: dict = Field(
        ...,
        description="Task details: title, description, assignee, due_date, priority, tags"
    )
    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Client-generated idempotency key to prevent duplicate task creation"
    )

    @field_validator("task_payload")
    @classmethod
    def validate_payload(cls, v: dict) -> dict:
        required = {"title", "description"}
        missing = required - set(v.keys())
        if missing:
            raise ValueError(f"Missing required fields in task_payload: {missing}")
        if len(v.get("title", "")) > 500:
            raise ValueError("title must be <= 500 characters")
        return v
```

#### Output Schema

```python
class TaskResult(BaseModel):
    task_id: str = Field(..., description="Unique task identifier assigned by the system")
    title: str
    status: str = Field(default="open", pattern=r"^(open|in_progress|done|cancelled)$")
    created_at: datetime
    idempotency_key: str
```

#### Preconditions
- `task_payload` must contain `title` and `description`.
- `idempotency_key` must be unique for new tasks (or match an existing task for idempotent replay).

#### Postconditions
- A `TaskResult` with a valid `task_id` is returned.
- The task is persisted in the task management system.
- The task status is `open`.

#### Failure Modes
| Error Code | Condition | Retryable |
|---|---|---|
| `VALIDATION_ERROR` | Missing required fields in payload | No |
| `IDEMPOTENCY_CONFLICT` | Same key used with different payload | No |
| `EXTERNAL_SERVICE_ERROR` | Task management system unavailable | Yes |
| `TIMEOUT_ERROR` | Creation exceeds 10 seconds | Yes |

#### Retry Policy
- **Max retries:** 3
- **Backoff:** Exponential, base=1s, max=10s
- **Retryable errors:** `EXTERNAL_SERVICE_ERROR`, `TIMEOUT_ERROR`

#### Idempotency
- **Idempotent:** Yes, by `idempotency_key`.
- If the same `idempotency_key` is submitted with the same payload, the existing `TaskResult` is returned.
- If the same `idempotency_key` is submitted with a different payload, `IDEMPOTENCY_CONFLICT` is raised.

#### Unit Test Requirements
- Verify task creation with valid payload.
- Verify `VALIDATION_ERROR` for missing `title` or `description`.
- Verify idempotent replay returns same result.
- Verify `IDEMPOTENCY_CONFLICT` for key reuse with different payload.

#### Integration Test Requirements
- End-to-end: create task → verify task exists in task management system.
- Verify idempotency across retries.

---

### 10. save_extracted_fields

**Purpose:** Persists extracted fields from a document into the structured data store, enabling downstream queries and reporting.

#### Input Schema

```python
class SaveExtractedFieldsInput(BaseModel):
    document_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique identifier for the document"
    )
    fields: dict[str, Any] = Field(
        ...,
        min_length=1,
        description="Map of field_name → extracted_value to persist"
    )
    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Client-generated idempotency key"
    )
```

#### Output Schema

```python
class SaveResult(BaseModel):
    document_id: str
    fields_saved: int = Field(..., ge=1)
    save_id: str = Field(..., description="Unique ID for this save operation")
    saved_at: datetime
    idempotency_key: str
```

#### Preconditions
- `document_id` must reference an existing document.
- `fields` must contain at least one key-value pair.
- `idempotency_key` must be unique for new saves.

#### Postconditions
- All fields are persisted in the structured data store.
- A `SaveResult` is returned with `fields_saved` matching the input count.
- The document's `last_extracted_at` timestamp is updated.

#### Failure Modes
| Error Code | Condition | Retryable |
|---|---|---|
| `NOT_FOUND` | `document_id` not found | No |
| `VALIDATION_ERROR` | Empty fields dict | No |
| `IDEMPOTENCY_CONFLICT` | Same key used with different fields | No |
| `EXTERNAL_SERVICE_ERROR` | Data store unavailable | Yes |
| `TIMEOUT_ERROR` | Save exceeds 10 seconds | Yes |

#### Retry Policy
- **Max retries:** 3
- **Backoff:** Exponential, base=1s, max=10s
- **Retryable errors:** `EXTERNAL_SERVICE_ERROR`, `TIMEOUT_ERROR`

#### Idempotency
- **Idempotent:** Yes, by `idempotency_key`.
- Same key + same fields returns the existing `SaveResult`.
- Same key + different fields raises `IDEMPOTENCY_CONFLICT`.

#### Unit Test Requirements
- Verify fields are saved correctly.
- Verify `VALIDATION_ERROR` for empty fields.
- Verify idempotent replay returns same result.
- Verify `IDEMPOTENCY_CONFLICT` for key reuse with different fields.

#### Integration Test Requirements
- End-to-end: extract fields → save → verify fields queryable in data store.
- Verify idempotency across retries.

---

### 11. generate_report

**Purpose:** Generates a structured report from a document's extracted data, risks, and checklist, formatted for human consumption.

#### Input Schema

```python
class GenerateReportInput(BaseModel):
    document_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique identifier for the document"
    )
    report_type: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Type of report to generate: summary, risk_assessment, compliance, full"
    )
    include_sections: list[str] | None = Field(
        default=None,
        description="Optional list of sections to include. If None, includes all default sections."
    )
```

#### Output Schema

```python
class ReportSection(BaseModel):
    section_id: str
    title: str
    content: str = Field(..., min_length=1)
    section_type: str = Field(..., description="text, table, list, chart")

class ReportResult(BaseModel):
    report_id: str = Field(..., description="Unique report identifier")
    document_id: str
    report_type: str
    title: str
    sections: list[ReportSection]
    total_sections: int = Field(..., ge=1)
    generated_at: datetime
    generation_duration_ms: int = Field(..., ge=0)
```

#### Preconditions
- `document_id` must reference an existing document.
- `report_type` must be in the set of supported report types.
- If `include_sections` is provided, each must be a valid section ID for the report type.

#### Postconditions
- A `ReportResult` with at least one section is returned.
- The report is persisted in the report store.
- The report can be exported via `export_report`.

#### Failure Modes
| Error Code | Condition | Retryable |
|---|---|---|
| `NOT_FOUND` | `document_id` or `report_type` not found | No |
| `VALIDATION_ERROR` | Invalid section in `include_sections` | No |
| `INTERNAL_ERROR` | Report generation logic failure | Yes |
| `TIMEOUT_ERROR` | Generation exceeds 60 seconds | Yes |

#### Retry Policy
- **Max retries:** 2
- **Backoff:** Exponential, base=2s, max=20s
- **Retryable errors:** `INTERNAL_ERROR`, `TIMEOUT_ERROR`

#### Idempotency
- **Idempotent:** Yes, by `document_id` + `report_type`.
- Same parameters return the cached report if the underlying data has not changed.

#### Unit Test Requirements
- Verify report generation for each `report_type`.
- Verify `include_sections` filters correctly.
- Verify each section has non-empty content.
- Verify `VALIDATION_ERROR` for invalid section.

#### Integration Test Requirements
- End-to-end: full pipeline → generate report → verify report stored.
- Verify report content reflects extracted data and risks.

---

### 12. export_report

**Purpose:** Exports a generated report into a specified file format (PDF, DOCX, HTML, Markdown).

#### Input Schema

```python
class ExportReportInput(BaseModel):
    report_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique identifier for the report to export"
    )
    format: str = Field(
        ...,
        pattern=r"^(pdf|docx|html|markdown)$",
        description="Target export format"
    )
    template: str | None = Field(
        default=None,
        description="Optional template name for formatting"
    )
```

#### Output Schema

```python
class ExportResult(BaseModel):
    report_id: str
    format: str
    file_path: str = Field(..., description="Path to the exported file")
    file_size_bytes: int = Field(..., ge=0)
    export_id: str = Field(..., description="Unique export operation identifier")
    exported_at: datetime
    export_duration_ms: int = Field(..., ge=0)
```

#### Preconditions
- `report_id` must reference an existing generated report.
- `format` must be one of: `pdf`, `docx`, `html`, `markdown`.
- If `template` is provided, it must exist in the template registry.

#### Postconditions
- An `ExportResult` with a valid `file_path` is returned.
- The exported file exists at `file_path` and is non-empty.
- The file size matches `file_size_bytes`.

#### Failure Modes
| Error Code | Condition | Retryable |
|---|---|---|
| `NOT_FOUND` | `report_id` or `template` not found | No |
| `VALIDATION_ERROR` | Invalid format | No |
| `INTERNAL_ERROR` | Export/rendering failure | Yes |
| `TIMEOUT_ERROR` | Export exceeds 120 seconds | Yes |

#### Retry Policy
- **Max retries:** 2
- **Backoff:** Exponential, base=3s, max=30s
- **Retryable errors:** `INTERNAL_ERROR`, `TIMEOUT_ERROR`

#### Idempotency
- **Idempotent:** Yes, by `report_id` + `format`.
- Same parameters return the cached export if the report has not changed.

#### Unit Test Requirements
- Verify export in each supported format.
- Verify exported file exists and is non-empty.
- Verify `file_size_bytes` matches actual file size.
- Verify `NOT_FOUND` for invalid `report_id`.
- Verify template application when `template` is provided.

#### Integration Test Requirements
- End-to-end: generate report → export → verify file accessible.
- Verify export in each format produces valid output.
- Verify template rendering.

---

## Appendix A: Common Pydantic Validators

```python
from pydantic import field_validator

class DocumentIdMixin:
    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("document_id cannot be blank")
        return v.strip()

class IdempotencyKeyMixin:
    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("idempotency_key cannot be blank")
        return v.strip()
```

## Appendix B: Error Code Reference

| Code | HTTP Equivalent | Retryable | Description |
|---|---|---|---|
| `VALIDATION_ERROR` | 400 | No | Input failed schema or business validation |
| `NOT_FOUND` | 404 | No | Referenced resource does not exist |
| `PERMISSION_DENIED` | 403 | No | Insufficient permissions |
| `IDEMPOTENCY_CONFLICT` | 409 | No | Idempotency key reused with different payload |
| `PARSE_ERROR` | 422 | No | Document parsing failed |
| `TIMEOUT_ERROR` | 504 | Yes | Execution exceeded configured timeout |
| `RATE_LIMIT_ERROR` | 429 | Yes | Upstream rate limit hit |
| `EXTERNAL_SERVICE_ERROR` | 502 | Yes | External dependency unavailable |
| `INTERNAL_ERROR` | 500 | Yes | Unexpected internal failure |

## Appendix C: Test Coverage Matrix

| Tool | Unit Tests | Integration Tests | E2E Tests |
|---|---|---|---|
| `parse_document` | 6 | 4 | 2 |
| `classify_document` | 5 | 3 | 1 |
| `extract_fields` | 4 | 3 | 2 |
| `search_documents` | 4 | 3 | 1 |
| `rerank_evidence` | 4 | 2 | 1 |
| `compile_context_pack` | 4 | 2 | 1 |
| `detect_risks` | 5 | 2 | 1 |
| `generate_checklist` | 4 | 2 | 1 |
| `create_task` | 4 | 2 | 1 |
| `save_extracted_fields` | 4 | 2 | 1 |
| `generate_report` | 4 | 2 | 2 |
| `export_report` | 5 | 3 | 1 |
| **Total** | **53** | **30** | **15** |

---

## Appendix D: Tool Dependency Graph

```
parse_document
    └── classify_document
    └── extract_fields
            └── save_extracted_fields

search_documents
    └── rerank_evidence
            └── compile_context_pack
                    └── detect_risks
                            └── generate_checklist
                                    └── create_task

generate_report
    └── export_report
```

## Appendix E: Versioning Policy

- Tool contracts follow semantic versioning.
- Breaking changes (schema removal, type change) require a major version bump.
- Additive changes (new optional field) require a minor version bump.
- Bug fixes require a patch version bump.
- All versions are recorded in the tool registry metadata.
