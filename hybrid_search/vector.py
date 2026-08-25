def cosine_distance_to_similarity(distance: float) -> float:
    """Convert pgvector's `<=>` cosine distance ([0, 2]) to cosine similarity ([-1, 1]).

    pgvector defines cosine distance as `1 - cosine_similarity`, so similarity is
    the inverse: `1 - distance`. Used only for display (e.g. a relevance percentage
    in the API response) — ranking itself uses RRF on rank position, not this value.
    """
    return 1 - distance
