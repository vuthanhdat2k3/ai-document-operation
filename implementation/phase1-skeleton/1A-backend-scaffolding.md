# Phase 1A: Backend Scaffolding — Implementation Plan

## Task
Initialize Python project with pyproject.toml, FastAPI application skeleton, config, dependency injection, and error handling.

## Dependencies
None (first task)

## Files to Create

### 1. `backend/pyproject.toml`
- Project metadata (name, version, description)
- Python >=3.11
- Dependencies: fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic, pydantic, pydantic-settings, redis, qdrant-client, minio, langchain, langgraph, structlog, opentelemetry-api, opentelemetry-sdk, httpx, python-multipart
- Dev dependencies: pytest, pytest-asyncio, pytest-cov, httpx, ruff, mypy
- Ruff config: line-length=99, target-version="py311", select=["E","F","I","N","UP","B","A","SIM","TCH"]
- MyPy config: python_version="3.11", strict=true, plugins=["pydantic.mypy"]
- Pytest config: asyncio_mode="auto", testpaths=["tests"]

### 2. `backend/app/__init__.py`
- Empty init

### 3. `backend/app/config.py`
- Settings class using pydantic-settings BaseSettings
- Fields: APP_NAME, DEBUG, LOG_LEVEL, DATABASE_URL, DB_POOL_SIZE, DB_ECHO, REDIS_URL, QDRANT_URL, QDRANT_API_KEY, MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET, OPENAI_API_KEY, DEFAULT_MODEL, EMBEDDING_MODEL, RERANKER_MODEL, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST, MAX_FILE_SIZE_MB, CHUNK_SIZE, CHUNK_OVERLAP, MAX_ITERATIONS, CORS_ORIGINS
- SettingsConfigDict with env_file=".env", case_sensitive=False, extra="ignore"
- get_settings() function with lru_cache

### 4. `backend/app/main.py`
- create_app() factory function
- asynccontextmanager lifespan (init_db, init_vector_store, warm_up_models on startup; shutdown on teardown)
- Register middleware, routes, exception handlers
- Health endpoints

### 5. `backend/app/deps.py`
- get_db() async generator for SQLAlchemy session
- get_settings() dependency
- get_redis() dependency
- get_qdrant() dependency
- get_minio() dependency

### 6. `backend/app/api/__init__.py`
- Empty init

### 7. `backend/app/api/v1/__init__.py`
- Empty init

### 8. `backend/app/api/v1/router.py`
- v1 APIRouter aggregation
- Include health, documents routers

### 9. `backend/app/api/v1/admin.py`
- GET /health — returns {"status": "ok", "version": "1.0.0"}
- GET /ready — checks PostgreSQL, Redis, Qdrant, MinIO connectivity

### 10. `backend/app/api/middleware/__init__.py`
- Empty init

### 11. `backend/app/api/middleware/request_id.py`
- Middleware to assign X-Request-ID (UUID4) to every request
- Store in request.state and add to response headers

### 12. `backend/app/api/middleware/error_handler.py`
- Global exception handlers for AppError, ValidationError, NotFoundError, RateLimitError
- Structured JSON error responses

### 13. `backend/app/api/schemas/__init__.py`
- Empty init

### 14. `backend/app/api/schemas/common.py`
- ErrorResponse model
- PaginatedResponse model
- HealthResponse model

### 15. `backend/app/services/__init__.py`
- Empty init

### 16. `backend/app/db/__init__.py`
- Empty init

### 17. `backend/app/db/base.py`
- SQLAlchemy DeclarativeBase
- TimestampMixin (created_at, updated_at)
- SoftDeleteMixin (deleted_at)
- UUIDMixin (id as UUID primary key)

### 18. `backend/app/db/session.py`
- create_async_engine with settings
- async_session_factory (AsyncSession)
- get_db dependency

### 19. `backend/app/utils/__init__.py`
- Empty init

### 20. `backend/app/utils/hash.py`
- content_hash(data: bytes) -> str — SHA-256

### 21. `backend/app/utils/file.py`
- sanitize_filename(filename: str) -> str
- get_file_extension(filename: str) -> str

## Acceptance Criteria
- [ ] `pip install -e ".[dev]"` installs all dependencies
- [ ] `ruff check .` passes with zero errors
- [ ] `mypy --strict backend/app` passes
- [ ] `uvicorn app.main:create_app --factory` starts without errors
- [ ] GET /health returns 200 with {"status": "ok"}

## Coding Standards
- Python 3.11+ type hints everywhere
- Google-style docstrings
- Async/await for all I/O
- No bare except
- No mutable default arguments
