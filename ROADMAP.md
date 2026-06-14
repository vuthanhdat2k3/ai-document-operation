# AI Document Operations Agent — Roadmap

> **Last updated:** 2026-06-11
> **Total estimated duration:** 18 weeks

---

## Table of Contents

- [Phase 0: Planning & Documentation](#phase-0-planning--documentation)
- [Phase 1: Project Skeleton](#phase-1-project-skeleton)
- [Phase 2: Document Upload & Storage](#phase-2-document-upload--storage)
- [Phase 3: Parsing / OCR Pipeline](#phase-3-parsing--ocr-pipeline)
- [Phase 4: Chunking + Embedding + Vector Store](#phase-4-chunking--embedding--vector-store)
- [Phase 5: RAG Q&A with Citations](#phase-5-rag-qa-with-citations)
- [Phase 6: Agent Harness + Tool Registry](#phase-6-agent-harness--tool-registry)
- [Phase 7: Field Extraction + Validation](#phase-7-field-extraction--validation)
- [Phase 8: Risk Detection + Checklist](#phase-8-risk-detection--checklist)
- [Phase 9: Report Export](#phase-9-report-export)
- [Phase 10: Observability + Evaluation](#phase-10-observability--evaluation)
- [Phase 11: Frontend Dashboard](#phase-11-frontend-dashboard)
- [Phase 12: Hardening + Deployment](#phase-12-hardening--deployment)

---

## Phase 0: Planning & Documentation

**Goal:** Establish a shared understanding of the system architecture, define conventions, and scaffold all project documentation before any code is written.

**Scope:** Documentation, architecture diagrams, project scaffolding.

### Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| 0.1 | Create `ARCHITECTURE.md` with system context, container, and component diagrams (C4 model) | Lead | ☐ |
| 0.2 | Create `ROADMAP.md` (this file) with all 13 phases | Lead | ☐ |
| 0.3 | Create `CONTRIBUTING.md` with branching strategy, commit conventions, PR template | Lead | ☐ |
| 0.4 | Create `AGENTS.md` with agent coding rules and conventions | Lead | ☐ |
| 0.5 | Create `API_SPEC.md` with OpenAPI 3.1 outline for all planned endpoints | Lead | ☐ |
| 0.6 | Create `DATA_MODEL.md` with ER diagram and table definitions | Lead | ☐ |
| 0.7 | Create `DEPLOYMENT.md` with infrastructure topology and runbook | Lead | ☐ |
| 0.8 | Create `SECURITY.md` with threat model and mitigation strategies | Lead | ☐ |
| 0.9 | Create `EVALUATION.md` with metrics definitions and gold dataset plan | Lead | ☐ |
| 0.10 | Review and finalize architecture with stakeholders | Team | ☐ |
| 0.11 | Setup monorepo directory structure (`backend/`, `frontend/`, `infra/`, `docs/`) | Lead | ☐ |

### Acceptance Criteria

- [ ] All documentation files exist and are peer-reviewed.
- [ ] Architecture diagram covers all system components and data flows.
- [ ] Directory structure is committed to the repository.
- [ ] Stakeholders have signed off on the architecture.

### Tests Required

- No automated tests in this phase.

### Docs to Update

- `ARCHITECTURE.md`, `ROADMAP.md`, `CONTRIBUTING.md`, `AGENTS.md`, `API_SPEC.md`, `DATA_MODEL.md`, `DEPLOYMENT.md`, `SECURITY.md`, `EVALUATION.md`

### Estimated Duration

**1 week**

---

## Phase 1: Project Skeleton

**Goal:** Bootstrap the backend, frontend, infrastructure, and CI/CD so that all subsequent phases can run on a working foundation.

**Scope:** Python backend, Next.js frontend, Docker Compose, database, cache, vector store, object storage, CI pipeline.

### Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| 1.1 | Initialize Python project with `pyproject.toml`, `ruff`, `mypy` strict config | Backend | ☐ |
| 1.2 | Create FastAPI application skeleton with lifespan events | Backend | ☐ |
| 1.3 | Initialize Next.js 14 project (App Router, TypeScript, Tailwind, shadcn/ui) | Frontend | ☐ |
| 1.4 | Create `docker-compose.yml` with PostgreSQL 16, Redis 7, Qdrant, MinIO | DevOps | ☐ |
| 1.5 | Setup Alembic with initial migration and `alembic.ini` | Backend | ☐ |
| 1.6 | Create SQLAlchemy 2.0 async engine and session factory | Backend | ☐ |
| 1.7 | Configure Redis connection pool and health check | Backend | ☐ |
| 1.8 | Configure Qdrant client and collection bootstrap | Backend | ☐ |
| 1.9 | Configure MinIO client and bucket creation on startup | Backend | ☐ |
| 1.10 | Create GitHub Actions CI workflow (lint, typecheck, test, docker build) | DevOps | ☐ |
| 1.11 | Create `GET /health` endpoint returning service status | Backend | ☐ |
| 1.12 | Create `GET /ready` endpoint checking all dependencies | Backend | ☐ |

### Acceptance Criteria

- [ ] `docker compose up` brings up all services without errors.
- [ ] `GET /health` returns `200 OK`.
- [ ] `GET /ready` returns status of PostgreSQL, Redis, Qdrant, MinIO.
- [ ] `ruff check` and `mypy --strict` pass with zero errors.
- [ ] CI pipeline runs green on the default branch.
- [ ] Alembic migration creates all tables successfully.

### Tests Required

- `tests/test_health.py` — health and readiness endpoint tests.
- `tests/test_infra.py` — database, Redis, Qdrant, MinIO connectivity tests.

### Docs to Update

- `DEPLOYMENT.md` — add local development setup instructions.
- `README.md` — add quickstart guide.

### Estimated Duration

**1–2 weeks**

---

## Phase 2: Document Upload & Storage

**Goal:** Enable users to upload documents that are validated, stored in MinIO, and tracked in PostgreSQL.

**Scope:** Upload API, file validation, MinIO integration, document CRUD.

### Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| 2.1 | Create `Document` SQLAlchemy model (id, filename, mime_type, size, checksum, status, created_at, updated_at) | Backend | ☐ |
| 2.2 | Create Alembic migration for `documents` table | Backend | ☐ |
| 2.3 | Implement file validation middleware (allowed types: PDF, DOCX, XLSX; max size: 100 MB; magic-byte check) | Backend | ☐ |
| 2.4 | Implement `POST /api/v1/documents` — multipart upload, store to MinIO, create DB record | Backend | ☐ |
| 2.5 | Implement `GET /api/v1/documents` — paginated list with filters | Backend | ☐ |
| 2.6 | Implement `GET /api/v1/documents/{id}` — document detail with metadata | Backend | ☐ |
| 2.7 | Implement `PATCH /api/v1/documents/{id}` — update metadata | Backend | ☐ |
| 2.8 | Implement `DELETE /api/v1/documents/{id}` — soft-delete (set status to `deleted`) | Backend | ☐ |
| 2.9 | Implement `GET /api/v1/documents/{id}/download` — presigned URL generation | Backend | ☐ |
| 2.10 | Create Pydantic request/response schemas for all endpoints | Backend | ☐ |

### Acceptance Criteria

- [ ] Uploading a valid PDF returns `201` with document metadata.
- [ ] Uploading an unsupported file type returns `415`.
- [ ] Uploading a file exceeding size limit returns `413`.
- [ ] CRUD operations return correct status codes and payloads.
- [ ] MinIO bucket contains the uploaded file with correct path.
- [ ] Database record matches uploaded file metadata.

### Tests Required

- `tests/api/test_documents.py` — integration tests for all CRUD endpoints.
- `tests/services/test_storage.py` — MinIO upload/download unit tests.
- `tests/services/test_validation.py` — file validation unit tests.

### Docs to Update

- `API_SPEC.md` — document upload endpoints.
- `DATA_MODEL.md` — `documents` table schema.

### Estimated Duration

**1–2 weeks**

---

## Phase 3: Parsing / OCR Pipeline

**Goal:** Extract structured text, tables, and layout information from uploaded documents using a combination of native parsers and OCR.

**Scope:** PDF, DOCX, XLSX parsing; OCR; layout detection; table extraction; quality scoring; background processing.

### Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| 3.1 | Create `ParsedDocument` and `ParsedPage` SQLAlchemy models | Backend | ☐ |
| 3.2 | Create Alembic migration for parsed document tables | Backend | ☐ |
| 3.3 | Implement PDF text extraction using PyMuPDF (`fitz`) | Backend | ☐ |
| 3.4 | Implement PDF OCR fallback using PaddleOCR for scanned pages | Backend | ☐ |
| 3.5 | Implement DOCX parsing using `python-docx` (paragraphs, tables, styles) | Backend | ☐ |
| 3.6 | Implement XLSX parsing using `openpyxl` (sheets, cells, formulas) | Backend | ☐ |
| 3.7 | Implement layout detection using Docling (page segmentation, reading order) | Backend | ☐ |
| 3.8 | Implement table extraction with structure recognition | Backend | ☐ |
| 3.9 | Implement quality scoring (confidence, completeness, readability) | Backend | ☐ |
| 3.10 | Create Celery worker with Redis broker for background task processing | Backend | ☐ |
| 3.11 | Create `POST /api/v1/documents/{id}/parse` — enqueue parsing job | Backend | ☐ |
| 3.12 | Create `GET /api/v1/documents/{id}/parse-status` — job status polling | Backend | ☐ |
| 3.13 | Create `GET /api/v1/documents/{id}/parsed` — retrieve parsed content | Backend | ☐ |

### Acceptance Criteria

- [ ] Parsing a text-based PDF extracts correct text per page.
- [ ] Parsing a scanned PDF triggers OCR and returns recognized text.
- [ ] DOCX parsing preserves paragraph structure and tables.
- [ ] XLSX parsing returns sheet names, cell values, and merged cell info.
- [ ] Quality score is between 0.0 and 1.0 for all parsed documents.
- [ ] Parsing runs as a background task and status is pollable.
- [ ] Parsed results are persisted in the database.

### Tests Required

- `tests/services/test_pdf_parser.py` — PDF extraction and OCR tests.
- `tests/services/test_docx_parser.py` — DOCX parsing tests.
- `tests/services/test_xlsx_parser.py` — XLSX parsing tests.
- `tests/services/test_quality_scorer.py` — quality scoring tests.
- `tests/workers/test_parse_task.py` — Celery task integration tests.

### Docs to Update

- `API_SPEC.md` — parsing endpoints.
- `ARCHITECTURE.md` — parsing pipeline diagram.
- `DATA_MODEL.md` — parsed document tables.

### Estimated Duration

**2–3 weeks**

---

## Phase 4: Chunking + Embedding + Vector Store

**Goal:** Split parsed documents into chunks, generate embeddings, and index them in Qdrant for semantic search.

**Scope:** Text chunking, embedding generation, Qdrant indexing, hybrid search.

### Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| 4.1 | Create `Chunk` SQLAlchemy model (id, document_id, page, text, metadata, embedding_id) | Backend | ☐ |
| 4.2 | Create Alembic migration for `chunks` table | Backend | ☐ |
| 4.3 | Implement recursive character text splitter with configurable chunk_size (512) and overlap (64) | Backend | ☐ |
| 4.4 | Implement semantic chunking using sentence-boundary detection | Backend | ☐ |
| 4.5 | Implement bge-m3 embedding generation (local or API) | Backend | ☐ |
| 4.6 | Create Qdrant collection with dense + sparse vector configs | Backend | ☐ |
| 4.7 | Implement chunk indexing pipeline (chunk → embed → upsert to Qdrant) | Backend | ☐ |
| 4.8 | Implement hybrid search (dense cosine + sparse BM25) | Backend | ☐ |
| 4.9 | Create `POST /api/v1/documents/{id}/index` — enqueue indexing job | Backend | ☐ |
| 4.10 | Create `GET /api/v1/search` — hybrid search endpoint | Backend | ☐ |

### Acceptance Criteria

- [ ] Chunking produces chunks within configured size limits.
- [ ] Overlapping text exists between consecutive chunks.
- [ ] Embedding vectors have correct dimensionality (1024 for bge-m3).
- [ ] Qdrant collection is created with both dense and sparse vectors.
- [ ] Hybrid search returns relevant results ranked by combined score.
- [ ] Indexing runs as a background task after parsing completes.

### Tests Required

- `tests/services/test_chunker.py` — chunking strategy tests.
- `tests/services/test_embedder.py` — embedding generation tests.
- `tests/services/test_vector_store.py` — Qdrant indexing and search tests.
- `tests/api/test_search.py` — search endpoint integration tests.

### Docs to Update

- `API_SPEC.md` — search endpoint.
- `ARCHITECTURE.md` — indexing pipeline.
- `DATA_MODEL.md` — `chunks` table.

### Estimated Duration

**1–2 weeks**

---

## Phase 5: RAG Q&A with Citations

**Goal:** Answer user questions about documents using retrieval-augmented generation with grounded citations and hallucination detection.

**Scope:** Query understanding, HyDE rewrite, metadata filtering, RRF fusion, reranking, context compilation, answer generation, citation extraction, groundedness validation.

### Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| 5.1 | Create `QASession` and `QAMessage` SQLAlchemy models | Backend | ☐ |
| 5.2 | Implement query understanding (intent classification, entity extraction) | Backend | ☐ |
| 5.3 | Implement HyDE (Hypothetical Document Embeddings) query rewrite | Backend | ☐ |
| 5.4 | Implement metadata filtering (by document, page, section) | Backend | ☐ |
| 5.5 | Implement RRF (Reciprocal Rank Fusion) for combining dense + sparse results | Backend | ☐ |
| 5.6 | Integrate bge-reranker-v2-m3 for cross-encoder reranking | Backend | ☐ |
| 5.7 | Implement context pack compilation (top-K chunks with source metadata) | Backend | ☐ |
| 5.8 | Implement grounded answer generation using LLM with structured prompt | Backend | ☐ |
| 5.9 | Implement citation extraction (map answer sentences to source chunks) | Backend | ☐ |
| 5.10 | Implement groundedness validation (score answer fidelity to sources) | Backend | ☐ |
| 5.11 | Create `POST /api/v1/qa/ask` — ask a question about documents | Backend | ☐ |
| 5.12 | Create `GET /api/v1/qa/sessions/{id}` — retrieve Q&A session history | Backend | ☐ |

### Acceptance Criteria

- [ ] Asking a question returns an answer with at least one citation.
- [ ] Citations include document ID, page number, and source text excerpt.
- [ ] Groundedness score is between 0.0 and 1.0.
- [ ] HyDE rewrite improves retrieval recall on benchmark queries.
- [ ] Reranking improves precision@5 over non-reranked results.
- [ ] Hallucinated content is flagged when groundedness < 0.5.

### Tests Required

- `tests/services/test_query_understanding.py` — intent classification tests.
- `tests/services/test_hyde.py` — HyDE rewrite tests.
- `tests/services/test_reranker.py` — reranking tests.
- `tests/services/test_rag_pipeline.py` — end-to-end RAG pipeline tests.
- `tests/services/test_groundedness.py` — groundedness scoring tests.
- `tests/api/test_qa.py` — Q&A endpoint integration tests.

### Docs to Update

- `API_SPEC.md` — Q&A endpoints.
- `ARCHITECTURE.md` — RAG pipeline diagram.
- `EVALUATION.md` — RAG metrics (faithfulness, relevance, citation accuracy).

### Estimated Duration

**2–3 weeks**

---

## Phase 6: Agent Harness + Tool Registry

**Goal:** Build a LangGraph-based agent that orchestrates multi-step document operations using registered tools with safety controls.

**Scope:** LangGraph state machine, tool registry, schema validation, sandbox execution, orchestrator, loop detection, cost tracking.

### Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| 6.1 | Create `AgentSession` and `AgentStep` SQLAlchemy models | Backend | ☐ |
| 6.2 | Implement LangGraph `StateGraph` with nodes: plan, execute, observe, respond | Backend | ☐ |
| 6.3 | Implement tool registry with decorator-based registration (`@tool`) | Backend | ☐ |
| 6.4 | Implement tool schema validation using JSON Schema | Backend | ☐ |
| 6.5 | Implement tool execution sandbox (timeout, resource limits, error isolation) | Backend | ☐ |
| 6.6 | Implement agent orchestrator (tool selection, argument construction, result handling) | Backend | ☐ |
| 6.7 | Implement loop detection (max iterations, repeated tool calls) | Backend | ☐ |
| 6.8 | Implement cost tracking (token usage, API calls, compute time per step) | Backend | ☐ |
| 6.9 | Create `POST /api/v1/agent/run` — execute agent task | Backend | ☐ |
| 6.10 | Create `GET /api/v1/agent/sessions/{id}` — retrieve agent session with steps | Backend | ☐ |

### Acceptance Criteria

- [ ] Agent can invoke at least 3 registered tools in a single session.
- [ ] Tool schema validation rejects malformed arguments.
- [ ] Loop detection terminates agent after max 10 iterations.
- [ ] Cost tracking reports token usage per step and total session cost.
- [ ] Agent session history is persisted and retrievable.
- [ ] Sandbox prevents tools from exceeding timeout or resource limits.

### Tests Required

- `tests/agent/test_state_machine.py` — LangGraph state transition tests.
- `tests/agent/test_tool_registry.py` — tool registration and validation tests.
- `tests/agent/test_sandbox.py` — sandbox execution tests.
- `tests/agent/test_loop_detection.py` — loop detection tests.
- `tests/agent/test_cost_tracker.py` — cost tracking tests.
- `tests/api/test_agent.py` — agent endpoint integration tests.

### Docs to Update

- `API_SPEC.md` — agent endpoints.
- `ARCHITECTURE.md` — agent architecture diagram.
- `DATA_MODEL.md` — agent session tables.

### Estimated Duration

**2–3 weeks**

---

## Phase 7: Field Extraction + Validation

**Goal:** Extract structured fields from documents (e.g., contract parties, dates, amounts) and validate them against schemas.

**Scope:** Document classification, schema-based extraction, Pydantic validation, normalization, quality scoring.

### Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| 7.1 | Create `ExtractedField` and `ExtractionSchema` SQLAlchemy models | Backend | ☐ |
| 7.2 | Implement document classification (contract, invoice, report, etc.) using LLM | Backend | ☐ |
| 7.3 | Implement schema-based field extraction using structured LLM output | Backend | ☐ |
| 7.4 | Implement Pydantic model validation for extracted fields | Backend | ☐ |
| 7.5 | Implement field normalization (date formats, currency, addresses) | Backend | ☐ |
| 7.6 | Implement extraction quality scoring (completeness, confidence) | Backend | ☐ |
| 7.7 | Create `POST /api/v1/documents/{id}/extract` — run field extraction | Backend | ☐ |
| 7.8 | Create `GET /api/v1/documents/{id}/fields` — retrieve extracted fields | Backend | ☐ |
| 7.9 | Create `PUT /api/v1/documents/{id}/fields` — manually correct fields | Backend | ☐ |

### Acceptance Criteria

- [ ] Document classification achieves >90% accuracy on test set.
- [ ] Extracted fields match the schema for the classified document type.
- [ ] Pydantic validation catches type errors and missing required fields.
- [ ] Normalized dates are in ISO 8601 format.
- [ ] Extraction quality score correlates with human-labeled accuracy.
- [ ] Manual corrections are persisted and tracked.

### Tests Required

- `tests/services/test_classifier.py` — document classification tests.
- `tests/services/test_field_extractor.py` — extraction tests with sample documents.
- `tests/services/test_validator.py` — Pydantic validation tests.
- `tests/services/test_normalizer.py` — field normalization tests.
- `tests/api/test_extraction.py` — extraction endpoint integration tests.

### Docs to Update

- `API_SPEC.md` — extraction endpoints.
- `DATA_MODEL.md` — extraction tables.

### Estimated Duration

**1–2 weeks**

---

## Phase 8: Risk Detection + Checklist

**Goal:** Identify risks, missing clauses, and anomalies in documents and generate actionable checklists.

**Scope:** Risk rules, missing clause detection, anomaly detection, checklist generation, task creation.

### Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| 8.1 | Create `RiskItem` and `ChecklistItem` SQLAlchemy models | Backend | ☐ |
| 8.2 | Implement rule-based risk detection (high-value clauses, unusual terms, deadlines) | Backend | ☐ |
| 8.3 | Implement missing clause detection (compare against standard templates) | Backend | ☐ |
| 8.4 | Implement anomaly detection (statistical outliers in extracted fields) | Backend | ☐ |
| 8.5 | Implement checklist generation from detected risks and missing items | Backend | ☐ |
| 8.6 | Implement task creation integration (assign, due date, priority) | Backend | ☐ |
| 8.7 | Create `POST /api/v1/documents/{id}/analyze` — run risk analysis | Backend | ☐ |
| 8.8 | Create `GET /api/v1/documents/{id}/risks` — retrieve risk items | Backend | ☐ |
| 8.9 | Create `GET /api/v1/documents/{id}/checklist` — retrieve checklist | Backend | ☐ |

### Acceptance Criteria

- [ ] Risk detection identifies at least 3 categories: financial, legal, temporal.
- [ ] Missing clause detection compares against configurable template library.
- [ ] Anomaly detection flags values >2 standard deviations from norms.
- [ ] Checklist items include description, severity, and suggested action.
- [ ] Tasks can be created from checklist items with correct metadata.

### Tests Required

- `tests/services/test_risk_detector.py` — risk detection tests.
- `tests/services/test_clause_detector.py` — missing clause tests.
- `tests/services/test_anomaly_detector.py` — anomaly detection tests.
- `tests/services/test_checklist_generator.py` — checklist generation tests.
- `tests/api/test_risks.py` — risk endpoint integration tests.

### Docs to Update

- `API_SPEC.md` — risk and checklist endpoints.
- `ARCHITECTURE.md` — risk analysis pipeline.

### Estimated Duration

**1–2 weeks**

---

## Phase 9: Report Export

**Goal:** Generate comprehensive summary reports from document analysis and export them in Markdown and PDF formats.

**Scope:** Summary generation, Markdown export, PDF export.

### Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| 9.1 | Create `Report` SQLAlchemy model | Backend | ☐ |
| 9.2 | Implement summary report generation (document overview, key findings, risks, recommendations) | Backend | ☐ |
| 9.3 | Implement Markdown export with proper formatting and section structure | Backend | ☐ |
| 9.4 | Implement PDF export using WeasyPrint with custom CSS template | Backend | ☐ |
| 9.5 | Create `POST /api/v1/documents/{id}/report` — generate report | Backend | ☐ |
| 9.6 | Create `GET /api/v1/reports/{id}` — retrieve report metadata | Backend | ☐ |
| 9.7 | Create `GET /api/v1/reports/{id}/download` — download report (MD or PDF) | Backend | ☐ |

### Acceptance Criteria

- [ ] Report includes all sections: overview, findings, risks, checklist, recommendations.
- [ ] Markdown export renders correctly in standard viewers.
- [ ] PDF export has professional formatting with headers, footers, page numbers.
- [ ] Report generation completes within 30 seconds for typical documents.
- [ ] Reports are stored in MinIO and retrievable via API.

### Tests Required

- `tests/services/test_report_generator.py` — report generation tests.
- `tests/services/test_markdown_export.py` — Markdown formatting tests.
- `tests/services/test_pdf_export.py` — PDF generation tests.
- `tests/api/test_reports.py` — report endpoint integration tests.

### Docs to Update

- `API_SPEC.md` — report endpoints.

### Estimated Duration

**1–2 weeks**

---

## Phase 10: Observability + Evaluation

**Goal:** Instrument the system with tracing, metrics, and logging, and build an evaluation framework for measuring quality.

**Scope:** Langfuse, OpenTelemetry, structured logging, Prometheus, evaluation framework, gold dataset, benchmarks.

### Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| 10.1 | Integrate Langfuse for LLM call tracing and cost monitoring | Backend | ☐ |
| 10.2 | Integrate OpenTelemetry for distributed tracing (FastAPI, Celery, HTTP clients) | Backend | ☐ |
| 10.3 | Implement structured JSON logging with correlation IDs | Backend | ☐ |
| 10.4 | Expose Prometheus metrics endpoint (`GET /metrics`) | Backend | ☐ |
| 10.5 | Define custom metrics (request latency, parsing success rate, search relevance) | Backend | ☐ |
| 10.6 | Create evaluation framework with metric runners (faithfulness, relevance, citation accuracy) | Backend | ☐ |
| 10.7 | Create gold dataset with 100+ labeled Q&A pairs across document types | QA | ☐ |
| 10.8 | Create benchmark suite that runs evaluation against gold dataset | Backend | ☐ |
| 10.9 | Create `POST /api/v1/eval/run` — trigger evaluation run | Backend | ☐ |
| 10.10 | Create `GET /api/v1/eval/results` — retrieve evaluation results | Backend | ☐ |

### Acceptance Criteria

- [ ] Langfuse traces show all LLM calls with token counts and latency.
- [ ] OpenTelemetry traces propagate across FastAPI → Celery → external services.
- [ ] Logs are structured JSON with request_id, user_id, document_id fields.
- [ ] Prometheus metrics are scrapeable at `/metrics`.
- [ ] Evaluation framework reports faithfulness >0.8, relevance >0.75 on gold dataset.
- [ ] Benchmark suite runs in CI and blocks regression.

### Tests Required

- `tests/observability/test_tracing.py` — trace propagation tests.
- `tests/observability/test_metrics.py` — metrics endpoint tests.
- `tests/observability/test_logging.py` — structured logging tests.
- `tests/eval/test_framework.py` — evaluation framework tests.
- `tests/eval/test_benchmark.py` — benchmark regression tests.

### Docs to Update

- `EVALUATION.md` — evaluation metrics, gold dataset, benchmark results.
- `DEPLOYMENT.md` — observability stack setup.
- `API_SPEC.md` — evaluation endpoints.

### Estimated Duration

**1–2 weeks**

---

## Phase 11: Frontend Dashboard

**Goal:** Build a complete web interface for document management, Q&A, report viewing, and agent interaction.

**Scope:** Upload UI, document views, chat interface, report viewer, agent session viewer, evaluation dashboard.

### Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| 11.1 | Implement document upload UI with drag-and-drop, progress bar, validation feedback | Frontend | ☐ |
| 11.2 | Implement document list view with search, filters, pagination, status indicators | Frontend | ☐ |
| 11.3 | Implement document detail view with metadata, parsed content, extracted fields, risks | Frontend | ☐ |
| 11.4 | Implement Q&A chat interface with streaming responses, citation highlighting | Frontend | ☐ |
| 11.5 | Implement report viewer with Markdown rendering and PDF download | Frontend | ☐ |
| 11.6 | Implement agent session viewer with step-by-step execution trace | Frontend | ☐ |
| 11.7 | Implement evaluation dashboard with metric charts and comparison views | Frontend | ☐ |
| 11.8 | Implement responsive layout and dark mode | Frontend | ☐ |
| 11.9 | Implement authentication UI (login, register, session management) | Frontend | ☐ |

### Acceptance Criteria

- [ ] File upload works with drag-and-drop and shows real-time progress.
- [ ] Document list loads within 2 seconds with pagination.
- [ ] Q&A chat streams responses token-by-token.
- [ ] Citations in answers are clickable and highlight source text.
- [ ] Report viewer renders Markdown and allows PDF download.
- [ ] Agent session viewer shows each step with inputs, outputs, and timing.
- [ ] Evaluation dashboard displays metric trends over time.
- [ ] UI is responsive on screens ≥1024px wide.

### Tests Required

- `frontend/__tests__/components/Upload.test.tsx` — upload component tests.
- `frontend/__tests__/components/DocumentList.test.tsx` — document list tests.
- `frontend/__tests__/components/Chat.test.tsx` — chat interface tests.
- `frontend/__tests__/components/ReportViewer.test.tsx` — report viewer tests.
- `frontend/__tests__/components/AgentViewer.test.tsx` — agent viewer tests.
- `frontend/__tests__/e2e/` — Playwright end-to-end tests.

### Docs to Update

- `README.md` — add screenshots and usage guide.

### Estimated Duration

**2–3 weeks**

---

## Phase 12: Hardening + Deployment

**Goal:** Prepare the system for production with security hardening, performance optimization, load testing, and deployment automation.

**Scope:** Security, performance, load testing, production deployment, monitoring, documentation.

### Tasks

| # | Task | Owner | Status |
|---|------|-------|--------|
| 12.1 | Implement rate limiting (per-user, per-endpoint) | Backend | ☐ |
| 12.2 | Implement input sanitization and output encoding | Backend | ☐ |
| 12.3 | Add CORS, CSP, and security headers | Backend | ☐ |
| 12.4 | Implement JWT authentication with refresh tokens | Backend | ☐ |
| 12.5 | Add RBAC (role-based access control) | Backend | ☐ |
| 12.6 | Implement database connection pooling optimization | Backend | ☐ |
| 12.7 | Add Redis caching for frequently accessed data | Backend | ☐ |
| 12.8 | Implement query optimization and database indexing | Backend | ☐ |
| 12.9 | Run load tests with k6 (target: 100 concurrent users, p95 < 500ms) | DevOps | ☐ |
| 12.10 | Create Kubernetes deployment manifests (Deployments, Services, Ingress) | DevOps | ☐ |
| 12.11 | Setup Helm charts with environment-specific values | DevOps | ☐ |
| 12.12 | Configure Prometheus + Grafana dashboards | DevOps | ☐ |
| 12.13 | Setup alerting rules (error rate, latency, resource usage) | DevOps | ☐ |
| 12.14 | Finalize all documentation and create user guide | Team | ☐ |
| 12.15 | Conduct security audit and penetration testing | Security | ☐ |

### Acceptance Criteria

- [ ] Rate limiting returns `429` when limits are exceeded.
- [ ] All user inputs are sanitized; no SQL injection or XSS vectors.
- [ ] Authentication and authorization work correctly for all endpoints.
- [ ] Load test passes with p95 latency < 500ms at 100 concurrent users.
- [ ] Kubernetes deployment is stable with health checks and auto-restart.
- [ ] Grafana dashboards show key metrics (latency, error rate, throughput).
- [ ] Alerts fire correctly when thresholds are breached.
- [ ] Security audit finds no critical or high-severity vulnerabilities.
- [ ] All documentation is complete and up-to-date.

### Tests Required

- `tests/security/test_rate_limiting.py` — rate limiting tests.
- `tests/security/test_auth.py` — authentication and authorization tests.
- `tests/security/test_input_validation.py` — input sanitization tests.
- `tests/performance/test_load.py` — k6 load test scripts.
- `tests/integration/test_deployment.py` — deployment smoke tests.

### Docs to Update

- `DEPLOYMENT.md` — production deployment guide.
- `SECURITY.md` — security audit results.
- `README.md` — final quickstart and architecture overview.

### Estimated Duration

**2–3 weeks**

---

## Summary

| Phase | Name | Duration | Dependencies |
|-------|------|----------|-------------|
| 0 | Planning & Documentation | 1 week | — |
| 1 | Project Skeleton | 1–2 weeks | Phase 0 |
| 2 | Document Upload & Storage | 1–2 weeks | Phase 1 |
| 3 | Parsing / OCR Pipeline | 2–3 weeks | Phase 2 |
| 4 | Chunking + Embedding + Vector Store | 1–2 weeks | Phase 3 |
| 5 | RAG Q&A with Citations | 2–3 weeks | Phase 4 |
| 6 | Agent Harness + Tool Registry | 2–3 weeks | Phase 5 |
| 7 | Field Extraction + Validation | 1–2 weeks | Phase 6 |
| 8 | Risk Detection + Checklist | 1–2 weeks | Phase 7 |
| 9 | Report Export | 1–2 weeks | Phase 8 |
| 10 | Observability + Evaluation | 1–2 weeks | Phase 5 |
| 11 | Frontend Dashboard | 2–3 weeks | Phase 9, 10 |
| 12 | Hardening + Deployment | 2–3 weeks | Phase 11 |

**Total estimated duration: 16–18 weeks**
