"""Redis-backed query result caching for search operations."""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.cache.redis import RedisCache

logger = logging.getLogger(__name__)

SEARCH_PREFIX = "search"
DOC_FIELDS_PREFIX = "doc_fields"


class QueryCache:
    """High-level cache layer for search results and document field lookups.

    Wraps :class:`RedisCache` with domain-specific key patterns and
    serialization helpers.

    Args:
        redis_cache: An initialised ``RedisCache`` instance.
    """

    def __init__(self, redis_cache: RedisCache) -> None:
        self._cache = redis_cache

    @staticmethod
    def _hash_query(query: str) -> str:
        """Produce a deterministic SHA-256 hex digest for a query string."""
        return hashlib.sha256(query.encode("utf-8")).hexdigest()

    async def cache_search_result(
        self,
        query_hash: str,
        results: list[dict[str, Any]],
        ttl: int = 300,
    ) -> None:
        """Store search results in cache.

        Args:
            query_hash: Unique hash identifying the query (see :meth:`_hash_query`).
            results: List of serialisable result dicts.
            ttl: Time-to-live in seconds (default 5 minutes).
        """
        key = f"{SEARCH_PREFIX}:{query_hash}"
        await self._cache.set(key, results, ttl=ttl)
        logger.debug("Cached search results for key=%s ttl=%ds", key, ttl)

    async def get_cached_search(self, query_hash: str) -> list[dict[str, Any]] | None:
        """Retrieve cached search results.

        Args:
            query_hash: The query hash used during caching.

        Returns:
            List of result dicts, or ``None`` on cache miss.
        """
        key = f"{SEARCH_PREFIX}:{query_hash}"
        data = await self._cache.get(key)
        if data is not None:
            logger.debug("Cache hit for search key=%s", key)
        return data

    async def cache_document_fields(
        self,
        document_id: str,
        fields: list[dict[str, Any]],
        ttl: int = 600,
    ) -> None:
        """Cache extracted fields for a document.

        Args:
            document_id: Document UUID string.
            fields: List of field dicts to cache.
            ttl: Time-to-live in seconds (default 10 minutes).
        """
        key = f"{DOC_FIELDS_PREFIX}:{document_id}"
        await self._cache.set(key, fields, ttl=ttl)
        logger.debug("Cached document fields for doc=%s ttl=%ds", document_id, ttl)

    async def get_document_fields(self, document_id: str) -> list[dict[str, Any]] | None:
        """Retrieve cached document fields.

        Args:
            document_id: Document UUID string.

        Returns:
            List of field dicts, or ``None`` on cache miss.
        """
        key = f"{DOC_FIELDS_PREFIX}:{document_id}"
        return await self._cache.get(key)

    async def invalidate_document(self, document_id: str) -> None:
        """Invalidate all cached data for a given document.

        Removes the document-fields cache entry. Search-result cache entries
        are not individually tracked per document, so callers should also
        invalidate search caches separately if needed.

        Args:
            document_id: Document UUID string.
        """
        key = f"{DOC_FIELDS_PREFIX}:{document_id}"
        await self._cache.delete(key)
        logger.debug("Invalidated cache for document=%s", document_id)
