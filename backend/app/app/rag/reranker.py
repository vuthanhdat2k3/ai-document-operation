"""Cross-encoder reranker with a safe fallback when sentence-transformers is unavailable."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import CrossEncoder

    _HAS_CROSS_ENCODER = True
except ImportError:
    _HAS_CROSS_ENCODER = False
    logger.warning(
        "sentence-transformers is not installed. Reranker will use a "
        "deterministic fallback. Install with: pip install sentence-transformers"
    )


class _FallbackCrossEncoder:
    """Deterministic hash-based scorer used when sentence-transformers is unavailable."""

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        import hashlib
        import struct

        scores: list[float] = []
        for query, doc in pairs:
            combined = f"{query}|||{doc}".encode("utf-8")
            digest = hashlib.sha256(combined).digest()
            raw = struct.unpack("f", digest[:4])[0]
            scores.append(max(0.0, min(1.0, abs(raw) / 10.0)))
        return scores


class Reranker:
    """Cross-encoder reranker for re-scoring query-document pairs.

    Uses ``BAAI/bge-reranker-v2-m3`` by default. Falls back to a deterministic
    hash-based scorer when ``sentence-transformers`` is not installed.

    Args:
        model_name: HuggingFace model identifier for the cross-encoder.
        device: Torch device string.
        batch_size: Number of pairs per prediction batch.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        device: str = "cpu",
        batch_size: int = 32,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model: CrossEncoder | _FallbackCrossEncoder | None = None

    def _get_model(self) -> CrossEncoder | _FallbackCrossEncoder:
        if self._model is None:
            if _HAS_CROSS_ENCODER:
                logger.info("Loading reranker model %s on %s", self.model_name, self.device)
                self._model = CrossEncoder(self.model_name, device=self.device)
            else:
                self._model = _FallbackCrossEncoder()
        return self._model

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """Rerank *documents* against *query* and return the top results.

        Args:
            query: The search query.
            documents: Candidate document texts to rerank.
            top_k: Number of top results to return.

        Returns:
            List of ``(index, score)`` tuples sorted by score descending.
            *index* is the position of the document in the original
            *documents* list.
        """
        if not documents:
            return []

        model = self._get_model()
        pairs = [(query, doc) for doc in documents]

        scores: list[float] = []
        for start in range(0, len(pairs), self.batch_size):
            batch = pairs[start : start + self.batch_size]
            batch_scores = model.predict(batch)
            scores.extend(batch_scores)

        indexed = list(enumerate(scores))
        indexed.sort(key=lambda x: x[1], reverse=True)
        return indexed[:top_k]
