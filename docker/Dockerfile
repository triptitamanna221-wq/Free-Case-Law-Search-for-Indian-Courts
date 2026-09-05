FROM python:3.11-slim AS builder

# gcc/libpq-dev are only needed to build psycopg[binary]'s C extension and are
# not required at runtime -- this stage's /app/.venv is copied into the slim
# runtime stage below, leaving the compiler toolchain behind.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app ./app
COPY hybrid_search ./hybrid_search
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
COPY README.md ./

RUN uv sync --frozen --no-dev

FROM python:3.11-slim AS runtime

# libpq5 is the runtime client library psycopg[binary]'s compiled extension
# links against; libpq-dev/gcc from the builder stage aren't needed here.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/app ./app
COPY --from=builder /app/hybrid_search ./hybrid_search
COPY --from=builder /app/alembic ./alembic
COPY --from=builder /app/alembic.ini ./
COPY --from=builder /app/scripts ./scripts
COPY --from=builder /app/README.md ./

ENV PATH="/app/.venv/bin:$PATH"

# Bake the onnx model + tokenizer into the image so a cold container never
# needs a network round-trip to HuggingFace on its first /search request.
# Calling the real accessors (rather than hardcoding filenames) both fetches
# exactly what the serving path loads and fails the build here, loudly, if
# the session can't be constructed -- better than discovering that on the
# first production request.
#
# Note this deliberately does NOT warm the sentence-transformers/torch cache:
# that path is for ingestion, which runs off-container, and importing torch
# in the API process is what was OOM-killing it (~315MB for the import alone
# against a 512MB cap).
ENV HF_HOME=/app/.cache/huggingface
RUN python -c "from app.ingestion.onnx_embedder import get_session, get_tokenizer; get_session(); get_tokenizer()"

# With the files baked in above, huggingface_hub still round-trips to the Hub
# at runtime to revalidate etags (~0.8s locally on a fast connection, and an
# unbounded stall if the Hub is slow or unreachable from the container). The
# image is self-contained, so refuse network lookups outright: cache hit or
# loud failure, no silent dependency on huggingface.co being up to serve a
# search request.
ENV HF_HUB_OFFLINE=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
