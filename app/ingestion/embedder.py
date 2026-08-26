from functools import lru_cache
from typing import Protocol

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
BATCH_SIZE = 64


class Embedder(Protocol):
    def encode(self, texts: list[str], batch_size: int, show_progress_bar: bool) -> object: ...


@lru_cache(maxsize=1)
def get_model() -> Embedder:
    """Loads the MiniLM model once per process (~20MB download, cached under
    ~/.cache/huggingface). Kept behind a lazy import so unit tests never pull in
    torch/sentence-transformers unless they explicitly ask for the real model."""
    from sentence_transformers import SentenceTransformer

    from app.config import get_settings

    return SentenceTransformer(get_settings().embedding_model)


def embed_texts(
    texts: list[str],
    model: Embedder | None = None,
    batch_size: int = BATCH_SIZE,
    show_progress_bar: bool = False,
) -> list[list[float]]:
    """Embed a batch of chunk texts in a single model call (not one call per chunk).

    `batch_size` controls how the model internally groups texts for CPU inference;
    64 is the throughput sweet spot for ~256-token judgment chunks on a laptop CPU.
    `show_progress_bar` defaults off for the background job path (loaders.py's
    embed_pending_chunks); the interactive ingestion CLI turns it on.
    Tests inject `model` to avoid loading the real model.
    """
    if not texts:
        return []
    model = model or get_model()
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=show_progress_bar)
    return [list(map(float, vector)) for vector in embeddings]
