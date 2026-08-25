from hybrid_search.types import BM25Hit, RankedResult, VectorHit

DEFAULT_K = 60
DEFAULT_LIMIT = 20


def _ranks_by_chunk_id(chunk_ids: list[int]) -> dict[int, int]:
    """1-indexed rank per chunk_id, first occurrence wins if a list has duplicates."""
    ranks: dict[int, int] = {}
    for position, chunk_id in enumerate(chunk_ids, start=1):
        ranks.setdefault(chunk_id, position)
    return ranks


def reciprocal_rank_fusion(
    bm25_hits: list[BM25Hit],
    vector_hits: list[VectorHit],
    k: int = DEFAULT_K,
    limit: int = DEFAULT_LIMIT,
) -> list[RankedResult]:
    """Fuse two independently-ranked retrieval lists via Reciprocal Rank Fusion.

    score(doc) = sum(1 / (k + rank_in_list)) over every input list containing doc,
    where rank_in_list is the doc's 1-indexed position in that list (Cormack et al.,
    2009). RRF only consumes rank position, not raw BM25/cosine scores, so it needs
    no cross-scale normalization between ts_rank_cd and vector distance.

    Neither input list is mutated.
    """
    bm25_ranks = _ranks_by_chunk_id([hit.chunk_id for hit in bm25_hits])
    vector_ranks = _ranks_by_chunk_id([hit.chunk_id for hit in vector_hits])
    bm25_rank_values = {hit.chunk_id: hit.rank for hit in bm25_hits}
    vector_distance_values = {hit.chunk_id: hit.distance for hit in vector_hits}

    all_chunk_ids = set(bm25_ranks) | set(vector_ranks)

    results = []
    for chunk_id in all_chunk_ids:
        score = 0.0
        if chunk_id in bm25_ranks:
            score += 1 / (k + bm25_ranks[chunk_id])
        if chunk_id in vector_ranks:
            score += 1 / (k + vector_ranks[chunk_id])
        results.append(
            RankedResult(
                chunk_id=chunk_id,
                fused_score=score,
                bm25_rank=bm25_rank_values.get(chunk_id),
                vector_distance=vector_distance_values.get(chunk_id),
            )
        )

    results.sort(key=lambda r: (-r.fused_score, r.chunk_id))
    return results[:limit]
