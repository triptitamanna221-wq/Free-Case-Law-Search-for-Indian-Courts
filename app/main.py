from fastapi import FastAPI

from app.api.routes.judgments import router as judgments_router
from app.api.routes.search import router as search_router

app = FastAPI(
    title="Semantic Search over Indian Case Law",
    description="Free hybrid (BM25 + pgvector) search over Indian court judgments.",
    version="0.1.0",
)

app.include_router(search_router)
app.include_router(judgments_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
