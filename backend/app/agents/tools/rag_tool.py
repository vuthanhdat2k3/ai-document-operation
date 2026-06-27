"""rag_query tool — full RAG pipeline as a single agent-callable tool.

The agent decides whether to invoke this tool based on the user query.
If the query needs document context, the agent calls ``rag_query`` which
runs: hybrid retrieval → reranking → context compilation → answer generation
→ groundedness validation — all in one atomic tool call.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.agents.tools.registry import ToolRegistry, get_registry

logger = logging.getLogger(__name__)


class RagQueryInput(BaseModel):
    """Input schema for the rag_query tool."""

    query: str = Field(
        ..., min_length=1, max_length=2000,
        description="The question to answer using the document corpus.",
    )
    document_id: str | None = Field(
        None,
        description="Optional document UUID to scope the search. If omitted, searches across all accessible documents.",
    )
    top_k: int = Field(
        10, ge=1, le=50,
        description="Maximum number of document chunks to retrieve.",
    )


def register_rag_tool(registry: ToolRegistry) -> None:
    """Register a stub rag_query tool (returns empty result).

    The real tool is created by ``create_rag_tool`` which binds live
    dependencies (retriever, reranker, LLM).  The stub prevents crashes
    when the tool is invoked without a bound pipeline.
    """
    @registry.register(
        name="rag_query",
        description=(
            "Answer a question using the document corpus. "
            "Performs hybrid search (dense + sparse), reranks results, "
            "generates a grounded answer with citations, and validates "
            "groundedness. Use this tool when the user asks a question "
            "that requires information from uploaded documents."
        ),
        input_schema=RagQueryInput,
        output_example={
            "answer": "The contract expires on 2025-12-31.",
            "citations": [
                {
                    "chunk_id": "abc123",
                    "document_id": "doc-uuid",
                    "page": 3,
                    "text_excerpt": "This agreement shall expire on December 31, 2025.",
                    "relevance_score": 0.92,
                }
            ],
            "groundedness_score": 0.95,
            "confidence": 0.9,
        },
    )
    async def _rag_query_stub(
        query: str,
        document_id: str | None = None,
        top_k: int = 10,
    ) -> dict[str, Any]:
        """Stub: returns empty result. Use create_rag_tool() for real usage."""
        logger.warning("rag_query called without a bound pipeline; returning empty result")
        return {
            "answer": "",
            "citations": [],
            "groundedness_score": 0.0,
            "confidence": 0.0,
        }


def create_rag_tool(
    retriever: Any,
    reranker: Any | None = None,
    llm_provider: Any | None = None,
) -> Any:
    """Create an async rag_query function bound to live pipeline components.

    Args:
        retriever: A ``HybridRetriever`` instance.
        reranker: A ``Reranker`` instance (optional).
        llm_provider: An ``LLMProvider`` instance.

    Returns:
        An async callable with the same signature as ``rag_query``.
    """
    from app.rag.answer_generator import AnswerGenerator
    from app.rag.context_compiler import ContextCompiler
    from app.rag.groundedness import GroundednessValidator
    from app.rag.query_rewrite import QueryRewriter

    compiler = ContextCompiler()
    rewriter = QueryRewriter(llm_provider=llm_provider) if llm_provider else None
    generator = AnswerGenerator(llm_provider=llm_provider) if llm_provider else None
    validator = GroundednessValidator()

    async def rag_query(
        query: str,
        document_id: str | None = None,
        top_k: int = 10,
    ) -> dict[str, Any]:
        """Execute the full RAG pipeline and return a grounded answer.

        Args:
            query: The user's question.
            document_id: Optional document UUID to scope the search.
            top_k: Maximum number of chunks to retrieve.

        Returns:
            Dict with keys: answer, citations[], groundedness_score, confidence.
        """
        from app.rag.retriever import SearchResult

        filters: dict = {}
        if document_id:
            filters["document_id"] = document_id

        # 1. Hybrid retrieval
        all_results: list[SearchResult] = []
        queries_to_search: list[str] = [query]

        # Try HyDE rewrite for complex queries
        if rewriter:
            try:
                hyde = await rewriter.hyde_rewrite(query)
                if hyde and hyde != query:
                    queries_to_search.append(hyde)
            except Exception:
                logger.debug("HyDE rewrite failed, skipping")

        seen_ids: set[str] = set()
        for q in queries_to_search:
            try:
                results = await retriever.search(q, top_k=top_k, filters=filters)
                for r in results:
                    if r.chunk_id not in seen_ids:
                        seen_ids.add(r.chunk_id)
                        all_results.append(r)
            except Exception:
                logger.warning("Retrieval failed for query: %s", q[:80], exc_info=True)

        if not all_results:
            logger.info("rag_query: no results found for query=%r", query[:80])
            return {
                "answer": "",
                "citations": [],
                "groundedness_score": 0.0,
                "confidence": 0.0,
            }

        # 2. Rerank if we have enough results
        if reranker and len(all_results) > 5:
            try:
                doc_texts = [r.text for r in all_results]
                reranked = reranker.rerank(query, doc_texts, top_k=8)
                all_results = [all_results[idx] for idx, _ in reranked]
            except Exception:
                logger.debug("Reranking failed, using original order")
                all_results = all_results[:8]
        else:
            all_results = all_results[:8]

        # 3. Compile context
        from app.rag.context_compiler import Citation as ContextCitation

        context = compiler.compile(query, all_results)

        # 4. Generate answer
        if generator:
            answer = await generator.generate(query, context)
            answer_text = answer.text
            citations = answer.citations
            confidence = answer.confidence
        else:
            # Fallback: return raw chunks as answer
            answer_text = "No LLM provider available.\n\n"
            answer_text += "\n\n".join(
                f"[{i}] (doc={r.document_id}, score={r.score:.3f}): {r.text[:500]}"
                for i, r in enumerate(all_results, 1)
            )
            citations = [
                ContextCitation(
                    chunk_id=r.chunk_id,
                    document_id=r.document_id,
                    page=r.page,
                    text_excerpt=r.text[:300],
                    relevance_score=r.score,
                )
                for r in all_results
            ]
            confidence = 0.0

        # 5. Groundedness validation
        source_texts = [c.text_excerpt for c in context.citations if c.text_excerpt]
        groundedness = validator.validate(answer_text, source_texts)

        if groundedness.score < 0.5:
            logger.warning(
                "rag_query: low groundedness (score=%.3f) for query=%r",
                groundedness.score, query[:80],
            )

        return {
            "answer": answer_text,
            "citations": [
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "page": c.page,
                    "text_excerpt": c.text_excerpt,
                    "relevance_score": c.relevance_score,
                }
                for c in citations
            ],
            "groundedness_score": groundedness.score,
            "confidence": confidence,
        }

    return rag_query
