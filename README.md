# Semantic Search over Indian Case Law

Finding a relevant Indian court judgment today means either paying for a
commercial legal database, or keyword-searching Indian Kanoon and hoping the
right words are in the text. Neither handles the case where you know *what
happened* but not the *legal terms of art* a judgment would use — "a company
run into the ground by its own directors" won't keyword-match "oppression and
mismanagement," even though that's exactly the doctrine you're looking for.

This project is a free, open search backend over Indian case law that ranks
results by **both** keyword match (BM25 via Postgres full-text search) and
meaning (embedding similarity via pgvector), fused with the same algorithm
Elasticsearch/OpenSearch use for hybrid search — so a query gets both an exact
citation lookup and a "these mean the same thing" match, whichever the search
actually needs.

**Live demo:** _TBD — filled in once deployed (see [Deployment](#deployment))._

## What it does

- `POST /search` — hybrid keyword + semantic search over judgment text, returns
  ranked chunks with the parent judgment's metadata.
- `GET /judgments/{id}` — full judgment detail by id.
- A `hybrid_search/` module with zero framework dependencies, designed to be
  lifted into its own PyPI package unchanged: the fusion algorithm doesn't
  know SQLAlchemy or FastAPI exist.

## Numbers

| Metric | Value |
|---|---|
| Judgments processed | **41,839** — the full corpus, chunked + embedded end-to-end (`data/ingestion_metrics.json`) |
| Chunks embedded | **883,787** (427.4M tokens total) |
| Embedding latency (p50 / p95, ms/chunk) | **9.1 / 14.4** — real, from the full 41,839-judgment run (`data/ingestion_metrics.json`) |
| DB insert latency (p50 / p95, ms/record) | _TBD — requires a live Postgres, not available in the environment that built this pipeline; this run used `--dry-run` (embed-only, no DB writes)_ |
| Search p50 / p95 latency | _TBD, measured locally against the seeded sample_ |
| Test coverage | _TBD, `uv run pytest --cov`_ |
| Uptime | _TBD once deployed_ |

(Deliberately left unfilled rather than guessed — updated as each is actually
measured, not estimated.)

## Architecture

Full schema + index rationale: [`docs/erd.md`](docs/erd.md).
Data provenance + licensing: [`docs/data_sources.md`](docs/data_sources.md).
Ingestion pipeline details: [`docs/data_pipeline.md`](docs/data_pipeline.md).

```mermaid
flowchart LR
    subgraph Ingest
        A[HF datasets] --> B[chunking]
        B --> C[batched embedding]
    end
    C --> D[(Postgres + pgvector)]
    subgraph Search
        E[POST /search] --> F[BM25 query\nts_rank_cd]
        E --> G[vector query\ncosine <=>]
        F --> H[Reciprocal Rank Fusion]
        G --> H
        H --> I[ranked results]
    end
    D --> F
    D --> G
```

### Why these choices

- **pgvector, not a separate vector store.** At the ~150–250K-vector scale
  this project targets, a dedicated vector database (Qdrant, Pinecone) isn't
  justified — it's another service to run, another failure mode, another
  thing to keep in sync with Postgres. pgvector's HNSW index handles this
  scale inside the same database that already holds the judgments.
- **Reciprocal Rank Fusion, not a weighted score blend.** `ts_rank_cd` and
  cosine distance live on incomparable scales; a weighted average needs
  per-query normalization and undefendable magic-number weights. RRF only
  consumes rank position — scale-invariant, one documented constant (`k=60`,
  [Cormack et al. 2009](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)).
- **HNSW over IVFFlat.** IVFFlat needs a `lists` parameter tuned to the
  *final* row count and gives poor recall if built before the table is
  populated — a bad fit for a resumable, incrementally-growing ingest. HNSW
  builds incrementally with better recall/latency at this scale.
- **An open HF dataset, not scraping Indian Kanoon directly.** See
  [`docs/data_sources.md`](docs/data_sources.md) for the full reasoning and
  history (including a pivot away from two originally-planned datasets that
  turned out to require HuggingFace auth) — short version: no free bulk API,
  ToS-questionable at 50K-document scale, and a bare scraper loop isn't
  itself something worth shipping.
- **Render for both the app and Postgres.** One dashboard, one Blueprint
  (`render.yaml`), no cross-provider networking to debug. The real tradeoff:
  Render's free Postgres is deleted (not just paused) after 30 days of
  inactivity — a genuine risk for a demo link opened weeks after an
  application goes out. See [Deployment](#deployment) for the mitigation
  (a scheduled keep-alive query, or a manual recreate-from-`render.yaml`
  if it does expire — the Blueprint makes that a few minutes of work either
  way, not a rebuild from scratch).

## Getting started

Requires [Docker](https://docs.docker.com/get-docker/) and
[uv](https://docs.astral.sh/uv/).

```bash
git clone <this-repo>
cd <this-repo>

# 1. bring up Postgres + pgvector and the app, two services
docker compose -f docker/docker-compose.yml up -d

# 2. install deps and run migrations
uv sync
uv run alembic upgrade head

# 3. pull a sample of judgments and run the ingestion pipeline
uv run python scripts/download_datasets.py --max-rows 500
uv run python scripts/ingest_judgments.py --source data/staging --limit 500

# 4. try it
curl -X POST localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "oppression and mismanagement of a company"}'

# 5. (optional) the search UI -- see web/README.md for the full setup,
#    including a mock-data demo mode that needs no backend at all
cd web && npm install && npm run dev   # http://localhost:3000
```

## Testing

```bash
uv run pytest tests/unit          # 36 tests, no DB/network required
uv run pytest tests/integration   # spins up a real pgvector/pgvector:pg15 container
uv run pytest -m integration -v   # just the DB-marked subset, same tests/integration/ tree
```

CI (`.github/workflows/ci.yml`) runs lint → unit tests → integration tests →
Docker build on every push.

## Deployment

Deploys to [Render](https://render.com) via the Blueprint at
[`render.yaml`](render.yaml): a free Web Service running `docker/Dockerfile`
plus a free managed Postgres database, wired together automatically.

**This repo has no Render account or API credentials attached to it** — the
steps below need to be run once, by hand, from the Render dashboard (repo
connection is an OAuth flow; there's no headless equivalent).

### 1. First deploy

1. Push this repo to GitHub (already done if you're reading this from GitHub).
2. In the [Render dashboard](https://dashboard.render.com), **New +** →
   **Blueprint**, connect the GitHub repo. Render reads `render.yaml` and
   proposes one Web Service (`case-law-search-api`) + one Postgres database
   (`case-law-db`), both free tier. Confirm.
3. Render provisions the database first, then builds the Docker image from
   `docker/Dockerfile`, then runs `alembic upgrade head` as the pre-deploy
   command (this creates all tables *and* runs `CREATE EXTENSION IF NOT
   EXISTS vector`, per migration `0001`), then starts
   `gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000`.
4. **Verify pgvector is actually available**: Render's managed Postgres
   supports the `vector` extension, but this hasn't been confirmed against
   a live instance from this environment (no Docker/Postgres access here —
   see `docs/data_pipeline.md`). If the pre-deploy migration step fails on
   `CREATE EXTENSION vector`, check Render's Postgres extension list for
   your plan; the fallback is running Postgres as a second Docker-based
   private service (`pgvector/pgvector:pg15`, same image CI already uses)
   instead of Render's managed database.
5. Once live, health checks hit `GET /health` (a plain `{"status": "ok"}`
   route — lighter than `GET /docs`, which renders the full Swagger UI on
   every check).

### 2. Seed data

The free web service has no room to download a corpus, embed it, *and* serve
traffic within a build/pre-deploy step — and `data/staging/` (the parquet
this repo's ingestion pipeline reads) isn't committed (550MB, gitignored).
Seed from your own machine instead, which already has the model cached and
the corpus staged locally:

```bash
# find the External Database URL on the case-law-db page in the Render
# dashboard -- looks like postgresql://user:pass@host.render.com/db
DATABASE_URL="<paste External Database URL>" \
  uv run python scripts/ingest_judgments.py --source data/staging --limit 100
```

`app/config.py` normalizes a plain `postgres://`/`postgresql://` URL (what
Render hands back) to the `postgresql+psycopg://` form SQLAlchemy needs —
no manual edit required. Drop `--limit 100` to seed the full corpus instead
(expect several hours; see `data/ingestion_metrics.json` for real per-chunk
timing from the full run).

### 3. Environment variables

`DATABASE_URL` and `EMBEDDING_MODEL` are wired automatically by
`render.yaml`. Set `CORS_ORIGINS` by hand in the Render dashboard once the
frontend has a real URL (Environment tab, e.g.
`CORS_ORIGINS=https://your-app.vercel.app`) — left unset in the Blueprint
since no committed value should assume a specific deployment.

### 4. Verifying the live deployment

Once deployed, from your own machine:

```bash
curl https://<your-service>.onrender.com/health
curl -X POST https://<your-service>.onrender.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "oppression and mismanagement of a company"}'
curl https://<your-service>.onrender.com/judgments/1
```

Two things worth measuring and recording here once you have a live URL,
rather than assumed: actual `/search` latency (the free-tier instance has a
fraction of a dev machine's CPU, so real numbers may differ from the
embedding-latency figures above, which were measured locally), and cold-start
latency after the free tier's idle spin-down (Render free services sleep
after 15 minutes of no traffic; the next request pays a rebuild-container
cost typically in the tens of seconds).

## Roadmap

- [x] Schema + migrations (Alembic, HNSW + GIN indexes)
- [x] Hybrid search module (RRF, framework-agnostic)
- [x] Two endpoints, ~25 unit tests, integration test on real Postgres
- [x] Docker + docker-compose (app, db)
- [x] CI: lint → test → build
- [x] Production ingestion CLI with real metrics (`scripts/ingest_judgments.py`, `docs/data_pipeline.md`)
- [x] Search UI (`web/`, Next.js + shadcn/ui) — search, filters, judgment detail panel, dark mode, mock demo mode
- [ ] Week 1: ~500–1,000 judgments ingested end-to-end, CI green on a pushed branch
- [ ] Week 2–3: full ~41.8K-judgment corpus ingested as an offline batch job
- [ ] Deployed to Render + Supabase with a live URL, `web/` deployed alongside it
- [ ] Later: auth (schema already has a `users` table for it)

## License

Code: MIT (or your preferred license — not yet chosen).
Data: see [`docs/data_sources.md`](docs/data_sources.md) — one source dataset
is CC-BY-NC-SA-4.0 (non-commercial).
