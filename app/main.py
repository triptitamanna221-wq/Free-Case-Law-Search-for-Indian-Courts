from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.judgments import router as judgments_router
from app.api.routes.search import router as search_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Loads (and, on a cold container, downloads) the embedding model once,
    # during startup, instead of lazily on the first /search request. This
    # isn't the migration-on-startup anti-pattern warned about elsewhere in
    # this repo: there's no shared external resource or cross-worker race
    # here, since each worker process needs its own copy of the model in its
    # own memory regardless of when it's loaded. What it does fix is a real
    # bug observed on Render's free instance (0.1 CPU): loading the model
    # lazily meant the first real request, arriving *after* health checks
    # were already passing, pegged the only available CPU for the whole
    # load -- starving /health of CPU until it started failing and Render
    # restarted the container before the load ever finished. Loading here
    # instead means that cost is paid during the startup grace period
    # platforms expect to be slow, before the service is marked healthy.
    from app.ingestion.embedder import get_model

    get_model()
    yield


app = FastAPI(
    title="Semantic Search over Indian Case Law",
    description="Free hybrid (BM25 + pgvector) search over Indian court judgments.",
    version="0.1.0",
    lifespan=lifespan,
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
