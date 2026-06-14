"""Reciprocal Rank Fusion (RRF) for merging ranked result lists."""

from __future__ import annotations

from collections import defaultdict

from app.rag.retriever import SearchResult


def rrf_fusion(
    results: list[list[SearchResult]],
    k: int = 60,
) -> list[SearchResult]:
    """Merge multiple ranked ``SearchResult`` lists using Reciprocal Rank Fusion.

    RRF score for a document *d* across all ranked lists::

        score(d) = Σ  1 / (k + rank_i(d))

    where ``rank_i(d)`` is the 1-based rank of *d* in the *i*-th list and *k*
    is a smoothing constant (default 60, per Cormack et al. 2009).

    When the same ``chunk_id`` appears in multiple lists, the resulting
    ``SearchResult`` keeps the payload from the **first** list it was seen in,
    but the ``score`` field is replaced with the computed RRF score.

    Args:
        results: Each element is a ranked list of ``SearchResult``.
        k: Smoothing constant. Higher values flatten the contribution of
           lower-ranked items.

    Returns:
        A single merged list sorted by RRF score descending.
    """
    if not results:
        return []

    rrf_scores: dict[str, float] = defaultdict(float)
    best: dict[str, SearchResult] = {}

    for ranked_list in results:
        for rank, item in enumerate(ranked_list, start=1):
            rrf_scores[item.chunk_id] += 1.0 / (k + rank)
            if item.chunk_id not in best:
                best[item.chunk_id] = item

    merged: list[SearchResult] = []
    for chunk_id, score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
        original = best[chunk_id]
        merged.append(
            SearchResult(
                chunk_id=original.chunk_id,
                document_id=original.document_id,
                text=original.text,
                score=score,
                page=original.page,
                metadata=original.metadata,
            )
        )

    return merged
