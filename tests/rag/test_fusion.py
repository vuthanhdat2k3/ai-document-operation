"""Tests for RRF (Reciprocal Rank Fusion) formula."""

from __future__ import annotations

import pytest

from app.rag.fusion import rrf_fusion
from app.rag.retriever import SearchResult


def _sr(chunk_id: str, score: float = 0.0, text: str = "", doc_id: str = "d1") -> SearchResult:
    """Shorthand for creating SearchResult in tests."""
    return SearchResult(
        chunk_id=chunk_id,
        document_id=doc_id,
        text=text or f"text_{chunk_id}",
        score=score,
        page=1,
    )


class TestRRFFusion:
    """rrf_fusion tests."""

    def test_empty_input(self) -> None:
        assert rrf_fusion([]) == []

    def test_empty_lists(self) -> None:
        assert rrf_fusion([[], []]) == []

    def test_single_list_passthrough(self) -> None:
        items = [_sr("a", 0.9), _sr("b", 0.8), _sr("c", 0.7)]
        result = rrf_fusion([items])
        assert len(result) == 3
        assert result[0].chunk_id == "a"
        assert result[1].chunk_id == "b"
        assert result[2].chunk_id == "c"

    def test_rrf_score_formula(self) -> None:
        """Verify RRF score = sum of 1/(k + rank) for each list."""
        k = 60
        list1 = [_sr("a"), _sr("b")]
        list2 = [_sr("b"), _sr("c")]

        result = rrf_fusion([list1, list2], k=k)
        scores = {r.chunk_id: r.score for r in result}

        # a: rank 1 in list1 only → 1/(60+1) = 1/61
        assert scores["a"] == pytest.approx(1.0 / (k + 1))
        # b: rank 2 in list1 + rank 1 in list2 → 1/(60+2) + 1/(60+1)
        assert scores["b"] == pytest.approx(1.0 / (k + 2) + 1.0 / (k + 1))
        # c: rank 2 in list2 only → 1/(60+2)
        assert scores["c"] == pytest.approx(1.0 / (k + 2))

    def test_ranking_by_rrf_score(self) -> None:
        """Document appearing in both lists should rank higher."""
        list1 = [_sr("a"), _sr("b"), _sr("c")]
        list2 = [_sr("b"), _sr("a"), _sr("d")]

        result = rrf_fusion([list1, list2])
        ids = [r.chunk_id for r in result]

        # a: rank 1 + rank 2 = 1/61 + 1/62
        # b: rank 2 + rank 1 = 1/62 + 1/61
        # a and b should be top 2 (tied, but both above c and d)
        assert ids[0] in ("a", "b")
        assert ids[1] in ("a", "b")

    def test_three_lists_fusion(self) -> None:
        list1 = [_sr("x"), _sr("y")]
        list2 = [_sr("y"), _sr("z")]
        list3 = [_sr("x"), _sr("z")]

        result = rrf_fusion([list1, list2, list3])
        scores = {r.chunk_id: r.score for r in result}

        # x: rank 1 in list1 + rank 1 in list3 = 1/61 + 1/61
        # y: rank 2 in list1 + rank 1 in list2 = 1/62 + 1/61
        # z: rank 2 in list2 + rank 2 in list3 = 1/62 + 1/62
        assert scores["x"] > scores["y"] > scores["z"]

    def test_custom_k_value(self) -> None:
        list1 = [_sr("a"), _sr("b")]
        list2 = [_sr("a")]

        result = rrf_fusion([list1, list2], k=10)
        scores = {r.chunk_id: r.score for r in result}

        # a: rank 1 in list1 + rank 1 in list2 = 1/(10+1) + 1/(10+1)
        assert scores["a"] == pytest.approx(2.0 / 11)

    def test_preserves_first_seen_payload(self) -> None:
        """When same chunk_id appears in multiple lists, payload from first list is kept."""
        list1 = [_sr("a", score=0.9, text="from_list1", doc_id="doc1")]
        list2 = [_sr("a", score=0.1, text="from_list2", doc_id="doc2")]

        result = rrf_fusion([list1, list2])
        assert len(result) == 1
        assert result[0].text == "from_list1"
        assert result[0].document_id == "doc1"

    def test_no_overlap(self) -> None:
        list1 = [_sr("a"), _sr("b")]
        list2 = [_sr("c"), _sr("d")]

        result = rrf_fusion([list1, list2])
        assert len(result) == 4

    def test_score_is_rrf_not_original(self) -> None:
        """Result scores should be RRF scores, not original scores."""
        list1 = [_sr("a", score=0.99)]
        result = rrf_fusion([list1])
        # RRF score = 1/(60+1) ≈ 0.01639
        assert result[0].score == pytest.approx(1.0 / 61)
        assert result[0].score != 0.99

    def test_descending_order(self) -> None:
        list1 = [_sr("a"), _sr("b"), _sr("c"), _sr("d")]
        list2 = [_sr("d"), _sr("c"), _sr("b"), _sr("a")]

        result = rrf_fusion([list1, list2])
        for i in range(len(result) - 1):
            assert result[i].score >= result[i + 1].score


class TestRRFFusionEdgeCases:
    """Edge cases for rrf_fusion."""

    def test_single_item_in_each_list(self) -> None:
        list1 = [_sr("a")]
        list2 = [_sr("b")]
        result = rrf_fusion([list1, list2])
        assert len(result) == 2

    def test_many_lists_same_item(self) -> None:
        """Item appearing in many lists should accumulate high RRF score."""
        lists = [[_sr("a")] for _ in range(10)]
        result = rrf_fusion(lists)
        assert len(result) == 1
        expected = sum(1.0 / 61 for _ in range(10))
        assert result[0].score == pytest.approx(expected)

    def test_rank_starts_at_1_not_0(self) -> None:
        """Verify rank is 1-based (enumerate start=1)."""
        items = [_sr("top"), _sr("second")]
        result = rrf_fusion([items])
        # top: rank 1 → 1/(60+1)
        assert result[0].score == pytest.approx(1.0 / 61)
        # second: rank 2 → 1/(60+2)
        assert result[1].score == pytest.approx(1.0 / 62)
