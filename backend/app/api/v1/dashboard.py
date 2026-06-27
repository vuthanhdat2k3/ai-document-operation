"""Dashboard statistics API endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.auth.dependencies import get_current_user_id
from app.db.models.chat import ChatSession
from app.db.models.document import Document
from app.db.models.document_page import DocumentPage
from app.db.models.risk import RiskItem
from app.db.session import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """Get dashboard statistics for the current user.

    Recent documents use load_only to fetch only the columns needed by the UI.
    """

    base_filter = (Document.deleted_at.is_(None), Document.user_id == user_id)

    async def _count_docs() -> int:
        result = await db.execute(
            select(func.count()).select_from(Document).where(*base_filter)
        )
        return result.scalar() or 0

    async def _docs_by_status() -> dict[str, int]:
        rows = (
            await db.execute(
                select(Document.status, func.count())
                .where(*base_filter)
                .group_by(Document.status)
            )
        ).all()
        return {row[0]: row[1] for row in rows}

    async def _count_pages() -> int:
        result = await db.execute(
            select(func.count())
            .select_from(DocumentPage)
            .join(Document, Document.id == DocumentPage.document_id)
            .where(Document.user_id == user_id)
        )
        return result.scalar() or 0

    async def _count_sessions() -> int:
        result = await db.execute(
            select(func.count())
            .select_from(ChatSession)
            .where(ChatSession.user_id == user_id)
        )
        return result.scalar() or 0

    async def _count_risks() -> int:
        result = await db.execute(
            select(func.count())
            .select_from(RiskItem)
            .join(Document, Document.id == RiskItem.document_id)
            .where(Document.user_id == user_id)
        )
        return result.scalar() or 0

    async def _recent_docs() -> list[dict]:
        rows = (
            await db.execute(
                select(Document)
                .options(
                    load_only(
                        Document.id,
                        Document.filename,
                        Document.mime_type,
                        Document.file_size_bytes,
                        Document.status,
                        Document.created_at,
                    )
                )
                .where(*base_filter)
                .order_by(Document.created_at.desc())
                .limit(5)
            )
        ).scalars().all()
        return [
            {
                "id": str(d.id),
                "filename": d.filename,
                "mime_type": d.mime_type,
                "file_size_bytes": d.file_size_bytes,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in rows
        ]

    doc_count = await _count_docs()
    docs_by_status = await _docs_by_status()
    page_count = await _count_pages()
    session_count = await _count_sessions()
    risk_count = await _count_risks()
    recent_docs = await _recent_docs()

    return {
        "total_documents": doc_count,
        "total_pages": page_count,
        "total_sessions": session_count,
        "total_risks": risk_count,
        "documents_by_status": docs_by_status,
        "recent_documents": recent_docs,
    }
