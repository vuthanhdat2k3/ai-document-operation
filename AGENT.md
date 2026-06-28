# AGENT.md — AI Coding Agent Guide

## Project: AI Document Operations Agent

A production-grade system for processing enterprise documents end-to-end. Ingests PDFs, scanned images, Word docs, spreadsheets, and emails; extracts structured data; indexes into vector and relational stores; and exposes a conversational Q&A interface with full source grounding.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (async), Pydantic v2, Uvicorn |
| Orchestration | LangGraph (state machines for multi-step agent flows) |
| Relational DB | PostgreSQL 16 (SQLAlchemy 2 async, Alembic migrations) |
| Vector DB | Qdrant (embeddings, semantic search) |
| Cache / Queue | Redis 7 (caching, rate limiting, task queues via Celery) |
| LLM Providers | OpenAI GPT-4o, Anthropic Claude 3.5 Sonnet, local Ollama fallback |
| Frontend | Next.js 14 (TypeScript, App Router, Tailwind CSS) |
| Observability | OpenTelemetry, Structured JSON logging, Prometheus metrics |
| Infrastructure | Docker Compose, GitHub Actions CI |

---

## 1. Non-Negotiable Engineering Rules

These rules are absolute. Violations block PRs and must be fixed before merge.

| # | Rule |
|---|------|
| 1 | **Never implement without reading the relevant spec, schema, or interface contract first.** |
| 2 | **Never bypass validation to make a test pass.** Fix the code or the test, never weaken validation. |
| 3 | **Never call an external side-effect tool (LLM API, DB write, file storage, webhook) without an idempotency key.** |
| 4 | **Never commit if any test in the affected suite fails.** Run the suite, fix failures, then commit. |
| 5 | **Never introduce a new tool without a JSON Schema, at least one unit test, one integration test, and updated docs.** |
| 6 | **Never return ungrounded answers for document Q&A.** Every answer must cite source document IDs, page numbers, and relevant excerpts. |
| 7 | **Always add or update tests for every code change.** A PR with zero test changes is rejected unless it is docs-only. |
| 8 | **Always update docs when changing architecture, API contracts, tool contracts, or database schema.** |
| 9 | **Always run the relevant test suite after implementation and before committing.** |
| 10 | **Always prefer deterministic code over prompt-only behavior.** If logic can be expressed in code, do not rely on the LLM. |
| 11 | **Never hardcode secrets, API keys, tokens, or connection strings.** Use environment variables or a secrets manager. |
| 12 | **Never use `SELECT *` in production queries.** Always specify columns explicitly. |
| 13 | **Never mutate shared state inside an async function without proper locking.** |
| 14 | **Never swallow exceptions silently.** Log the error with context, then re-raise or return a structured error response. |
| 15 | **Never use `print()` for logging.** Use the project's structured logger (`app.core.logger`). |
| 16 | **Never add a new dependency without pinning the exact version in `pyproject.toml` or `package.json`.** |
| 17 | **Never skip input validation on API endpoints.** Every request body, query param, and path param must be validated via Pydantic. |
| 18 | **Never use synchronous blocking calls inside async handlers.** Use `asyncio.to_thread()` or async-native libraries. |
| 19 | **Never deploy without running the full test suite, linting, and type checking in CI.** |
| 20 | **Never leave dead code, commented-out code, or TODO comments in a merged PR.** |
| 21 | **Never allow an agent loop to run without a maximum iteration guard.** Default max: 10 iterations. |
| 22 | **Never trust LLM output without validation.** Parse, validate schema, and sanitize before use. |

---

## 2. Architecture Principles

### 2.1 Separation of Concerns

```
app/
├── api/            # FastAPI route handlers (thin — delegate to services)
├── core/           # Config, logging, security, dependencies
├── db/             # SQLAlchemy models, repositories, Alembic migrations
├── agents/         # LangGraph agent definitions, tools, state schemas
├── services/       # Business logic (orchestrates repos, agents, external APIs)
├── schemas/        # Pydantic request/response models
├── tools/          # Agent tool implementations (each with JSON Schema)
├── ingest/         # Document parsing, chunking, embedding pipelines
├── search/         # Qdrant queries, hybrid search, reranking
├── eval/           # Evaluation datasets, scorers, regression runners
└── tests/          # Mirrors app/ structure
```

- **API layer** handles HTTP concerns only: parsing, validation, auth, response formatting.
- **Service layer** contains all business logic. Services are injectable and testable.
- **Repository layer** wraps all database queries. No raw SQL in services.
- **Agent layer** defines LangGraph graphs. Tools are plain functions with JSON Schema.

### 2.2 Dependency Injection

Use FastAPI's `Depends()` for all service and repository dependencies. Never instantiate services directly inside route handlers.

### 2.3 Async-First

All I/O-bound code must be async. Use `sqlalchemy.ext.asyncio`, `httpx.AsyncClient`, `redis.asyncio`. Blocking code runs in `asyncio.to_thread()`.

### 2.4 Fail-Fast

Validate inputs at the boundary (API layer). Reject invalid requests with 422 and structured error bodies. Do not pass partial data into services hoping they will handle it.

### 2.5 Idempotency

Every operation that writes data or calls an external service must be idempotent. Use idempotency keys stored in Redis with a 24-hour TTL. If a duplicate key is detected, return the cached result.

### 2.6 Observability

Every request gets a `request_id` (UUID). Every log line includes `request_id`, `user_id`, `operation`. Use OpenTelemetry spans for distributed tracing.

---

## 3. Coding Standards

### 3.1 Python

- **Python version**: 3.11+
- **Formatter**: `ruff format` (line length 100)
- **Linter**: `ruff check --select ALL`
- **Type checker**: `mypy --strict`
- **All functions must have type annotations** for parameters and return values.
- **Use `dataclass` or Pydantic `BaseModel`** for structured data. Never use raw dicts for internal data passing.
- **Prefer `pathlib.Path`** over `os.path`.
- **Use `enum.Enum`** for fixed sets of values. Never use magic strings.

```python
# Good
from enum import Enum

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

async def get_document(doc_id: str, db: AsyncSession) -> Document:
    ...

# Bad
def get_document(doc_id, db):
    ...
```

### 3.2 TypeScript (Frontend)

- **TypeScript version**: 5.x with strict mode
- **Formatter**: Prettier
- **Linter**: ESLint with `@typescript-eslint/recommended`
- **No `any` type.** Use `unknown` and narrow with type guards.
- **Use Zod** for runtime validation of API responses.
- **Prefer named exports** over default exports.

### 3.3 Naming Conventions

| Context | Convention | Example |
|---------|-----------|---------|
| Python functions/methods | snake_case | `process_document()` |
| Python classes | PascalCase | `DocumentProcessor` |
| Python constants | UPPER_SNAKE_CASE | `MAX_CHUNK_SIZE` |
| TypeScript functions | camelCase | `fetchDocuments()` |
| TypeScript components | PascalCase | `DocumentCard` |
| Database tables | snake_case, plural | `document_chunks` |
| Database columns | snake_case | `created_at` |
| API endpoints | kebab-case, plural | `POST /api/v1/documents` |
| Environment variables | UPPER_SNAKE_CASE | `DATABASE_URL` |

### 3.4 Import Order

```python
# 1. Standard library
import asyncio
import uuid
from pathlib import Path

# 2. Third-party
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

# 3. Project modules
from app.core.config import settings
from app.db.repositories.document import DocumentRepository
from app.schemas.document import DocumentCreate, DocumentResponse
```

### 3.5 Error Handling

```python
from app.core.exceptions import (
    AppError,
    NotFoundError,
    ValidationError,
    ExternalServiceError,
)

async def process_document(doc_id: str) -> Document:
    doc = await repo.get(doc_id)
    if doc is None:
        raise NotFoundError(f"Document {doc_id} not found")

    try:
        result = await llm_client.extract(doc.content)
    except httpx.HTTPStatusError as e:
        raise ExternalServiceError(
            service="openai",
            status_code=e.response.status_code,
            detail=str(e),
        ) from e

    return result
```

- **Define custom exception classes** in `app/core/exceptions.py`.
- **Map exceptions to HTTP status codes** in a global exception handler.
- **Always include enough context** in error messages to diagnose the issue.

---

## 4. Testing Rules

### 4.1 Test Pyramid

```
        /  Eval  \          <- LLM quality evaluations (weekly + on-change)
       / Contract \         <- API contract tests (every PR)
      / Integration\       <- DB, Redis, Qdrant integration tests (every PR)
     /    Unit Tests \     <- Pure logic, mocked dependencies (every commit)
    /__________________\
```

### 4.2 Unit Tests

- **Location**: `tests/unit/`
- **Naming**: `test_<module>.py`
- **Pattern**: `test_<function>_<scenario>_<expected_result>`
- **Mock all external dependencies**: DB, Redis, LLM APIs, file system.
- **Every branch must be covered.** Minimum 90% line coverage for new code.
- **Run**: `pytest tests/unit/ -v --cov=app --cov-report=term-missing`

```python
async def test_process_document_when_not_found_raises_error():
    repo = MockDocumentRepository(get_return=None)
    service = DocumentService(repo=repo)

    with pytest.raises(NotFoundError, match="Document doc-123 not found"):
        await service.process_document("doc-123")
```

### 4.3 Integration Tests

- **Location**: `tests/integration/`
- **Use testcontainers** for PostgreSQL, Redis, and Qdrant.
- **Each test gets a clean database** via transaction rollback after test.
- **Test real database queries, real Redis caching, real Qdrant upsert.**
- **Run**: `pytest tests/integration/ -v --timeout=60`

### 4.4 Evaluation Tests

- **Location**: `tests/eval/`
- **Golden datasets** in `tests/eval/datasets/` (JSON files).
- **Each eval case**: input query, expected answer, expected source citations, minimum score.
- **Scorers**: exact match, semantic similarity (embedding cosine), citation accuracy.
- **Run on every PR that touches agent logic or tools.**
- **Run**: `pytest tests/eval/ -v --eval-threshold=0.85`

### 4.5 Contract Tests

- **Location**: `tests/contract/`
- **Verify API request/response schemas** match the OpenAPI spec.
- **Use `schemathesis`** for property-based API testing.
- **Run**: `pytest tests/contract/ -v`

### 4.6 Regression Tests

- **When a bug is found**, add a regression test before fixing.
- **Regression tests are permanent.** Never delete them.
- **Location**: `tests/regression/`

---

## 5. Commit Rules

### 5.1 Conventional Commits

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Types**: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `ci`, `build`

**Scopes**: `api`, `agent`, `db`, `ingest`, `search`, `eval`, `frontend`, `infra`

**Examples**:
```
feat(agent): add document summarization tool with JSON Schema validation
fix(api): return 404 instead of 500 when document not found
test(eval): add golden dataset for financial document Q&A
docs(agent): update tool contract for new extract_entities parameters
```

### 5.2 Commit Checklist

- [ ] All tests in affected suites pass locally
- [ ] No linting errors (`ruff check`)
- [ ] No type errors (`mypy --strict`)
- [ ] No formatting issues (`ruff format --check`)
- [ ] New code has tests
- [ ] Docs updated if architecture/API/schema changed
- [ ] No secrets or credentials in the diff
- [ ] Commit message follows conventional commits format

---

## 6. Documentation Update Rules

Update docs **immediately** when:

| Change Type | Update |
|-------------|--------|
| New API endpoint | `docs/api/` OpenAPI spec + `docs/api/<resource>.md` |
| New agent tool | `docs/tools/<tool-name>.md` with schema, examples, error cases |
| Database schema change | `docs/schema/` ER diagram + migration notes |
| Architecture change | `docs/architecture/` diagrams + ADR |
| New environment variable | `docs/config/environment.md` |
| New dependency | `docs/setup/dependencies.md` |
| Breaking change | `docs/migration/<version>.md` upgrade guide |

---

## 7. Security Rules

1. **No secrets in code.** All secrets live in environment variables or a secrets manager (AWS Secrets Manager, HashiCorp Vault).
2. **No secrets in logs.** Redact API keys, tokens, passwords from all log output.
3. **No secrets in git history.** Use `git-secrets` or `detect-secrets` as a pre-commit hook.
4. **Validate and sanitize all user input.** Never trust client-side data.
5. **Use parameterized queries.** Never construct SQL with string concatenation.
6. **Rate limit all public endpoints.** Use Redis-backed rate limiting.
7. **Authenticate all API endpoints** except explicitly public ones. Use JWT with short-lived access tokens and refresh token rotation.
8. **Authorize at the service layer.** Check permissions before executing business logic.
9. **Encrypt data at rest** (PostgreSQL TDE, encrypted S3 buckets).
10. **Use HTTPS everywhere.** No plain HTTP in any environment.
11. **Scan dependencies for vulnerabilities** (`pip-audit`, `npm audit`) in CI.
12. **Principle of least privilege** for all service accounts and API keys.

---

## 8. LLM / Agent Safety Rules

### 8.1 Grounding

- **Every document Q&A answer must include citations**: document ID, page number, paragraph/section, and the exact text excerpt.
- **If the answer cannot be grounded in the provided documents, say "I don't have enough information to answer this based on the available documents."** Never fabricate.
- **Confidence scores are required.** Return a float 0.0–1.0. Answers below 0.5 confidence must include a disclaimer.

### 8.2 Output Validation

- **Parse all LLM output.** Use Pydantic models with `model_validate_json()`.
- **If parsing fails, retry once with a stricter prompt.** If it fails again, return an error to the user.
- **Never execute raw LLM output as code or commands.**

### 8.3 Tool Execution

- **Validate tool input against its JSON Schema before execution.**
- **Every tool call requires an idempotency key** (UUID v4 generated by the orchestrator).
- **Log every tool invocation**: tool name, input hash, output hash, duration, success/failure.
- **Tool timeouts**: default 30 seconds, configurable per tool. Hard max: 120 seconds.

### 8.4 Loop Guards

- **Maximum agent iterations**: 10 (configurable via `MAX_AGENT_ITERATIONS` env var).
- **If the loop limit is hit, terminate gracefully**, log the full trace, and return a partial result with a warning.
- **Detect and break infinite loops**: if the same tool is called with the same input more than 2 consecutive times, break.

### 8.5 Prompt Injection Defense

- **Sanitize all user input** before including in prompts. Strip control characters, limit length to 10,000 chars.
- **Use system prompts that instruct the model to ignore adversarial instructions.**
- **Never expose raw system prompts to the user.**

### 8.6 Cost Control

- **Track token usage per request.** Log input tokens, output tokens, estimated cost.
- **Set per-request token budgets.** Default: 8,000 input tokens, 4,000 output tokens.
- **Set daily spending caps** in the LLM provider dashboard and in application code.
- **Use cheaper models for simple tasks** (classification, extraction) and expensive models only for complex reasoning.

---

## 9. Definition of Done

A feature is done when **all** of the following are true:

- [ ] Implementation matches the spec/requirements
- [ ] All unit tests pass (`pytest tests/unit/`)
- [ ] All integration tests pass (`pytest tests/integration/`)
- [ ] All contract tests pass (`pytest tests/contract/`)
- [ ] New code has >= 90% line coverage
- [ ] No linting errors (`ruff check --select ALL`)
- [ ] No type errors (`mypy --strict`)
- [ ] Code is formatted (`ruff format`)
- [ ] API endpoints documented in OpenAPI spec
- [ ] Tool contracts documented in `docs/tools/`
- [ ] Database migrations are reversible
- [ ] No secrets in code, logs, or git diff
- [ ] Structured logging for all operations
- [ ] Error responses follow the standard error schema
- [ ] Performance: API responses < 500ms (p95) for non-LLM endpoints
- [ ] Commit message follows conventional commits
- [ ] PR description includes: what changed, why, how to test
- [ ] **Docker images rebuilt và containers restart** để áp dụng thay đổi (xem mục 15)

---

## 10. How to Implement a New Feature

1. **Read the spec.** Find the relevant spec in `docs/specs/` or the GitHub issue. Understand the requirements completely before writing any code.

2. **Create a branch.** `git checkout -b feat/<scope>-<short-description>`

3. **Design the data model** (if applicable):
   - Define or update SQLAlchemy models in `app/db/models/`
   - Create an Alembic migration: `alembic revision --autogenerate -m "add <table>"`
   - Define Pydantic schemas in `app/schemas/`
   - Add repository in `app/db/repositories/`

4. **Implement the service layer** in `app/services/`:
   - Define the interface (what methods, what inputs/outputs)
   - Implement business logic
   - Handle errors with custom exceptions

5. **Implement the API endpoint** (if applicable):
   - Add route in `app/api/v1/`
   - Use Pydantic models for request/response validation
   - Add authentication/authorization via dependencies
   - Register the router in `app/api/v1/router.py`

6. **Implement the agent tool** (if applicable):
   - See "How to Add a New Tool" below

7. **Write tests**:
   - Unit tests in `tests/unit/` (mock external dependencies)
   - Integration tests in `tests/integration/` (real DB/Redis/Qdrant)
   - Contract tests in `tests/contract/` (API schema validation)

8. **Run tests locally**:
   ```bash
   pytest tests/unit/ tests/integration/ tests/contract/ -v
   ```

9. **Run linting and type checking**:
   ```bash
   ruff check --select ALL app/ tests/
   ruff format --check app/ tests/
   mypy --strict app/
   ```

10. **Update documentation**:
    - API docs if you added/changed endpoints
    - Tool docs if you added/changed tools
    - Schema docs if you changed the database
    - Architecture docs if you changed the system design

11. **Commit and push**:
    ```bash
    git add .
    git commit -m "feat(<scope>): <description>"
    git push origin feat/<scope>-<short-description>
    ```

12. **Open a PR** with a description that includes: what changed, why, how to test, and any migration steps.

---

## 11. How to Add a New Tool

### Step 1: Define the Tool Schema

Create a JSON Schema file at `app/tools/schemas/<tool_name>.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "summarize_document",
  "description": "Generate a concise summary of a document",
  "type": "object",
  "properties": {
    "document_id": {
      "type": "string",
      "description": "The unique identifier of the document to summarize"
    },
    "max_length": {
      "type": "integer",
      "default": 500,
      "minimum": 50,
      "maximum": 5000,
      "description": "Maximum length of the summary in words"
    },
    "style": {
      "type": "string",
      "enum": ["bullet_points", "paragraph", "executive"],
      "default": "paragraph",
      "description": "Output format style"
    }
  },
  "required": ["document_id"],
  "additionalProperties": false
}
```

### Step 2: Implement the Tool

Create `app/tools/<tool_name>.py`:

```python
from app.core.logger import logger
from app.tools.base import BaseTool, ToolResult
from app.tools.schemas import load_schema
from app.db.repositories.document import DocumentRepository
from app.services.llm import LLMService

class SummarizeDocumentTool(BaseTool):
    name = "summarize_document"
    description = "Generate a concise summary of a document"
    schema = load_schema("summarize_document")

    def __init__(
        self,
        doc_repo: DocumentRepository,
        llm_service: LLMService,
    ) -> None:
        self._doc_repo = doc_repo
        self._llm_service = llm_service

    async def execute(
        self,
        document_id: str,
        max_length: int = 500,
        style: str = "paragraph",
        idempotency_key: str | None = None,
    ) -> ToolResult:
        logger.info(
            "tool.execute",
            tool=self.name,
            document_id=document_id,
            idempotency_key=idempotency_key,
        )

        doc = await self._doc_repo.get(document_id)
        if doc is None:
            return ToolResult(
                success=False,
                error=f"Document {document_id} not found",
            )

        summary = await self._llm_service.summarize(
            content=doc.content,
            max_length=max_length,
            style=style,
        )

        return ToolResult(
            success=True,
            data={
                "document_id": document_id,
                "summary": summary,
                "word_count": len(summary.split()),
            },
        )
```

### Step 3: Register the Tool

Add to `app/tools/registry.py`:

```python
from app.tools.summarize_document import SummarizeDocumentTool

TOOL_REGISTRY: dict[str, type[BaseTool]] = {
    ...
    "summarize_document": SummarizeDocumentTool,
}
```

### Step 4: Write Tests

**Unit test** (`tests/unit/tools/test_summarize_document.py`):

```python
async def test_summarize_document_success():
    doc_repo = MockDocumentRepository(get_return=Document(id="doc-1", content="Test content"))
    llm_service = MockLLMService(summarize_return="This is a summary.")
    tool = SummarizeDocumentTool(doc_repo=doc_repo, llm_service=llm_service)

    result = await tool.execute(document_id="doc-1", idempotency_key="key-123")

    assert result.success is True
    assert result.data["summary"] == "This is a summary."

async def test_summarize_document_not_found():
    doc_repo = MockDocumentRepository(get_return=None)
    llm_service = MockLLMService()
    tool = SummarizeDocumentTool(doc_repo=doc_repo, llm_service=llm_service)

    result = await tool.execute(document_id="nonexistent", idempotency_key="key-456")

    assert result.success is False
    assert "not found" in result.error
```

**Integration test** (`tests/integration/tools/test_summarize_document.py`):

```python
async def test_summarize_document_with_real_db(db_session, qdrant_client):
    # Seed database
    doc_repo = DocumentRepository(db_session)
    await doc_repo.create(DocumentCreate(content="Financial report Q3 2024..."))

    # Execute tool
    tool = SummarizeDocumentTool(doc_repo=doc_repo, llm_service=real_llm_service)
    result = await tool.execute(document_id="doc-1", idempotency_key="integ-key-1")

    assert result.success is True
    assert len(result.data["summary"]) > 0
```

### Step 5: Write Documentation

Create `docs/tools/summarize_document.md`:

```markdown
# summarize_document

## Description
Generates a concise summary of a specified document.

## Schema
[Embed the JSON Schema]

## Parameters
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| document_id | string | yes | - | Document ID to summarize |
| max_length | integer | no | 500 | Max summary length (words) |
| style | string | no | paragraph | bullet_points, paragraph, or executive |

## Returns
| Field | Type | Description |
|-------|------|-------------|
| document_id | string | The summarized document's ID |
| summary | string | The generated summary |
| word_count | integer | Word count of the summary |

## Error Cases
| Error | Cause | Resolution |
|-------|-------|------------|
| Document not found | Invalid document_id | Verify the document ID exists |
| LLM timeout | LLM provider slow/down | Retry or check provider status |
```

### Step 6: Add Eval Dataset (if the tool involves LLM reasoning)

Add test cases to `tests/eval/datasets/summarization.json`:

```json
[
  {
    "input": {"document_id": "eval-doc-1", "style": "bullet_points"},
    "expected_contains": ["revenue", "growth", "quarter"],
    "min_score": 0.8
  }
]
```

### Step 7: Run All Tests and Commit

```bash
pytest tests/unit/tools/test_summarize_document.py -v
pytest tests/integration/tools/test_summarize_document.py -v
ruff check app/tools/summarize_document.py
mypy --strict app/tools/summarize_document.py
git commit -m "feat(agent): add summarize_document tool with schema and tests"
```

---

## 12. How to Add a New API Endpoint

### Step 1: Read the API Design Spec

Review `docs/api/design.md` for URL conventions, auth patterns, and response formats.

### Step 2: Define Request/Response Schemas

Create or update `app/schemas/<resource>.py`:

```python
from pydantic import BaseModel, Field
from datetime import datetime

class DocumentSummaryRequest(BaseModel):
    style: str = Field(default="paragraph", pattern="^(bullet_points|paragraph|executive)$")
    max_length: int = Field(default=500, ge=50, le=5000)

class DocumentSummaryResponse(BaseModel):
    document_id: str
    summary: str
    word_count: int
    generated_at: datetime
```

### Step 3: Implement the Route

Create or update `app/api/v1/documents.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from app.schemas.document import DocumentSummaryRequest, DocumentSummaryResponse
from app.services.document import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post(
    "/{document_id}/summarize",
    response_model=DocumentSummaryResponse,
    status_code=200,
    summary="Summarize a document",
    description="Generate a summary of the specified document.",
)
async def summarize_document(
    document_id: str,
    request: DocumentSummaryRequest,
    user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentSummaryResponse:
    result = await service.summarize(
        document_id=document_id,
        style=request.style,
        max_length=request.max_length,
        user_id=user.id,
    )
    return result
```

### Step 4: Register the Router

In `app/api/v1/router.py`:

```python
from app.api.v1 import documents

api_router.include_router(documents.router, prefix="/api/v1")
```

### Step 5: Write Tests

```python
async def test_summarize_document_returns_200(client, auth_headers):
    response = await client.post(
        "/api/v1/documents/doc-1/summarize",
        json={"style": "bullet_points", "max_length": 200},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert data["word_count"] <= 200

async def test_summarize_document_returns_404_for_missing(client, auth_headers):
    response = await client.post(
        "/api/v1/documents/nonexistent/summarize",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 404

async def test_summarize_document_returns_422_for_invalid_style(client, auth_headers):
    response = await client.post(
        "/api/v1/documents/doc-1/summarize",
        json={"style": "invalid_style"},
        headers=auth_headers,
    )
    assert response.status_code == 422
```

### Step 6: Update API Documentation

Update `docs/api/documents.md` and regenerate the OpenAPI spec.

### Step 7: Run Tests and Commit

```bash
pytest tests/unit/api/test_documents.py tests/integration/api/test_documents.py tests/contract/ -v
git commit -m "feat(api): add POST /documents/{id}/summarize endpoint"
```

---

## 13. How to Add a New Evaluation

### Step 1: Create the Golden Dataset

Create `tests/eval/datasets/<eval_name>.json`:

```json
[
  {
    "id": "eval-001",
    "query": "What was the total revenue in Q3 2024?",
    "ground_truth": "Total revenue in Q3 2024 was $4.2 billion, representing a 15% year-over-year increase.",
    "required_citations": [
      {
        "document_id": "financial-report-q3-2024",
        "page": 3,
        "excerpt_contains": "total revenue"
      }
    ],
    "tags": ["financial", "revenue", "quarterly"]
  },
  {
    "id": "eval-002",
    "query": "What are the main risk factors mentioned in the annual report?",
    "ground_truth": "The main risk factors include market volatility, regulatory changes, supply chain disruptions, and cybersecurity threats.",
    "required_citations": [
      {
        "document_id": "annual-report-2024",
        "page": 12,
        "excerpt_contains": "risk factors"
      }
    ],
    "tags": ["risk", "annual-report"]
  }
]
```

### Step 2: Implement the Scorer

Create `tests/eval/scorers/<eval_name>_scorer.py`:

```python
from app.eval.base import BaseScorer, ScoreResult

class DocumentQAScorer(BaseScorer):
    async def score(
        self,
        query: str,
        predicted_answer: str,
        ground_truth: str,
        citations: list[dict],
        required_citations: list[dict],
    ) -> ScoreResult:
        # Semantic similarity between predicted and ground truth
        semantic_score = await self._embedding_similarity(predicted_answer, ground_truth)

        # Citation accuracy
        citation_score = self._check_citations(citations, required_citations)

        # Combined score (weighted)
        combined = 0.6 * semantic_score + 0.4 * citation_score

        return ScoreResult(
            score=combined,
            details={
                "semantic_similarity": semantic_score,
                "citation_accuracy": citation_score,
            },
        )
```

### Step 3: Create the Evaluation Runner

Create `tests/eval/test_<eval_name>.py`:

```python
import pytest
from tests.eval.scorers.document_qa_scorer import DocumentQAScorer
from tests.eval.datasets import load_dataset

@pytest.mark.eval
@pytest.mark.parametrize("case", load_dataset("document_qa"))
async def test_document_qa_quality(case, agent_service):
    result = await agent_service.answer(question=case["query"])

    scorer = DocumentQAScorer()
    score = await scorer.score(
        query=case["query"],
        predicted_answer=result.answer,
        ground_truth=case["ground_truth"],
        citations=result.citations,
        required_citations=case["required_citations"],
    )

    assert score.score >= 0.85, (
        f"Eval case {case['id']} scored {score.score:.2f} (min 0.85). "
        f"Query: {case['query']}. "
        f"Predicted: {result.answer[:200]}... "
        f"Details: {score.details}"
    )
```

### Step 4: Add CI Integration

In `.github/workflows/eval.yml`:

```yaml
name: Evaluations
on:
  pull_request:
    paths:
      - 'app/agents/**'
      - 'app/tools/**'
      - 'app/search/**'
      - 'tests/eval/**'

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run evaluations
        run: pytest tests/eval/ -v --eval-threshold=0.85 --tb=short
```

### Step 5: Document the Evaluation

Create `docs/eval/<eval_name>.md` with: dataset description, scoring methodology, thresholds, and how to add new test cases.

---

## 14. How to Debug Failures

### 14.1 Check Logs

```bash
# Structured logs with request tracing
docker compose logs -f api | jq 'select(.request_id == "<REQUEST_ID>")'
```

### 14.2 Reproduce Locally

```bash
# Run the failing test in isolation
pytest tests/path/to/test_file.py::test_function_name -v --tb=long -s

# Run with debug logging
LOG_LEVEL=DEBUG pytest tests/path/to/test_file.py::test_function_name -v -s
```

### 14.3 Inspect Agent Traces

Agent runs are logged with full traces. Check:

```bash
# View agent execution trace
curl http://localhost:8000/api/v1/traces/<trace_id> | jq .
```

The trace shows every tool call, LLM input/output, iteration count, and timing.

### 14.4 Database Debugging

```bash
# Connect to the dev database
docker compose exec postgres psql -U postgres -d ai_doc_ops

# Check recent migrations
alembic history
alembic current
```

### 14.5 Common Failure Patterns

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ValidationError` on tool call | LLM output doesn't match schema | Check prompt, add few-shot examples, validate schema |
| Agent hits max iterations | Loop in agent graph | Check termination conditions, add loop guard |
| `TimeoutError` on tool | External service slow | Check service health, increase timeout, add retry |
| `IntegrityError` on DB insert | Missing idempotency check | Ensure idempotency key is checked before insert |
| Low eval scores | Prompt regression or data issue | Compare with previous eval run, check dataset quality |
| `429 Too Many Requests` | Rate limit hit | Check rate limit config, add backoff/retry |
| Missing citations in Q&A | Retrieval issue | Check Qdrant index, verify embeddings, tune search params |

### 14.6 Performance Debugging

```bash
# Profile a slow endpoint
pyinstrument -r html -o profile.html app/main.py

# Check database query performance
docker compose exec postgres psql -U postgres -d ai_doc_ops -c "EXPLAIN ANALYZE <query>"

# Check Redis hit rate
docker compose exec redis redis-cli INFO stats | grep keyspace
```

---

## 15. How to Apply Changes (Rebuild Docker)

Sau khi sửa code backend (đặc biệt là **system prompt**, **agent logic**, hoặc **dependencies**), phải rebuild Docker để thay đổi có hiệu lực:

### 15.1 Rebuild và restart tất cả services

```bash
# Build lại images (không dùng cache để đảm bảo code mới nhất)
docker compose build --no-cache api

# Hoặc rebuild tất cả
docker compose build --no-cache

# Restart containers với image mới
docker compose up -d
```

### 15.2 Rebuild nhanh (chỉ restart container)

Nếu chỉ sửa code Python (không thay đổi `pyproject.toml` hay `Dockerfile`):

```bash
# Chỉ restart API container để áp dụng code mới
docker compose restart api
```

### 15.3 Kiểm tra container đã dùng code mới

```bash
# Kiểm tra logs xác nhận container dùng code mới
docker compose logs api --tail=20

# Kiểm tra health endpoint
curl http://localhost:8000/health
```

### 15.4 Xử lý lỗi khi rebuild

| Lỗi | Nguyên nhân | Fix |
|-----|------------|-----|
| `Python: can't open file` | Build cache cũ | `docker compose build --no-cache api` |
| Lỗi import module | Thiếu dependency | Kiểm tra `pyproject.toml`, thêm dependency, rebuild |
| Container crash loop | Lỗi syntax Python | Kiểm tra logs: `docker compose logs api` |
| Thay đổi không có hiệu lực | Container chưa được restart | `docker compose restart api` |

---

*This document is the single source of truth for all engineering practices on this project. When in doubt, refer to this file. If this file is incomplete, open a PR to improve it.*
