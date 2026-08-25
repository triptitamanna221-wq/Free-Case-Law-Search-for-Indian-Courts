from datetime import date

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    court: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class SearchResultItem(BaseModel):
    judgment_id: int
    chunk_id: int
    title: str
    court: str | None
    decision_date: date | None
    snippet: str
    fused_score: float
    matched_keyword: bool
    matched_semantic: bool


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    took_ms: float
