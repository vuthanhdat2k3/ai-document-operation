# System Architecture — AI Document Operations Agent

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture Diagram](#2-high-level-architecture-diagram)
3. [Component Breakdown](#3-component-breakdown)
4. [Data Flow Diagrams](#4-data-flow-diagrams)
5. [Technology Decisions & Trade-offs](#5-technology-decisions--trade-offs)
6. [Scalability Considerations](#6-scalability-considerations)
7. [Failure Handling Strategy](#7-failure-handling-strategy)
8. [Security Architecture](#8-security-architecture)
9. [Deployment Architecture](#9-deployment-architecture)
10. [Implementation Checklist](#10-implementation-checklist)

---

## 1. System Overview

### Purpose

The AI Document Operations Agent is an end-to-end intelligent document processing and question-answering system. It ingests heterogeneous document formats (PDF, DOCX, images, scanned forms), extracts structured fields, validates data integrity, indexes content into a vector store, and exposes an agentic Q&A and reporting interface backed by retrieval-augmented generation (RAG).

### Scope

| Capability | Description |
|---|---|
| Document Ingestion | Upload via API, support for PDF, DOCX, PNG, JPG, TIFF |
| OCR & Parsing | Full-text extraction, table detection, layout analysis |
| Classification | Automatic document type detection (invoice, contract, report, form, receipt) |
| Field Extraction | Schema-driven extraction of key-value fields per document type |
| Validation | Business-rule validation, cross-field consistency checks |
| Q&A | Natural language questions answered with cited sources |
| Report Generation | Aggregated summaries, checklists, compliance reports |
| Observability | Full tracing, metrics, evaluation pipelines |

### Design Philosophy

- **Defense in depth**: Every pipeline stage has input validation, error boundaries, and fallback behavior.
- **Separation of concerns**: Each component is a independently deployable unit with well-defined contracts.
- **Observability-first**: Every request is traced end-to-end via OpenTelemetry; every LLM call is logged via Langfuse.
- **Schema-driven**: Document types, extraction schemas, validation rules, and tool definitions are declared in configuration, not hardcoded.
- **Fail gracefully**: Degraded modes (e.g., OCR failure → skip extraction → still index raw text) ensure partial results rather than total failure.

---

## 2. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CLIENT LAYER                                             │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────────────────────┐   │
│  │   Next.js Web UI │    │  Mobile / API    │    │  Third-Party Integrations (webhook)  │   │
│  └────────┬─────────┘    └────────┬─────────┘    └──────────────────┬───────────────────┘   │
└───────────┼───────────────────────┼─────────────────────────────────┼───────────────────────┘
            │                       │                                 │
            ▼                       ▼                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                  API GATEWAY (FastAPI)                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌─────────────┐  │
│  │ Auth /   │  │ Rate     │  │ Request  │  │ CORS /    │  │ Validation│  │ OpenAPI     │  │
│  │ RBAC     │  │ Limiter  │  │ Router   │  │ Security  │  │ Middleware│  │ Schema      │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘  └───────────┘  └─────────────┘  │
└────────────────────────────┬────────────────────────────────────────────────────────────────┘
                             │
            ┌────────────────┼────────────────────┐
            ▼                ▼                    ▼
┌──────────────────┐ ┌───────────────┐ ┌────────────────────────────────────────────┐
│ Document Upload  │ │  Q&A / Chat   │ │  Report / Checklist Generation            │
│ Service          │ │  Endpoint     │ │  Endpoint                                 │
└────────┬─────────┘ └───────┬───────┘ └──────────────────┬─────────────────────────┘
         │                   │                             │
         ▼                   │                             │
┌──────────────────┐         │                             │
│ Document Parsing │         │                             │
│ / OCR Pipeline   │         │                             │
│ ┌──────────────┐ │         │                             │
│ │  Docling     │ │         │                             │
│ │  PyMuPDF     │ │         │                             │
│ │  PaddleOCR   │ │         │                             │
│ └──────────────┘ │         │                             │
└────────┬─────────┘         │                             │
         ▼                   │                             │
┌──────────────────┐         │                             │
│  Document        │         │                             │
│  Classification  │         │                             │
│  Engine          │         │                             │
└────────┬─────────┘         │                             │
         ▼                   │                             │
┌──────────────────┐         │                             │
│  Field           │         │                             │
│  Extraction      │         │                             │
│  Engine          │         │                             │
└────────┬─────────┘         │                             │
         ▼                   │                             │
┌──────────────────┐         │                             │
│  Validation      │         │                             │
│  Layer           │         │                             │
└────────┬─────────┘         │                             │
         ▼                   │                             │
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                           STORAGE LAYER                                                     │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐  ┌───────────────────────────┐   │
│  │  PostgreSQL   │  │  MinIO / S3      │  │  Redis       │  │  Qdrant Vector Store      │   │
│  │  ───────────  │  │  ───────────────  │  │  ──────────  │  │  ──────────────────────   │   │
│  │  Metadata     │  │  Raw documents   │  │  Cache       │  │  Dense embeddings         │   │
│  │  Extracted    │  │  Parsed output   │  │  Sessions    │  │  Sparse (BM25) indices    │   │
│  │  fields       │  │  Thumbnails      │  │  Rate limits │  │  Payloads (metadata)      │   │
│  │  Audit logs   │  │  Exports         │  │  Queues      │  │                           │   │
│  └──────────────┘  └──────────────────┘  └──────────────┘  └───────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────────────────────────────┘
                             │
         ┌───────────────────┼──────────────────────┐
         ▼                   ▼                      ▼
┌──────────────────┐ ┌───────────────┐ ┌────────────────────────────────────────────┐
│  Chunking +      │ │  Hybrid       │ │  Agent Orchestrator (LangGraph)            │
│  Embedding       │ │  Retrieval    │ │  ┌────────────────┐  ┌──────────────────┐  │
│  Pipeline        │ │  Engine       │ │  │  Tool Registry │  │  Tool Validation │  │
│  ┌────────────┐  │ │  ┌─────────┐  │ │  └────────────────┘  └──────────────────┘  │
│  │  bge-m3    │  │ │  │  Dense  │  │ │  ┌────────────────┐  ┌──────────────────┐  │
│  │  embeddings│  │ │  │  BM25   │  │ │  │  Tool Executor │  │  State Manager   │  │
│  └────────────┘  │ │  │  RRF    │  │ │  └────────────────┘  └──────────────────┘  │
│                  │ │  └─────────┘  │ │                                            │
└──────────────────┘ └───────┬───────┘ │  ┌────────────────────────────────────────┐│
                             │         │  │  Context Pack Compiler                 ││
                             ▼         │  │  (assemble retrieved chunks + metadata ││
                      ┌──────────────┐ │  │   into LLM-ready context)              ││
                      │  Reranker    │ │  └────────────────────────────────────────┘│
                      │  bge-        │ └────────────────────┬────────────────────────┘
                      │  reranker-   │                      │
                      │  v2-m3       │                      ▼
                      └──────────────┘           ┌──────────────────────┐
                                                 │  Final Answer /      │
                                                 │  Report / Checklist  │
                                                 └──────────┬───────────┘
                                                            │
                                                 ┌──────────▼───────────┐
                                                 │  Observability Stack │
                                                 │  ┌────────┐┌───────┐│
                                                 │  │Langfuse││  OTel ││
                                                 │  └────────┘└───────┘│
                                                 │  ┌────────┐┌───────┐│
                                                 │  │Promethe-││Grafana││
                                                 │  │us       ││       ││
                                                 │  └────────┘└───────┘│
                                                 └──────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 API Gateway (FastAPI)

**Responsibility**: Single entry point for all client requests. Handles authentication, rate limiting, request routing, input validation, and response serialization.

```python
# Application structure
app/
├── main.py                  # FastAPI app factory
├── api/
│   ├── v1/
│   │   ├── documents.py     # POST /documents/upload, GET /documents/{id}
│   │   ├── qa.py            # POST /qa/ask
│   │   ├── reports.py       # POST /reports/generate
│   │   └── health.py        # GET /health, GET /ready
│   └── deps.py              # Dependency injection (DB session, current user, etc.)
├── middleware/
│   ├── auth.py              # JWT / API key validation
│   ├── rate_limit.py        # Redis-backed sliding window rate limiter
│   ├── request_id.py        # X-Request-ID propagation
│   └── logging.py           # Structured request/response logging
└── schemas/
    ├── documents.py          # Pydantic request/response models
    ├── qa.py
    └── reports.py
```

**Key decisions**:
- Async endpoints (`async def`) with `asyncpg` for non-blocking DB access.
- Pydantic v2 for all request/response validation with strict mode.
- Background tasks via `BackgroundTasks` for lightweight jobs; Celery/RQ for heavy workloads.

### 3.2 Document Upload Service

**Responsibility**: Accept file uploads, perform initial validation (file type, size limits, virus scan), store raw files in object storage, and enqueue parsing jobs.

| Feature | Implementation |
|---|---|
| Max file size | 50 MB (configurable) |
| Allowed types | `.pdf`, `.docx`, `.png`, `.jpg`, `.jpeg`, `.tiff` |
| Storage target | MinIO (S3-compatible) with path: `{tenant}/{doc_id}/raw/{filename}` |
| Deduplication | SHA-256 content hash; skip re-processing if hash exists |
| Async processing | Redis queue (`doc:parse:pending`) with worker consumers |

### 3.3 Document Parsing Pipeline

**Responsibility**: Extract raw text, tables, images, and structural layout from uploaded documents.

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Raw File   │────▶│  Format      │────▶│  Parser      │────▶│  Parsed      │
│  (S3 ref)   │     │  Detection   │     │  Selection   │     │  Output      │
└─────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                  │
                                           ┌──────────────────────┼──────────────┐
                                           ▼                      ▼              ▼
                                     ┌───────────┐       ┌────────────┐   ┌──────────┐
                                     │  Text     │       │  Tables    │   │  Images  │
                                     │  Blocks   │       │  (HTML/    │   │  (base64 │
                                     │           │       │   Markdown)│   │   refs)  │
                                     └───────────┘       └────────────┘   └──────────┘
```

| Parser | Use Case | Strengths |
|---|---|---|
| **Docling** | Primary parser for PDF/DOCX | Layout-aware, table extraction, multi-modal |
| **PyMuPDF** | Fallback PDF parser | Fast, reliable for text-heavy PDFs |
| **PaddleOCR** | Scanned documents / images | High-accuracy OCR for CJK + Latin scripts |

**Parser selection logic**:
1. If PDF has embedded text layer → Docling first, PyMuPDF fallback.
2. If PDF is scanned (no text layer) → PaddleOCR.
3. If DOCX → Docling native DOCX parser.
4. If image (PNG/JPG/TIFF) → PaddleOCR.

**Output schema** (Pydantic model):

```python
class ParsedDocument(BaseModel):
    doc_id: str
    pages: list[PageContent]
    tables: list[TableContent]
    images: list[ImageRef]
    metadata: DocumentMetadata
    parse_duration_ms: int
    parser_used: str

class PageContent(BaseModel):
    page_number: int
    text: str
    layout_blocks: list[LayoutBlock]

class TableContent(BaseModel):
    page_number: int
    table_index: int
    headers: list[str]
    rows: list[list[str]]
    html: str
    markdown: str
```

### 3.4 Classification Engine

**Responsibility**: Automatically detect document type to drive downstream extraction schemas and validation rules.

| Approach | Details |
|---|---|
| Primary | Zero-shot classification via LLM with structured output (Pydantic) |
| Fallback | Keyword/heuristic classifier for offline or cost-sensitive mode |
| Supported types | `invoice`, `contract`, `report`, `form`, `receipt`, `letter`, `other` |

Classification output determines:
- Which extraction schema to apply (Section 3.5)
- Which validation rule set to run (Section 3.6)
- Which metadata fields to index in Qdrant payloads

### 3.5 Field Extraction Engine

**Responsibility**: Extract structured key-value fields from parsed documents using schema-driven prompts.

```yaml
# Example extraction schema: invoice
invoice:
  fields:
    - name: invoice_number
      type: string
      required: true
      description: "Unique invoice identifier"
    - name: invoice_date
      type: date
      required: true
    - name: due_date
      type: date
      required: false
    - name: total_amount
      type: decimal
      required: true
    - name: currency
      type: string
      required: true
      default: "USD"
    - name: vendor_name
      type: string
      required: true
    - name: line_items
      type: array
      items:
        description: { type: string }
        quantity: { type: integer }
        unit_price: { type: decimal }
        amount: { type: decimal }
```

**Extraction strategy**:
1. Pass parsed text + schema to LLM with structured output (`response_model=InvoiceFields`).
2. Confidence score per field (0.0–1.0). Fields below threshold flagged for human review.
3. Regex post-processing for known patterns (dates, amounts, IDs).

### 3.6 Validation Layer

**Responsibility**: Validate extracted fields against business rules, cross-field consistency, and external references.

| Validation Type | Example |
|---|---|
| Format | Date is valid ISO 8601, amount is positive decimal |
| Cross-field | `due_date > invoice_date`, `sum(line_items) ≈ total_amount` |
| Business rule | Vendor exists in approved vendor list |
| Duplicate detection | Same invoice number not already processed |

Validation results are persisted as a `ValidationReport` with severity levels: `error`, `warning`, `info`.

### 3.7 Storage Layer

#### PostgreSQL

| Table | Purpose |
|---|---|
| `documents` | Core document metadata, status, classification |
| `extracted_fields` | Key-value pairs extracted per document |
| `validation_reports` | Validation results with severity |
| `audit_log` | Immutable event log (who did what, when) |
| `users` / `tenants` | Multi-tenancy support |
| `chunks` | Text chunk references (links to vector store) |

**Connection pooling**: `asyncpg` with `asyncpg.create_pool(min_size=5, max_size=20)`.

**Migrations**: Alembic with version-controlled migration scripts.

#### MinIO / S3

| Path Pattern | Content |
|---|---|
| `{tenant_id}/{doc_id}/raw/{filename}` | Original uploaded file |
| `{tenant_id}/{doc_id}/parsed/output.json` | Parsed document output |
| `{tenant_id}/{doc_id}/pages/{n}.png` | Page-level images (for OCR) |
| `{tenant_id}/{doc_id}/thumbnails/` | Generated thumbnails |
| `exports/{report_id}/` | Generated reports |

#### Redis

| Key Pattern | Purpose | TTL |
|---|---|---|
| `session:{session_id}` | User session data | 24h |
| `rate:{user_id}:{window}` | Rate limiting counters | Per window |
| `cache:doc:{doc_id}:meta` | Cached document metadata | 1h |
| `queue:doc:parse:pending` | Parse job queue | N/A (persistent) |
| `lock:doc:{doc_id}` | Distributed lock for concurrent processing | 60s |

### 3.8 Embedding Pipeline

**Responsibility**: Chunk parsed documents and generate dense + sparse embeddings for vector search.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Parsed      │────▶│  Chunking    │────▶│  Embedding   │────▶│  Qdrant      │
│  Document    │     │  Strategy    │     │  Generation  │     │  Upsert      │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

**Chunking strategy**:
- **Method**: Recursive character splitter with document-structure-aware separators (`\n\n`, `\n`, `. `).
- **Chunk size**: 512 tokens (configurable).
- **Overlap**: 64 tokens.
- **Metadata preserved per chunk**: `doc_id`, `page_number`, `chunk_index`, `section_title`, `doc_type`.

**Embedding model**: `bge-m3` (BAAI)
- Dense embeddings: 1024 dimensions
- Sparse embeddings (BM25-style): native support via `bge-m3`
- Batched inference for throughput (batch size 32)

### 3.9 Vector Store (Qdrant)

**Responsibility**: Store and retrieve document embeddings for similarity search.

| Configuration | Value |
|---|---|
| Collection name | `documents` |
| Dense vector dimension | 1024 |
| Distance metric | Cosine |
| Sparse vectors | Enabled (native Qdrant sparse support) |
| Payload indexing | `doc_type`, `tenant_id`, `page_number`, `created_at` |
| HNSW parameters | `m=16`, `ef_construct=128`, `ef=128` |

**Collection schema**:

```json
{
  "vectors": {
    "dense": {
      "size": 1024,
      "distance": "Cosine"
    }
  },
  "sparse_vectors": {
    "bm25": {}
  },
  "payload_schema": {
    "doc_id": { "type": "keyword" },
    "tenant_id": { "type": "keyword" },
    "doc_type": { "type": "keyword" },
    "page_number": { "type": "integer" },
    "chunk_index": { "type": "integer" },
    "text": { "type": "text" },
    "created_at": { "type": "datetime" }
  }
}
```

### 3.10 Retrieval Engine (Hybrid: Dense + BM25 + RRF)

**Responsibility**: Retrieve the most relevant chunks for a given query using multiple retrieval strategies fused via Reciprocal Rank Fusion (RRF).

```
                    ┌──────────────────────────┐
                    │       User Query         │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   Query Embedding        │
                    │   (bge-m3 dense + sparse)│
                    └────────────┬─────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │  Dense       │   │  Sparse      │   │  Metadata    │
    │  Vector      │   │  (BM25)      │   │  Filter      │
    │  Search      │   │  Search      │   │  (optional)  │
    │  (top-k=20)  │   │  (top-k=20)  │   │              │
    └──────┬───────┘   └──────┬───────┘   └──────────────┘
           │                  │
           ▼                  ▼
    ┌──────────────────────────────────────┐
    │   Reciprocal Rank Fusion (RRF)      │
    │   score(d) = Σ 1/(k + rank_i(d))   │
    │   k = 60 (default)                  │
    └──────────────────┬───────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │  Top-N results │
              │  (N = 10)      │
              └────────────────┘
```

**RRF formula**:
```
RRF_score(d) = Σ_{i ∈ retrievers} 1 / (k + rank_i(d))
```

Where `k=60` is a smoothing constant that prevents top-ranked documents from dominating.

### 3.11 Reranker

**Responsibility**: Refine retrieval results using a cross-encoder model for higher precision.

| Configuration | Value |
|---|---|
| Model | `bge-reranker-v2-m3` (BAAI) |
| Input | Query + each retrieved chunk |
| Output | Relevance score (logits) |
| Top-N after rerank | 5 (configurable) |
| Max input length | 8192 tokens |

The reranker operates as a second-pass filter after the hybrid retrieval, ensuring the context window is filled with the highest-quality evidence.

### 3.12 Context Pack Compiler

**Responsibility**: Assemble retrieved chunks, metadata, and system instructions into a structured prompt for the LLM.

```python
class ContextPack(BaseModel):
    query: str
    chunks: list[ScoredChunk]          # top-N after reranking
    document_metadata: list[DocMeta]   # source document info
    system_prompt: str                 # agent-specific instructions
    tools_available: list[ToolDef]     # tools the agent can invoke
    conversation_history: list[Message] # prior turns
    max_context_tokens: int = 8192
```

**Token budget allocation**:
- System prompt: ~1000 tokens
- Conversation history: ~1500 tokens
- Retrieved context: ~4000 tokens
- Tool descriptions: ~1000 tokens
- Reserved for output: ~500 tokens

### 3.13 Agent Orchestrator (LangGraph)

**Responsibility**: Manage multi-step reasoning, tool invocation, and state transitions using a graph-based workflow.

```
┌─────────────┐
│   START     │
│   (receive  │
│    query)   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  RETRIEVE   │  ← Retrieve relevant chunks
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  RERANK     │  ← Rerank retrieved results
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  COMPILE    │  ← Build context pack
│  CONTEXT    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│  DECIDE     │────▶│  TOOL_CALL   │ ← If agent decides to use a tool
│  (LLM)      │     └──────┬───────┘
└──────┬──────┘            │
       │                   ▼
       │           ┌──────────────┐
       │           │  VALIDATE    │ ← Validate tool arguments
       │           │  TOOL_ARGS   │
       │           └──────┬───────┘
       │                   │
       │                   ▼
       │           ┌──────────────┐
       │           │  EXECUTE     │ ← Execute tool
       │           │  TOOL        │
       │           └──────┬───────┘
       │                   │
       │                   ▼
       │           ┌──────────────┐
       └───────────│  UPDATE      │ ← Update state with tool result
                   │  STATE       │
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │  DECIDE      │ ← Continue or finish
                   │  (LLM)       │
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │  FINAL       │ ← Generate final answer
                   │  ANSWER      │
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │    END       │
                   └──────────────┘
```

**LangGraph state schema**:

```python
class AgentState(TypedDict):
    query: str
    conversation_history: list[Message]
    retrieved_chunks: list[ScoredChunk]
    reranked_chunks: list[ScoredChunk]
    context_pack: ContextPack
    tool_calls: list[ToolCall]
    tool_results: list[ToolResult]
    intermediate_reasoning: list[str]
    final_answer: str | None
    sources: list[SourceCitation]
    metadata: dict
```

### 3.14 Tool Registry

**Responsibility**: Catalog and manage tools available to the agent with their schemas, permissions, and execution handlers.

```python
class ToolDefinition(BaseModel):
    name: str                          # e.g., "search_documents"
    description: str                   # Natural language description for LLM
    parameters: dict                   # JSON Schema for parameters
    handler: str                       # Dotted path to handler function
    requires_auth: bool = True
    timeout_seconds: int = 30
    retry_policy: RetryPolicy | None = None

# Registered tools:
# - search_documents: Search across indexed documents
# - get_document_details: Retrieve full document metadata + fields
# - validate_fields: Run validation on extracted fields
# - generate_report: Create a summary report from multiple documents
# - create_checklist: Generate a compliance/action checklist
# - list_documents: List documents with filters
```

### 3.15 Observability Stack

| Component | Role |
|---|---|
| **Langfuse** | LLM call tracing, prompt management, cost tracking, evaluation |
| **OpenTelemetry** | Distributed tracing across all services, spans for each pipeline stage |
| **Prometheus** | Metrics collection (request latency, error rates, queue depths) |
| **Grafana** | Dashboards for operational monitoring |
| **Structured Logging** | JSON logs via `structlog` with request ID correlation |

**Key metrics tracked**:

| Metric | Description |
|---|---|
| `doc_parse_duration_seconds` | Time to parse a document |
| `doc_classification_confidence` | Classification confidence score |
| `extraction_field_accuracy` | Field extraction accuracy (vs. ground truth) |
| `retrieval_recall_at_k` | Retrieval recall at k=5,10,20 |
| `reranker_improvement` | NDCG improvement from reranking |
| `agent_tool_call_count` | Number of tool invocations per query |
| `agent_total_latency_seconds` | End-to-end Q&A latency |
| `llm_tokens_consumed` | Token usage per request (input + output) |

---

## 4. Data Flow Diagrams

### 4.1 Document Upload Flow

```
User                  API Gateway         Upload Service       MinIO            Redis              Worker
 │                        │                    │                │                │                   │
 │  POST /documents       │                    │                │                │                   │
 │  (multipart/form-data) │                    │                │                │                   │
 ├───────────────────────▶│                    │                │                │                   │
 │                        │  Validate auth     │                │                │                   │
 │                        │  + file params     │                │                │                   │
 │                        ├───────────────────▶│                │                │                   │
 │                        │                    │  Compute       │                │                   │
 │                        │                    │  SHA-256 hash  │                │                   │
 │                        │                    │                │                │                   │
 │                        │                    │  Check dedup   │                │                   │
 │                        │                    │───────────────────────────────▶│                   │
 │                        │                    │                │                │                   │
 │                        │                    │  Upload raw    │                │                   │
 │                        │                    │  file to S3    │                │                   │
 │                        │                    ├───────────────▶│                │                   │
 │                        │                    │                │                │                   │
 │                        │                    │  Create DB     │                │                   │
 │                        │                    │  record (status│                │                   │
 │                        │                    │  = "uploaded") │                │                   │
 │                        │                    │                │                │                   │
 │                        │                    │  Enqueue parse │                │                   │
 │                        │                    │  job           │                │                   │
 │                        │                    ├───────────────────────────────▶│                   │
 │                        │                    │                │                │                   │
 │                        │  Return 201        │                │                │                   │
 │                        │  {doc_id, status}  │                │                │                   │
 │◀───────────────────────┤                    │                │                │                   │
 │                        │                    │                │                │  Dequeue job      │
 │                        │                    │                │                │                   │
 │                        │                    │                │                │◀──────────────────│
 │                        │                    │                │                │                   │
 │                        │                    │                │                │  Start parse      │
 │                        │                    │                │                │  pipeline         │
```

### 4.2 Document Parsing Flow

```
Worker                S3               Docling/OCR        Classification      Extraction       Validation     PostgreSQL
 │                    │                    │                    │                  │                │               │
 │  Download raw      │                    │                    │                  │                │               │
 │  file from S3      │                    │                    │                  │                │               │
 ├───────────────────▶│                    │                    │                  │                │               │
 │◀───────────────────│                    │                    │                  │                │               │
 │                    │                    │                    │                  │                │               │
 │  Update status     │                    │                    │                  │                │               │
 │  = "parsing"       │                    │                    │                  │                │               │
 ├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────▶│
 │                    │                    │                    │                  │                │               │
 │  Run parser        │                    │                    │                  │                │               │
 │  (Docling/PyMuPDF/ │                    │                    │                  │                │               │
 │   PaddleOCR)       │                    │                    │                  │                │               │
 ├───────────────────▶│                    │                    │                  │                │               │
 │◀───────────────────│                    │                    │                  │                │               │
 │                    │                    │                    │                  │                │               │
 │  Store parsed      │                    │                    │                  │                │               │
 │  output to S3      │                    │                    │                  │                │               │
 ├───────────────────▶│                    │                    │                  │                │               │
 │                    │                    │                    │                  │                │               │
 │  Classify doc      │                    │                    │                  │                │               │
 ├───────────────────────────────────────▶│                    │                  │                │               │
 │◀───────────────────────────────────────│                    │                  │                │               │
 │                    │                    │                    │                  │                │               │
 │  Extract fields    │                    │                    │                  │                │               │
 ├─────────────────────────────────────────────────────────────▶│                  │                │               │
 │◀─────────────────────────────────────────────────────────────│                  │                │               │
 │                    │                    │                    │                  │                │               │
 │  Validate fields   │                    │                    │                  │                │               │
 ├────────────────────────────────────────────────────────────────────────────────▶│                │               │
 │◀────────────────────────────────────────────────────────────────────────────────│                │               │
 │                    │                    │                    │                  │                │               │
 │  Persist results   │                    │                    │                  │                │               │
 ├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────▶│
 │                    │                    │                    │                  │                │               │
 │  Enqueue chunking  │                    │                    │                  │                │               │
 │  + embedding job   │                    │                    │                  │                │               │
```

### 4.3 Q&A Flow

```
User              API Gateway       Agent Orchestrator     Retrieval Engine     Reranker     Qdrant       LLM
 │                    │                    │                    │                 │            │            │
 │  POST /qa/ask      │                    │                    │                 │            │            │
 │  {question}        │                    │                    │                 │            │            │
 ├───────────────────▶│                    │                    │                 │            │            │
 │                    │  Route + validate  │                    │                 │            │            │
 │                    ├───────────────────▶│                    │                 │            │            │
 │                    │                    │                    │                 │            │            │
 │                    │                    │  Embed query       │                 │            │            │
 │                    │                    │  (bge-m3)          │                 │            │            │
 │                    │                    │                    │                 │            │            │
 │                    │                    │  Hybrid search     │                 │            │            │
 │                    │                    ├───────────────────▶│                 │            │            │
 │                    │                    │                    │  Dense search   │            │            │
 │                    │                    │                    ├─────────────────────────────▶│            │
 │                    │                    │                    │◀─────────────────────────────│            │
 │                    │                    │                    │  BM25 search    │            │            │
 │                    │                    │                    ├─────────────────────────────▶│            │
 │                    │                    │                    │◀─────────────────────────────│            │
 │                    │                    │                    │  RRF fusion     │            │            │
 │                    │                    │◀───────────────────│                 │            │            │
 │                    │                    │                    │                 │            │            │
 │                    │                    │  Rerank results    │                 │            │            │
 │                    │                    ├────────────────────────────────────▶│            │            │
 │                    │                    │◀────────────────────────────────────│            │            │
 │                    │                    │                    │                 │            │            │
 │                    │                    │  Compile context   │                 │            │            │
 │                    │                    │  pack              │                 │            │            │
 │                    │                    │                    │                 │            │            │
 │                    │                    │  LLM call          │                 │            │            │
 │                    │                    ├─────────────────────────────────────────────────────────────▶│
 │                    │                    │                    │                 │            │            │
 │                    │                    │  (may trigger      │                 │            │            │
 │                    │                    │   tool calls and   │                 │            │            │
 │                    │                    │   re-invoke LLM)   │                 │            │            │
 │                    │                    │◀─────────────────────────────────────────────────────────────│
 │                    │                    │                    │                 │            │            │
 │                    │  Return answer     │                    │                 │            │            │
 │                    │  + sources         │                    │                 │            │            │
 │◀───────────────────┤                    │                    │                 │            │            │
```

### 4.4 Report Generation Flow

```
User              API Gateway       Agent Orchestrator     Tool Executor      PostgreSQL     LLM         Export
 │                    │                    │                    │                │            │            │
 │  POST /reports     │                    │                    │                │            │            │
 │  {doc_ids, type}   │                    │                    │                │            │            │
 ├───────────────────▶│                    │                    │                │            │            │
 │                    ├───────────────────▶│                    │                │            │            │
 │                    │                    │                    │                │            │            │
 │                    │                    │  Retrieve doc      │                │            │            │
 │                    │                    │  metadata + fields │                │            │            │
 │                    │                    ├───────────────────▶│                │            │            │
 │                    │                    │                    ├───────────────▶│            │            │
 │                    │                    │                    │◀───────────────│            │            │
 │                    │                    │◀───────────────────│                │            │            │
 │                    │                    │                    │                │            │            │
 │                    │                    │  Generate report   │                │            │            │
 │                    │                    │  via LLM           │                │            │            │
 │                    │                    ├────────────────────────────────────────────────▶│            │
 │                    │                    │◀────────────────────────────────────────────────│            │
 │                    │                    │                    │                │            │            │
 │                    │                    │  Format output     │                │            │            │
 │                    │                    │  (PDF / Markdown)  │                │            │            │
 │                    │                    ├─────────────────────────────────────────────────────────────▶│
 │                    │                    │◀─────────────────────────────────────────────────────────────│
 │                    │                    │                    │                │            │            │
 │                    │  Return report     │                    │                │            │            │
 │                    │  URL + metadata    │                    │                │            │            │
 │◀───────────────────┤                    │                    │                │            │            │
```

---

## 5. Technology Decisions & Trade-offs

| Decision | Choice | Alternatives Considered | Rationale |
|---|---|---|---|
| **Web framework** | FastAPI | Flask, Django REST | Async native, Pydantic integration, auto OpenAPI docs, high performance |
| **Frontend** | Next.js (App Router) | React SPA, Vue | SSR for SEO, server actions for API calls, good DX with TypeScript |
| **Agent framework** | LangGraph | LangChain Agents, AutoGen, CrewAI | Explicit state graph, checkpointing, human-in-the-loop support, type-safe state |
| **Primary database** | PostgreSQL | MySQL, MongoDB | JSONB for flexible schemas, full-text search, mature ecosystem, strong ACID |
| **Object storage** | MinIO (S3-compatible) | AWS S3, Azure Blob | Self-hosted option, S3 API compatibility, no vendor lock-in |
| **Cache / Queue** | Redis | RabbitMQ, Kafka | Multi-purpose (cache + queue + rate limiting), simple ops, sufficient throughput |
| **Vector store** | Qdrant | Pinecone, Weaviate, Milvus, Chroma | Sparse + dense hybrid search native support, Rust performance, easy deployment |
| **Embedding model** | bge-m3 | OpenAI ada-002, E5, Jina | Multi-lingual, dense+sparse in one model, good cost/quality ratio, runs locally |
| **Reranker** | bge-reranker-v2-m3 | Cohere, cross-encoder-ms-marco | Multi-lingual, long context (8K), pairs well with bge-m3, runs locally |
| **Document parser** | Docling + PyMuPDF + PaddleOCR | Apache Tika, Unstructured.io | Docling for layout-aware parsing, PyMuPDF for speed, PaddleOCR for scanned docs |
| **Validation** | Pydantic v2 | Marshmallow, Cerberus | Fast, type-safe, integrates with FastAPI and LangChain natively |
| **Observability** | Langfuse + OpenTelemetry | LangSmith, Helicone, custom | Langfuse for LLM-specific tracing + prompt management, OTel for infrastructure |
| **Containerization** | Docker Compose | K8s, ECS | Appropriate for single-node/small-team deployment, easy local dev, can migrate to K8s later |

---

## 6. Scalability Considerations

### Horizontal Scaling

| Component | Scaling Strategy |
|---|---|
| API Gateway | Stateless; scale behind load balancer (nginx/traefik) |
| Document Workers | Add workers to consumer group; Redis queue auto-distributes |
| Embedding Service | GPU-backed replicas; batch requests for throughput |
| PostgreSQL | Read replicas for query-heavy workloads; connection pooling |
| Qdrant | Sharding + replication at collection level |
| Redis | Redis Cluster for high availability; Sentinel for failover |

### Vertical Scaling

| Bottleneck | Mitigation |
|---|---|
| OCR processing (CPU/GPU) | Dedicated GPU node for PaddleOCR; off-peak batch scheduling |
| LLM inference | Use API providers (OpenAI, Anthropic) for burst; self-host for steady state |
| Large document parsing | Streaming parser; process pages in parallel |

### Queue-Based Decoupling

All long-running operations (parsing, embedding, report generation) are decoupled via Redis queues:

```
Upload API → Redis Queue → Parse Worker → Redis Queue → Embed Worker → Qdrant
```

This prevents API timeouts and allows independent scaling of each pipeline stage.

---

## 7. Failure Handling Strategy

### Per-Component Failure Modes

| Component | Failure Mode | Mitigation |
|---|---|---|
| **Document parser** | Corrupted file, unsupported format | Fallback parser chain; mark doc as `parse_failed` with error details; user can retry |
| **OCR** | Low confidence, garbled output | Confidence threshold check; flag for human review; store raw image for re-processing |
| **Classification** | Ambiguous document | Default to `other` type; use generic extraction schema; log for model improvement |
| **Field extraction** | Missing fields, hallucinated values | Pydantic validation catches type errors; cross-field validation catches inconsistencies; confidence scoring |
| **Validation** | Business rule violation | Severity-based: `error` blocks processing, `warning` allows with flag, `info` is advisory |
| **Embedding service** | Model unavailable, OOM | Retry with exponential backoff; fallback to smaller model; queue for later processing |
| **Qdrant** | Connection failure | Retry with backoff; serve cached results if available; degrade to keyword search |
| **LLM** | Rate limit, timeout, hallucination | Retry with backoff; circuit breaker pattern; structured output validation; cite sources |
| **PostgreSQL** | Connection pool exhaustion | Async pool with overflow; read replica failover; cache-first reads |
| **Redis** | Cache miss, connection failure | Graceful degradation (skip cache); persistent queues survive Redis restart via AOF |

### Circuit Breaker Pattern

Applied to external services (LLM APIs, Qdrant):

```python
circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30,
    expected_exceptions=(ConnectionError, TimeoutError)
)
```

### Retry Policy

| Operation | Max Retries | Backoff | Jitter |
|---|---|---|---|
| File upload to S3 | 3 | 1s, 2s, 4s | Yes |
| LLM API call | 3 | 2s, 4s, 8s | Yes |
| Qdrant upsert | 3 | 1s, 2s, 4s | Yes |
| PostgreSQL write | 2 | 0.5s, 1s | Yes |

---

## 8. Security Architecture

### Authentication & Authorization

| Layer | Mechanism |
|---|---|
| API Authentication | JWT tokens (RS256) with short-lived access tokens (15min) + refresh tokens (7d) |
| API Key Auth | For programmatic access; scoped to specific operations |
| RBAC | Role-based access: `admin`, `operator`, `viewer` |
| Multi-tenancy | Row-level security in PostgreSQL; S3 path isolation per tenant |

### Data Protection

| Concern | Approach |
|---|---|
| Data at rest | PostgreSQL TDE; S3 server-side encryption (AES-256) |
| Data in transit | TLS 1.3 for all internal and external communication |
| Secrets management | Environment variables via Docker secrets; no hardcoded credentials |
| PII handling | Configurable PII detection + redaction in parsed text before storage |

### Input Validation

- All API inputs validated via Pydantic models with strict mode.
- File upload: magic byte verification (not just extension), size limits, malware scanning (ClamAV integration).
- SQL injection: prevented by parameterized queries (SQLAlchemy async).
- Prompt injection: input sanitization for user queries before LLM invocation.

### Network Security

- All services communicate within Docker network; only API gateway exposed externally.
- Rate limiting: 100 req/min per user (configurable).
- CORS: strict origin allowlist.
- Request size limits: 50 MB for uploads, 1 MB for JSON payloads.

---

## 9. Deployment Architecture

### Docker Compose (Development / Single-Node Production)

```yaml
services:
  api:
    build: ./app
    ports: ["8000:8000"]
    depends_on: [postgres, redis, qdrant, minio]
    environment:
      DATABASE_URL: postgresql+asyncpg://user:pass@postgres:5432/docops
      REDIS_URL: redis://redis:6379/0
      QDRANT_URL: http://qdrant:6333
      S3_ENDPOINT: http://minio:9000
      LANGFUSE_HOST: http://langfuse:3000

  worker:
    build: ./app
    command: celery -A app.worker worker -l info -c 4
    depends_on: [postgres, redis, qdrant, minio]
    deploy:
      replicas: 2

  embedding-service:
    build: ./embedding
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]

  postgres:
    image: postgres:16-alpine
    volumes: ["pg_data:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    volumes: ["redis_data:/data"]

  qdrant:
    image: qdrant/qdrant:v1.12.1
    volumes: ["qdrant_data:/qdrant/storage"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    volumes: ["minio_data:/data"]

  langfuse:
    image: langfuse/langfuse:latest
    ports: ["3000:3000"]

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs

  frontend:
    build: ./frontend
    depends_on: [api]

volumes:
  pg_data:
  redis_data:
  qdrant_data:
  minio_data:
```

### Directory Structure

```
AI-document-operations-agent/
├── app/                          # Backend API + Worker
│   ├── api/                      # FastAPI routes
│   ├── core/                     # Config, security, dependencies
│   ├── models/                   # SQLAlchemy + Pydantic models
│   ├── services/                 # Business logic
│   │   ├── document_service.py
│   │   ├── parsing_service.py
│   │   ├── classification_service.py
│   │   ├── extraction_service.py
│   │   ├── validation_service.py
│   │   ├── embedding_service.py
│   │   ├── retrieval_service.py
│   │   ├── reranker_service.py
│   │   ├── context_compiler.py
│   │   └── report_service.py
│   ├── agent/                    # LangGraph agent
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── tools.py
│   │   └── prompts/
│   ├── worker.py                 # Celery worker
│   └── main.py                   # FastAPI app
├── frontend/                     # Next.js application
├── embedding/                    # Embedding model service
├── nginx/                        # Reverse proxy config
├── docs/                         # Documentation (this file)
├── tests/                        # Test suite
├── alembic/                      # Database migrations
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

### Production Considerations

| Concern | Recommendation |
|---|---|
| Container orchestration | Migrate to Kubernetes (Helm charts) for multi-node |
| CI/CD | GitHub Actions: lint → test → build → deploy |
| Monitoring | Prometheus + Grafana dashboards for all metrics |
| Log aggregation | Loki or ELK stack for centralized logging |
| Backup | PostgreSQL: pg_dump + WAL archiving; S3: cross-region replication |
| SSL termination | Nginx / Traefik with Let's Encrypt |

---

## 10. Implementation Checklist

### Phase 1: Foundation (Week 1-2)

- [ ] Project scaffolding (FastAPI app, Next.js frontend, Docker Compose)
- [ ] PostgreSQL schema design + Alembic migrations
- [ ] MinIO integration for object storage
- [ ] Redis setup for caching + queues
- [ ] Basic API Gateway with auth middleware (JWT)
- [ ] Health check endpoints (`/health`, `/ready`)
- [ ] CI pipeline (lint, type check, unit tests)

### Phase 2: Document Ingestion (Week 3-4)

- [ ] Document upload endpoint with validation
- [ ] File deduplication (SHA-256)
- [ ] Raw file storage in MinIO
- [ ] Worker infrastructure (Celery + Redis broker)
- [ ] Document parsing pipeline (Docling for PDF/DOCX)
- [ ] PaddleOCR integration for scanned documents
- [ ] PyMuPDF fallback parser
- [ ] Parsed output storage and DB status updates

### Phase 3: Classification & Extraction (Week 5-6)

- [ ] Document classification engine (zero-shot + heuristic fallback)
- [ ] Extraction schema definitions (YAML/JSON per doc type)
- [ ] Field extraction via LLM with Pydantic structured output
- [ ] Confidence scoring per extracted field
- [ ] Validation layer (format, cross-field, business rules)
- [ ] Validation report generation
- [ ] Human review flagging for low-confidence extractions

### Phase 4: Embedding & Retrieval (Week 7-8)

- [ ] Qdrant collection setup with dense + sparse vectors
- [ ] Chunking pipeline (recursive splitter with structure awareness)
- [ ] bge-m3 embedding service (dense + sparse)
- [ ] Batch embedding worker
- [ ] Hybrid retrieval engine (dense + BM25 + RRF)
- [ ] bge-reranker-v2-m3 integration
- [ ] Context pack compiler with token budgeting
- [ ] Retrieval quality evaluation (recall@k, MRR)

### Phase 5: Agent & Q&A (Week 9-10)

- [ ] LangGraph agent graph definition
- [ ] Tool registry with JSON Schema definitions
- [ ] Tool validation and execution framework
- [ ] State management (conversation history, intermediate results)
- [ ] Q&A endpoint with streaming response
- [ ] Source citation in answers
- [ ] Multi-turn conversation support

### Phase 6: Reports & Observability (Week 11-12)

- [ ] Report generation tool (summary, checklist, compliance)
- [ ] Report export (PDF, Markdown)
- [ ] Langfuse integration for LLM tracing
- [ ] OpenTelemetry instrumentation for all services
- [ ] Prometheus metrics + Grafana dashboards
- [ ] Structured logging with request ID correlation
- [ ] Alert rules for error rates and latency SLAs

### Phase 7: Production Hardening (Week 13-14)

- [ ] Security audit (input validation, secrets, network isolation)
- [ ] Load testing (k6 / Locust) with target: 100 concurrent users
- [ ] Failure injection testing (parser failures, LLM timeouts, DB outages)
- [ ] Documentation (API docs, runbooks, architecture — this document)
- [ ] Backup and disaster recovery procedures
- [ ] Production deployment (staging → production)
- [ ] Monitoring and alerting validation

---

## Appendix A: Environment Variables

```bash
# Application
APP_ENV=production
APP_SECRET_KEY=<random-32-chars>
APP_LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/docops
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://redis:6379/0

# Qdrant
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=documents

# Object Storage
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=docops

# Embedding
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_BATCH_SIZE=32
EMBEDDING_DEVICE=cuda

# Reranker
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_N=5

# LLM
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=<your-key>
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.1

# Observability
LANGFUSE_PUBLIC_KEY=<key>
LANGFUSE_SECRET_KEY=<secret>
LANGFUSE_HOST=http://langfuse:3000
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# Auth
JWT_SECRET_KEY=<random-32-chars>
JWT_ALGORITHM=RS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
```

## Appendix B: API Endpoints Summary

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/documents/upload` | Upload a document |
| `GET` | `/api/v1/documents/{doc_id}` | Get document details + extracted fields |
| `GET` | `/api/v1/documents` | List documents with filters |
| `DELETE` | `/api/v1/documents/{doc_id}` | Soft-delete a document |
| `POST` | `/api/v1/documents/{doc_id}/reprocess` | Re-trigger parsing pipeline |
| `POST` | `/api/v1/qa/ask` | Ask a question (single-turn) |
| `POST` | `/api/v1/qa/chat` | Multi-turn conversation |
| `POST` | `/api/v1/reports/generate` | Generate a report |
| `GET` | `/api/v1/reports/{report_id}` | Get report content |
| `GET` | `/api/v1/reports/{report_id}/download` | Download report file |
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/ready` | Readiness check |
