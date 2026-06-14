# AI Document Operations Agent — Deployment Plan

## 1. Deployment Overview

This document outlines the complete deployment strategy for the AI Document Operations Agent platform. The system consists of a FastAPI backend, Next.js frontend, async workers (ARQ/Celery), PostgreSQL database, Qdrant vector store, Redis message broker, MinIO object storage, and Langfuse observability. The deployment follows a progressive promotion model: Local → Staging → Production, with automated CI/CD, zero-downtime deploys, and comprehensive monitoring.

**Key Principles:**
- Infrastructure as Code (Docker, Docker Compose, GitHub Actions)
- Zero-downtime deployments via rolling updates
- Automated backups with tested recovery procedures
- Observability-first with Langfuse and OpenTelemetry
- Least-privilege security (non-root containers, secrets management)

---

## 2. Environment Strategy

### 2.1 Local Development

| Component       | Purpose                                    |
|-----------------|--------------------------------------------|
| Docker Compose  | Spin up all services with a single command |
| Hot-reload      | Backend (uvicorn --reload), Frontend (next dev) |
| Seed data       | Automated DB seeding and fixture loading   |
| MinIO           | Local S3-compatible object storage         |
| Langfuse        | Local tracing for prompt debugging         |

```bash
# Start local environment
cp .env.example .env.local
docker compose -f docker-compose.dev.yml up --build

# Seed database
docker compose exec api python -m app.db.seed

# Run migrations
docker compose exec api alembic upgrade head
```

### 2.2 Staging

| Property         | Value                                      |
|------------------|--------------------------------------------|
| Purpose          | Pre-production validation, integration tests |
| Infrastructure   | Managed PostgreSQL, Qdrant, Redis on cloud |
| Data             | Anonymized production snapshot              |
| Auth             | SSO with test IdP                           |
| Observability    | Full Langfuse + OTEL tracing               |
| URL              | `https://staging.agent.example.com`        |

### 2.3 Production

| Property         | Value                                      |
|------------------|--------------------------------------------|
| Purpose          | Live user traffic                          |
| Infrastructure   | Managed services with HA, auto-scaling     |
| Data             | Real user data, encrypted at rest          |
| Auth             | SSO with production IdP                    |
| Observability    | Full tracing, alerting, dashboards         |
| URL              | `https://agent.example.com`               |

---

## 3. Docker Configuration

### 3.1 Backend Dockerfile (FastAPI)

```dockerfile
# ---- Build stage ----
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Runtime stage ----
FROM python:3.12-slim AS runtime

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app
COPY --from=builder /install /usr/local
COPY ./backend /app

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 3.2 Frontend Dockerfile (Next.js)

```dockerfile
# ---- Dependencies ----
FROM node:20-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts

# ---- Build ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---- Production ----
FROM nginx:1.27-alpine AS production

COPY --from=builder /app/.next/static /usr/share/nginx/html/_next/static
COPY --from=builder /app/public /usr/share/nginx/html/public
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:3000/health || exit 1

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
```

### 3.3 Worker Dockerfile (ARQ/Celery)

```dockerfile
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY ./backend /app

RUN chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import redis; r = redis.Redis.from_url('${REDIS_URL}'); r.ping()" || exit 1

CMD ["arq", "app.worker.WorkerSettings"]
```

### 3.4 Docker Compose — Local Development

```yaml
# docker-compose.dev.yml
version: "3.9"

x-common-env: &common-env
  DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/agent_dev
  REDIS_URL: redis://redis:6379/0
  QDRANT_URL: http://qdrant:6333
  MINIO_ENDPOINT: minio:9000
  MINIO_ACCESS_KEY: minioadmin
  MINIO_SECRET_KEY: minioadmin
  LANGFUSE_HOST: http://langfuse:3000
  OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
  ENVIRONMENT: development

services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    environment:
      <<: *common-env
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_started
      minio:
        condition: service_started

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    volumes:
      - ./backend:/app
    environment:
      <<: *common-env
    command: arq app.worker.WorkerSettings
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  frontend:
    build:
      context: .
      dockerfile: docker/Dockerfile.frontend
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    depends_on:
      - api

  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: agent_dev
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:v1.12.1
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"

  langfuse:
    image: langfuse/langfuse:latest
    ports:
      - "3001:3000"
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/langfuse_dev
      NEXTAUTH_URL: http://localhost:3001
      NEXTAUTH_SECRET: dev-secret
    depends_on:
      postgres:
        condition: service_healthy

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    ports:
      - "4317:4317"
      - "4318:4318"
    volumes:
      - ./config/otel-collector.yml:/etc/otelcol-contrib/config.yaml

volumes:
  postgres_data:
  qdrant_data:
  redis_data:
  minio_data:
```

### 3.5 Docker Compose — Production

```yaml
# docker-compose.prod.yml
version: "3.9"

x-common-env: &common-env
  DATABASE_URL: ${DATABASE_URL}
  REDIS_URL: ${REDIS_URL}
  QDRANT_URL: ${QDRANT_URL}
  MINIO_ENDPOINT: ${MINIO_ENDPOINT}
  MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY}
  MINIO_SECRET_KEY: ${MINIO_SECRET_KEY}
  LANGFUSE_HOST: ${LANGFUSE_HOST}
  OTEL_EXPORTER_OTLP_ENDPOINT: ${OTEL_EXPORTER_OTLP_ENDPOINT}
  ENVIRONMENT: production
  OPENAI_API_KEY: ${OPENAI_API_KEY}

services:
  api:
    image: ${DOCKER_REGISTRY}/agent-api:${IMAGE_TAG}
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
        reservations:
          cpus: "0.5"
          memory: 512M
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
    environment:
      <<: *common-env
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s

  worker:
    image: ${DOCKER_REGISTRY}/agent-worker:${IMAGE_TAG}
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
        reservations:
          cpus: "0.5"
          memory: 512M
    environment:
      <<: *common-env

  frontend:
    image: ${DOCKER_REGISTRY}/agent-frontend:${IMAGE_TAG}
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
    ports:
      - "80:3000"
      - "443:3000"
```

---

## 4. Services Overview

| Service        | Image/Stack              | Port(s)       | Purpose                              |
|----------------|--------------------------|---------------|--------------------------------------|
| `api`          | FastAPI / Uvicorn        | 8000          | REST API, document processing        |
| `worker`       | ARQ (async)              | —             | Background jobs (embedding, parsing) |
| `frontend`     | Next.js → Nginx          | 3000          | User-facing web application          |
| `postgres`     | PostgreSQL 16            | 5432          | Primary relational database          |
| `qdrant`       | Qdrant                   | 6333, 6334    | Vector similarity search             |
| `redis`        | Redis 7                  | 6379          | Message broker, cache, rate limiting |
| `minio`        | MinIO                    | 9000, 9001    | S3-compatible object storage         |
| `langfuse`     | Langfuse                 | 3001          | LLM observability and tracing        |
| `otel-collector` | OpenTelemetry Collector | 4317, 4318   | Telemetry aggregation                |

---

## 5. Infrastructure Configuration

### 5.1 PostgreSQL

```sql
-- postgresql.conf overrides
max_connections = 200
shared_buffers = 1GB
effective_cache_size = 3GB
work_mem = 16MB
maintenance_work_mem = 256MB
wal_level = replica
max_wal_senders = 5
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/wal_archive/%f'
checkpoint_completion_target = 0.9
```

**Connection Pooling (PgBouncer):**

```ini
[databases]
agent_prod = host=postgres port=5432 dbname=agent_prod

[pgbouncer]
listen_port = 6432
listen_addr = 0.0.0.0
pool_mode = transaction
default_pool_size = 25
max_client_conn = 500
max_db_connections = 100
```

### 5.2 Qdrant

```yaml
# qdrant config
storage:
  storage_path: /qdrant/storage
  snapshots_path: /qdrant/snapshots
  performance:
    max_search_threads: 4
    max_optimization_threads: 2
service:
  grpc_port: 6334
  http_port: 6333
  host: "0.0.0.0"
```

### 5.3 Redis

```
# redis.conf
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
appendonly yes
appendfsync everysec
```

### 5.4 MinIO / S3

```yaml
# MinIO bucket policy
buckets:
  - name: documents
    policy: private
  - name: exports
    policy: private
  - name: temp
    policy: private
    lifecycle:
      - expiration: 7d
```

---

## 6. CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  DOCKER_REGISTRY: ghcr.io/${{ github.repository }}

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff mypy
      - run: ruff check backend/
      - run: ruff format --check backend/

  typecheck:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: mypy backend/app --ignore-missing-imports

  unit-tests:
    runs-on: ubuntu-latest
    needs: typecheck
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt -r requirements-test.txt
      - run: pytest backend/tests/unit -v --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports: ["5432:5432"]
        options: --health-cmd pg_isready --health-interval 10s --health-timeout 5s --health-retries 5
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt -r requirements-test.txt
      - run: pytest backend/tests/integration -v
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5432/test
          REDIS_URL: redis://localhost:6379/0

  build:
    runs-on: ubuntu-latest
    needs: [integration-tests]
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/develop'
    strategy:
      matrix:
        service: [api, worker, frontend]
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/Dockerfile.${{ matrix.service }}
          push: true
          tags: |
            ${{ env.DOCKER_REGISTRY }}/${{ matrix.service }}:${{ github.sha }}
            ${{ env.DOCKER_REGISTRY }}/${{ matrix.service }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy-staging:
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/develop'
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Staging
        run: |
          export IMAGE_TAG=${{ github.sha }}
          docker compose -f docker-compose.prod.yml pull
          docker compose -f docker-compose.prod.yml up -d
      - name: Run smoke tests
        run: |
          sleep 30
          curl -sf https://staging.agent.example.com/health || exit 1
          pytest tests/smoke/ --base-url=https://staging.agent.example.com

  deploy-production:
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Production
        run: |
          export IMAGE_TAG=${{ github.sha }}
          docker compose -f docker-compose.prod.yml pull
          docker compose -f docker-compose.prod.yml up -d
      - name: Health check
        run: |
          sleep 30
          curl -sf https://agent.example.com/health || exit 1

  evaluation:
    runs-on: ubuntu-latest
    needs: deploy-staging
    if: github.ref == 'refs/heads/develop'
    steps:
      - uses: actions/checkout@v4
      - name: Run evaluation suite
        run: |
          python scripts/run_evaluation.py \
            --base-url=https://staging.agent.example.com \
            --dataset=evals/golden_dataset.jsonl \
            --threshold=0.85
```

---

## 7. Deployment Procedures

### 7.1 Database Migrations (Alembic)

```bash
# Generate migration
alembic revision --autogenerate -m "add document_chunks table"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Check current revision
alembic current

# Migration history
alembic history --verbose
```

**Migration Rules:**
- All schema changes must go through Alembic migrations
- Migrations must be backward-compatible for zero-downtime deploys
- Destructive changes require a two-phase deploy (add new → migrate data → drop old)
- Migrations run automatically during deployment before API restart

### 7.2 Zero-Downtime Deployment Strategy

```
Phase 1: Pre-deploy
  ├── Run database migrations (backward-compatible)
  ├── Warm up new containers
  └── Verify health checks pass

Phase 2: Rolling update
  ├── Update 1 instance at a time
  ├── Drain connections from old instance (30s grace period)
  ├── Route traffic to new instance
  ├── Verify health check passes
  └── Proceed to next instance

Phase 3: Post-deploy
  ├── Run smoke tests
  ├── Monitor error rates (5 min window)
  ├── If error rate > 1% → automatic rollback
  └── If stable → mark deployment as successful
```

### 7.3 Rollback Procedures

```bash
# Automatic rollback (triggered by health check failure)
# The CI/CD pipeline will:
# 1. Detect failed health checks
# 2. Re-deploy previous IMAGE_TAG
# 3. Rollback database migration (if applicable)
# 4. Notify team via Slack

# Manual rollback
export IMAGE_TAG=<previous-commit-sha>
docker compose -f docker-compose.prod.yml up -d
alembic downgrade -1  # Only if migration was applied
```

### 7.4 Health Check Endpoints

| Endpoint           | Method | Purpose                          | Response                |
|--------------------|--------|----------------------------------|-------------------------|
| `/health`          | GET    | Basic liveness check             | `{"status": "ok"}`      |
| `/health/ready`    | GET    | Readiness (DB, Redis, Qdrant)    | `{"status": "ready", "checks": {...}}` |
| `/health/live`     | GET    | Liveness (process alive)         | `{"status": "alive"}`   |

```python
# Backend health check implementation
@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.VERSION}

@app.get("/health/ready")
async def readiness():
    checks = {}
    try:
        await database.execute("SELECT 1")
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "fail"
        raise HTTPException(503)

    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "fail"
        raise HTTPException(503)

    try:
        await qdrant.get_collections()
        checks["qdrant"] = "ok"
    except Exception:
        checks["qdrant"] = "fail"
        raise HTTPException(503)

    return {"status": "ready", "checks": checks}
```

---

## 8. Monitoring in Production

### 8.1 Health Checks

| Probe             | Path             | Interval | Timeout | Failure Threshold |
|-------------------|------------------|----------|---------|-------------------|
| Liveness          | `/health/live`   | 15s      | 3s      | 3                 |
| Readiness         | `/health/ready`  | 10s      | 5s      | 3                 |
| Startup           | `/health`        | 5s       | 3s      | 30                |

### 8.2 Resource Limits

| Service     | CPU Limit | CPU Reserve | Memory Limit | Memory Reserve |
|-------------|-----------|-------------|--------------|----------------|
| api         | 1.0       | 0.5         | 1Gi          | 512Mi          |
| worker      | 2.0       | 0.5         | 2Gi          | 512Mi          |
| frontend    | 0.5       | 0.25        | 256Mi        | 128Mi          |
| postgres    | 2.0       | 1.0         | 4Gi          | 2Gi            |
| qdrant      | 2.0       | 1.0         | 4Gi          | 2Gi            |
| redis       | 0.5       | 0.25        | 1Gi          | 512Mi          |

### 8.3 Auto-Scaling Rules

```yaml
# Horizontal Pod Autoscaler configuration
scaling:
  api:
    min_replicas: 2
    max_replicas: 10
    metrics:
      - type: cpu
        target: 70%
      - type: memory
        target: 80%
      - type: requests_per_second
        target: 100
  worker:
    min_replicas: 1
    max_replicas: 5
    metrics:
      - type: queue_depth
        target: 50
      - type: cpu
        target: 75%
```

### 8.4 Alerting Rules

| Alert                  | Condition                            | Severity | Action              |
|------------------------|--------------------------------------|----------|---------------------|
| High error rate        | > 1% 5xx errors for 5 min           | Critical | PagerDuty + Slack   |
| High latency           | p99 > 5s for 5 min                  | Warning  | Slack               |
| Disk space low         | > 85% used                          | Warning  | Slack               |
| DB connection pool full| > 90% pool utilization              | Critical | PagerDuty + Slack   |
| Worker queue depth     | > 1000 pending tasks                | Warning  | Slack               |
| OOM killed             | Container OOM event                  | Critical | PagerDuty           |
| Backup failure         | Backup job failed                    | Critical | PagerDuty + Slack   |

---

## 9. Backup Strategy

### 9.1 PostgreSQL Backup

```bash
#!/bin/bash
# scripts/backup-postgres.sh

BACKUP_DIR="/backups/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/agent_${TIMESTAMP}.sql.gz"

# Full logical backup (daily)
pg_dump -h $PGHOST -U $PGUSER agent_prod | gzip > "$BACKUP_FILE"

# Retention: keep last 30 daily backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

# WAL archiving (continuous)
# Configured in postgresql.conf:
# archive_mode = on
# archive_command = 'cp %p /var/lib/postgresql/wal_archive/%f'
```

| Backup Type      | Frequency    | Retention | Storage          |
|------------------|--------------|-----------|------------------|
| Full dump        | Daily 02:00  | 30 days   | S3 (encrypted)   |
| WAL archives     | Continuous   | 7 days    | S3 (encrypted)   |
| Point-in-time    | On-demand    | Per request| S3              |

### 9.2 Qdrant Backup

```bash
#!/bin/bash
# scripts/backup-qdrant.sh

SNAPSHOT_URL="http://qdrant:6333/collections/documents/snapshots"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create snapshot
curl -X POST "$SNAPSHOT_URL" -o "/backups/qdrant/snapshot_${TIMESTAMP}.snapshot"

# Upload to S3
aws s3 cp "/backups/qdrant/snapshot_${TIMESTAMP}.snapshot" \
  s3://backups/qdrant/ --sse AES256

# Retention: 14 days
find /backups/qdrant -name "*.snapshot" -mtime +14 -delete
```

### 9.3 MinIO Backup

```bash
#!/bin/bash
# scripts/backup-minio.sh

# Mirror documents bucket to backup location
mc mirror --overwrite minio/documents s3/backups/minio/documents/

# Retention: 90 days for documents
mc rm --recursive --force --older-than 90d s3/backups/minio/temp/
```

### 9.4 Backup Verification

```bash
#!/bin/bash
# scripts/verify-backup.sh

# Monthly restore test (automated via cron)
# 1. Spin up temporary PostgreSQL instance
# 2. Restore latest backup
# 3. Run data integrity checks
# 4. Report results
# 5. Tear down temporary instance

docker run -d --name pg-verify -e POSTGRES_PASSWORD=verify postgres:16
sleep 10
gunzip -c /backups/postgres/latest.sql.gz | docker exec -i pg-verify psql -U postgres
docker exec pg-verify psql -U postgres -c "SELECT count(*) FROM documents;"
docker rm -f pg-verify
```

---

## 10. Disaster Recovery

### 10.1 Objectives

| Metric | Target  | Description                                      |
|--------|---------|--------------------------------------------------|
| RTO    | 4 hours | Maximum time to restore full service             |
| RPO    | 1 hour  | Maximum acceptable data loss (WAL archive freq.) |

### 10.2 Failover Procedures

```
Scenario 1: Single Service Failure
  ├── Docker restart policy handles automatically
  ├── Alert if restart count > 3 in 10 min
  └── Manual investigation required

Scenario 2: Database Failure
  ├── Promote read replica (if available)
  ├── Restore from latest backup + WAL replay
  ├── Update connection strings
  ├── Run alembic upgrade head
  └── Verify data integrity

Scenario 3: Full Region Outage
  ├── Switch DNS to DR region
  ├── Restore PostgreSQL from S3 backup
  ├── Restore Qdrant from snapshot
  ├── Restore MinIO data
  ├── Verify all services healthy
  └── Notify users of service restoration
```

### 10.3 Recovery Steps

```bash
# 1. Restore PostgreSQL
pg_restore -h $PGHOST -U $PGUSER -d agent_prod /backups/latest.dump

# 2. Replay WAL (point-in-time recovery)
recovery_target_time = '2026-06-11 14:00:00+07'

# 3. Restore Qdrant
curl -X PUT "http://qdrant:6333/collections/documents/snapshots/recover" \
  -H "Content-Type: application/json" \
  -d '{"location": "s3://backups/qdrant/latest.snapshot"}'

# 4. Restore MinIO
mc mirror s3/backups/minio/documents/ minio/documents/

# 5. Verify
python scripts/verify_recovery.py
```

---

## 11. Cost Estimation

### 11.1 Monthly Cost Breakdown

| Category           | Component              | Specification       | Monthly Cost (USD) |
|--------------------|------------------------|---------------------|--------------------|
| **Compute**        | API servers (3x)       | 2 vCPU, 4GB RAM     | $150               |
|                    | Worker servers (2x)    | 2 vCPU, 4GB RAM     | $100               |
|                    | Frontend (2x)          | 1 vCPU, 1GB RAM     | $50                |
| **Database**       | PostgreSQL (managed)   | 4 vCPU, 16GB, 100GB | $200               |
|                    | PgBouncer              | Shared              | $0                 |
| **Vector Store**   | Qdrant (managed)       | 4 vCPU, 16GB, 50GB  | $150               |
| **Cache**          | Redis (managed)        | 2 vCPU, 4GB         | $60                |
| **Storage**        | MinIO / S3             | 500GB documents     | $12                |
|                    | Backups                | 1TB S3              | $23                |
| **Observability**  | Langfuse               | Self-hosted         | $0                 |
|                    | OTEL Collector         | Shared              | $0                 |
| **LLM APIs**       | OpenAI GPT-4           | ~500K tokens/day    | $600               |
|                    | Embeddings (Ada-002)   | ~1M tokens/day      | $100               |
| **Networking**     | Load balancer          | Managed LB          | $20                |
|                    | CDN                    | CloudFront/similar  | $15                |
| **CI/CD**          | GitHub Actions         | ~2000 min/month     | $40                |
|                    |                        |                     |                    |
| **TOTAL**          |                        |                     | **~$1,520/month**  |

### 11.2 Cost Optimization

- Use spot/preemptible instances for workers (60% savings)
- Right-size instances based on actual utilization metrics
- Implement request caching to reduce LLM API calls
- Use smaller models (GPT-3.5) for non-critical tasks
- Set up billing alerts at 80% and 100% of budget

---

## 12. Implementation Checklist

- [ ] **Infrastructure Setup**
  - [ ] Provision cloud infrastructure (compute, storage, networking)
  - [ ] Set up managed PostgreSQL with automated backups
  - [ ] Deploy Qdrant with persistent storage
  - [ ] Configure Redis with persistence
  - [ ] Set up MinIO/S3 with bucket policies
  - [ ] Configure PgBouncer for connection pooling
  - [ ] Set up DNS and TLS certificates

- [ ] **Docker & Containerization**
  - [ ] Build and test backend Dockerfile
  - [ ] Build and test frontend Dockerfile
  - [ ] Build and test worker Dockerfile
  - [ ] Validate docker-compose.dev.yml locally
  - [ ] Validate docker-compose.prod.yml in staging
  - [ ] Set up container registry (GHCR)

- [ ] **CI/CD Pipeline**
  - [ ] Configure GitHub Actions workflows
  - [ ] Set up linting and type checking
  - [ ] Configure unit test pipeline with coverage
  - [ ] Set up integration test environment
  - [ ] Configure build and push to registry
  - [ ] Set up staging deployment automation
  - [ ] Set up production deployment with approvals
  - [ ] Configure evaluation pipeline

- [ ] **Security**
  - [ ] Secrets management (environment variables, vault)
  - [ ] Network policies (internal service communication)
  - [ ] TLS everywhere (internal and external)
  - [ ] Container image scanning (Trivy/Snyk)
  - [ ] Dependency vulnerability scanning
  - [ ] RBAC for production access

- [ ] **Monitoring & Observability**
  - [ ] Deploy Langfuse for LLM tracing
  - [ ] Configure OpenTelemetry collector
  - [ ] Set up health check endpoints
  - [ ] Configure alerting rules
  - [ ] Create dashboards (Grafana/Langfuse)
  - [ ] Set up log aggregation

- [ ] **Backup & Recovery**
  - [ ] Automate PostgreSQL backups with WAL archiving
  - [ ] Automate Qdrant snapshot backups
  - [ ] Automate MinIO data backups
  - [ ] Schedule monthly backup verification tests
  - [ ] Document and test recovery procedures
  - [ ] Set up cross-region backup replication

- [ ] **Documentation**
  - [ ] Document runbooks for common operations
  - [ ] Create incident response playbook
  - [ ] Document scaling procedures
  - [ ] Create onboarding guide for new developers

---

## 13. Acceptance Criteria

| #   | Criterion                                          | Validation Method                        |
|-----|---------------------------------------------------|------------------------------------------|
| AC1 | All services start with `docker compose up`       | Manual test, CI smoke test               |
| AC2 | API responds to `/health/ready` within 2 seconds  | Automated health check                   |
| AC3 | Database migrations apply without downtime         | Staging deploy test                      |
| AC4 | Zero-downtime deployment verified in staging       | Rolling update test with active traffic  |
| AC5 | CI pipeline completes in under 15 minutes          | GitHub Actions metrics                   |
| AC6 | All integration tests pass in CI                   | CI pipeline green                        |
| AC7 | Backup and restore cycle verified monthly          | Automated restore test script            |
| AC8 | RTO < 4 hours validated via DR drill               | Quarterly DR exercise                    |
| AC9 | RPO < 1 hour validated via WAL replay test         | Point-in-time recovery test              |
| AC10| Auto-scaling triggers correctly under load         | Load test with k6/vegeta                |
| AC11| All containers run as non-root user                | Docker image audit                       |
| AC12| Resource limits enforced for all services          | Docker inspect / monitoring dashboards   |
| AC13| Alerts fire within 2 minutes of incident           | Alert simulation test                    |
| AC14| LLM costs tracked per request via Langfuse         | Langfuse dashboard verification          |
| AC15| Production deployment requires approval gate        | GitHub Actions environment protection    |
| AC16| Rollback completes within 5 minutes                | Manual rollback test in staging          |
| AC17| All secrets stored securely (no plaintext)         | Secret scanning in CI                    |
| AC18| Container images scanned for vulnerabilities       | Trivy scan in CI pipeline                |

---

*Last updated: 2026-06-11*
*Owner: Platform Engineering Team*
*Review cycle: Monthly*
