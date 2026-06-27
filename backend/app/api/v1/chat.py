"""Chat session API endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware.error_handler import NotFoundError, ValidationErrorDetail
from app.api.schemas.qa import CitationResponse, DebugStep, QAResponse
from app.auth.dependencies import get_current_user_id
from app.db.session import get_db
from app.services.chat_service import ChatSessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageRequest(BaseModel):
    """Request body for sending a chat message."""

    query: str = Field(..., min_length=1, max_length=2000, description="The message to send.")
    session_id: str | None = Field(None, description="Existing session UUID for conversation continuity.")
    document_id: str | None = Field(None, description="Optional document UUID to scope the search.")


def _get_service() -> ChatSessionService:
    return ChatSessionService()


@router.post("/sessions", status_code=201)
async def create_session(
    body: dict | None = None,
    service: ChatSessionService = Depends(_get_service),  # noqa: B008
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """Create a new chat session."""
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
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """List all chat sessions for the current user."""
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
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """Get a session with full message history."""
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
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> None:
    """Delete a chat session and all its messages."""
    try:
        await service.delete_session(session_id, user_id, db)
        await db.commit()
    except ValueError as exc:
        raise NotFoundError(str(exc)) from exc


@router.post("/messages", response_model=QAResponse)
async def send_message(
    body: ChatMessageRequest,
    service: ChatSessionService = Depends(_get_service),  # noqa: B008
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> QAResponse:
    """Send a message and get an agent-driven response.

    Routes the message through the ``doc-qa`` agent, which decides
    whether to call the ``rag_query`` tool or answer directly.
    """
    from app.services.agent_service import AgentService

    agent_service = AgentService()
    doc_uuid = uuid.UUID(body.document_id) if body.document_id else None

    if body.session_id:
        try:
            session = await service.get_session(uuid.UUID(body.session_id), user_id, db)
        except (ValueError, Exception):
            session = await service.create_session(user_id=user_id, db=db, document_id=doc_uuid)
    else:
        session = await service.create_session(user_id=user_id, db=db, document_id=doc_uuid)
    session_uuid = session.id

    await service.add_message(
        session_id=session_uuid, role="user", content=body.query, db=db,
    )

    if session.message_count <= 1:
        title = await service.generate_title(body.query)
        await service.update_session_title(session_uuid, title, db)

    history = await service.get_context_messages(session_uuid, db, max_messages=10)

    try:
        agent_result = await agent_service.run_agent(
            agent_name="doc-qa",
            input_data={
                "query": body.query,
                "messages": history,
                "context": {"document_id": str(doc_uuid)} if doc_uuid else {},
            },
            db=db,
            user_id=user_id,
            document_id=doc_uuid,
        )
    except Exception as exc:
        await db.rollback()
        logger.error("doc-qa agent failed: %s", exc)
        raise HTTPException(status_code=500, detail="Agent processing failed.") from exc

    answer = agent_result.answer

    citations_data: list[dict] = []
    groundedness_score = 0.0
    try:
        for step in agent_result.steps:
            if isinstance(step, dict):
                output_summary = step.get("output_summary", "")
                if "rag_query" in str(step.get("input_data", {})):
                    import json as _json
                    try:
                        tool_output = _json.loads(
                            output_summary.replace("output=", "")
                        )
                        citations_data = tool_output.get("citations", [])
                        groundedness_score = tool_output.get("groundedness_score", 0.0)
                    except (_json.JSONDecodeError, AttributeError):
                        pass
    except Exception:
        logger.debug("Could not extract citations from agent steps")

    # Build debug steps from agent execution trace
    debug_steps: list[DebugStep] = []
    try:
        for step in agent_result.steps:
            if isinstance(step, dict):
                debug_steps.append(
                    DebugStep(
                        step_type=step.get("step_type", "unknown"),
                        iteration=step.get("iteration", 0),
                        input_summary=step.get("input_summary", ""),
                        output_summary=step.get("output_summary", ""),
                        duration_ms=step.get("duration_ms", 0),
                    )
                )
    except Exception:
        logger.debug("Could not extract debug steps from agent result")

    await service.add_message(
        session_id=session_uuid,
        role="assistant",
        content=answer,
        db=db,
        citations=citations_data or None,
        token_count=0,
        groundedness_score=groundedness_score,
    )
    await db.commit()

    return QAResponse(
        answer=answer,
        citations=[CitationResponse(**c) for c in citations_data] if citations_data else [],
        groundedness_score=groundedness_score,
        session_id=str(session_uuid),
        debug_steps=debug_steps,
    )
