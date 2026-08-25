import pytest

from hybrid_search.fusion import reciprocal_rank_fusion
from hybrid_search.types import BM25Hit, VectorHit


def test_disjoint_lists_interleave_by_rank():
    bm25 = [BM25Hit(chunk_id=1, rank=0.9), BM25Hit(chunk_id=2, rank=0.5)]
    vector = [VectorHit(chunk_id=3, distance=0.1), VectorHit(chunk_id=4, distance=0.4)]

    results = reciprocal_rank_fusion(bm25, vector, k=60)
    ids = [r.chunk_id for r in results]

    # rank-1 hits from each list tie at the same RRF score; rank-2 hits tie below them.
    assert set(ids[:2]) == {1, 3}
    assert set(ids[2:]) == {2, 4}


def test_full_overlap_doc_scores_the_sum_of_both_rank_1_terms():
    bm25 = [BM25Hit(chunk_id=1, rank=0.9)]
    vector = [VectorHit(chunk_id=1, distance=0.1)]

    [result] = reciprocal_rank_fusion(bm25, vector, k=60)

    assert result.fused_score == pytest.approx(2 / 61)


def test_overlapping_doc_outranks_a_rank_1_single_list_doc():
    # chunk 1: bm25 rank 1 AND vector rank 2 -> 1/61 + 1/62
    # chunk 2: bm25 rank 2 only               -> 1/62
    # chunk 3: vector rank 1 only              -> 1/61
    bm25 = [BM25Hit(chunk_id=1, rank=0.9), BM25Hit(chunk_id=2, rank=0.5)]
    vector = [VectorHit(chunk_id=3, distance=0.05), VectorHit(chunk_id=1, distance=0.2)]

    results = reciprocal_rank_fusion(bm25, vector, k=60)

    assert results[0].chunk_id == 1
    assert results[0].fused_score > results[1].fused_score > results[2].fused_score


def test_k_sensitivity_changes_relative_weighting():
    bm25 = [BM25Hit(chunk_id=1, rank=0.9), BM25Hit(chunk_id=2, rank=0.8)]
    vector = [VectorHit(chunk_id=2, distance=0.01), VectorHit(chunk_id=1, distance=0.5)]

    # small k: rank-1 dominates heavily -> chunk 1 (bm25 rank1) can win
    small_k = reciprocal_rank_fusion(bm25, vector, k=1)
    # large k: differences between ranks shrink, overlap-in-both-lists matters more
    large_k = reciprocal_rank_fusion(bm25, vector, k=1000)

    assert [r.chunk_id for r in small_k] != [] and [r.chunk_id for r in large_k] != []
    assert small_k[0].fused_score != large_k[0].fused_score


def test_empty_bm25_falls_back_to_pure_vector_order():
    vector = [VectorHit(chunk_id=5, distance=0.1), VectorHit(chunk_id=6, distance=0.3)]

    results = reciprocal_rank_fusion([], vector, k=60)

    assert [r.chunk_id for r in results] == [5, 6]
    assert all(r.bm25_rank is None for r in results)


def test_empty_vector_falls_back_to_pure_bm25_order():
    bm25 = [BM25Hit(chunk_id=5, rank=0.9), BM25Hit(chunk_id=6, rank=0.3)]

    results = reciprocal_rank_fusion(bm25, [], k=60)

    assert [r.chunk_id for r in results] == [5, 6]
    assert all(r.vector_distance is None for r in results)


def test_both_empty_returns_empty_list_without_crashing():
    assert reciprocal_rank_fusion([], [], k=60) == []


def test_limit_truncates_to_exactly_top_n():
    bm25 = [BM25Hit(chunk_id=i, rank=1.0 / i) for i in range(1, 11)]

    results = reciprocal_rank_fusion(bm25, [], k=60, limit=3)

    assert len(results) == 3
    assert [r.chunk_id for r in results] == [1, 2, 3]


def test_duplicate_chunk_id_within_one_list_uses_first_occurrence_only():
    bm25 = [BM25Hit(chunk_id=1, rank=0.9), BM25Hit(chunk_id=1, rank=0.1)]

    [result] = reciprocal_rank_fusion(bm25, [], k=60)

    # duplicate must not be double-counted or overwritten by its later, worse rank
    assert result.fused_score == pytest.approx(1 / 61)


def test_fusion_is_deterministic_across_repeated_runs():
    bm25 = [BM25Hit(chunk_id=1, rank=0.9), BM25Hit(chunk_id=2, rank=0.5)]
    vector = [VectorHit(chunk_id=3, distance=0.1)]

    first = reciprocal_rank_fusion(bm25, vector, k=60)
    second = reciprocal_rank_fusion(bm25, vector, k=60)

    assert first == second


def test_tied_scores_break_ties_by_chunk_id_ascending():
    bm25 = [BM25Hit(chunk_id=9, rank=0.9)]
    vector = [VectorHit(chunk_id=2, distance=0.1)]

    results = reciprocal_rank_fusion(bm25, vector, k=60)

    assert results[0].fused_score == results[1].fused_score
    assert [r.chunk_id for r in results] == [2, 9]


def test_fusion_does_not_mutate_input_lists():
    bm25 = [BM25Hit(chunk_id=1, rank=0.9)]
    vector = [VectorHit(chunk_id=2, distance=0.1)]
    bm25_copy, vector_copy = list(bm25), list(vector)

    reciprocal_rank_fusion(bm25, vector, k=60)

    assert bm25 == bm25_copy
    assert vector == vector_copy
