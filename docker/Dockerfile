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

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
