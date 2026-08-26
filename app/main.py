from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.judgments import router as judgments_router
from app.api.routes.search import router as search_router
from app.config import get_settings

app = FastAPI(
    title="Semantic Search over Indian Case Law",
    description="Free hybrid (BM25 + pgvector) search over Indian court judgments.",
    version="0.1.0",
)

cors_origins = [origin.strip() for origin in get_settings().cors_origins.split(",") if origin.strip()]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

app.include_router(search_router)
app.include_router(judgments_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
