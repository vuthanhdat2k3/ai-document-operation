# AI Document Operations Agent — Technical Specification

> Version: 1.0.0 | Status: Draft | Last Updated: 2026-06-11

---

## Table of Contents

1. [Technical Overview](#1-technical-overview)
2. [Technology Stack](#2-technology-stack)
3. [Project Structure](#3-project-structure)
4. [Backend Architecture](#4-backend-architecture)
5. [Database Design Principles](#5-database-design-principles)
6. [LLM Integration Design](#6-llm-integration-design)
7. [Agent Framework Design](#7-agent-framework-design)
8. [RAG Pipeline Technical Design](#8-rag-pipeline-technical-design)
9. [Document Processing Pipeline Technical Design](#9-document-processing-pipeline-technical-design)
10. [Validation Framework](#10-validation-framework)
11. [Configuration Management](#11-configuration-management)
12. [Coding Standards](#12-coding-standards)
13. [Implementation Checklist](#13-implementation-checklist)
14. [Acceptance Criteria](#14-acceptance-criteria)

---

## 1. Technical Overview

### 1.1 System Purpose

The AI Document Operations Agent is an intelligent document processing platform that ingests, parses, indexes, and enables semantic search and question-answering over heterogeneous document collections. The system combines deterministic document processing pipelines with LLM-powered agent workflows orchestrated via LangGraph state machines.

### 1.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                        │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────────┐  │
│  │ Dashboard │  │ Document │  │  Search   │  │  Chat / QA    │  │
│  │          │  │ Manager  │  │  Explorer │  │  Interface    │  │
│  └──────────┘  └──────────┘  └───────────┘  └───────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST / WebSocket
┌──────────────────────────▼──────────────────────────────────────┐
│                     API Gateway (FastAPI)                         │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────────┐  │
│  │ Auth     │  │ Rate     │  │ CORS      │  │ Request       │  │
│  │ Middleware│  │ Limiter  │  │ Middleware│  │ ID Middleware │  │
│  └──────────┘  └──────────┘  └───────────┘  └───────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────────┐  │
│  │ Document │  │ Search   │  │ Agent     │  │ Admin         │  │
│  │ Router   │  │ Router   │  │ Router    │  │ Router        │  │
│  └──────────┘  └──────────┘  └───────────┘  └───────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    Service Layer                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ Document     │  │ RAG          │  │ Agent                  │ │
│  │ Service      │  │ Service      │  │ Service                │ │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬─────────────┘ │
│         │                 │                      │               │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────────▼─────────────┐ │
│  │ Processing   │  │ Embedding    │  │ LangGraph              │ │
│  │ Pipeline     │  │ Pipeline     │  │ Orchestrator           │ │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬─────────────┘ │
└─────────┼─────────────────┼──────────────────────┼──────────────┘
          │                 │                      │
┌─────────▼─────────────────▼──────────────────────▼──────────────┐
│                    Data Layer                                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────────┐  │
│  │PostgreSQL│  │ Qdrant   │  │  Redis    │  │ Object Store  │  │
│  │ (primary)│  │ (vectors)│  │  (cache)  │  │ (files)       │  │
│  └──────────┘  └──────────┘  └───────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Key Design Principles

- **Separation of Concerns** — Each layer (API, service, data) has a single responsibility.
- **Provider Abstraction** — LLM, embedding, and storage backends are behind interfaces.
- **Idempotency** — All mutation endpoints produce identical results when retried with the same request ID.
- **Observability First** — Every request is traced end-to-end via OpenTelemetry; LLM calls are tracked via Langfuse.
- **Type Safety** — Pydantic v2 models enforce contracts at every boundary; MyPy strict mode on backend.

---

## 2. Technology Stack

### 2.1 Core Backend

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Language | Python | 3.11+ | Backend runtime |
| Web Framework | FastAPI | 0.110+ | Async REST API |
| ORM | SQLAlchemy | 2.0+ | Database access |
| Migrations | Alembic | latest | Schema versioning |
| Agent Framework | LangGraph | latest | State machine orchestration |
| LLM Framework | LangChain | latest | LLM abstraction layer |
| Validation | Pydantic | v2 (2.6+) | Data validation and serialization |

### 2.2 Data Stores

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| RDBMS | PostgreSQL | 16 | Primary data store |
| Vector DB | Qdrant | latest | Dense/sparse vector search |
| Cache / Queue | Redis | 7 | Caching, rate limiting, task queue |

### 2.3 Document Processing

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| PDF Parser | PyMuPDF (fitz) | latest | Fast PDF text extraction |
| Document AI | Docling | latest | Advanced document layout analysis |
| OCR Engine | PaddleOCR | latest | Image-based text recognition |
| DOCX Parser | python-docx | latest | Word document parsing |
| XLSX Parser | openpyxl | latest | Excel spreadsheet parsing |

### 2.4 ML / Embedding

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Embedding Model | bge-m3 | — | Dense + sparse + ColBERT vectors |
| Reranker | bge-reranker-v2-m3 | — | Cross-encoder reranking |
| Model Runtime | sentence-transformers | latest | Model loading and inference |

### 2.5 Observability

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| LLM Tracing | Langfuse | latest | LLM call tracking, cost, latency |
| Distributed Tracing | OpenTelemetry | latest | End-to-end request tracing |

### 2.6 Testing & Quality

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Test Framework | Pytest | 8.0+ | Unit and integration tests |
| Linter | Ruff | latest | Python linting and formatting |
| Type Checker | MyPy | latest | Static type analysis |

### 2.7 Frontend

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | Next.js | 14+ | React meta-framework (App Router) |
| UI Library | React | 18+ | Component library |
| Styling | TailwindCSS | 3.4+ | Utility-first CSS |

### 2.8 Infrastructure

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Containerization | Docker | 24+ | Application packaging |
| Orchestration | Docker Compose | v2 | Local development environment |
| CI/CD | GitHub Actions | — | Automated build, test, deploy |

---

## 3. Project Structure

```
ai-document-operations-agent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI application factory
│   │   ├── config.py                   # Settings via pydantic-settings
│   │   ├── deps.py                     # Dependency injection providers
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py           # v1 API router aggregator
│   │   │   │   ├── documents.py        # Document CRUD + upload endpoints
│   │   │   │   ├── search.py           # Search and retrieval endpoints
│   │   │   │   ├── agents.py           # Agent interaction endpoints
│   │   │   │   ├── collections.py      # Collection management
│   │   │   │   └── admin.py            # Admin / health endpoints
│   │   │   ├── middleware/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── request_id.py       # X-Request-ID middleware
│   │   │   │   ├── logging.py          # Structured logging middleware
│   │   │   │   └── error_handler.py    # Global exception handlers
│   │   │   └── schemas/                # Request/response Pydantic models
│   │   │       ├── __init__.py
│   │   │       ├── documents.py
│   │   │       ├── search.py
│   │   │       ├── agents.py
│   │   │       └── common.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── document_service.py     # Document lifecycle management
│   │   │   ├── search_service.py       # Hybrid search orchestration
│   │   │   ├── agent_service.py        # LangGraph agent management
│   │   │   └── collection_service.py   # Collection CRUD
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── graph.py                # LangGraph state machine definition
│   │   │   ├── state.py                # Agent state TypedDict
│   │   │   ├── nodes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── retrieve.py         # RAG retrieval node
│   │   │   │   ├── reason.py           # LLM reasoning node
│   │   │   │   ├── tool_call.py        # Tool execution node
│   │   │   │   └── synthesize.py       # Response synthesis node
│   │   │   ├── tools/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── search_tool.py      # Vector search tool
│   │   │   │   ├── document_tool.py    # Document fetch tool
│   │   │   │   └── calculator_tool.py  # Utility tools
│   │   │   └── prompts/
│   │   │       ├── system.md           # System prompt template
│   │   │       └── rag_prompt.md       # RAG-specific prompt
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # Abstract LLM provider interface
│   │   │   ├── openai_provider.py      # OpenAI / compatible provider
│   │   │   ├── anthropic_provider.py   # Anthropic provider
│   │   │   ├── local_provider.py       # Local / self-hosted provider
│   │   │   ├── router.py              # Model routing logic
│   │   │   ├── token_counter.py        # Token counting utilities
│   │   │   └── cost_tracker.py         # Cost calculation and tracking
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── chunker.py              # Document chunking strategies
│   │   │   ├── embedder.py             # Embedding pipeline
│   │   │   ├── retriever.py            # Hybrid retrieval (dense + sparse)
│   │   │   ├── reranker.py             # Cross-encoder reranking
│   │   │   └── fusion.py               # RRF and score fusion
│   │   ├── processing/
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py             # Processing pipeline orchestrator
│   │   │   ├── detector.py             # File type detection
│   │   │   ├── parsers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py             # Abstract parser interface
│   │   │   │   ├── pdf_parser.py       # PyMuPDF + Docling parser
│   │   │   │   ├── docx_parser.py      # python-docx parser
│   │   │   │   ├── xlsx_parser.py      # openpyxl parser
│   │   │   │   ├── image_parser.py     # PaddleOCR parser
│   │   │   │   └── text_parser.py      # Plain text parser
│   │   │   ├── ocr/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── engine.py           # PaddleOCR wrapper
│   │   │   │   └── config.py           # OCR configuration
│   │   │   └── quality.py              # Extraction quality scoring
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── session.py              # SQLAlchemy async session factory
│   │   │   ├── base.py                 # Declarative base + mixins
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── document.py         # Document ORM model
│   │   │       ├── chunk.py            # Chunk ORM model
│   │   │       ├── collection.py       # Collection ORM model
│   │   │       └── audit.py            # Audit log ORM model
│   │   ├── vector/
│   │   │   ├── __init__.py
│   │   │   ├── client.py               # Qdrant client wrapper
│   │   │   ├── collections.py          # Collection management
│   │   │   └── search.py               # Search operations
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   └── redis.py                # Redis cache wrapper
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   ├── task_queue.py           # ARQ task queue setup
│   │   │   └── tasks/
│   │   │       ├── __init__.py
│   │   │       ├── process_document.py # Document processing task
│   │   │       ├── embed_chunks.py     # Batch embedding task
│   │   │       └── reindex.py          # Reindexing task
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── file.py                 # File handling utilities
│   │       ├── hash.py                 # Content hashing
│   │       └── metrics.py              # Custom metric helpers
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                 # Shared fixtures
│       ├── unit/
│       │   ├── test_chunker.py
│       │   ├── test_parsers.py
│       │   └── test_fusion.py
│       ├── integration/
│       │   ├── test_api_documents.py
│       │   ├── test_search.py
│       │   └── test_agent.py
│       └── e2e/
│           └── test_full_pipeline.py
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── documents/
│   │   │   │   └── page.tsx
│   │   │   ├── search/
│   │   │   │   └── page.tsx
│   │   │   └── chat/
│   │   │       └── page.tsx
│   │   ├── components/
│   │   │   ├── ui/                     # Shared UI primitives
│   │   │   ├── DocumentUploader.tsx
│   │   │   ├── SearchResults.tsx
│   │   │   └── ChatInterface.tsx
│   │   ├── lib/
│   │   │   ├── api.ts                  # API client
│   │   │   └── hooks/                  # Custom React hooks
│   │   └── types/
│   │       └── index.ts                # Shared TypeScript types
│   ├── public/
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── Dockerfile
├── config/
│   ├── nginx.conf                      # Reverse proxy config
│   └── qdrant_config.yaml              # Qdrant configuration
├── deploy/
│   └── docker-compose.yml              # Full stack composition
├── scripts/
│   ├── seed.py                         # Database seeding
│   ├── benchmark.py                    # Performance benchmarks
│   └── migrate.sh                      # Migration helper
├── tests/                              # Cross-service integration tests
│   └── conftest.py
├── evals/
│   ├── ragas_eval.py                   # RAG quality evaluation
│   └── datasets/
│       └── sample_qa.jsonl
├── docs/
│   ├── TECHNICAL_SPEC.md               # This document
│   ├── API.md                          # API reference
│   └── ARCHITECTURE.md                 # Architecture decision records
├── .github/
│   └── workflows/
│       ├── ci.yml                      # Lint + test + typecheck
│       ├── build.yml                   # Docker image build
│       └── deploy.yml                  # Deployment pipeline
├── .env.example
├── .gitignore
├── Makefile
├── docker-compose.yml                  # Development composition
└── README.md
```

---

## 4. Backend Architecture

### 4.1 Application Factory Pattern

The FastAPI application is created via a factory function that encapsulates all initialization logic, enabling isolated test instances and multiple deployment configurations.

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize DB pool, Qdrant collections, Redis, model warm-up
    await init_db()
    await init_vector_store()
    await warm_up_models()
    yield
    # Shutdown: close connections, flush metrics
    await shutdown_db()
    await shutdown_vector_store()
    await flush_telemetry()

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="AI Document Operations Agent",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.DEBUG else None,
    )
    register_middleware(app, settings)
    register_routes(app)
    register_exception_handlers(app)
    register_telemetry(app, settings)
    return app
```

### 4.2 Dependency Injection

FastAPI's `Depends` system is used for all cross-cutting concerns. Providers are defined in `app/deps.py` and return properly-scoped instances.

```python
# backend/app/deps.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_factory

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

async def get_document_service(
    db: AsyncSession = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant),
    redis: Redis = Depends(get_redis),
) -> DocumentService:
    return DocumentService(db=db, vector_store=qdrant, cache=redis)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await AuthService(db).verify_token(token)
```

### 4.3 Middleware Stack

Middleware is applied in the following order (outermost first):

1. **Request ID** — Assigns `X-Request-ID` (UUID4) to every request; propagates to all logs and traces.
2. **CORS** — Configured per environment; strict origin whitelist in production.
3. **Rate Limiting** — Redis-backed sliding window; configurable per endpoint group.
4. **Structured Logging** — Logs request method, path, status, duration, request ID.
5. **Authentication** — JWT validation on protected routes.

### 4.4 Error Handling

All errors are caught by global exception handlers that return structured JSON responses:

```python
class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: str
    status_code: int

# Exception hierarchy
class AppError(Exception):
    status_code: int = 500
    error: str = "internal_error"

class NotFoundError(AppError):
    status_code = 404
    error = "not_found"

class ValidationError(AppError):
    status_code = 422
    error = "validation_error"

class RateLimitError(AppError):
    status_code = 429
    error = "rate_limit_exceeded"
```

### 4.5 Background Tasks

Long-running operations (document processing, embedding, reindexing) are dispatched to **ARQ** (async Redis queue) workers:

- `process_document_task` — Parse, chunk, and index a document.
- `embed_chunks_task` — Generate embeddings for a batch of chunks.
- `reindex_task` — Rebuild vector index for a collection.

Task progress is stored in Redis and exposed via a `/tasks/{task_id}/status` endpoint.

---

## 5. Database Design Principles

### 5.1 Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Tables | plural, snake_case | `documents`, `chunks` |
| Columns | snake_case | `created_at`, `file_size_bytes` |
| Primary keys | `id` (UUID) | `id UUID DEFAULT gen_random_uuid()` |
| Foreign keys | `{referenced_table_singular}_id` | `document_id` |
| Indexes | `ix_{table}_{columns}` | `ix_documents_collection_id` |
| Unique constraints | `uq_{table}_{columns}` | `uq_chunks_document_position` |
| Check constraints | `ck_{table}_{condition}` | `ck_documents_file_size_positive` |

### 5.2 Migration Strategy

- Alembic migrations are **forward-only** in production; downgrades are permitted in development.
- Every migration must include a `downgrade()` function.
- Migrations that alter large tables must use batch operations to minimize lock time.
- Column additions with defaults use `server_default` to avoid table rewrites.
- All migrations are tested in CI against a disposable PostgreSQL container.

### 5.3 Connection Pooling

```python
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo=settings.DB_ECHO,
)
```

- **pool_size**: 20 persistent connections (tuned for async workload).
- **max_overflow**: 10 additional connections under burst load.
- **pool_pre_ping**: Validates connections before use to handle idle disconnects.
- **pool_recycle**: Recycles connections every 30 minutes.

---

## 6. LLM Integration Design

### 6.1 Provider Abstraction

All LLM providers implement a common interface:

```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        tools: list[Tool] | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        model: str,
        **kwargs,
    ) -> AsyncIterator[str]: ...

    @abstractmethod
    def count_tokens(self, messages: list[Message], model: str) -> int: ...
```

Implementations: `OpenAIProvider`, `AnthropicProvider`, `LocalProvider` (Ollama / vLLM).

### 6.2 Model Routing

A routing layer selects the appropriate provider and model based on:

- **Task type**: `reasoning`, `synthesis`, `classification`, `extraction`
- **Cost tier**: `low`, `medium`, `high`
- **Latency requirement**: `realtime` (< 1s), `standard` (< 5s), `batch` (no constraint)
- **Fallback chain**: Primary → secondary → degraded response

```python
class ModelRouter:
    def route(self, task: TaskType, constraints: Constraints) -> ModelConfig:
        candidates = self.registry.get(task, constraints)
        return candidates[0]  # sorted by cost-efficiency
```

### 6.3 Token Counting

Token counting uses `tiktoken` for OpenAI-compatible models and provider-specific tokenizers otherwise. Counts are logged to Langfuse on every LLM call.

### 6.4 Cost Tracking

Every LLM call records: input tokens, output tokens, model, provider, and calculated cost. Aggregated cost data is available via the admin API and Langfuse dashboards.

### 6.5 Response Caching

LLM responses are cached in Redis keyed by a SHA-256 hash of `(messages, model, temperature, tools)`. Cache TTL is 24 hours by default. Deterministic tasks (classification, extraction) use `temperature=0` to maximize cache hits.

---

## 7. Agent Framework Design

### 7.1 State Machine Definition

The agent is defined as a LangGraph `StateGraph` with typed state:

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    documents: list[Document]          # Retrieved documents
    current_step: str                  # Current node name
    iteration: int                     # Current iteration count
    max_iterations: int                # Loop limit
    tool_results: list[ToolResult]     # Accumulated tool outputs
    final_answer: str | None           # Synthesized answer
    metadata: dict                     # Tracing metadata
```

### 7.2 Graph Topology

```
START → retrieve → reason → [route]
                            ├── tool_call → reason  (loop)
                            └── synthesize → END
```

- **retrieve**: Performs hybrid search against Qdrant.
- **reason**: LLM evaluates context and decides next action.
- **tool_call**: Executes a tool and appends result to state.
- **synthesize**: Produces the final answer from accumulated context.

### 7.3 Tool Execution Model

Tools are Python functions decorated with `@tool` that implement a strict interface:

```python
@tool
async def search_documents(
    query: str,
    collection_id: str,
    top_k: int = 10,
) -> list[SearchResult]:
    """Search documents in a collection using hybrid retrieval."""
    ...
```

Tool execution is wrapped in a try/except with a 30-second timeout. Failed tools return an error message rather than raising.

### 7.4 Context Window Management

- Documents are ranked by relevance score and truncated to fit within the model's context window.
- A sliding window strategy retains the most recent messages when context exceeds the limit.
- Summarization of older messages is triggered when the window is > 80% full.

### 7.5 Loop Detection

- An `iteration` counter in state tracks the number of reason→tool_call cycles.
- If the same tool is called with identical arguments more than twice, the loop is broken.
- A hash of tool call arguments is stored in `metadata["seen_calls"]` for deduplication.

### 7.6 Max Iteration Limits

- Default: **10 iterations** (configurable per request).
- On exceeding the limit, the agent transitions directly to `synthesize` with a warning appended.
- Hard ceiling: **25 iterations** (enforced at the graph level, non-configurable).

---

## 8. RAG Pipeline Technical Design

### 8.1 Chunking Strategy

Two chunking strategies are supported, selectable per collection:

**Recursive Chunking** (default):
- Splits by separators in priority: `\n\n` → `\n` → `. ` → ` ` → `""`
- Chunk size: 512 tokens (configurable)
- Overlap: 64 tokens (configurable)
- Preserves document structure boundaries when possible

**Semantic Chunking**:
- Uses sentence-transformers to compute sentence embeddings.
- Splits at points where cosine similarity between consecutive sentences drops below a threshold.
- Produces variable-length chunks with higher semantic coherence.

### 8.2 Embedding Pipeline

```python
class EmbeddingPipeline:
    model: str = "BAAI/bge-m3"

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """
        Returns:
            dense: list[list[float]]    # 1024-dim dense vectors
            sparse: list[dict[int, float]]  # Sparse lexical vectors
        """
        outputs = self.model.encode(texts, return_dense=True, return_sparse=True)
        return EmbeddingResult(dense=outputs.dense, sparse=outputs.sparse)
```

- Batch size: 64 texts per request (configurable).
- Embeddings are stored in Qdrant with named vectors: `dense` and `sparse`.
- Async processing via the background task queue for large batches.

### 8.3 Hybrid Search Implementation

Search combines dense (semantic) and sparse (lexical) retrieval:

1. **Dense search**: Cosine similarity against `dense` named vectors in Qdrant.
2. **Sparse search**: Dot product against `sparse` named vectors in Qdrant.
3. Both searches return `top_k * 2` candidates for fusion.

### 8.4 RRF Fusion Formula

Reciprocal Rank Fusion combines results from dense and sparse search:

```
RRF_score(d) = Σ  1 / (k + rank_i(d))
              i∈{dense, sparse}
```

Where:
- `k = 60` (standard RRF constant, configurable)
- `rank_i(d)` = rank of document `d` in retrieval method `i` (1-indexed)
- Documents appearing in both lists get boosted scores

### 8.5 Reranking Pipeline

After RRF fusion, the top-N candidates are reranked using `bge-reranker-v2-m3`:

```python
class Reranker:
    model: str = "BAAI/bge-reranker-v2-m3"
    top_k: int = 5

    async def rerank(
        self, query: str, documents: list[Document]
    ) -> list[ScoredDocument]:
        pairs = [(query, doc.text) for doc in documents]
        scores = self.model.compute_score(pairs)
        ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
        return ranked[: self.top_k]
```

- The reranker is a cross-encoder that scores (query, document) pairs directly.
- Reranking is applied only to the top 20 candidates from RRF to control latency.
- Final result set size: configurable (default 5).

---

## 9. Document Processing Pipeline Technical Design

### 9.1 File Type Detection

Detection uses a three-layer approach:

1. **Magic bytes** — `python-magic` identifies MIME type from file content.
2. **Extension mapping** — Fallback to file extension when magic is ambiguous.
3. **Content heuristics** — Inspects file headers for compound formats (e.g., `.docx` is a ZIP with specific XML entries).

### 9.2 Parser Selection

| MIME Type | Parser | Fallback |
|-----------|--------|---------|
| `application/pdf` | PyMuPDF → Docling | PaddleOCR (scanned pages) |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | python-docx | — |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | openpyxl | — |
| `image/*` | PaddleOCR | — |
| `text/plain` | TextParser | — |
| `text/markdown` | TextParser (Markdown mode) | — |

### 9.3 OCR Configuration

```python
class OCRConfig(BaseModel):
    engine: str = "paddleocr"
    language: str = "en"
    use_gpu: bool = False
    det_model_dir: str | None = None
    rec_model_dir: str | None = None
    cls_model_dir: str | None = None
    det_db_thresh: float = 0.3
    det_db_box_thresh: float = 0.5
    rec_batch_num: int = 6
    max_text_length: int = 25
    use_angle_cls: bool = True
```

OCR is triggered when:
- PDF text extraction yields < 50 characters per page.
- The file is an image.
- The parser explicitly requests OCR for scanned content.

### 9.4 Quality Scoring

Each parsed document receives a quality score (0.0–1.0) based on:

| Factor | Weight | Scoring Method |
|--------|--------|---------------|
| Text density | 0.3 | Characters per page vs. expected range |
| Structure preservation | 0.2 | Headings, lists, tables detected |
| Encoding confidence | 0.2 | Ratio of valid UTF-8 characters |
| Completeness | 0.2 | Pages successfully parsed / total pages |
| Language consistency | 0.1 | Detected language matches expected |

Documents scoring below **0.4** are flagged for manual review.

---

## 10. Validation Framework

### 10.1 Pydantic Models

All API boundaries use Pydantic v2 `BaseModel` subclasses with strict configuration:

```python
class StrictModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        validate_default=True,
        coerce_numbers_to_str=False,
    )
```

### 10.2 JSON Schema

OpenAPI JSON Schema is auto-generated by FastAPI and validated in CI. Schema changes require explicit review. All endpoint request/response bodies are fully typed — no `dict` or `Any` return types.

### 10.3 Custom Validators

Reusable validators for common patterns:

```python
@field_validator("collection_id")
@classmethod
def validate_uuid(cls, v: str) -> str:
    UUID(v)  # raises ValueError if invalid
    return v

@field_validator("file_size_bytes")
@classmethod
def validate_file_size(cls, v: int) -> int:
    max_size = 100 * 1024 * 1024  # 100 MB
    if v > max_size:
        raise ValueError(f"File size exceeds maximum of {max_size} bytes")
    return v

@field_validator("query")
@classmethod
def validate_query(cls, v: str) -> str:
    v = v.strip()
    if len(v) < 2:
        raise ValueError("Query must be at least 2 characters")
    if len(v) > 2000:
        raise ValueError("Query must not exceed 2000 characters")
    return v
```

---

## 11. Configuration Management

### 11.1 Environment Variables

All configuration is loaded from environment variables with `.env` file support for development. A sample `.env.example` is committed to the repository; actual `.env` files are gitignored.

### 11.2 Config Classes

Configuration is organized into hierarchical Pydantic `BaseSettings` classes:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "ai-doc-agent"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 20
    DB_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None

    # LLM
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    DEFAULT_MODEL: str = "gpt-4o"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"

    # Langfuse
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # Processing
    MAX_FILE_SIZE_MB: int = 100
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    MAX_ITERATIONS: int = 10
```

### 11.3 Secrets Management

- Production secrets are injected via environment variables (Docker secrets, Kubernetes secrets, or cloud secret managers).
- **No secrets are committed to the repository.** CI scans for leaked credentials using `gitleaks`.
- API keys for LLM providers are stored encrypted at rest and decrypted only at application startup.

---

## 12. Coding Standards

### 12.1 Python Style Guide

- **Formatter/Linter**: Ruff (replaces Black, isort, flake8).
- **Line length**: 99 characters.
- **Type annotations**: Required for all function signatures (MyPy strict mode).
- **Async-first**: All I/O operations use `async/await`.
- **No bare `except`**: Always catch specific exceptions.
- **No mutable default arguments**: Use `None` sentinel pattern.

```toml
# pyproject.toml [tool.ruff]
[tool.ruff]
line-length = 99
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "SIM", "TCH"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["app"]

[tool.mypy]
python_version = "3.11"
strict = true
plugins = ["pydantic.mypy"]
```

### 12.2 TypeScript Style Guide

- **Formatter**: Prettier (integrated with ESLint).
- **Strict mode**: `"strict": true` in `tsconfig.json`.
- **No `any`**: Use `unknown` and narrow with type guards.
- **Component style**: Functional components with typed props.
- **State management**: React hooks + server state via React Query / SWR.

### 12.3 Docstring Format

Google-style docstrings for all public functions and classes:

```python
async def process_document(
    file_path: Path,
    collection_id: UUID,
    *,
    ocr_enabled: bool = True,
    chunk_strategy: ChunkStrategy = ChunkStrategy.RECURSIVE,
) -> ProcessingResult:
    """Process a document through the full ingestion pipeline.

    Args:
        file_path: Absolute path to the uploaded file.
        collection_id: Target collection for the processed document.
        ocr_enabled: Whether to apply OCR for scanned content.
        chunk_strategy: Chunking strategy to use for text splitting.

    Returns:
        ProcessingResult containing document ID, chunk count, and quality score.

    Raises:
        UnsupportedFileTypeError: If the file type is not supported.
        ProcessingError: If parsing or chunking fails.
    """
```

### 12.4 Import Ordering

Enforced by Ruff `isort` rules:

1. Standard library imports
2. Third-party imports
3. First-party (`app.*`) imports
4. Local relative imports

Groups are separated by a blank line. No wildcard imports.

---

## 13. Implementation Checklist

### Phase 1: Foundation (Week 1–2)

- [ ] Initialize monorepo structure (backend, frontend, deploy, docs)
- [ ] Set up `pyproject.toml` with Ruff, MyPy, Pytest configuration
- [ ] Configure Docker Compose (PostgreSQL, Redis, Qdrant)
- [ ] Implement application factory with lifespan management
- [ ] Implement database session management with SQLAlchemy async
- [ ] Define Alembic baseline migration with all core tables
- [ ] Implement Pydantic settings with `.env` support
- [ ] Set up GitHub Actions CI (lint, typecheck, test)

### Phase 2: Core Services (Week 3–4)

- [ ] Implement document CRUD API (upload, list, get, delete)
- [ ] Implement file type detection and parser registry
- [ ] Implement PDF parser (PyMuPDF + Docling)
- [ ] Implement DOCX and XLSX parsers
- [ ] Implement PaddleOCR integration for scanned content
- [ ] Implement quality scoring for parsed documents
- [ ] Implement ARQ worker for background document processing
- [ ] Implement chunking strategies (recursive, semantic)

### Phase 3: RAG Pipeline (Week 5–6)

- [ ] Implement bge-m3 embedding pipeline (dense + sparse)
- [ ] Implement Qdrant collection management
- [ ] Implement hybrid search (dense + sparse)
- [ ] Implement RRF fusion
- [ ] Implement bge-reranker-v2-m3 reranking pipeline
- [ ] Implement search API endpoint
- [ ] Implement LLM provider abstraction (OpenAI, Anthropic, Local)
- [ ] Implement model router with fallback chains
- [ ] Implement token counting and cost tracking
- [ ] Implement LLM response caching in Redis

### Phase 4: Agent Framework (Week 7–8)

- [ ] Define LangGraph state machine with typed state
- [ ] Implement retrieve node
- [ ] Implement reason node (LLM decision-making)
- [ ] Implement tool_call node with timeout and error handling
- [ ] Implement synthesize node (final answer generation)
- [ ] Implement loop detection and max iteration limits
- [ ] Implement context window management
- [ ] Implement agent API endpoint with streaming support

### Phase 5: Observability & Frontend (Week 9–10)

- [ ] Integrate Langfuse for LLM call tracing
- [ ] Integrate OpenTelemetry for distributed tracing
- [ ] Implement structured logging with request ID propagation
- [ ] Set up Next.js project with App Router
- [ ] Implement document upload and management UI
- [ ] Implement search explorer UI
- [ ] Implement chat/QA interface with streaming
- [ ] Implement responsive layout with TailwindCSS

### Phase 6: Testing & Hardening (Week 11–12)

- [ ] Write unit tests for all parsers (target: 90% coverage)
- [ ] Write unit tests for chunking and fusion algorithms
- [ ] Write integration tests for API endpoints
- [ ] Write integration tests for RAG pipeline
- [ ] Write E2E tests for full document processing flow
- [ ] Run RAGAS evaluation on sample QA dataset
- [ ] Security audit: input validation, file upload safety, auth
- [ ] Performance benchmarking: ingestion throughput, search latency
- [ ] Production Docker Compose configuration
- [ ] Deployment documentation

---

## 14. Acceptance Criteria

### 14.1 Document Processing

| ID | Criterion | Metric |
|----|-----------|--------|
| AC-1 | System accepts PDF, DOCX, XLSX, TXT, MD, and image files | All formats parseable |
| AC-2 | Scanned PDFs are processed via OCR | Text extraction > 90% accuracy on test set |
| AC-3 | Document processing completes within 60 seconds for a 50-page PDF | p95 latency |
| AC-4 | Quality score is assigned to every processed document | Score range 0.0–1.0 |
| AC-5 | Files exceeding 100 MB are rejected with a clear error | 413 status code |

### 14.2 RAG Pipeline

| ID | Criterion | Metric |
|----|-----------|--------|
| AC-6 | Hybrid search (dense + sparse) outperforms dense-only search | NDCG@10 improvement > 5% |
| AC-7 | Reranking improves top-5 precision over RRF-only results | MRR improvement > 10% |
| AC-8 | Search latency (hybrid + rerank) is under 500ms for p95 | Measured on 10K document corpus |
| AC-9 | Embedding pipeline handles 1000 chunks/minute | Throughput benchmark |
| AC-10 | Chunk overlap prevents information loss at boundaries | Manual evaluation on 50 documents |

### 14.3 Agent Framework

| ID | Criterion | Metric |
|----|-----------|--------|
| AC-11 | Agent never exceeds max iteration limit | Hard ceiling of 25 enforced |
| AC-12 | Loop detection prevents infinite tool-call cycles | Tested with adversarial inputs |
| AC-13 | Agent produces grounded answers with source citations | RAGAS faithfulness > 0.8 |
| AC-14 | Agent response latency is under 10 seconds for standard queries | p95 latency |
| AC-15 | Streaming responses begin within 2 seconds of request | Time to first token |

### 14.4 System Quality

| ID | Criterion | Metric |
|----|-----------|--------|
| AC-16 | All Python code passes MyPy strict mode | Zero type errors |
| AC-17 | All Python code passes Ruff linting | Zero violations |
| AC-18 | Backend test coverage is at least 85% | `pytest --cov` report |
| AC-19 | All API endpoints are documented in OpenAPI schema | Auto-generated docs complete |
| AC-20 | Docker Compose brings up full stack in under 60 seconds | Cold start benchmark |
| AC-21 | Langfuse traces capture 100% of LLM calls | Verified in Langfuse UI |
| AC-22 | OpenTelemetry traces cover the full request lifecycle | End-to-end trace completeness |
| AC-23 | No secrets or API keys in source code | gitleaks scan passes |
| AC-24 | CI pipeline (lint + typecheck + test) completes in under 5 minutes | GitHub Actions duration |

---

*End of Technical Specification*
