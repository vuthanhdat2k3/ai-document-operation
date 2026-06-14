"""Get document info tool for the agent registry."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.agents.tools.registry import get_registry

logger = logging.getLogger(__name__)

registry = get_registry()


class GetDocumentInfoInput(BaseModel):
    """Input schema for the get_document_info tool."""

    document_id: str = Field(..., description="UUID of the document to retrieve")


@registry.register(
    name="get_document_info",
    description=(
        "Retrieve metadata for a specific document including filename, "
        "MIME type, size, page count, status, upload date, and classification."
    ),
    input_schema=GetDocumentInfoInput,
    output_example={
        "document_id": "uuid-string",
        "filename": "contract.pdf",
        "mime_type": "application/pdf",
        "file_size_bytes": 1048576,
        "page_count": 12,
        "status": "completed",
        "document_type": "contract",
        "uploaded_at": "2024-01-15T10:30:00Z",
    },
)
def get_document_info(document_id: str) -> dict[str, Any]:
    """Retrieve document metadata by ID.

    This is the default (sync) stub. The agent service replaces it at
    runtime with a database-backed version via ``create_bound_document_tool``.

    Args:
        document_id: UUID string of the target document.

    Returns:
        Dict of document metadata fields.
    """
    logger.warning(
        "get_document_info called without a bound DB session; returning placeholder"
    )
    return {
        "document_id": document_id,
        "error": "No database session available. Use create_bound_document_tool().",
    }


def create_bound_document_tool(db_session_factory: Any) -> callable:
    """Create an async document info function bound to a DB session factory.

    Args:
        db_session_factory: Callable returning an async context manager
            that yields an ``AsyncSession``.

    Returns:
        An async callable that queries the database for document metadata.
    """

    async def bound_get_document_info(document_id: str) -> dict[str, Any]:
        from sqlalchemy import select

        from app.db.models.document import Document

        try:
            import uuid

            doc_uuid = uuid.UUID(document_id)
        except ValueError:
            return {"error": f"Invalid document_id format: {document_id}"}

        try:
            async with db_session_factory() as session:
                stmt = select(Document).where(
                    Document.id == doc_uuid,
                    Document.deleted_at.is_(None),
                )
                result = await session.execute(stmt)
                doc = result.scalar_one_or_none()

                if doc is None:
                    return {"error": f"Document {document_id} not found"}

                return {
                    "document_id": str(doc.id),
                    "filename": doc.original_filename,
                    "mime_type": doc.mime_type,
                    "file_size_bytes": doc.file_size_bytes,
                    "page_count": doc.page_count,
                    "status": doc.status,
                    "document_type": doc.document_type,
                    "classification": doc.classification,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                    "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
                }
        except Exception as e:
            logger.error("get_document_info failed for %s: %s", document_id, e)
            return {"error": str(e)}

    return bound_get_document_info
