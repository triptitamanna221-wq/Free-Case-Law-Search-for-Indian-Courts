from dataclasses import dataclass


@dataclass(frozen=True)
class BM25Hit:
    """One row from the Postgres full-text search path, ordered by rank descending."""

    chunk_id: int
    rank: float


@dataclass(frozen=True)
class VectorHit:
    """One row from the pgvector ANN search path (`<=>` cosine distance operator)."""

    chunk_id: int
    distance: float


@dataclass(frozen=True)
class RankedResult:
    """A chunk_id fused across the two retrieval paths, sorted by fused_score descending."""

    chunk_id: int
    fused_score: float
    bm25_rank: float | None
    vector_distance: float | None
