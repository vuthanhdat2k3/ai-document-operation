# AI Document Operations Agent

An end-to-end enterprise document processing agent that ingests, classifies, parses, extracts, validates, and stores documents with full RAG-based Q&A support and observability.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client Layer                                    │
│                         Next.js 15 Dashboard                                 │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│   │  Upload   │  │  Q&A     │  │ Reports  │  │ Tasks    │  │  Admin   │    │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
└────────┼─────────────┼─────────────┼─────────────┼─────────────┼───────────┘
         │             │             │             │             │
         ▼             ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API Gateway                                       │
│                         FastAPI + Pydantic                                   │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│   │ /ingest  │  │  /query  │  │ /export  │  │ /tasks   │  │ /admin   │    │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
└────────┼─────────────┼─────────────┼─────────────┼─────────────┼───────────┘
         │             │             │             │             │
         ▼             ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LangGraph Orchestrator                               │
│                                                                             │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐    │
│   │ Classify│──▶│  Parse  │──▶│ Extract │──▶│ Validate│──▶│  Risk   │    │
│   │  Agent  │   │  Agent  │   │  Agent  │   │  Agent  │   │  Agent  │    │
│   └─────────┘   └─────────┘   └─────────┘   └─────────┘   └────┬────┘    │
│                                                                  │         │
│   ┌──────────────────────────────────────────────────────────────┘         │
│   │                                                                        │
│   ▼                                                                        │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐                                │
│   │ Checklist│──▶│  Store  │──▶│  Index  │                                │
│   │Generator │   │  Agent  │   │  Agent  │                                │
│   └─────────┘   └─────────┘   └─────────┘                                │
└─────────────────────────────────────────────────────────────────────────────┘
         │             │             │             │
         ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Data Layer                                          │
│                                                                             │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│   │  PostgreSQL   │  │    Qdrant    │  │    Redis     │  │    MinIO     │  │
│   │  (metadata,   │  │  (vectors,   │  │  (cache,     │  │  (file       │  │
│   │   records)    │  │   embeddings)│  │   queues)    │  │   storage)   │  │
│   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
         │             │             │             │
         ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Observability Layer                                    │
│                                                                             │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│   │   Langfuse    │  │ OpenTelemetry│  │  Structured  │                     │
│   │  (traces,     │  │  (traces,    │  │    Logs      │                     │
│   │   cost, eval) │  │   metrics)   │  │  (JSON log)  │                     │
│   └──────────────┘  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Features

- **Multi-format ingestion** -- Upload contracts, invoices, meeting minutes, regulations, dispatches, emails, scanned images, PDFs, DOCX, XLSX
- **Auto-classification** -- Document type detection with confidence scoring
- **Parse & OCR** -- Native text extraction via Docling/PyMuPDF; scanned document OCR via PaddleOCR
- **Key field extraction** -- LLM-powered extraction of entities, dates, amounts, parties, clauses
- **Schema normalization** -- Pydantic models enforce consistent output structure per document type
- **Data validation** -- Cross-field consistency checks, format validation, business rule enforcement
- **Risk & gap detection** -- Identifies missing clauses, deadline risks, compliance gaps, anomalous values
- **Checklist & task generation** -- Auto-generates actionable follow-up items with deadlines and assignees
- **Dual storage** -- PostgreSQL for structured records; Qdrant for vector embeddings
- **RAG Q&A with citations** -- Retrieve-augmented generation over document corpus with source attribution
- **Report export** -- Generate Markdown and PDF summaries, audit trails, compliance reports
- **Full observability** -- Distributed traces, structured logs, LLM cost tracking, latency monitoring via Langfuse + OpenTelemetry
- **Role-based access** -- JWT authentication with configurable permissions
- **Async processing** -- Background task queue for long-running document pipelines

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Backend API** | FastAPI | >= 0.115 |
| **Frontend** | Next.js | >= 15.1 |
| **Orchestration** | LangGraph | >= 0.3 |
| **LLM Framework** | LangChain | >= 0.3 |
| **Document Parsing** | Docling | >= 2.26 |
| **PDF Extraction** | PyMuPDF | >= 1.25 |
| **OCR Engine** | PaddleOCR | >= 2.9 |
| **Embeddings** | bge-m3 (BAAI) | latest |
| **Reranker** | bge-reranker-v2-m3 (BAAI) | latest |
| **Database** | PostgreSQL | 16 |
| **Vector Store** | Qdrant | >= 1.13 |
| **Cache / Queue** | Redis | 7 |
| **Object Storage** | MinIO | latest |
| **Validation** | Pydantic | >= 2.10 |
| **Tracing** | Langfuse | >= 2.57 |
| **Telemetry** | OpenTelemetry | >= 1.30 |
| **Testing** | Pytest | >= 8.3 |
| **Containerization** | Docker Compose | v2 |
| **CI/CD** | GitHub Actions | v4 |

## Quick Start

### Prerequisites

- Docker >= 24.0
- Docker Compose >= 2.23
- Git

### 1. Clone the repository

```bash
git clone https://github.com/your-org/ai-document-operations-agent.git
cd ai-document-operations-agent
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# LLM Provider
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Database
POSTGRES_USER=docagent
POSTGRES_PASSWORD=change-me-in-production
POSTGRES_DB=docagent

# Qdrant
QDRANT_URL=http://qdrant:6333

# Redis
REDIS_URL=redis://redis:6379/0

# Langfuse (observability)
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Auth
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
```

### 3. Start all services

```bash
docker compose up -d
```

This starts:
- **API** (FastAPI) on `http://localhost:8000`
- **Web** (Next.js) on `http://localhost:3000`
- **PostgreSQL** on `localhost:5432`
- **Qdrant** on `localhost:6333`
- **Redis** on `localhost:6379`
- **MinIO** on `localhost:9000` (console: `localhost:9001`)
- **Langfuse** on `http://localhost:3002`

### 4. Run database migrations

```bash
docker compose exec api alembic upgrade head
```

### 5. Access the application

- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API ReDoc**: http://localhost:8000/redoc
- **MinIO Console**: http://localhost:9001
- **Langfuse Dashboard**: http://localhost:3002

## Project Structure

```
ai-document-operations-agent/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Lint, type-check, test
│       ├── cd.yml                    # Build & deploy
│       └── security.yml              # Dependency scanning
├── apps/
│   ├── api/                          # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/                  # Route handlers
│   │   │   │   ├── v1/
│   │   │   │   │   ├── documents.py
│   │   │   │   │   ├── query.py
│   │   │   │   │   ├── tasks.py
│   │   │   │   │   ├── reports.py
│   │   │   │   │   └── admin.py
│   │   │   │   └── deps.py
│   │   │   ├── core/                 # Configuration & security
│   │   │   │   ├── config.py
│   │   │   │   ├── security.py
│   │   │   │   └── logging.py
│   │   │   ├── db/                   # Database setup
│   │   │   │   ├── session.py
│   │   │   │   └── migrations/
│   │   │   ├── models/               # SQLAlchemy ORM models
│   │   │   │   ├── document.py
│   │   │   │   ├── task.py
│   │   │   │   └── user.py
│   │   │   ├── schemas/              # Pydantic schemas
│   │   │   │   ├── document.py
│   │   │   │   ├── extraction.py
│   │   │   │   ├── task.py
│   │   │   │   └── report.py
│   │   │   ├── services/             # Business logic
│   │   │   │   ├── ingestion.py
│   │   │   │   ├── classification.py
│   │   │   │   ├── parsing.py
│   │   │   │   ├── extraction.py
│   │   │   │   ├── validation.py
│   │   │   │   ├── risk_detection.py
│   │   │   │   ├── checklist.py
│   │   │   │   ├── storage.py
│   │   │   │   ├── rag.py
│   │   │   │   └── export.py
│   │   │   ├── graph/                # LangGraph pipelines
│   │   │   │   ├── document_pipeline.py
│   │   │   │   ├── rag_pipeline.py
│   │   │   │   └── nodes/
│   │   │   │       ├── classify.py
│   │   │   │       ├── parse.py
│   │   │   │       ├── extract.py
│   │   │   │       ├── validate.py
│   │   │   │       ├── risk.py
│   │   │   │       ├── checklist.py
│   │   │   │       ├── store.py
│   │   │   │       └── index.py
│   │   │   └── telemetry/            # Observability
│   │   │       ├── langfuse.py
│   │   │       ├── otel.py
│   │   │       └── cost_tracker.py
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   ├── e2e/
│   │   │   ├── conftest.py
│   │   │   └── factories.py
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── alembic.ini
│   └── web/                          # Next.js frontend
│       ├── src/
│       │   ├── app/
│       │   │   ├── (auth)/
│       │   │   ├── (dashboard)/
│       │   │   │   ├── documents/
│       │   │   │   ├── query/
│       │   │   │   ├── tasks/
│       │   │   │   └── reports/
│       │   │   └── layout.tsx
│       │   ├── components/
│       │   ├── lib/
│       │   ├── hooks/
│       │   └── types/
│       ├── public/
│       ├── Dockerfile
│       ├── next.config.ts
│       ├── tailwind.config.ts
│       ├── tsconfig.json
│       └── package.json
├── packages/
│   ├── shared/                       # Shared types & utilities
│   │   ├── schemas/
│   │   ├── constants/
│   │   └── utils/
│   └── prompts/                      # LLM prompt templates
│       ├── classification.py
│       ├── extraction.py
│       ├── risk_analysis.py
│       └── rag.py
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   ├── nginx/
│   │   └── nginx.conf
│   └── terraform/                    # IaC for cloud deployment
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── scripts/
│   ├── seed.py
│   ├── migrate.sh
│   └── benchmark.py
├── docs/
│   ├── architecture.md
│   ├── api-reference.md
│   ├── deployment.md
│   └── adr/                          # Architecture Decision Records
├── .env.example
├── .gitignore
├── .editorconfig
├── Makefile
├── docker-compose.yml
└── README.md
```

## Development Setup

### Prerequisites

- Python >= 3.12
- Node.js >= 22
- pnpm >= 9
- PostgreSQL 16
- Redis 7
- Qdrant >= 1.13

### Backend (API)

```bash
cd apps/api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 8000
```

### Frontend (Web)

```bash
cd apps/web

# Install dependencies
pnpm install

# Start development server
pnpm dev
```

### Infrastructure (local services)

```bash
# Start only infrastructure services (no app containers)
docker compose up -d postgres qdrant redis minio
```

## Testing

### Run all tests

```bash
# Backend unit tests
cd apps/api && pytest tests/unit -v

# Backend integration tests (requires running services)
cd apps/api && pytest tests/integration -v

# Backend end-to-end tests
cd apps/api && pytest tests/e2e -v

# Full test suite with coverage
cd apps/api && pytest --cov=app --cov-report=html --cov-report=term-missing

# Frontend tests
cd apps/web && pnpm test

# Type checking
cd apps/api && mypy app
cd apps/web && pnpm typecheck

# Linting
cd apps/api && ruff check .
cd apps/web && pnpm lint
```

### Run tests with Docker

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm api pytest
```

### Benchmark

```bash
python scripts/benchmark.py --documents 100 --concurrency 10
```

## API Overview

### Authentication

All endpoints require a Bearer token:

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/documents
```

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/documents/upload` | Upload and process a document |
| `GET` | `/api/v1/documents` | List all documents (paginated) |
| `GET` | `/api/v1/documents/{id}` | Get document details with extracted fields |
| `GET` | `/api/v1/documents/{id}/status` | Get processing pipeline status |
| `DELETE` | `/api/v1/documents/{id}` | Soft-delete a document |

### Query (RAG)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/query` | Ask a question over the document corpus |
| `GET` | `/api/v1/query/history` | Get query history |

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/tasks` | List all generated tasks |
| `PATCH` | `/api/v1/tasks/{id}` | Update task status |
| `GET` | `/api/v1/tasks/overdue` | Get overdue tasks |

### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/reports/generate` | Generate a report |
| `GET` | `/api/v1/reports/{id}/download` | Download report (Markdown/PDF) |

### Example: Upload and process a document

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@contract.pdf" \
  -F "document_type=contract"
```

Response:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "document_type": null,
  "created_at": "2026-06-11T07:46:51Z"
}
```

### Example: Query documents

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What contracts expire in the next 30 days?"}'
```

Response:

```json
{
  "answer": "3 contracts expire within 30 days...",
  "citations": [
    {
      "document_id": "550e8400-...",
      "document_type": "contract",
      "excerpt": "...",
      "relevance_score": 0.94
    }
  ],
  "confidence": 0.89
}
```

## Deployment

### Docker Compose (Production)

```bash
# Use production compose override
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Scale API workers
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale api=4
```

### Cloud Deployment

The `infra/terraform/` directory contains Terraform configurations for deploying to cloud providers:

```bash
cd infra/terraform
terraform init
terraform plan -var="environment=production"
terraform apply
```

### Environment Variables (Production)

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for LLM calls | Yes |
| `OPENAI_MODEL` | Model to use (default: `gpt-4o`) | No |
| `POSTGRES_*` | PostgreSQL connection details | Yes |
| `QDRANT_URL` | Qdrant endpoint | Yes |
| `REDIS_URL` | Redis endpoint | Yes |
| `LANGFUSE_*` | Langfuse observability keys | Yes |
| `JWT_SECRET` | Secret for JWT signing (min 32 chars) | Yes |
| `MINIO_*` | MinIO object storage credentials | Yes |
| `SENTRY_DSN` | Sentry error tracking DSN | No |
| `LOG_LEVEL` | Logging level (default: `INFO`) | No |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Commit your changes (`git commit -m 'feat: add your feature'`)
4. Push to the branch (`git push origin feat/your-feature`)
5. Open a Pull Request

### Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` -- New feature
- `fix:` -- Bug fix
- `docs:` -- Documentation changes
- `refactor:` -- Code refactoring
- `test:` -- Adding or updating tests
- `chore:` -- Maintenance tasks
- `perf:` -- Performance improvements

### Code Quality

All contributions must pass:

- `ruff check` (Python linting)
- `mypy` (Python type checking)
- `eslint` + `prettier` (TypeScript linting/formatting)
- `pytest` with >= 80% coverage (backend)
- `pnpm test` (frontend)

## License

This project is licensed under the [MIT License](LICENSE).

```
MIT License

Copyright (c) 2026 AI Document Operations Agent Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
