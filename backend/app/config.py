"""Application configuration via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "ai-doc-ops-agent"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database (PostgreSQL)
    DATABASE_URL: str = "postgresql+asyncpg://docops:docops@localhost:5432/docops"
    DB_POOL_SIZE: int = 40
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Qdrant (Vector Database)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None

    # MinIO (Object Storage)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "documents"
    MINIO_USE_SSL: bool = False

    # LLM Provider
    LLM_PROVIDER: str = "openai"  # openai | anthropic | xiaomi | local
    LLM_MODEL: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096
    LLM_TIMEOUT: int = 60
    LLM_STREAMING: bool = True

    # OpenAI-compatible
    OPENAI_API_KEY: str | None = None
    OPENAI_API_BASE: str = "https://api.openai.com/v1"

    # Anthropic / Xiaomi (Anthropic-compatible)
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"

    # Xiaomi MiMo (Anthropic-compatible)
    XIAOMI_API_KEY: str | None = None
    XIAOMI_BASE_URL: str = "https://token-plan-sgp.xiaomimimo.com/anthropic"
    XIAOMI_MODEL: str = "mimo-v2.5-pro"

    # Local model (Ollama / vLLM)
    LOCAL_LLM_BASE_URL: str = "http://localhost:11434"

    # Embedding
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"

    # Langfuse (Observability)
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # Document Processing
    MAX_FILE_SIZE_MB: int = 100
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64

    # Agent
    MAX_ITERATIONS: int = 10

    # JWT / Auth
    JWT_SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton.

    Returns:
        Settings instance populated from environment variables.
    """
    return Settings()
