"""Chat session API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.error_handler import NotFoundError, ValidationErrorDetail
from app.db.session import get_db
from app.services.chat_service import ChatSessionService

router = APIRouter(prefix="/chat", tags=["chat"])

CURRENT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _get_service() -> ChatSessionService:
    return ChatSessionService()


@router.post("/sessions", status_code=201)
async def create_session(
    body: dict | None = None,
    service: ChatSessionService = Depends(_get_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """Create a new chat session."""
    user_id = CURRENT_USER_ID
    title = (body or {}).get("title", "New Chat")
    document_id = (body or {}).get("document_id")

    session = await service.create_session(
        user_id=user_id,
        title=title,
        document_id=uuid.UUID(document_id) if document_id else None,
        db=db,
    )
    await db.commit()
    return {
        "id": str(session.id),
        "title": session.title,
        "document_id": str(session.document_id) if session.document_id else None,
        "message_count": 0,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


@router.get("/sessions")
async def list_sessions(
    service: ChatSessionService = Depends(_get_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """List all chat sessions for the current user."""
    user_id = CURRENT_USER_ID
    sessions, total = await service.list_sessions(user_id, db)
    return {
        "items": [
            {
                "id": str(s.id),
                "title": s.title,
                "document_id": str(s.document_id) if s.document_id else None,
                "message_count": s.message_count,
                "total_tokens": s.total_tokens,
                "last_message_at": s.last_message_at.isoformat() if s.last_message_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions
        ],
        "total": total,
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    service: ChatSessionService = Depends(_get_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """Get a session with full message history."""
    user_id = CURRENT_USER_ID
    try:
        session = await service.get_session(session_id, user_id, db)
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc

    messages = await service.get_history(session_id, db)
    return {
        "id": str(session.id),
        "title": session.title,
        "document_id": str(session.document_id) if session.document_id else None,
        "message_count": session.message_count,
        "total_tokens": session.total_tokens,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "citations": m.citations,
                "token_count": m.token_count,
                "groundedness_score": m.groundedness_score,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    service: ChatSessionService = Depends(_get_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> None:
    """Delete a chat session and all its messages."""
    user_id = CURRENT_USER_ID
    try:
        await service.delete_session(session_id, user_id, db)
        await db.commit()
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc
