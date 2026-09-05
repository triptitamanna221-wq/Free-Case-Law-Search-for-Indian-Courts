import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import Settings, get_settings
from app.ingestion.onnx_embedder import embed_texts_onnx
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from hybrid_search import BM25Hit, VectorHit, reciprocal_rank_fusion

router = APIRouter(tags=["search"])

_BM25_QUERY = text(
    """
    SELECT c.id AS chunk_id, ts_rank_cd(c.text_tsv, plainto_tsquery('english', :query)) AS rank
    FROM chunks c
    JOIN judgments j ON j.id = c.judgment_id
    WHERE c.text_tsv @@ plainto_tsquery('english', :query)
      AND ((:court)::text IS NULL OR j.court = (:court)::text)
    ORDER BY rank DESC
    LIMIT :candidate_count
    """
)

_VECTOR_QUERY = text(
    """
    SELECT c.id AS chunk_id, c.embedding <=> (:embedding)::vector AS distance
    FROM chunks c
    JOIN judgments j ON j.id = c.judgment_id
    WHERE c.embedding IS NOT NULL
      AND ((:court)::text IS NULL OR j.court = (:court)::text)
    ORDER BY c.embedding <=> (:embedding)::vector ASC
    LIMIT :candidate_count
    """
)

_CHUNK_DETAIL_QUERY = text(
    """
    SELECT c.id AS chunk_id, c.judgment_id, c.text AS snippet,
           j.title, j.court, j.decision_date
    FROM chunks c
    JOIN judgments j ON j.id = c.judgment_id
    WHERE c.id = ANY(:chunk_ids)
    """
)

_SNIPPET_LENGTH = 400


def _to_pgvector_literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(x) for x in vector) + "]"


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    started = time.perf_counter()

    # search_mode narrows to one retrieval path by simply not running the other
    # query -- reciprocal_rank_fusion already handles an empty input list
    # correctly (falls back to pure single-path ordering, see hybrid_search's
    # own unit tests), so no special-casing is needed in the fusion step.
    run_keyword = request.search_mode in ("hybrid", "keyword")
    run_semantic = request.search_mode in ("hybrid", "semantic")

    bm25_hits: list[BM25Hit] = []
    if run_keyword:
        bm25_rows = db.execute(
            _BM25_QUERY,
            {
                "query": request.query,
                "court": request.court,
                "candidate_count": settings.bm25_candidate_count,
            },
        ).all()
        bm25_hits = [BM25Hit(chunk_id=row.chunk_id, rank=row.rank) for row in bm25_rows]

    vector_hits: list[VectorHit] = []
    if run_semantic:
        # onnx path, not the sentence-transformers one used during ingestion:
        # identical weights and vectors (see app/ingestion/onnx_embedder.py),
        # but without importing torch, which alone costs more RSS than the
        # whole serving container is allowed.
        [query_embedding] = embed_texts_onnx([request.query])
        vector_rows = db.execute(
            _VECTOR_QUERY,
            {
                "embedding": _to_pgvector_literal(query_embedding),
                "court": request.court,
                "candidate_count": settings.vector_candidate_count,
            },
        ).all()
        vector_hits = [VectorHit(chunk_id=row.chunk_id, distance=row.distance) for row in vector_rows]
    bm25_chunk_ids = {hit.chunk_id for hit in bm25_hits}
    vector_chunk_ids = {hit.chunk_id for hit in vector_hits}

    fused = reciprocal_rank_fusion(bm25_hits, vector_hits, k=settings.rrf_k, limit=request.limit)

    if not fused:
        return SearchResponse(
            query=request.query, results=[], took_ms=(time.perf_counter() - started) * 1000
        )

    detail_rows = db.execute(
        _CHUNK_DETAIL_QUERY, {"chunk_ids": [r.chunk_id for r in fused]}
    ).all()
    detail_by_chunk_id = {row.chunk_id: row for row in detail_rows}

    results = []
    for r in fused:
        detail = detail_by_chunk_id.get(r.chunk_id)
        if detail is None:
            continue
        snippet = detail.snippet[:_SNIPPET_LENGTH]
        results.append(
            SearchResultItem(
                judgment_id=detail.judgment_id,
                chunk_id=r.chunk_id,
                title=detail.title,
                court=detail.court,
                decision_date=detail.decision_date,
                snippet=snippet,
                fused_score=r.fused_score,
                matched_keyword=r.chunk_id in bm25_chunk_ids,
                matched_semantic=r.chunk_id in vector_chunk_ids,
            )
        )

    return SearchResponse(
        query=request.query, results=results, took_ms=(time.perf_counter() - started) * 1000
    )
