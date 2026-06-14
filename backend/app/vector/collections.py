"""Collection management helpers for Qdrant vector database."""

from __future__ import annotations

import logging

from app.vector.client import QdrantClientWrapper

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "document_chunks"
DENSE_VECTOR_NAME = "dense"
DENSE_VECTOR_SIZE = 1024
SPARSE_VECTOR_NAME = "sparse"


async def create_document_collection(
    client: QdrantClientWrapper,
    collection_name: str = DEFAULT_COLLECTION,
    dense_vector_size: int = DENSE_VECTOR_SIZE,
) -> dict:
    """Create the primary document-chunk collection with dense + sparse vectors.

    The collection stores parsed document chunks for hybrid retrieval:
      - ``dense`` — a 1024-dimensional float vector (e.g. BGE-M3 embeddings).
      - ``sparse`` — a sparse vector for keyword/BM25-style retrieval.

    Payload schema expected on each point:
      ``document_id`` (uuid), ``page`` (int), ``chunk_index`` (int),
      ``text`` (str), ``metadata`` (dict).

    Args:
        client: An initialised QdrantClientWrapper.
        collection_name: Name of the collection to create.
        dense_vector_size: Dimensionality of the dense embedding vector.

    Returns:
        Qdrant JSON response confirming collection creation.
    """
    vectors_config = {
        DENSE_VECTOR_NAME: {
            "size": dense_vector_size,
            "distance": "Cosine",
        },
    }

    sparse_vectors_config = {
        SPARSE_VECTOR_NAME: {
            "index": {
                "on_disk": False,
            },
        },
    }

    logger.info(
        "Creating collection %s (dense=%d, sparse=%s)",
        collection_name,
        dense_vector_size,
        SPARSE_VECTOR_NAME,
    )

    return await client.create_collection(
        name=collection_name,
        vectors_config=vectors_config,
        sparse_vectors_config=sparse_vectors_config,
    )


async def ensure_document_collection(
    client: QdrantClientWrapper,
    collection_name: str = DEFAULT_COLLECTION,
    dense_vector_size: int = DENSE_VECTOR_SIZE,
) -> None:
    """Create the document collection if it does not already exist.

    Args:
        client: An initialised QdrantClientWrapper.
        collection_name: Name of the collection.
        dense_vector_size: Dimensionality of the dense embedding vector.
    """
    if await client.collection_exists(collection_name):
        logger.info("Collection %s already exists, skipping creation", collection_name)
        return

    await create_document_collection(client, collection_name, dense_vector_size)
    logger.info("Collection %s created successfully", collection_name)
