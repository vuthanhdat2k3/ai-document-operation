# Testing Strategy - AI Document Operations Agent

## 1. Testing Philosophy and Principles

### Core Principles

- **Test-Driven Confidence**: Every line of production code must be exercised by at least one test. Tests are the safety net that enables rapid iteration.
- **Fast Feedback Loop**: Unit tests must complete in seconds. Slow tests degrade developer productivity and are skipped.
- **Isolation**: Tests must not depend on external state, execution order, or other tests. Each test is self-contained.
- **Determinism**: Given the same input, tests must always produce the same output. No randomness, no time dependencies unless mocked.
- **Realistic Coverage**: Test not just the happy path but also edge cases, error handling, timeouts, and malformed inputs.
- **Production Parity**: Integration and E2E tests should mirror production as closely as possible (same DB, same services, same configurations).
- **Testability by Design**: Code must be written with testing in mind — dependency injection, interface-based abstractions, and pure functions wherever possible.

### Anti-Patterns to Avoid

- Tests that depend on network availability without mocking
- Tests that share mutable state (databases, files, globals)
- Tests that assert on implementation details rather than behavior
- Flaky tests that pass/fail intermittently
- Tests without clear failure messages
- Over-mocking that hides real integration issues

---

## 2. Test Pyramid

```
          ┌─────────┐
          │   E2E   │  10% — Full stack, slow, high confidence
          │  Tests  │
          ├─────────┤
          │Integration│  20% — Real DB/services, medium speed
          │  Tests   │
          ├──────────┤
          │  Unit    │  70% — Fast, isolated, mocked
          │  Tests   │
          └──────────┘
```

### Unit Tests (70%)

- **Speed**: < 100ms per test
- **Scope**: Single function, single class, single module
- **Dependencies**: All mocked (DB, LLM, external APIs, file system)
- **Run frequency**: On every save (via watch mode)
- **Coverage target**: > 90% line coverage for unit-tested modules

### Integration Tests (20%)

- **Speed**: < 5s per test
- **Scope**: Multiple modules working together, real database, real services
- **Dependencies**: Real PostgreSQL, real Qdrant, real Redis; mocked LLM
- **Run frequency**: Before every commit
- **Coverage target**: All critical paths covered

### E2E Tests (10%)

- **Speed**: < 30s per test
- **Scope**: Full user workflows from API to database
- **Dependencies**: All real (or realistic mocks for external LLM APIs)
- **Run frequency**: Before PR merge, in CI pipeline
- **Coverage target**: All user-facing workflows covered

---

## 3. Test Categories

### 3.1 Unit Tests

#### Parser Unit Tests

- **Scope**: Document parsing logic for each supported format (PDF, DOCX, XLSX, CSV, TXT, MD, HTML)
- **Tools**: pytest, unittest.mock, sample fixture files
- **When to run**: On every change to `backend/parsing/`
- **Examples**:
  - Parse valid PDF returns structured Document object
  - Parse corrupted PDF raises `DocumentParseError`
  - Parse password-protected PDF raises appropriate error
  - Parse empty file returns empty document with metadata
  - Extract metadata (author, creation date, page count) correctly
  - Handle unicode content in DOCX files
  - Parse multi-sheet XLSX returns sheet-per-section structure

#### Classifier Unit Tests

- **Scope**: Document type classification logic
- **Tools**: pytest, unittest.mock (mock LLM responses)
- **When to run**: On every change to `backend/classification/`
- **Examples**:
  - Classify invoice document returns `invoice` type
  - Classify contract document returns `contract` type
  - Classify ambiguous document returns type with low confidence
  - Handle empty document gracefully
  - Classification prompt is correctly formatted

#### Extractor Unit Tests

- **Scope**: Information extraction from parsed documents
- **Tools**: pytest, unittest.mock (mock LLM responses)
- **When to run**: On every change to `backend/extraction/`
- **Examples**:
  - Extract invoice fields (amount, date, vendor) from parsed content
  - Extract contract parties and effective dates
  - Handle missing fields gracefully with defaults
  - Validate extracted data types (dates are dates, amounts are numbers)
  - Extraction with custom schema returns correctly shaped output

#### Validator Unit Tests

- **Scope**: Data validation logic for extracted information
- **Tools**: pytest, pydantic validation
- **When to run**: On every change to `backend/validation/`
- **Examples**:
  - Valid invoice data passes validation
  - Missing required field fails validation with clear message
  - Invalid date format fails validation
  - Amount with wrong currency symbol fails validation
  - Cross-field validation (end date > start date)

#### Tool Unit Tests

- **Scope**: Individual tool implementations (search, calculator, web lookup, etc.)
- **Tools**: pytest, unittest.mock
- **When to run**: On every change to `backend/tools/`
- **Examples**:
  - Search tool returns formatted results
  - Calculator tool handles arithmetic expressions correctly
  - Tool with invalid input raises `ToolInputError`
  - Tool timeout raises `ToolTimeoutError`
  - Tool execution logs are captured correctly

#### RAG Component Tests

##### Chunker Tests
- **Scope**: Document chunking strategies
- **Tools**: pytest
- **When to run**: On every change to `backend/rag/chunking/`
- **Examples**:
  - Fixed-size chunker produces chunks of correct size
  - Semantic chunker splits at paragraph boundaries
  - Overlap is correctly applied between chunks
  - Very small document produces single chunk
  - Chunk metadata preserves source document reference

##### Embedder Tests
- **Scope**: Text embedding generation
- **Tools**: pytest, unittest.mock (mock embedding model)
- **When to run**: On every change to `backend/rag/embedding/`
- **Examples**:
  - Embedder produces vectors of correct dimension
  - Batch embedding processes all texts
  - Empty text raises appropriate error
  - Embedding cache prevents redundant computation

##### Retriever Tests
- **Scope**: Document retrieval from vector store
- **Tools**: pytest, unittest.mock (mock vector store client)
- **When to run**: On every change to `backend/rag/retrieval/`
- **Examples**:
  - Retriever returns top-k results sorted by similarity
  - Retriever applies metadata filters correctly
  - Retriever handles empty results gracefully
  - Hybrid search combines vector and keyword results correctly

#### Agent Node Tests

- **Scope**: Individual agent graph nodes (planner, executor, responder)
- **Tools**: pytest, unittest.mock
- **When to run**: On every change to `backend/agent/nodes/`
- **Examples**:
  - Planner node produces valid execution plan
  - Executor node calls correct tool with correct arguments
  - Responder node formats response with citations
  - Node handles LLM parsing errors gracefully
  - Conditional routing logic selects correct next node

---

### 3.2 Integration Tests

#### Database Integration (PostgreSQL)

- **Scope**: Repository layer, migrations, queries
- **Tools**: pytest, pytest-asyncio, testcontainers (PostgreSQL container)
- **When to run**: Before every commit
- **Examples**:
  - Create and retrieve document record
  - Query documents with pagination and filtering
  - Transaction rollback on error
  - Migration up/down preserves data integrity
  - Concurrent writes do not cause deadlocks

#### Vector Store Integration (Qdrant)

- **Scope**: Vector storage, search, collection management
- **Tools**: pytest, testcontainers (Qdrant container)
- **When to run**: Before every commit
- **Examples**:
  - Create collection with correct schema
  - Insert vectors and retrieve by similarity search
  - Delete vectors by document ID
  - Filter search results by metadata
  - Handle collection not found gracefully

#### Cache Integration (Redis)

- **Scope**: Caching layer for LLM responses, embeddings, search results
- **Tools**: pytest, testcontainers (Redis container)
- **When to run**: Before every commit
- **Examples**:
  - Set and get cached values
  - Cache expiration works correctly
  - Cache invalidation by key pattern
  - Graceful degradation when Redis is unavailable

#### LLM Integration (Mock Server)

- **Scope**: LLM client, prompt formatting, response parsing
- **Tools**: pytest, respx or httpx mock, custom mock LLM server
- **When to run**: Before every commit
- **Examples**:
  - Send prompt and receive structured response
  - Handle rate limiting with retry logic
  - Handle timeout with fallback behavior
  - Stream response chunks correctly
  - Token counting and cost tracking

#### Tool Integration (Full Tool Execution)

- **Scope**: Tool execution pipeline including input validation, execution, output formatting
- **Tools**: pytest, unittest.mock (external APIs only)
- **When to run**: Before every commit
- **Examples**:
  - End-to-end tool call from agent request to formatted result
  - Tool chain execution (output of tool A feeds into tool B)
  - Tool error handling and recovery
  - Tool execution with timeout enforcement

#### API Integration (FastAPI TestClient)

- **Scope**: HTTP endpoints, request/response handling, middleware
- **Tools**: pytest, httpx.AsyncClient, FastAPI TestClient
- **When to run**: Before every commit
- **Examples**:
  - POST /documents/upload returns 201 with document ID
  - GET /documents/{id} returns document details
  - POST /qa returns answer with citations
  - Authentication middleware rejects unauthorized requests
  - Rate limiting middleware returns 429 on excess requests
  - Validation errors return 422 with detailed messages

---

### 3.3 RAG Evaluation Tests

#### Retrieval Quality Tests

- **Scope**: Precision, recall, and relevance of retrieved documents
- **Tools**: pytest, custom evaluation metrics
- **When to run**: After modifying retrieval, chunking, or embedding logic
- **Examples**:
  - Given a known question, relevant document chunks are in top-10 results
  - Precision@5 > 0.6 for benchmark query set
  - Recall@10 > 0.8 for benchmark query set
  - No irrelevant documents in top-3 results for factoid questions

#### Reranking Quality Tests

- **Scope**: Reranker improves initial retrieval ordering
- **Tools**: pytest, custom evaluation metrics
- **When to run**: After modifying reranker configuration or model
- **Examples**:
  - Reranked top-3 results are more relevant than raw top-3
  - NDCG@5 improves after reranking on benchmark dataset
  - Reranker handles edge case of single result gracefully

#### End-to-End RAG Quality Tests

- **Scope**: Full RAG pipeline from question to answer quality
- **Tools**: pytest, LLM-as-judge evaluation
- **When to run**: Before PR merge, weekly regression
- **Examples**:
  - Answer correctness on golden Q&A dataset > 85%
  - Answer contains no hallucinated information
  - Answer is grounded in retrieved context

#### Citation Accuracy Tests

- **Scope**: Citations in responses match actual source documents
- **Tools**: pytest
- **When to run**: After modifying citation extraction or formatting logic
- **Examples**:
  - Every citation in response maps to a real document chunk
  - Citation page numbers are correct
  - Citation source filenames are correct
  - No orphaned citations (citations without corresponding sources)

---

### 3.4 Agent Simulation Tests

#### Agent Task Completion Tests

- **Scope**: Agent ability to complete multi-step tasks
- **Tools**: pytest, mock LLM with scripted responses
- **When to run**: Before PR merge
- **Examples**:
  - Agent completes "summarize document" task within expected steps
  - Agent completes "compare two documents" task with correct output
  - Agent handles ambiguous instructions by asking clarifying questions

#### Agent Loop Detection Tests

- **Scope**: Agent does not get stuck in infinite loops
- **Tools**: pytest, mock LLM
- **When to run**: Before PR merge
- **Examples**:
  - Agent detects repeated tool calls and stops
  - Agent respects max iteration limit
  - Agent produces meaningful error when loop detected

#### Agent Error Handling Tests

- **Scope**: Agent recovery from tool failures, LLM errors, invalid states
- **Tools**: pytest, mock LLM, mock tools with failure injection
- **When to run**: Before PR merge
- **Examples**:
  - Agent retries on transient tool failure
  - Agent falls back to alternative tool on permanent failure
  - Agent reports clear error to user on unrecoverable failure
  - Agent handles LLM returning malformed JSON

#### Agent Cost Limit Tests

- **Scope**: Agent respects token budget and cost limits
- **Tools**: pytest, mock LLM with token counting
- **When to run**: Before PR merge
- **Examples**:
  - Agent stops when token budget exceeded
  - Agent logs warning at 80% budget consumption
  - Agent returns partial results when budget hit mid-task

---

### 3.5 Contract Tests

#### Tool Contract Validation

- **Scope**: Tool input/output schemas match expected contracts
- **Tools**: pytest, pydantic schema validation
- **When to run**: After adding or modifying any tool
- **Examples**:
  - Tool input schema matches registered schema definition
  - Tool output schema matches expected response format
  - Breaking schema change is detected by test

#### API Contract Validation

- **Scope**: API request/response schemas match OpenAPI spec
- **Tools**: pytest, schemathesis or pact
- **When to run**: After modifying any API endpoint
- **Examples**:
  - Response body matches documented schema
  - Error responses follow standard error format
  - Pagination response includes required metadata fields

#### Schema Compatibility Tests

- **Scope**: Database schema changes are backward compatible
- **Tools**: pytest, alembic migration testing
- **When to run**: After any database migration
- **Examples**:
  - New migration applies cleanly to existing data
  - Rollback migration restores previous state
  - Adding nullable column does not break existing queries

---

### 3.6 Regression Tests

#### Bug Fix Regression Tests

- **Scope**: Previously reported bugs remain fixed
- **Tools**: pytest
- **When to run**: On every commit
- **Examples**:
  - Test for each GitHub issue that was fixed
  - Specific input that triggered bug now produces correct output
  - Edge case that caused crash now handled gracefully

#### Performance Regression Tests

- **Scope**: Response times and resource usage remain within bounds
- **Tools**: pytest-benchmark, locust (for load scenarios)
- **When to run**: Nightly in CI, before releases
- **Examples**:
  - Document parsing completes within 2s for 10-page PDF
  - Q&A response returns within 3s for standard query
  - Embedding generation completes within 500ms per chunk
  - Memory usage stays below 512MB during batch processing

---

### 3.7 E2E Tests

#### Full Document Upload → Parse → Extract → Report Flow

- **Scope**: Complete document processing pipeline
- **Tools**: pytest, httpx.AsyncClient, testcontainers
- **When to run**: Before PR merge, in CI
- **Examples**:
  - Upload PDF → verify parsing → verify extraction → verify stored in DB → verify report generation
  - Upload multiple documents → verify batch processing → verify aggregate report
  - Upload unsupported format → verify appropriate error response

#### Full Q&A Flow with Citations

- **Scope**: End-to-end question answering with source attribution
- **Tools**: pytest, httpx.AsyncClient, testcontainers
- **When to run**: Before PR merge, in CI
- **Examples**:
  - Upload document → ask question → verify answer quality → verify citations point to correct source
  - Ask question with no relevant documents → verify "no answer" response
  - Ask follow-up question → verify conversation context maintained

#### Full Agent Task Flow

- **Scope**: Complex multi-step agent tasks end-to-end
- **Tools**: pytest, httpx.AsyncClient, testcontainers, mock LLM
- **When to run**: Before PR merge, in CI
- **Examples**:
  - "Analyze all uploaded invoices and create summary" → verify task completion and output
  - "Find all contracts expiring this month" → verify correct documents identified
  - Agent handles task that requires multiple tool calls → verify final output

---

### 3.8 Load Tests

#### Concurrent Upload Handling

- **Scope**: System behavior under concurrent document uploads
- **Tools**: locust, pytest-asyncio
- **When to run**: Before releases, nightly in CI
- **Examples**:
  - 50 concurrent uploads complete without errors
  - Response time p95 < 5s under 20 concurrent uploads
  - No data corruption under concurrent write load

#### Q&A Latency Under Load

- **Scope**: Q&A response times under concurrent queries
- **Tools**: locust, pytest-asyncio
- **When to run**: Before releases
- **Examples**:
  - p95 latency < 5s with 20 concurrent Q&A requests
  - No request drops under sustained load
  - Cache hit rate > 60% under repeated query patterns

#### Database Connection Pool Stress

- **Scope**: Database connection management under load
- **Tools**: pytest-asyncio, custom load generator
- **When to run**: Before releases
- **Examples**:
  - Connection pool correctly handles max connections
  - Connections are properly released after use
  - No connection leaks under sustained load

---

## 4. Testing Rules (MUST Follow)

| Rule | Enforcement |
|------|-------------|
| After implementing a module → run related unit tests | Pre-commit hook |
| After modifying agent/tool/rag → run integration tests | CI gate |
| After modifying retrieval/chunking/reranker → run RAG eval | CI gate |
| Before every commit → run full test suite | Pre-commit hook |
| If test fails → DO NOT COMMIT | Pre-commit hook (hard block) |
| Every bug fix → must have regression test | PR review checklist |
| Every new tool → must have contract test | PR review checklist |
| Every new API → must have API test | PR review checklist |
| Test coverage must not decrease | CI coverage check |
| No `@pytest.mark.skip` without linked issue | Linting rule |

---

## 5. Test Commands

```bash
# Run all tests
pytest

# Run by category
pytest tests/unit               # Unit tests only
pytest tests/integration        # Integration tests only
pytest tests/eval               # RAG evaluation tests
pytest tests/agent              # Agent simulation tests
pytest tests/contract           # Contract tests
pytest tests/e2e                # End-to-end tests
pytest tests/load               # Load tests (separate CI stage)

# Run with coverage
pytest --cov=backend --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_parser.py

# Run tests matching pattern
pytest -k "test_invoice"

# Run with verbose output
pytest -v

# Run in parallel (requires pytest-xdist)
pytest -n auto

# Linting and type checking
ruff check .
ruff format --check .
mypy backend/

# Run pre-commit checks manually
pre-commit run --all-files
```

---

## 6. Test Configuration

### pytest.ini / pyproject.toml Configuration

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
markers = [
    "unit: Unit tests (fast, isolated)",
    "integration: Integration tests (requires services)",
    "eval: RAG evaluation tests",
    "agent: Agent simulation tests",
    "contract: Contract tests",
    "e2e: End-to-end tests",
    "load: Load tests",
    "slow: Tests that take > 5s",
]
filterwarnings = [
    "ignore::DeprecationWarning",
]
addopts = [
    "--strict-markers",
    "--tb=short",
    "-q",
]
```

### Core Fixtures

```python
# tests/conftest.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def db_session(db_engine):
    async with AsyncSession(db_engine) as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client(app):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_llm():
    mock = AsyncMock()
    mock.ainvoke.return_value = MagicMock(content='{"result": "test"}')
    return mock

@pytest.fixture
def sample_invoice_pdf(tmp_path):
    path = tmp_path / "invoice.pdf"
    # Generate minimal valid PDF
    path.write_bytes(create_test_pdf(content="Invoice #12345, Amount: $500"))
    return path

@pytest.fixture
def sample_contract_docx(tmp_path):
    path = tmp_path / "contract.docx"
    # Generate minimal valid DOCX
    create_test_docx(path, content="Service Agreement between A and B")
    return path

@pytest.fixture
def golden_qa_dataset():
    return [
        {
            "question": "What is the total amount on invoice #12345?",
            "expected_answer": "$500",
            "source_document": "invoice.pdf",
            "source_page": 1,
        },
        # ... more test cases
    ]
```

### Test Data Management

```
tests/
├── conftest.py              # Global fixtures
├── fixtures/                # Shared test data
│   ├── documents/           # Sample documents per type
│   │   ├── invoices/
│   │   ├── contracts/
│   │   ├── reports/
│   │   └── correspondence/
│   ├── golden_datasets/     # Golden test datasets for RAG eval
│   │   ├── qa_pairs.json
│   │   └── retrieval_ground_truth.json
│   └── responses/           # Mock LLM responses
│       ├── classification/
│       ├── extraction/
│       └── qa/
├── factories/               # Factory pattern for test data
│   ├── document_factory.py
│   ├── user_factory.py
│   └── task_factory.py
├── unit/
├── integration/
├── eval/
├── agent/
├── contract/
├── e2e/
└── load/
```

### Parallel Execution

```toml
# pyproject.toml
[tool.pytest.ini_options]
addopts = ["-n", "auto"]  # requires pytest-xdist
```

Unit tests run in parallel. Integration tests run sequentially (shared DB state).

### Coverage Requirements

```toml
[tool.coverage.run]
source = ["backend"]
omit = [
    "backend/migrations/*",
    "backend/tests/*",
]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.",
]
```

---

## 7. Mock Strategy

### LLM Mocking (Deterministic Responses)

```python
class MockLLM:
    """Deterministic LLM mock for testing."""

    def __init__(self, responses: dict[str, str]):
        self.responses = responses
        self.call_count = 0
        self.calls: list[dict] = []

    async def ainvoke(self, prompt: str, **kwargs) -> MagicMock:
        self.call_count += 1
        self.calls.append({"prompt": prompt, **kwargs})

        for pattern, response in self.responses.items():
            if pattern in prompt:
                return MagicMock(content=response)

        return MagicMock(content='{"error": "no matching response"}')

@pytest.fixture
def mock_classification_llm():
    return MockLLM(responses={
        "classify this document": '{"type": "invoice", "confidence": 0.95}',
        "extract fields": '{"amount": 500, "date": "2024-01-15"}',
    })
```

### External API Mocking

```python
import respx
import httpx

@pytest.fixture
def mock_external_api():
    with respx.mock:
        respx.get("https://api.external.com/search").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        yield
```

### File System Mocking

```python
from unittest.mock import patch, mock_open

@pytest.fixture
def mock_file_system():
    with patch("builtins.open", mock_open(read_data=b"test file content")):
        yield
```

### Time Mocking

```python
from freezegun import freeze_time

@freeze_time("2024-01-15 10:00:00")
def test_document_timestamp():
    doc = create_document("test.pdf")
    assert doc.created_at.isoformat() == "2024-01-15T10:00:00"
```

---

## 8. Test Data Management

### Factory Pattern

```python
import factory
from backend.models import Document, User

class UserFactory(factory.Factory):
    class Meta:
        model = User

    id = factory.Sequence(lambda n: n + 1)
    email = factory.LazyAttribute(lambda o: f"user{o.id}@test.com")
    name = factory.Faker("name")

class DocumentFactory(factory.Factory):
    class Meta:
        model = Document

    id = factory.Sequence(lambda n: f"doc-{n}")
    filename = factory.Faker("file_name", extension="pdf")
    document_type = factory.Iterator(["invoice", "contract", "report"])
    status = "parsed"
    owner = factory.SubFactory(UserFactory)
```

### Sample Documents Per Type

```python
SAMPLE_DOCUMENTS = {
    "invoice": {
        "minimal": "fixtures/documents/invoices/minimal_invoice.pdf",
        "multi_item": "fixtures/documents/invoices/multi_item_invoice.pdf",
        "foreign_currency": "fixtures/documents/invoices/foreign_currency.pdf",
        "corrupted": "fixtures/documents/invoices/corrupted.pdf",
    },
    "contract": {
        "simple": "fixtures/documents/contracts/simple_contract.docx",
        "multi_party": "fixtures/documents/contracts/multi_party.docx",
        "expired": "fixtures/documents/contracts/expired_contract.pdf",
    },
    "report": {
        "quarterly": "fixtures/documents/reports/quarterly_report.pdf",
        "with_charts": "fixtures/documents/reports/report_with_charts.pdf",
    },
}
```

### Golden Test Datasets

```json
{
  "qa_pairs": [
    {
      "id": "qa-001",
      "question": "What is the total amount on invoice #12345?",
      "ground_truth": "$500.00",
      "source_documents": ["invoice_12345.pdf"],
      "source_pages": [1],
      "difficulty": "easy",
      "category": "factoid"
    },
    {
      "id": "qa-002",
      "question": "What are the payment terms in the service agreement?",
      "ground_truth": "Net 30 days from invoice date",
      "source_documents": ["service_agreement.pdf"],
      "source_pages": [3],
      "difficulty": "medium",
      "category": "extraction"
    }
  ]
}
```

### Database Seeding

```python
@pytest.fixture
async def seed_database(db_session):
    user = UserFactory()
    db_session.add(user)

    documents = [DocumentFactory(owner=user) for _ in range(10)]
    db_session.add_all(documents)

    await db_session.commit()
    return {"user": user, "documents": documents}
```

---

## 9. CI Integration

### GitHub Actions Workflow

```yaml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff mypy
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy backend/

  unit-tests:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[test]"
      - run: pytest tests/unit --cov=backend --cov-report=xml -q
      - uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        ports: ["6379:6379"]
      qdrant:
        image: qdrant/qdrant:latest
        ports: ["6333:6333"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[test]"
      - run: pytest tests/integration -q

  rag-eval:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[test]"
      - run: pytest tests/eval -q

  e2e-tests:
    runs-on: ubuntu-latest
    needs: integration-tests
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
      redis:
        image: redis:7
        ports: ["6379:6379"]
      qdrant:
        image: qdrant/qdrant:latest
        ports: ["6333:6333"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[test]"
      - run: pytest tests/e2e -q

  contract-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[test]"
      - run: pytest tests/contract -q

  coverage-check:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[test]"
      - run: pytest --cov=backend --cov-fail-under=80 -q
```

### Test Stages in CI

1. **Lint** — ruff, mypy (blocks all subsequent jobs on failure)
2. **Unit Tests** — fast, parallel, coverage reported
3. **Integration Tests** — requires service containers
4. **RAG Evaluation** — retrieval and answer quality checks
5. **Contract Tests** — schema and API compatibility
6. **E2E Tests** — full stack validation
7. **Coverage Check** — enforces minimum 80% threshold

### Coverage Reporting

- Coverage XML uploaded to Codecov on every CI run
- PR comments include coverage diff
- Coverage threshold of 80% enforced as CI gate
- Coverage trend dashboard monitored weekly

### Failure Notifications

- Slack notification on CI failure on `main` branch
- Email notification to PR author on test failure
- GitHub PR status checks block merge on failure

---

## 10. Implementation Checklist

- [ ] Set up pytest configuration in `pyproject.toml`
- [ ] Create test directory structure (`tests/unit`, `tests/integration`, etc.)
- [ ] Implement core fixtures in `tests/conftest.py`
- [ ] Set up testcontainers for PostgreSQL, Qdrant, Redis
- [ ] Create MockLLM class with deterministic response mapping
- [ ] Implement factory classes for test data generation
- [ ] Create sample documents for each document type
- [ ] Build golden Q&A dataset (minimum 50 question-answer pairs)
- [ ] Write unit tests for all parser modules
- [ ] Write unit tests for classifier
- [ ] Write unit tests for extractor
- [ ] Write unit tests for validator
- [ ] Write unit tests for all tools
- [ ] Write unit tests for RAG components (chunker, embedder, retriever)
- [ ] Write unit tests for agent nodes
- [ ] Write integration tests for database layer
- [ ] Write integration tests for vector store
- [ ] Write integration tests for cache
- [ ] Write integration tests for LLM client
- [ ] Write integration tests for tool pipeline
- [ ] Write integration tests for API endpoints
- [ ] Write RAG evaluation tests with metrics
- [ ] Write agent simulation tests
- [ ] Write contract tests for all tools
- [ ] Write contract tests for all APIs
- [ ] Write E2E tests for document processing flow
- [ ] Write E2E tests for Q&A flow
- [ ] Write E2E tests for agent task flow
- [ ] Write load tests for concurrent uploads
- [ ] Write load tests for Q&A latency
- [ ] Configure GitHub Actions CI pipeline
- [ ] Set up coverage reporting with Codecov
- [ ] Configure pre-commit hooks for test enforcement
- [ ] Document testing conventions in CONTRIBUTING.md

---

## 11. Acceptance Criteria

### Test Coverage
- Overall code coverage ≥ 80%
- Unit test coverage ≥ 90% for core modules (parsing, extraction, RAG, agent)
- Integration test coverage for all critical paths
- No untested public API endpoints

### Test Quality
- Zero flaky tests in CI (tests must be deterministic)
- All tests complete within CI time budget (< 15 minutes total)
- Unit tests < 2 minutes, integration tests < 5 minutes, E2E < 5 minutes
- Every test has a clear, descriptive name indicating what is being tested
- Every test failure message clearly indicates what went wrong

### Process Compliance
- 100% of bug fixes have corresponding regression tests
- 100% of new tools have contract tests
- 100% of new API endpoints have integration tests
- Pre-commit hooks block commits when tests fail
- CI pipeline blocks PR merge when tests fail
- Coverage threshold enforced as CI gate

### RAG Quality Metrics
- Retrieval precision@5 ≥ 0.6 on golden dataset
- Retrieval recall@10 ≥ 0.8 on golden dataset
- Answer correctness ≥ 85% on golden Q&A dataset
- Citation accuracy ≥ 95% (citations match source documents)
- No hallucinated content in generated answers

### Performance Baselines
- Document parsing: < 2s for 10-page PDF
- Q&A response: < 3s end-to-end
- Embedding generation: < 500ms per chunk
- API response time p95: < 500ms for read endpoints
- Concurrent upload handling: 50 concurrent uploads without errors
