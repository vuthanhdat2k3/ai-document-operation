"""Embedding pipeline wrapping sentence-transformers with a safe fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer

    _HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    _HAS_SENTENCE_TRANSFORMERS = False
    logger.warning(
        "sentence-transformers is not installed. EmbeddingPipeline will use a "
        "deterministic fallback that produces non-semantic vectors. Install "
        "with: pip install sentence-transformers"
    )


@dataclass
class EmbeddingResult:
    """Container for embedding outputs.

    Attributes:
        dense: List of dense embedding vectors (one per input text).
        sparse: Optional list of sparse embedding dicts (indices → values).
    """

    dense: list[list[float]]
    sparse: list[dict] | None = None


class _FallbackEncoder:
    """Deterministic hash-based encoder used when sentence-transformers is unavailable.

    Produces 1024-dimensional vectors. These are NOT semantically meaningful
    and exist only so the pipeline can be tested without GPU/model downloads.
    """

    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim

    def encode(self, texts: list[str], batch_size: int = 32, **_: object) -> list[list[float]]:
        import hashlib
        import struct

        results: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha512(text.encode("utf-8")).digest()
            vec: list[float] = []
            for i in range(0, len(digest), 4):
                if len(vec) >= self._dim:
                    break
                chunk = digest[i : i + 4]
                if len(chunk) < 4:
                    chunk = chunk + b"\x00" * (4 - len(chunk))
                vec.append(struct.unpack("f", chunk)[0])
            while len(vec) < self._dim:
                vec.append(0.0)
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            results.append(vec[: self._dim])
        return results


class EmbeddingPipeline:
    """Generate dense (and optionally sparse) embeddings for text batches.

    Uses ``sentence-transformers`` with the ``BAAI/bge-m3`` model by default.
    Falls back to a deterministic hash-based encoder when the library is not
    installed.

    Args:
        model_name: HuggingFace model identifier.
        device: Torch device string (``"cpu"``, ``"cuda"``, ``"mps"``).
        batch_size: Number of texts per encoding batch.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: str = "cpu",
        batch_size: int = 32,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model: SentenceTransformer | _FallbackEncoder | None = None

    def _get_model(self) -> SentenceTransformer | _FallbackEncoder:
        if self._model is None:
            if _HAS_SENTENCE_TRANSFORMERS:
                logger.info("Loading embedding model %s on %s", self.model_name, self.device)
                self._model = SentenceTransformer(self.model_name, device=self.device)
            else:
                self._model = _FallbackEncoder()
        return self._model

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        """Embed a batch of texts.

        Args:
            texts: List of strings to embed.

        Returns:
            ``EmbeddingResult`` with dense vectors. Sparse vectors are
            ``None`` when using the fallback encoder.
        """
        if not texts:
            return EmbeddingResult(dense=[], sparse=None)

        model = self._get_model()
        dense: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors = model.encode(batch, batch_size=self.batch_size)
            dense.extend([list(v) for v in vectors])

        sparse = None
        if _HAS_SENTENCE_TRANSFORMERS and hasattr(model, "encode"):
            try:
                sparse = self._encode_sparse(texts)
            except Exception:
                logger.debug("Sparse encoding not available for this model", exc_info=True)

        return EmbeddingResult(dense=dense, sparse=sparse)

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string.

        Args:
            text: The query text.

        Returns:
            A single dense embedding vector.
        """
        result = self.embed_texts([text])
        return result.dense[0]

    def _encode_sparse(self, texts: list[str]) -> list[dict]:
        """Attempt to produce sparse lexical vectors via the model's tokenizer.

        BGE-M3 natively supports sparse output through its ``encode`` method
        with ``return_sparse=True``.  If that kwarg is not supported, we
        fall back to a simple term-frequency approach.
        """
        model = self._model
        if model is None:
            return []

        try:
            results = model.encode(texts, batch_size=self.batch_size, return_sparse=True)
            if isinstance(results, dict) and "sparse" in results:
                sparse_data = results["sparse"]
                out: list[dict] = []
                for vec in sparse_data:
                    if hasattr(vec, "indices") and hasattr(vec, "values"):
                        out.append(
                            {
                                "indices": vec.indices.tolist(),
                                "values": vec.values.tolist(),
                            }
                        )
                    elif isinstance(vec, dict):
                        out.append(vec)
                    else:
                        out.append({})
                return out
        except TypeError:
            pass

        return self._tf_sparse(texts)

    @staticmethod
    def _tf_sparse(texts: list[str]) -> list[dict]:
        """Simple term-frequency sparse vector as a last resort."""
        results: list[dict] = []
        for text in texts:
            tokens = text.lower().split()
            tf: dict[str, int] = {}
            for tok in tokens:
                tf[tok] = tf.get(tok, 0) + 1
            indices = list(range(len(tf)))
            values = list(tf.values())
            results.append({"indices": indices, "values": values})
        return results
