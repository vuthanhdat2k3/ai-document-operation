"""Q&A service: orchestrates the full RAG pipeline for document Q&A."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.answer_generator import Answer, AnswerGenerator
from app.rag.context_compiler import Citation, ContextCompiler, ContextPack
from app.rag.groundedness import GroundednessResult, GroundednessValidator
from app.rag.query_rewrite import QueryRewriter
from app.rag.query_understanding import QueryAnalyzer, QueryAnalysis, QueryIntent
from app.rag.reranker import Reranker
from app.rag.retriever import HybridRetriever, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class QAResult:
    """Result of a Q&A request.

    Attributes:
        answer: The generated answer text.
        citations: Citations referenced in the answer.
        groundedness_score: Score between 0.0 and 1.0 indicating groundedness.
        session_id: Session identifier for conversation history.
        query_analysis: Analysis of the original query.
        confidence: Answer confidence from the generator.
    """

    answer: str
    citations: list[Citation] = field(default_factory=list)
    groundedness_score: float = 0.0
    session_id: str = ""
    query_analysis: QueryAnalysis | None = None
    confidence: float = 0.0


class QAServiceError(Exception):
    """Raised when the Q&A pipeline fails."""


class QAService:
    """Full RAG Q&A pipeline orchestrator.

    Pipeline stages:
        1. Query understanding (intent, entities, language, complexity)
        2. Query rewriting (HyDE + expansion)
        3. Hybrid retrieval (dense + sparse)
        4. Reranking (cross-encoder)
        5. Context compilation (token budgeting + citation formatting)
        6. Answer generation (LLM with grounding prompt)
        7. Groundedness validation (claim extraction + evidence matching)

    Args:
        retriever: Hybrid retriever instance.
        reranker: Cross-encoder reranker instance.
        llm_provider: LLM provider for HyDE and answer generation.
    """

    def __init__(
        self,
        retriever: HybridRetriever,
        reranker: Reranker | None = None,
        llm_provider: Any | None = None,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker or Reranker()
        self._llm = llm_provider

        self._analyzer = QueryAnalyzer()
        self._rewriter = QueryRewriter(llm_provider=llm_provider)
        self._compiler = ContextCompiler()
        self._generator = AnswerGenerator(llm_provider=llm_provider)
        self._validator = GroundednessValidator()

    async def ask(
        self,
        document_id: str,
        query: str,
        db: AsyncSession,
        session_id: str | None = None,
        conversation_history: list[dict] | None = None,
        user_id: str | None = None,
    ) -> QAResult:
        """Execute the full Q&A pipeline for a question about a document.

        Args:
            document_id: UUID string of the target document.
            query: User's natural language question.
            db: Async database session.
            session_id: Optional session ID for conversation continuity.
            conversation_history: Previous messages for context.
            user_id: UUID of the requesting user (for per-user isolation).

        Returns:
            A ``QAResult`` with the answer, citations, and metadata.

        Raises:
            QAServiceError: If the pipeline fails at any critical stage.
        """
        session_id = session_id or str(uuid.uuid4())
        history = conversation_history or []

        # Stage 1: Query understanding
        analysis = self._analyzer.analyze(query)
        logger.info(
            "QA pipeline — session=%s, intent=%s, complexity=%s, lang=%s",
            session_id,
            analysis.intent,
            analysis.complexity,
            analysis.language,
        )

        # ── Router: general chat (no RAG) ──────────────────────────────
        if analysis.intent == QueryIntent.GENERAL_CHAT:
            logger.info("General chat detected — skipping RAG pipeline")
            answer = await self._generator.generate_chat(
                query, conversation_history=history
            )
            return QAResult(
                answer=answer.text,
                citations=[],
                groundedness_score=1.0,
                session_id=session_id,
                query_analysis=analysis,
                confidence=answer.confidence,
            )

        # ── Full RAG pipeline ───────────────────────────────────────────

        # Stage 2: Query rewriting
        retrieval_query = query
        queries_to_search: list[str] = [query]

        if analysis.complexity in ("moderate", "complex"):
            try:
                hyde_query = await self._rewriter.hyde_rewrite(query)
                if hyde_query and hyde_query != query:
                    queries_to_search.append(hyde_query)
            except Exception:
                logger.warning("HyDE rewrite failed", exc_info=True)

        expansions = self._rewriter.expand_query(query)
        queries_to_search.extend(expansions)

        # Stage 3: Hybrid retrieval
        all_results: list[SearchResult] = []
        seen_ids: set[str] = set()
        filters: dict = {}
        if document_id:
            filters["document_id"] = document_id
        if user_id:
            filters["user_id"] = user_id

        for q in queries_to_search:
            try:
                results = await self._retriever.search(q, top_k=10, filters=filters)
                for r in results:
                    if r.chunk_id not in seen_ids:
                        seen_ids.add(r.chunk_id)
                        all_results.append(r)
            except Exception:
                logger.warning("Retrieval failed for query: %s", q[:80], exc_info=True)

        if not all_results:
            logger.warning("No results retrieved for document %s", document_id or "ALL")
            return QAResult(
                answer="No relevant information found in the document for your question.",
                citations=[],
                groundedness_score=0.0,
                session_id=session_id,
                query_analysis=analysis,
                confidence=0.0,
            )

        # Stage 4: Reranking
        if len(all_results) > 5:
            try:
                doc_texts = [r.text for r in all_results]
                reranked_indices = self._reranker.rerank(query, doc_texts, top_k=8)
                all_results = [all_results[idx] for idx, _ in reranked_indices]
            except Exception:
                logger.warning("Reranking failed, using original order", exc_info=True)
                all_results = all_results[:8]

        # Stage 5: Context compilation
        context = self._compiler.compile(query, all_results)

        # Stage 6: Answer generation (with conversation memory)
        answer = await self._generator.generate(
            query, context, conversation_history=history
        )

        # Stage 7: Groundedness validation
        source_texts = [c.text_excerpt for c in context.citations if c.text_excerpt]
        groundedness = self._validator.validate(answer.text, source_texts)

        # Flag hallucination
        if groundedness.score < 0.5:
            logger.warning(
                "Low groundedness (score=%.3f) detected for session=%s",
                groundedness.score,
                session_id,
            )

        logger.info(
            "QA pipeline complete — session=%s, citations=%d, groundedness=%.3f, confidence=%.3f",
            session_id,
            len(answer.citations),
            groundedness.score,
            answer.confidence,
        )

        return QAResult(
            answer=answer.text,
            citations=answer.citations,
            groundedness_score=groundedness.score,
            session_id=session_id,
            query_analysis=analysis,
            confidence=answer.confidence,
        )
