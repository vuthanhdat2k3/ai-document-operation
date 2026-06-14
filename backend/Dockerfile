# =============================================================================
# AI Document Operations Agent - Backend Dockerfile (multi-stage)
# =============================================================================

# --- Base stage ---
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# --- Dependencies stage ---
FROM base AS deps
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -e ".[dev]" 2>/dev/null || \
    pip install --no-cache-dir \
        "fastapi>=0.110,<1.0" \
        "uvicorn[standard]>=0.29,<1.0" \
        "sqlalchemy[asyncio]>=2.0,<3.0" \
        "asyncpg>=0.29,<1.0" \
        "alembic>=1.13,<2.0" \
        "pydantic>=2.6,<3.0" \
        "pydantic-settings>=2.2,<3.0" \
        "redis>=5.0,<6.0" \
        "httpx>=0.27,<1.0" \
        "python-multipart>=0.0.9" \
        "structlog>=24.1,<25.0" \
        "PyJWT>=2.8,<3.0" \
        "passlib[bcrypt]>=1.7,<2.0" \
        "anthropic>=0.34,<1.0" \
        "openai>=1.30,<2.0" \
        "arq>=0.26,<1.0" \
        "PyMuPDF>=1.24,<2.0" \
        "python-docx>=1.1,<2.0" \
        "openpyxl>=3.1,<4.0"

# --- Development stage ---
FROM deps AS development
COPY . .
ENV APP_ENV=development
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --- Production stage ---
FROM deps AS production
COPY . .
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser
USER appuser
ENV APP_ENV=production
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
