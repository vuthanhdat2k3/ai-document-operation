"""Dashboard statistics API endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
    """Get dashboard statistics for the current user."""

    # Total documents (not deleted)
    doc_count = (
        await db.execute(
            select(func.count())
            .select_from(Document)
            .where(Document.deleted_at.is_(None), Document.user_id == user_id)
        )
    ).scalar() or 0

    # Documents by status
    status_rows = (
        await db.execute(
            select(Document.status, func.count())
            .where(Document.deleted_at.is_(None), Document.user_id == user_id)
            .group_by(Document.status)
        )
    ).all()
    docs_by_status = {row[0]: row[1] for row in status_rows}

    # Total pages parsed (scoped to user's documents)
    page_count = (
        await db.execute(
            select(func.count())
            .select_from(DocumentPage)
            .join(Document, Document.id == DocumentPage.document_id)
            .where(Document.user_id == user_id)
        )
    ).scalar() or 0

    # Total chat sessions
    session_count = (
        await db.execute(
            select(func.count())
            .select_from(ChatSession)
            .where(ChatSession.user_id == user_id)
        )
    ).scalar() or 0

    # Total risk items (scoped to user's documents)
    risk_count = (
        await db.execute(
            select(func.count())
            .select_from(RiskItem)
            .join(Document, Document.id == RiskItem.document_id)
            .where(Document.user_id == user_id)
        )
    ).scalar() or 0

    # Recent documents
    recent_docs_result = (
        await db.execute(
            select(Document)
            .where(Document.deleted_at.is_(None), Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .limit(5)
        )
    ).scalars().all()

    recent_docs = [
        {
            "id": str(d.id),
            "filename": d.filename,
            "mime_type": d.mime_type,
            "file_size_bytes": d.file_size_bytes,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in recent_docs_result
    ]

    return {
        "total_documents": doc_count,
        "total_pages": page_count,
        "total_sessions": session_count,
        "total_risks": risk_count,
        "documents_by_status": docs_by_status,
        "recent_documents": recent_docs,
    }
