from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.judgments import router as judgments_router
from app.api.routes.search import router as search_router
from app.config import get_settings

# NOTE: do not add a lifespan hook that eagerly loads the embedding model
# here. It was tried and reverted: the torch-based serving path peaks at
# ~350MB in one worker (measured -- ~315MB of that is `import torch` alone,
# before any weights load), and Render's free container is capped at 512MB
# total including the gunicorn master. Loading eagerly moved the resulting
# OOM kill from "first /search request" to "every boot", turning a partly-
# working service into a crash loop where even /health never answered.
# The fix is to shrink the serving path (see app/ingestion/onnx_embedder.py),
# not to change *when* an oversized model gets loaded.

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
