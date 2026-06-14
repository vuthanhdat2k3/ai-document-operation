"""Gold dataset loading and schema definitions for evaluation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GoldSample:
    """A single gold-standard evaluation sample.

    Attributes:
        question: The question to ask the pipeline.
        expected_answer: The ground-truth answer.
        document_id: Optional target document identifier.
        context_chunks: List of chunk IDs that are relevant to this question.
        relevance_scores: Optional graded relevance scores per chunk
            (0 = irrelevant, 1 = partial, 2 = highly relevant).
        expected_label: Expected classification label (for classification evals).
        metadata: Arbitrary additional metadata.
    """

    question: str
    expected_answer: str
    document_id: str | None = None
    context_chunks: list[str] = field(default_factory=list)
    relevance_scores: dict[str, float] = field(default_factory=dict)
    expected_label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        data: dict[str, Any] = {
            "question": self.question,
            "expected_answer": self.expected_answer,
        }
        if self.document_id:
            data["document_id"] = self.document_id
        if self.context_chunks:
            data["context_chunks"] = self.context_chunks
        if self.relevance_scores:
            data["relevance_scores"] = self.relevance_scores
        if self.expected_label:
            data["expected_label"] = self.expected_label
        if self.metadata:
            data["metadata"] = self.metadata
        return data


def load_gold_dataset(path: str | Path) -> list[GoldSample]:
    """Load a gold dataset from a JSONL file.

    Each line in the file should be a JSON object with at least
    ``question`` and ``expected_answer`` fields.

    Supported optional fields:
    - ``id``: sample identifier
    - ``document_id``: target document
    - ``context_chunks``: list of relevant chunk IDs
    - ``relevance_scores``: dict of chunk ID to graded relevance
    - ``expected_label``: classification label
    - ``metadata``: arbitrary metadata dict

    Args:
        path: Path to the JSONL file.

    Returns:
        List of GoldSample instances.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If a line is missing required fields.
    """
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(f"Gold dataset not found: {filepath}")

    samples: list[GoldSample] = []
    with filepath.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_num} of {filepath}: {exc}"
                ) from exc

            if "question" not in record:
                raise ValueError(
                    f"Missing 'question' field on line {line_num} of {filepath}"
                )
            if "expected_answer" not in record:
                raise ValueError(
                    f"Missing 'expected_answer' field on line {line_num} of {filepath}"
                )

            samples.append(
                GoldSample(
                    question=record["question"],
                    expected_answer=record["expected_answer"],
                    document_id=record.get("document_id"),
                    context_chunks=record.get("context_chunks", []),
                    relevance_scores=record.get("relevance_scores", {}),
                    expected_label=record.get("expected_label"),
                    metadata=record.get("metadata", {}),
                )
            )

    logger.info("Loaded %d gold samples from %s", len(samples), filepath)
    return samples


def load_gold_dataset_as_dicts(path: str | Path) -> list[dict[str, Any]]:
    """Load a gold dataset and return as a list of plain dictionaries.

    This is a convenience wrapper around :func:`load_gold_dataset` for
    callers that prefer raw dicts (e.g., the Evaluator).

    Args:
        path: Path to the JSONL file.

    Returns:
        List of sample dictionaries.
    """
    samples = load_gold_dataset(path)
    result: list[dict[str, Any]] = []
    for sample in samples:
        d = sample.to_dict()
        if sample.metadata:
            d.update(sample.metadata)
        result.append(d)
    return result
