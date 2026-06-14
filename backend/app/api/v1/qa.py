"""Q&A API endpoints with session management."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.qa import (
    CitationResponse,
    QARequest,
    QAResponse,
)
from app.db.session import get_db
from app.deps import get_qdrant, get_redis
from app.rag.embedder import EmbeddingPipeline
from app.rag.reranker import Reranker
from app.rag.retriever import HybridRetriever
from app.services.chat_service import ChatSessionService
from app.services.qa_service import QAService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["qa"])

CURRENT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

CACHE_TTL = 300  # 5 minutes


async def _get_qa_service(
    qdrant_client=Depends(get_qdrant),  # noqa: B008
) -> QAService:
    """Build a QAService with all pipeline components."""
    from app.llm.factory import get_llm_provider
    from app.config import get_settings

    settings = get_settings()
    llm_provider = get_llm_provider(settings)

    embedder = EmbeddingPipeline()
    retriever = HybridRetriever(qdrant_client=qdrant_client, embedder=embedder)
    reranker = Reranker()
    return QAService(retriever=retriever, reranker=reranker, llm_provider=llm_provider)


def _to_citation_response(citations: list) -> list[CitationResponse]:
    return [
        CitationResponse(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            page=c.page,
            text=c.text_excerpt,
            score=c.relevance_score,
        )
        for c in citations
    ]


def _cache_key(query: str, document_id: str | None) -> str:
    raw = f"{query}:{document_id or 'all'}"
    return f"qa_cache:{hashlib.md5(raw.encode()).hexdigest()}"


@router.post("/ask", response_model=QAResponse)
async def ask_question(
    body: QARequest,
    qa_service: QAService = Depends(_get_qa_service),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    redis_client: aioredis.Redis = Depends(get_redis),  # noqa: B008
) -> QAResponse:
    """Ask a question with session support, history, and caching."""
    chat_service = ChatSessionService()
    document_id = body.document_id or None
    session_id = body.session_id

    # 1. Get or create session
    if session_id:
        try:
            session_uuid = uuid.UUID(session_id)
            session = await chat_service.get_session(session_uuid, CURRENT_USER_ID, db)
        except (ValueError, Exception):
            session = await chat_service.create_session(
                user_id=CURRENT_USER_ID, db=db, document_id=uuid.UUID(document_id) if document_id else None,
            )
    else:
        session = await chat_service.create_session(
            user_id=CURRENT_USER_ID, db=db, document_id=uuid.UUID(document_id) if document_id else None,
        )
    session_uuid = session.id

    # 2. Save user message
    await chat_service.add_message(
        session_id=session_uuid, role="user", content=body.query, db=db,
    )

    # 3. Auto-generate title from first message
    if session.message_count <= 1:
        title = await chat_service.generate_title(body.query)
        await chat_service.update_session_title(session_uuid, title, db)

    # 4. Check Redis cache
    cache_k = _cache_key(body.query, document_id)
    try:
        cached = await redis_client.get(cache_k)
        if cached:
            data = json.loads(cached)
            logger.info("Cache hit for query: %s", body.query[:50])
            # Save assistant message from cache
            await chat_service.add_message(
                session_id=session_uuid, role="assistant", content=data["answer"],
                db=db, citations=data.get("citations"), token_count=0,
            )
            await db.commit()
            return QAResponse(
                answer=data["answer"],
                citations=[CitationResponse(**c) for c in data.get("citations", [])],
                groundedness_score=data.get("groundedness_score", 0.0),
                session_id=str(session_uuid),
            )
    except Exception:
        logger.debug("Cache miss or error")

    # 5. Get conversation history for memory
    history = await chat_service.get_context_messages(session_uuid, db, max_messages=10)

    # 6. Run QA pipeline
    try:
        result = await qa_service.ask(
            document_id=document_id,
            query=body.query,
            db=db,
            session_id=str(session_uuid),
            conversation_history=history,
        )
    except Exception as exc:
        logger.error("QA pipeline failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Q&A pipeline failed.") from exc

    # 7. Save assistant message
    await chat_service.add_message(
        session_id=session_uuid,
        role="assistant",
        content=result.answer,
        db=db,
        citations=[c.__dict__ for c in result.citations],
        token_count=0,
        groundedness_score=result.groundedness_score,
    )
    await db.commit()

    # 8. Cache result
    try:
        cache_data = {
            "answer": result.answer,
            "citations": [
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "page": c.page,
                    "text": c.text_excerpt,
                    "score": c.relevance_score,
                }
                for c in result.citations
            ],
            "groundedness_score": result.groundedness_score,
        }
        await redis_client.setex(cache_k, CACHE_TTL, json.dumps(cache_data, ensure_ascii=False))
    except Exception:
        logger.debug("Cache write failed")

    # 9. Return response
    return QAResponse(
        answer=result.answer,
        citations=_to_citation_response(result.citations),
        groundedness_score=result.groundedness_score,
        session_id=str(session_uuid),
    )
