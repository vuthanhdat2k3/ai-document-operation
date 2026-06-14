# AI Document Operations Agent — Run Guide

Production-grade guide for running the AI Document Operations Agent.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone Repository](#2-clone-repository)
3. [Environment Setup](#3-environment-setup)
4. [Docker Compose Full Stack Startup](#4-docker-compose-full-stack-startup)
5. [Manual Setup (Without Docker)](#5-manual-setup-without-docker)
6. [Running Backend](#6-running-backend)
7. [Running Frontend](#7-running-frontend)
8. [Running Worker](#8-running-worker)
9. [Running Tests](#9-running-tests)
10. [Running Lint](#10-running-lint)
11. [Running Type Check](#11-running-type-check)
12. [Running Evaluation Benchmarks](#12-running-evaluation-benchmarks)
13. [Database Migrations (Alembic)](#13-database-migrations-alembic)
14. [Reset Database](#14-reset-database)
15. [Seed Demo Data](#15-seed-demo-data)
16. [Useful Commands Reference](#16-useful-commands-reference)
17. [Troubleshooting](#17-troubleshooting)
18. [Environment Variables Reference](#18-environment-variables-reference)

---

## 1. Prerequisites

| Tool             | Minimum Version | Check Command            |
|------------------|-----------------|--------------------------|
| Docker           | 24.0+           | `docker --version`       |
| Docker Compose   | 2.20+           | `docker compose version` |
| Python           | 3.11+           | `python3 --version`      |
| Node.js          | 20+             | `node --version`         |
| npm              | 10+             | `npm --version`          |
| Git              | 2.30+           | `git --version`          |
| PostgreSQL       | 15+ (manual)    | `psql --version`         |
| Redis            | 7+ (manual)     | `redis-server --version` |
| uv (optional)    | 0.4+            | `uv --version`           |

**Hardware (recommended for local model inference):**

- RAM: 16 GB minimum, 32 GB recommended
- GPU: NVIDIA with 8 GB+ VRAM (for embedding/reranker models)
- Disk: 20 GB free

---

## 2. Clone Repository

```bash
git clone https://github.com/your-org/ai-document-operations-agent.git
cd ai-document-operations-agent
```

---

## 3. Environment Setup

### 3.1 Copy the example environment file

```bash
cp .env.example .env
```

### 3.2 Fill in the values

Open `.env` in your editor and configure each variable:

```bash
# Use your preferred editor
nano .env
# or
code .env
```

### 3.3 Variable explanations

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_ENV` | Runtime environment: `local`, `dev`, `staging`, `prod` | `local` |
| `APP_DEBUG` | Enable debug logging and auto-reload | `true` |
| `APP_SECRET_KEY` | JWT/session signing key (generate with `openssl rand -hex 32`) | `a1b2c3...` |
| `APP_HOST` | Backend bind host | `0.0.0.0` |
| `APP_PORT` | Backend bind port | `8000` |
| `APP_CORS_ORIGINS` | Comma-separated allowed CORS origins | `http://localhost:3000` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://postgres:postgres@localhost:5432/ai_doc_ops` |
| `DATABASE_POOL_SIZE` | Connection pool size | `20` |
| `DATABASE_MAX_OVERFLOW` | Max overflow connections | `10` |
| `QDRANT_URL` | Qdrant server URL | `http://localhost:6333` |
| `QDRANT_API_KEY` | Qdrant API key (if secured) | `""` |
| `QDRANT_COLLECTION` | Default vector collection name | `documents` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `REDIS_PASSWORD` | Redis password (if secured) | `""` |
| `WORKER_CONCURRENCY` | Number of concurrent worker tasks | `4` |
| `LLM_PROVIDER` | LLM provider: `openai`, `anthropic`, `ollama` | `openai` |
| `LLM_API_KEY` | API key for the LLM provider | `sk-...` |
| `LLM_MODEL` | Model identifier | `gpt-4o` |
| `LLM_BASE_URL` | Custom LLM endpoint (for Ollama/proxy) | `http://localhost:11434/v1` |
| `EMBEDDING_MODEL` | Embedding model name | `BAAI/bge-m3` |
| `EMBEDDING_DEVICE` | Device for embedding model: `cpu`, `cuda` | `cuda` |
| `EMBEDDING_DIM` | Embedding vector dimension | `1024` |
| `RERANKER_MODEL` | Reranker model name | `BAAI/bge-reranker-v2-m3` |
| `RERANKER_DEVICE` | Device for reranker model: `cpu`, `cuda` | `cuda` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key for tracing | `pk-...` |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | `sk-...` |
| `LANGFUSE_HOST` | Langfuse server URL | `https://cloud.langfuse.com` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry collector endpoint | `http://localhost:4317` |
| `OTEL_SERVICE_NAME` | Service name for tracing | `ai-doc-ops` |
| `UPLOAD_DIR` | Directory for uploaded files | `./uploads` |
| `MAX_UPLOAD_SIZE_MB` | Max upload file size in MB | `100` |
| `LOG_LEVEL` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

---

## 4. Docker Compose Full Stack Startup

Start all services (PostgreSQL, Qdrant, Redis, backend, frontend, worker):

```bash
docker compose up -d
```

Start with build (after code changes):

```bash
docker compose up -d --build
```

View logs for all services:

```bash
docker compose logs -f
```

View logs for a specific service:

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f worker
```

Stop all services:

```bash
docker compose down
```

Stop and remove volumes (destroys all data):

```bash
docker compose down -v
```

Check service health:

```bash
docker compose ps
```

Run database migrations inside the container:

```bash
docker compose exec backend alembic upgrade head
```

Seed demo data inside the container:

```bash
docker compose exec backend python -m app.seeds.demo
```

---

## 5. Manual Setup (Without Docker)

### 5.1 Install PostgreSQL

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS (Homebrew):**

```bash
brew install postgresql@15
brew services start postgresql@15
```

Create the database and user:

```bash
sudo -u postgres psql -c "CREATE USER ai_doc_ops WITH PASSWORD 'postgres';"
sudo -u postgres psql -c "CREATE DATABASE ai_doc_ops OWNER ai_doc_ops;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ai_doc_ops TO ai_doc_ops;"
```

### 5.2 Install and Configure Qdrant

**Using Docker (recommended):**

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
```

**Install from binary:**

```bash
curl -L https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-gnu.tar.gz -o qdrant.tar.gz
tar -xzf qdrant.tar.gz
./qdrant
```

Verify Qdrant is running:

```bash
curl http://localhost:6333/healthz
```

### 5.3 Install and Configure Redis

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install -y redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**macOS (Homebrew):**

```bash
brew install redis
brew services start redis
```

Verify Redis is running:

```bash
redis-cli ping
# Expected output: PONG
```

### 5.4 Python Backend Setup

Create and activate a virtual environment:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

Or using `uv`:

```bash
cd backend
uv venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Or using `uv`:

```bash
uv pip install -r requirements.txt
```

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run database migrations:

```bash
alembic upgrade head
```

### 5.5 Frontend Setup

```bash
cd frontend
npm install
```

### 5.6 Worker Setup

The worker runs in the same Python environment as the backend. Ensure the backend virtual environment is activated, then start the worker (see [Section 8](#8-running-worker)).

---

## 6. Running Backend

Activate the virtual environment and start the FastAPI server:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Production mode (no auto-reload, multiple workers):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --log-level info
```

The API will be available at `http://localhost:8000`.

Interactive docs at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc` (ReDoc).

---

## 7. Running Frontend

```bash
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:3000`.

Build for production:

```bash
npm run build
npm run start
```

---

## 8. Running Worker

The worker processes background tasks (document ingestion, embedding, OCR).

Using arq (default):

```bash
cd backend
source .venv/bin/activate
arq app.worker.settings.WorkerSettings
```

Using Celery (if configured):

```bash
cd backend
source .venv/bin/activate
celery -A app.worker.celery_app worker --loglevel=info --concurrency=4
```

Run with multiple concurrency:

```bash
arq app.worker.settings.WorkerSettings --concurrency 8
```

---

## 9. Running Tests

All tests use Pytest. Ensure dev dependencies are installed:

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Run all tests

```bash
pytest
```

### Run unit tests only

```bash
pytest tests/unit
```

### Run integration tests only

```bash
pytest tests/integration
```

### Run evaluation tests only

```bash
pytest tests/eval
```

### Run with verbose output

```bash
pytest -v
```

### Run with coverage report

```bash
pytest --cov=app --cov-report=term-missing --cov-report=html
```

### Run a specific test file

```bash
pytest tests/unit/test_document_service.py
```

### Run a specific test function

```bash
pytest tests/unit/test_document_service.py::test_parse_pdf
```

### Run tests matching a keyword

```bash
pytest -k "embedding"
```

### Run tests in parallel

```bash
pytest -n auto
```

---

## 10. Running Lint

```bash
cd backend
ruff check .
```

Auto-fix lint issues:

```bash
ruff check . --fix
```

Check and fix a specific file:

```bash
ruff check app/services/ingestion.py --fix
```

Format code:

```bash
ruff format .
```

Check formatting without making changes:

```bash
ruff format --check .
```

---

## 11. Running Type Check

```bash
cd backend
mypy .
```

Run with strict mode:

```bash
mypy . --strict
```

Check a specific module:

```bash
mypy app/services/
```

Ignore missing imports (if third-party stubs are unavailable):

```bash
mypy . --ignore-missing-imports
```

---

## 12. Running Evaluation Benchmarks

Run the full evaluation suite:

```bash
cd backend
source .venv/bin/activate
pytest tests/eval -v
```

Run retrieval quality benchmark:

```bash
pytest tests/eval/test_retrieval_quality.py -v --tb=short
```

Run generation quality benchmark:

```bash
pytest tests/eval/test_generation_quality.py -v --tb=short
```

Run end-to-end pipeline benchmark:

```bash
pytest tests/eval/test_e2e_pipeline.py -v --tb=short
```

Generate evaluation report:

```bash
pytest tests/eval -v --html=reports/eval_report.html --self-contained-html
```

Run Langfuse-linked evaluation (requires Langfuse config):

```bash
EVAL_LANGFUSE_ENABLED=true pytest tests/eval -v
```

---

## 13. Database Migrations (Alembic)

All commands run from the `backend` directory with the virtual environment activated.

```bash
cd backend
source .venv/bin/activate
```

### Create a new migration

Auto-generate from model changes:

```bash
alembic revision --autogenerate -m "description_of_changes"
```

Create an empty migration:

```bash
alembic revision -m "description_of_changes"
```

### Apply migrations

Upgrade to the latest revision:

```bash
alembic upgrade head
```

Upgrade one revision forward:

```bash
alembic upgrade +1
```

### Downgrade migrations

Downgrade one revision:

```bash
alembic downgrade -1
```

Downgrade to a specific revision:

```bash
alembic downgrade <revision_id>
```

Downgrade all:

```bash
alembic downgrade base
```

### Migration status

Show current revision:

```bash
alembic current
```

Show migration history:

```bash
alembic history
```

Show pending migrations:

```bash
alembic history --indicate-current
```

---

## 14. Reset Database

**WARNING: This destroys all data.**

### Option A: Drop and recreate

```bash
sudo -u postgres psql -c "DROP DATABASE IF EXISTS ai_doc_ops;"
sudo -u postgres psql -c "CREATE DATABASE ai_doc_ops OWNER ai_doc_ops;"
```

Then re-run migrations:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

### Option B: Downgrade and re-migrate

```bash
cd backend
source .venv/bin/activate
alembic downgrade base
alembic upgrade head
```

### Option C: Docker Compose reset

```bash
docker compose down -v
docker compose up -d postgres
sleep 5
docker compose exec backend alembic upgrade head
```

---

## 15. Seed Demo Data

Run the demo seed script:

```bash
cd backend
source .venv/bin/activate
python -m app.seeds.demo
```

Seed specific data sets:

```bash
# Seed only sample documents
python -m app.seeds.demo --documents

# Seed only sample users
python -m app.seeds.demo --users

# Seed sample Qdrant collections
python -m app.seeds.demo --vectors
```

Inside Docker:

```bash
docker compose exec backend python -m app.seeds.demo
```

---

## 16. Useful Commands Reference

| Action                         | Command                                                        |
|--------------------------------|----------------------------------------------------------------|
| Start full stack (Docker)      | `docker compose up -d`                                        |
| Rebuild Docker services        | `docker compose up -d --build`                                |
| Stop full stack                | `docker compose down`                                         |
| Stop and wipe volumes          | `docker compose down -v`                                      |
| View all logs                  | `docker compose logs -f`                                      |
| Run backend (dev)              | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`   |
| Run backend (prod)             | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4`|
| Run frontend                   | `npm run dev` (in `frontend/`)                                |
| Run worker                     | `arq app.worker.settings.WorkerSettings`                      |
| DB migration upgrade           | `alembic upgrade head`                                        |
| DB migration new               | `alembic revision --autogenerate -m "msg"`                    |
| DB migration status            | `alembic current`                                             |
| Seed demo data                 | `python -m app.seeds.demo`                                    |
| Run all tests                  | `pytest`                                                      |
| Run unit tests                 | `pytest tests/unit`                                           |
| Run integration tests          | `pytest tests/integration`                                    |
| Run eval tests                 | `pytest tests/eval`                                           |
| Run tests with coverage        | `pytest --cov=app --cov-report=term-missing`                  |
| Lint                           | `ruff check .`                                                |
| Lint and fix                   | `ruff check . --fix`                                          |
| Format                         | `ruff format .`                                               |
| Type check                     | `mypy .`                                                      |
| Check Redis connection         | `redis-cli ping`                                              |
| Check Qdrant health            | `curl http://localhost:6333/healthz`                          |
| Check PostgreSQL connection    | `psql -U ai_doc_ops -d ai_doc_ops -c "SELECT 1;"`            |

---

## 17. Troubleshooting

### PostgreSQL connection refused

```
sqlalchemy.exc.OperationalError: connection refused
```

**Fix:** Ensure PostgreSQL is running and accepting connections:

```bash
sudo systemctl status postgresql
sudo systemctl start postgresql
```

Verify the `DATABASE_URL` in `.env` matches your PostgreSQL configuration. Check `pg_hba.conf` for authentication rules:

```bash
sudo -u postgres psql -c "SHOW hba_file;"
```

### Qdrant connection error

```
httpx.ConnectError: Connection refused
```

**Fix:** Verify Qdrant is running:

```bash
curl http://localhost:6333/healthz
```

If using Docker:

```bash
docker start qdrant
```

### Redis connection error

```
redis.exceptions.ConnectionError: Error connecting to localhost:6333
```

**Fix:** Start Redis and verify:

```bash
sudo systemctl start redis-server
redis-cli ping
```

### CUDA / GPU out of memory

```
torch.cuda.OutOfMemoryError: CUDA out of memory
```

**Fix:** Switch embedding and reranker models to CPU:

```bash
# In .env
EMBEDDING_DEVICE=cpu
RERANKER_DEVICE=cpu
```

Or reduce batch size:

```bash
EMBEDDING_BATCH_SIZE=16
```

### Alembic migration conflicts

```
alembic.util.exc.CommandError: Multiple head revisions
```

**Fix:** Merge the heads:

```bash
alembic merge heads -m "merge_conflicting_heads"
alembic upgrade head
```

### Port already in use

```
OSError: [Errno 98] Address already in use
```

**Fix:** Find and kill the process using the port:

```bash
# Find process on port 8000
lsof -i :8000
# Kill it
kill -9 <PID>
```

Or use a different port:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend build fails with memory error

```
FATAL ERROR: CALL_AND_RETRY_LAST Allocation failed - JavaScript heap out of memory
```

**Fix:** Increase Node.js memory limit:

```bash
export NODE_OPTIONS="--max-old-space-size=4096"
npm run build
```

### Worker not processing tasks

**Fix:** Verify Redis is running, check worker logs, and ensure the worker is connected to the same Redis database:

```bash
# Check worker status
docker compose logs worker

# Or if running manually
arq app.worker.settings.WorkerSettings --check
```

### Permission denied on uploads directory

```
PermissionError: [Errno 13] Permission denied: './uploads'
```

**Fix:** Create the directory and set permissions:

```bash
mkdir -p ./uploads
chmod 755 ./uploads
```

### Pydantic validation error on startup

```
pydantic.error_wrappers.ValidationError: 1 validation error for Settings
```

**Fix:** Check that all required environment variables are set in `.env`. The error message will indicate which variable is missing or has an invalid value.

---

## 18. Environment Variables Reference

### Application

| Variable              | Required | Default                      | Description                          |
|-----------------------|----------|------------------------------|--------------------------------------|
| `APP_ENV`             | Yes      | `local`                      | Runtime environment                  |
| `APP_DEBUG`           | No       | `true`                       | Enable debug mode                    |
| `APP_SECRET_KEY`      | Yes      | —                            | JWT/session signing key              |
| `APP_HOST`            | No       | `0.0.0.0`                    | Backend bind host                    |
| `APP_PORT`            | No       | `8000`                       | Backend bind port                    |
| `APP_CORS_ORIGINS`    | No       | `http://localhost:3000`      | Allowed CORS origins (comma-sep)     |
| `LOG_LEVEL`           | No       | `INFO`                       | Logging level                        |

### Database (PostgreSQL)

| Variable                 | Required | Default                                              | Description                    |
|--------------------------|----------|------------------------------------------------------|--------------------------------|
| `DATABASE_URL`           | Yes      | —                                                    | PostgreSQL connection string   |
| `DATABASE_POOL_SIZE`     | No       | `20`                                                 | Connection pool size           |
| `DATABASE_MAX_OVERFLOW`  | No       | `10`                                                 | Max overflow connections       |

### Vector Store (Qdrant)

| Variable              | Required | Default         | Description                    |
|-----------------------|----------|-----------------|--------------------------------|
| `QDRANT_URL`          | Yes      | —               | Qdrant server URL              |
| `QDRANT_API_KEY`      | No       | `""`            | Qdrant API key                 |
| `QDRANT_COLLECTION`   | No       | `documents`     | Default vector collection      |

### Cache / Queue (Redis)

| Variable          | Required | Default                  | Description            |
|-------------------|----------|--------------------------|------------------------|
| `REDIS_URL`       | Yes      | —                        | Redis connection URL   |
| `REDIS_PASSWORD`  | No       | `""`                     | Redis password         |

### Worker

| Variable              | Required | Default | Description                    |
|-----------------------|----------|---------|--------------------------------|
| `WORKER_CONCURRENCY`  | No       | `4`     | Number of concurrent tasks     |

### LLM

| Variable       | Required | Default | Description                          |
|----------------|----------|---------|--------------------------------------|
| `LLM_PROVIDER` | Yes      | —       | LLM provider: `openai`, `anthropic`, `ollama` |
| `LLM_API_KEY`  | Yes      | —       | API key for the LLM provider        |
| `LLM_MODEL`    | Yes      | —       | Model identifier                     |
| `LLM_BASE_URL` | No       | —       | Custom LLM endpoint                  |

### Embedding Model

| Variable           | Required | Default          | Description                         |
|--------------------|----------|------------------|-------------------------------------|
| `EMBEDDING_MODEL`  | Yes      | `BAAI/bge-m3`    | Embedding model name                |
| `EMBEDDING_DEVICE` | No       | `cuda`           | Device: `cpu` or `cuda`             |
| `EMBEDDING_DIM`    | No       | `1024`           | Embedding vector dimension          |

### Reranker Model

| Variable          | Required | Default                   | Description              |
|-------------------|----------|---------------------------|--------------------------|
| `RERANKER_MODEL`  | Yes      | `BAAI/bge-reranker-v2-m3`| Reranker model name      |
| `RERANKER_DEVICE` | No       | `cuda`                    | Device: `cpu` or `cuda`  |

### Observability (Langfuse)

| Variable              | Required | Default                        | Description           |
|-----------------------|----------|--------------------------------|-----------------------|
| `LANGFUSE_PUBLIC_KEY` | No       | —                              | Langfuse public key   |
| `LANGFUSE_SECRET_KEY` | No       | —                              | Langfuse secret key   |
| `LANGFUSE_HOST`       | No       | `https://cloud.langfuse.com`   | Langfuse server URL   |

### Observability (OpenTelemetry)

| Variable                        | Required | Default                | Description                    |
|---------------------------------|----------|------------------------|--------------------------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT`  | No       | `http://localhost:4317`| OTLP collector endpoint        |
| `OTEL_SERVICE_NAME`            | No       | `ai-doc-ops`           | Service name for tracing       |

### File Upload

| Variable             | Required | Default  | Description                   |
|----------------------|----------|----------|-------------------------------|
| `UPLOAD_DIR`         | No       | `./uploads` | Upload directory path      |
| `MAX_UPLOAD_SIZE_MB` | No       | `100`    | Max upload size in MB         |
