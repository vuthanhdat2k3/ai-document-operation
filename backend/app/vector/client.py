"""Async Qdrant vector database client wrapper using httpx."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class QdrantClientWrapper:
    """Thin async wrapper around the Qdrant REST API.

    Uses ``httpx.AsyncClient`` for all communication so the caller never
    depends on the Qdrant Python SDK at runtime.

    Args:
        settings: Application settings containing QDRANT_URL and QDRANT_API_KEY.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(self, settings: Settings, timeout: float = 10.0) -> None:
        self._base_url = settings.QDRANT_URL.rstrip("/")
        self._api_key = settings.QDRANT_API_KEY
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["api-key"] = self._api_key
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers(),
                timeout=self._timeout,
            )
        return self._client

    async def health_check(self) -> bool:
        """Check Qdrant liveness via ``/healthz``.

        Returns:
            ``True`` if the service responds with HTTP 200.
        """
        try:
            client = await self._get_client()
            resp = await client.get("/healthz")
            return resp.status_code == 200
        except Exception:
            logger.exception("Qdrant health check failed")
            return False

    async def create_collection(
        self,
        name: str,
        vectors_config: dict[str, Any],
        sparse_vectors_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new collection.

        Args:
            name: Collection name.
            vectors_config: Dense vector parameters (size, distance).
            sparse_vectors_config: Optional sparse vector parameters.

        Returns:
            JSON response from Qdrant.
        """
        payload: dict[str, Any] = {"vectors": vectors_config}
        if sparse_vectors_config:
            payload["sparse_vectors"] = sparse_vectors_config

        client = await self._get_client()
        resp = await client.put(f"/collections/{name}", json=payload)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    async def delete_collection(self, name: str) -> dict[str, Any]:
        """Delete a collection by name.

        Args:
            name: Collection name to delete.

        Returns:
            JSON response from Qdrant.
        """
        client = await self._get_client()
        resp = await client.delete(f"/collections/{name}")
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    async def list_collections(self) -> list[str]:
        """List all collection names.

        Returns:
            List of collection name strings.
        """
        client = await self._get_client()
        resp = await client.get("/collections")
        resp.raise_for_status()
        data = resp.json()
        collections = data.get("result", {}).get("collections", [])
        return [c["name"] for c in collections]

    async def collection_exists(self, name: str) -> bool:
        """Check whether a collection exists.

        Args:
            name: Collection name.

        Returns:
            ``True`` if the collection exists.
        """
        client = await self._get_client()
        resp = await client.get(f"/collections/{name}")
        return resp.status_code == 200

    async def get_collection_info(self, name: str) -> dict[str, Any]:
        """Retrieve detailed information about a collection.

        Args:
            name: Collection name.

        Returns:
            JSON response containing collection metadata.
        """
        client = await self._get_client()
        resp = await client.get(f"/collections/{name}")
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    async def delete_points_by_filter(
        self,
        collection_name: str,
        filter_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Delete points from a collection by filter.

        Uses Qdrant's ``POST /collections/{name}/points/delete`` endpoint
        with a filter object.  Typical usage::

            await client.delete_points_by_filter(
                "document_chunks",
                {"must": [{"key": "document_id", "match": {"value": str(doc_id)}}]},
            )

        Args:
            collection_name: Name of the collection to delete from.
            filter_dict: Qdrant filter condition object (``must`` / ``should`` / …).

        Returns:
            JSON response from Qdrant.
        """
        client = await self._get_client()
        payload: dict[str, Any] = {"filter": filter_dict}
        resp = await client.post(
            f"/collections/{collection_name}/points/delete",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
