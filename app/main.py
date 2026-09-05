from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.judgments import router as judgments_router
from app.api.routes.search import router as search_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm the onnx session during boot rather than on the first search.

    An earlier version of this hook loaded the *torch* model here and had to
    be reverted: that path peaks at ~350MB RSS in one worker against a 512MB
    container, so eager loading moved an OOM kill into boot and crash-looped
    the service until even /health stopped answering. What made that fatal
    was the memory, not the timing -- the onnx path measures ~290MB peak and
    leaves real headroom, so warming it here is now safe.

    It's also worth doing. Render's free tier spins the container down after
    15 minutes idle, and loading lazily meant the first request after every
    spin-up paid the whole session-init cost on 0.1 CPU. Paying it during
    boot, while Render is already waiting on the health check, keeps that
    cost off the first visitor's request.

    Deliberately not wrapped in try/except: if the model can't load, the
    process should fail loudly at boot rather than serve traffic that will
    500 on every /search.
    """
    from app.ingestion.onnx_embedder import get_session, get_tokenizer

    get_tokenizer()
    get_session()
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
