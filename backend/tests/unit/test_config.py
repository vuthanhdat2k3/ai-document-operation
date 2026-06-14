"""Unit tests for app.config.Settings."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.config import Settings, get_settings

_TEST_ENV_KEYS = [
    "APP_NAME", "DEBUG", "LOG_LEVEL", "DATABASE_URL", "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW", "DB_ECHO", "REDIS_URL", "QDRANT_URL", "QDRANT_API_KEY",
    "MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BUCKET",
    "MINIO_USE_SSL", "OPENAI_API_KEY", "DEFAULT_MODEL", "EMBEDDING_MODEL",
    "RERANKER_MODEL", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST", "MAX_FILE_SIZE_MB", "CHUNK_SIZE", "CHUNK_OVERLAP",
    "MAX_ITERATIONS", "CORS_ORIGINS",
]


def _clean_env() -> dict[str, str]:
    """Remove all Settings-related env vars so defaults are tested in isolation."""
    return {k: "" for k in _TEST_ENV_KEYS if k in os.environ}


class TestSettingsDefaults:
    """Verify default values for all Settings fields."""

    def test_app_name_default(self) -> None:
        with patch.dict(os.environ, _clean_env(), clear=False):
            for k in _clean_env():
                os.environ.pop(k, None)
            s = Settings()
            assert s.APP_NAME == "ai-doc-ops-agent"

    def test_debug_default_false(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.DEBUG is False

    def test_log_level_default_info(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.LOG_LEVEL == "INFO"

    def test_database_url_default(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert "postgresql+asyncpg" in s.DATABASE_URL

    def test_db_pool_size_default(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.DB_POOL_SIZE == 20

    def test_db_max_overflow_default(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.DB_MAX_OVERFLOW == 10

    def test_db_echo_default_false(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.DB_ECHO is False

    def test_redis_url_default(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.REDIS_URL.startswith("redis://")

    def test_qdrant_url_default(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.QDRANT_URL.startswith("http://")

    def test_qdrant_api_key_default_none(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.QDRANT_API_KEY is None

    def test_minio_endpoint_default(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.MINIO_ENDPOINT == "localhost:9000"

    def test_minio_access_key_default(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.MINIO_ACCESS_KEY == "minioadmin"

    def test_minio_secret_key_default(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.MINIO_SECRET_KEY == "minioadmin"

    def test_minio_bucket_default(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.MINIO_BUCKET == "documents"

    def test_minio_use_ssl_default_false(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.MINIO_USE_SSL is False

    def test_openai_api_key_default_none(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.OPENAI_API_KEY is None

    def test_default_model(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.DEFAULT_MODEL == "gpt-4o"

    def test_embedding_model(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.EMBEDDING_MODEL == "BAAI/bge-m3"

    def test_reranker_model(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.RERANKER_MODEL == "BAAI/bge-reranker-v2-m3"

    def test_langfuse_defaults(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.LANGFUSE_PUBLIC_KEY is None
            assert s.LANGFUSE_SECRET_KEY is None
            assert s.LANGFUSE_HOST == "https://cloud.langfuse.com"

    def test_document_processing_defaults(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.MAX_FILE_SIZE_MB == 100
            assert s.CHUNK_SIZE == 512
            assert s.CHUNK_OVERLAP == 64

    def test_max_iterations_default(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.MAX_ITERATIONS == 10

    def test_cors_origins_default(self) -> None:
        env_clean = _clean_env()
        with patch.dict(os.environ, env_clean, clear=False):
            for k in env_clean:
                os.environ.pop(k, None)
            s = Settings()
            assert s.CORS_ORIGINS == "http://localhost:3000"


class TestSettingsFromEnv:
    """Verify Settings loads values from environment variables."""

    def test_override_app_name(self) -> None:
        with patch.dict(os.environ, {"APP_NAME": "custom-app"}):
            s = Settings()
            assert s.APP_NAME == "custom-app"

    def test_override_debug(self) -> None:
        with patch.dict(os.environ, {"DEBUG": "true"}):
            s = Settings()
            assert s.DEBUG is True

    def test_override_database_url(self) -> None:
        url = "postgresql+asyncpg://u:p@db:5432/mydb"
        with patch.dict(os.environ, {"DATABASE_URL": url}):
            s = Settings()
            assert s.DATABASE_URL == url

    def test_override_redis_url(self) -> None:
        with patch.dict(os.environ, {"REDIS_URL": "redis://custom:6380/1"}):
            s = Settings()
            assert s.REDIS_URL == "redis://custom:6380/1"

    def test_case_insensitive(self) -> None:
        with patch.dict(os.environ, {"app_name": "lower-case-app"}):
            s = Settings()
            assert s.APP_NAME == "lower-case-app"

    def test_extra_fields_ignored(self) -> None:
        with patch.dict(os.environ, {"UNKNOWN_FIELD": "value"}):
            s = Settings()
            assert not hasattr(s, "UNKNOWN_FIELD")


class TestGetSettings:
    """Verify the get_settings() caching behavior."""

    def test_returns_settings_instance(self) -> None:
        get_settings.cache_clear()
        s = get_settings()
        assert isinstance(s, Settings)

    def test_returns_same_instance(self) -> None:
        get_settings.cache_clear()
        a = get_settings()
        b = get_settings()
        assert a is b

    def test_cache_clear(self) -> None:
        get_settings.cache_clear()
        a = get_settings()
        get_settings.cache_clear()
        b = get_settings()
        assert a is not b


class TestSettingsCustomValues:
    """Verify custom values are accepted."""

    def test_custom_values(self) -> None:
        s = Settings(
            APP_NAME="myapp",
            DEBUG=True,
            DB_POOL_SIZE=5,
            MAX_FILE_SIZE_MB=50,
            CHUNK_SIZE=1024,
            CHUNK_OVERLAP=128,
            MAX_ITERATIONS=5,
        )
        assert s.APP_NAME == "myapp"
        assert s.DEBUG is True
        assert s.DB_POOL_SIZE == 5
        assert s.MAX_FILE_SIZE_MB == 50
        assert s.CHUNK_SIZE == 1024
        assert s.CHUNK_OVERLAP == 128
        assert s.MAX_ITERATIONS == 5
