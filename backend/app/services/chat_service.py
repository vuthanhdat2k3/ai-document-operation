"""Chat session service: manage sessions, history, and conversation memory."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat import ChatMessage, ChatSession

logger = logging.getLogger(__name__)


class ChatSessionService:
    """Manage chat sessions and message history.

    Provides:
    - Session CRUD (create, list, get, update, delete)
    - Message persistence
    - Conversation memory (last N messages for LLM context)
    - Session title auto-generation
    """

    async def create_session(
        self,
        user_id: uuid.UUID,
        title: str = "New Chat",
        document_id: uuid.UUID | None = None,
        db: AsyncSession = None,
    ) -> ChatSession:
        session = ChatSession(
            user_id=user_id,
            title=title,
            document_id=document_id,
            status="active",
            message_count=0,
            total_tokens=0,
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        logger.info("Chat session created: %s", session.id)
        return session

    async def get_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> ChatSession:
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        return session

    async def list_sessions(
        self,
        user_id: uuid.UUID,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ChatSession], int]:
        count_stmt = select(func.count()).select_from(ChatSession).where(
            ChatSession.user_id == user_id,
        )
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.last_message_at.desc().nullslast(), ChatSession.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        sessions = list(result.scalars().all())
        return sessions, total

    async def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        db: AsyncSession,
        citations: list | None = None,
        token_count: int = 0,
        model: str | None = None,
        groundedness_score: float | None = None,
        metadata: dict | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            citations=citations,
            token_count=token_count,
            model=model,
            groundedness_score=groundedness_score,
            metadata=metadata or {},
        )
        db.add(message)

        await db.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(
                message_count=ChatSession.message_count + 1,
                total_tokens=ChatSession.total_tokens + token_count,
                last_message_at=datetime.now(UTC),
            )
        )
        await db.flush()
        return message

    async def get_history(
        self,
        session_id: uuid.UUID,
        db: AsyncSession,
        limit: int = 20,
    ) -> list[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_context_messages(
        self,
        session_id: uuid.UUID,
        db: AsyncSession,
        max_messages: int = 10,
    ) -> list[dict]:
        """Get recent messages formatted for LLM context.

        Returns list of {"role": ..., "content": ...} dicts.
        """
        messages = await self.get_history(session_id, db, limit=max_messages)
        return [{"role": m.role, "content": m.content} for m in messages]

    async def update_session_title(
        self,
        session_id: uuid.UUID,
        title: str,
        db: AsyncSession,
    ) -> None:
        await db.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(title=title)
        )
        await db.flush()

    async def delete_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> None:
        session = await self.get_session(session_id, user_id, db)
        await db.delete(session)
        await db.flush()
        logger.info("Chat session deleted: %s", session_id)

    async def generate_title(self, first_message: str) -> str:
        """Auto-generate a session title from the first user message."""
        title = first_message[:60].strip()
        if len(first_message) > 60:
            title += "..."
        return title
