"""Q&A API endpoints."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.qa import (
    CitationResponse,
    QARequest,
    QAResponse,
    QASessionResponse,
    QAHISTORYEntry,
)
from app.db.session import get_db
from app.deps import get_qdrant
from app.rag.embedder import EmbeddingPipeline
from app.rag.reranker import Reranker
from app.rag.retriever import HybridRetriever
from app.services.qa_service import QAService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["qa"])

_SESSION_STORE: dict[str, list[dict]] = {}


async def _get_qa_service(
    qdrant_client=Depends(get_qdrant),  # noqa: B008
) -> QAService:
    """Build a QAService with all pipeline components."""
    embedder = EmbeddingPipeline()
    retriever = HybridRetriever(qdrant_client=qdrant_client, embedder=embedder)
    reranker = Reranker()
    return QAService(retriever=retriever, reranker=reranker)


def _to_citation_response(citations: list) -> list[CitationResponse]:
    """Convert domain citations to API response models."""
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


@router.post("/ask", response_model=QAResponse)
async def ask_question(
    body: QARequest,
    qa_service: Annotated[QAService, Depends(_get_qa_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QAResponse:
    """Ask a question about a document or set of documents.

    The pipeline performs: query understanding → HyDE rewrite →
    hybrid retrieval → reranking → context compilation →
    answer generation → groundedness validation.
    """
    document_id = body.document_id or "00000000-0000-0000-0000-000000000000"

    try:
        result = await qa_service.ask(
            document_id=document_id,
            query=body.query,
            db=db,
            session_id=body.session_id,
        )
    except Exception as exc:
        logger.error("QA pipeline failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Q&A pipeline failed.") from exc

    session_id = result.session_id
    if session_id not in _SESSION_STORE:
        _SESSION_STORE[session_id] = []
    _SESSION_STORE[session_id].append(
        {
            "query": body.query,
            "answer": result.answer,
            "citations": result.citations,
            "groundedness_score": result.groundedness_score,
            "confidence": result.confidence,
        }
    )

    return QAResponse(
        answer=result.answer,
        citations=_to_citation_response(result.citations),
        groundedness_score=result.groundedness_score,
        session_id=session_id,
        confidence=result.confidence,
    )


@router.get("/sessions/{session_id}", response_model=QASessionResponse)
async def get_session(
    session_id: str,
) -> QASessionResponse:
    """Retrieve Q&A history for a session."""
    entries = _SESSION_STORE.get(session_id)
    if entries is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    history: list[QAHISTORYEntry] = []
    for entry in entries:
        history.append(
            QAHISTORYEntry(
                query=entry["query"],
                answer=entry["answer"],
                citations=_to_citation_response(entry["citations"]),
                groundedness_score=entry["groundedness_score"],
            )
        )

    return QASessionResponse(
        session_id=session_id,
        history=history,
        total=len(history),
    )
