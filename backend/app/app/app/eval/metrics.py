"""Evaluation metrics for retrieval, generation, and classification quality."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any


class RetrievalMetrics:
    """Compute standard information retrieval metrics.

    All methods accept lists of document/chunk IDs and return a float
    score.  Relevance is binary unless otherwise noted.
    """

    @staticmethod
    def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
        """Recall@k: fraction of relevant items found in top-k.

        Args:
            retrieved: Ordered list of retrieved document IDs.
            relevant: Set of relevant document IDs.
            k: Cutoff rank.

        Returns:
            Recall@k in [0, 1].
        """
        if not relevant:
            return 0.0
        top_k = set(retrieved[:k])
        return len(top_k & relevant) / len(relevant)

    @staticmethod
    def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
        """Precision@k: fraction of top-k items that are relevant.

        Args:
            retrieved: Ordered list of retrieved document IDs.
            relevant: Set of relevant document IDs.
            k: Cutoff rank.

        Returns:
            Precision@k in [0, 1].
        """
        if k <= 0:
            return 0.0
        top_k = retrieved[:k]
        return sum(1 for doc in top_k if doc in relevant) / k

    @staticmethod
    def mrr(retrieved: list[str], relevant: set[str]) -> float:
        """Mean Reciprocal Rank for a single query.

        Args:
            retrieved: Ordered list of retrieved document IDs.
            relevant: Set of relevant document IDs.

        Returns:
            Reciprocal rank of the first relevant result, or 0.0.
        """
        for i, doc in enumerate(retrieved):
            if doc in relevant:
                return 1.0 / (i + 1)
        return 0.0

    @staticmethod
    def ndcg_at_k(
        retrieved: list[str],
        relevance_scores: dict[str, float],
        k: int,
    ) -> float:
        """Normalized Discounted Cumulative Gain@k.

        Args:
            retrieved: Ordered list of retrieved document IDs.
            relevance_scores: Mapping of document ID to graded relevance
                (0 = irrelevant, 1 = partial, 2 = highly relevant).
            k: Cutoff rank.

        Returns:
            nDCG@k in [0, 1].
        """
        def _dcg(scores: list[float]) -> float:
            return sum(s / math.log2(i + 2) for i, s in enumerate(scores))

        actual_scores = [relevance_scores.get(doc, 0.0) for doc in retrieved[:k]]
        ideal_scores = sorted(relevance_scores.values(), reverse=True)[:k]

        dcg = _dcg(actual_scores)
        idcg = _dcg(ideal_scores)

        if idcg == 0:
            return 0.0
        return dcg / idcg

    @staticmethod
    def hit_rate_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
        """Hit Rate@k: 1.0 if at least one relevant item in top-k, else 0.0.

        Args:
            retrieved: Ordered list of retrieved document IDs.
            relevant: Set of relevant document IDs.
            k: Cutoff rank.

        Returns:
            1.0 or 0.0.
        """
        top_k = set(retrieved[:k])
        return 1.0 if top_k & relevant else 0.0

    @classmethod
    def compute_all(
        cls,
        retrieved: list[str],
        relevant: set[str],
        relevance_scores: dict[str, float] | None = None,
        ks: tuple[int, ...] = (5, 10, 20),
    ) -> dict[str, float]:
        """Compute all retrieval metrics for a single query.

        Args:
            retrieved: Ordered list of retrieved document IDs.
            relevant: Set of relevant document IDs.
            relevance_scores: Optional graded relevance scores.
            ks: Cutoff values for @k metrics.

        Returns:
            Dictionary of metric name to value.
        """
        results: dict[str, float] = {"mrr": cls.mrr(retrieved, relevant)}
        for k in ks:
            results[f"recall@{k}"] = cls.recall_at_k(retrieved, relevant, k)
            results[f"precision@{k}"] = cls.precision_at_k(retrieved, relevant, k)
            results[f"hit_rate@{k}"] = cls.hit_rate_at_k(retrieved, relevant, k)
            if relevance_scores:
                results[f"ndcg@{k}"] = cls.ndcg_at_k(retrieved, relevance_scores, k)
        return results


class GenerationMetrics:
    """Compute LLM generation quality metrics.

    These metrics are designed to be used with LLM-as-judge evaluation
    where each score is provided externally (e.g., by an LLM judge or
    human evaluator).
    """

    @staticmethod
    def answer_relevance(scores: list[float]) -> float:
        """Average answer relevance score across samples.

        Args:
            scores: Per-sample relevance scores (1-5 Likert scale).

        Returns:
            Mean score, or 0.0 if empty.
        """
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    @staticmethod
    def context_relevance(scores: list[float]) -> float:
        """Average context relevance score across samples.

        Args:
            scores: Per-sample context relevance scores (1-5 Likert scale).

        Returns:
            Mean score, or 0.0 if empty.
        """
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    @staticmethod
    def groundedness_score(supported_claims: int, total_claims: int) -> float:
        """Groundedness: fraction of claims supported by context.

        Args:
            supported_claims: Number of claims supported by context.
            total_claims: Total number of claims in the answer.

        Returns:
            Groundedness in [0, 1].
        """
        if total_claims <= 0:
            return 0.0
        return supported_claims / total_claims

    @staticmethod
    def citation_accuracy(correct_citations: int, total_citations: int) -> float:
        """Citation accuracy: fraction of correct citations.

        Args:
            correct_citations: Number of citations that are factually correct.
            total_citations: Total citations in the answer.

        Returns:
            Accuracy in [0, 1].
        """
        if total_citations <= 0:
            return 1.0
        return correct_citations / total_citations

    @classmethod
    def compute_all(
        cls,
        answer_relevance_scores: list[float] | None = None,
        context_relevance_scores: list[float] | None = None,
        supported_claims: int = 0,
        total_claims: int = 0,
        correct_citations: int = 0,
        total_citations: int = 0,
    ) -> dict[str, float]:
        """Compute all generation metrics.

        Returns:
            Dictionary of metric name to value.
        """
        return {
            "answer_relevance": cls.answer_relevance(answer_relevance_scores or []),
            "context_relevance": cls.context_relevance(context_relevance_scores or []),
            "groundedness": cls.groundedness_score(supported_claims, total_claims),
            "citation_accuracy": cls.citation_accuracy(correct_citations, total_citations),
        }


class ClassificationMetrics:
    """Compute classification quality metrics."""

    @staticmethod
    def accuracy(y_true: list[str], y_pred: list[str]) -> float:
        """Classification accuracy.

        Args:
            y_true: Ground truth labels.
            y_pred: Predicted labels.

        Returns:
            Accuracy in [0, 1].
        """
        if not y_true:
            return 0.0
        correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
        return correct / len(y_true)

    @staticmethod
    def precision(
        y_true: list[str],
        y_pred: list[str],
        positive_label: str,
    ) -> float:
        """Binary precision for a given positive label.

        Args:
            y_true: Ground truth labels.
            y_pred: Predicted labels.
            positive_label: The label considered as positive.

        Returns:
            Precision in [0, 1].
        """
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == positive_label and p == positive_label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != positive_label and p == positive_label)
        denom = tp + fp
        return tp / denom if denom > 0 else 0.0

    @staticmethod
    def recall(
        y_true: list[str],
        y_pred: list[str],
        positive_label: str,
    ) -> float:
        """Binary recall for a given positive label.

        Args:
            y_true: Ground truth labels.
            y_pred: Predicted labels.
            positive_label: The label considered as positive.

        Returns:
            Recall in [0, 1].
        """
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == positive_label and p == positive_label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == positive_label and p != positive_label)
        denom = tp + fn
        return tp / denom if denom > 0 else 0.0

    @classmethod
    def f1(
        cls,
        y_true: list[str],
        y_pred: list[str],
        positive_label: str,
    ) -> float:
        """Binary F1 score for a given positive label.

        Args:
            y_true: Ground truth labels.
            y_pred: Predicted labels.
            positive_label: The label considered as positive.

        Returns:
            F1 score in [0, 1].
        """
        p = cls.precision(y_true, y_pred, positive_label)
        r = cls.recall(y_true, y_pred, positive_label)
        if p + r == 0:
            return 0.0
        return 2 * (p * r) / (p + r)

    @classmethod
    def macro_f1(cls, y_true: list[str], y_pred: list[str]) -> float:
        """Macro-averaged F1 across all classes.

        Args:
            y_true: Ground truth labels.
            y_pred: Predicted labels.

        Returns:
            Macro F1 in [0, 1].
        """
        labels = set(y_true) | set(y_pred)
        if not labels:
            return 0.0
        f1_scores = [cls.f1(y_true, y_pred, label) for label in labels]
        return sum(f1_scores) / len(f1_scores)

    @classmethod
    def confusion_matrix(
        cls,
        y_true: list[str],
        y_pred: list[str],
    ) -> dict[str, dict[str, int]]:
        """Build a confusion matrix as a nested dictionary.

        Args:
            y_true: Ground truth labels.
            y_pred: Predicted labels.

        Returns:
            ``{true_label: {predicted_label: count}}``
        """
        labels = sorted(set(y_true) | set(y_pred))
        matrix: dict[str, dict[str, int]] = {
            label: {pred: 0 for pred in labels} for label in labels
        }
        for t, p in zip(y_true, y_pred):
            matrix[t][p] += 1
        return matrix

    @classmethod
    def compute_all(
        cls,
        y_true: list[str],
        y_pred: list[str],
    ) -> dict[str, float]:
        """Compute all classification metrics.

        Returns:
            Dictionary of metric name to value.
        """
        return {
            "accuracy": cls.accuracy(y_true, y_pred),
            "macro_f1": cls.macro_f1(y_true, y_pred),
        }
