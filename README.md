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
- **onnxruntime for serving, sentence-transformers for ingestion.** Same
  model (`all-MiniLM-L6-v2`), same weights, same 384-dim vectors — but the
  API process never imports torch. This wasn't a micro-optimization: the
  torch serving path peaks at ~350MB RSS in a single worker, ~315MB of which
  is `import torch` before any weights load, against a 512MB container. The
  kernel OOM-killed the container on every `/search`. Ingestion keeps the
  torch path, since it runs on a laptop with no memory ceiling and its output
  is already in the database. `tests/models/` asserts the two paths agree to
  cosine > 0.9999 (observed max difference ~1e-7) and that the serving path
  never pulls torch back in.
- **An open HF dataset, not scraping Indian Kanoon directly.** See
  [`docs/data_sources.md`](docs/data_sources.md) for the full reasoning and
  history (including a pivot away from two originally-planned datasets that
  turned out to require HuggingFace auth) — short version: no free bulk API,
  ToS-questionable at 50K-document scale, and a bare scraper loop isn't
  itself something worth shipping.
- **Render for both the app and Postgres.** One dashboard, one Blueprint
  (`render.yaml`), no cross-provider networking to debug. The real tradeoff:
  Render's free Postgres expires **30 days after creation** — a fixed clock,
  not activity-based, so a keep-alive query wouldn't prevent it — with a
  14-day grace period to upgrade before it's permanently deleted. A genuine
  risk for a demo link opened weeks after an application goes out. See
  [Deployment](#deployment) for the plan: re-run the Blueprint and reseed
  (a few minutes of work, not a rebuild) shortly before the 30-day mark, or
  upgrade the database to a paid plan once this is the one you're keeping.

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
uv run pytest tests/models        # onnx vs sentence-transformers equivalence (no DB)
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
   `docker/Dockerfile`, then starts
   `gunicorn -w 1 --timeout 120 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000`
   (single worker, generous timeout — see the comment in `render.yaml` for
   why: Render's free instance is 512MB RAM / 0.1 CPU, and the embedding
   model is loaded once *per worker*, so worker count multiplies the biggest
   cost in the container). The model loads lazily, on the first `/search`
   request; at ~290MB peak for the onnx path there's headroom for that,
   where the torch path had none. If you ever see the container restart with
   no traceback and gunicorn coming back at pid 1, suspect memory before
   timeouts — that signature is a kernel OOM kill, not an application error.
   **The service comes up with no tables yet** — free web services can't run
   a pre-deploy command (see "Manual Migrations" below), so this is a
   required manual step, not optional cleanup.
4. Once live, health checks hit `GET /health` (a plain `{"status": "ok"}`
   route — lighter than `GET /docs`, which renders the full Swagger UI on
   every check). It doesn't touch the database, so it going green is not
   confirmation the schema exists; `/search` returning 500 instead of an
   empty result set is the real signal migrations haven't run (step 3).

### 2. Manual migrations

Render restricts `preDeployCommand` to paid web services, private services,
and background workers — free web services aren't eligible, confirmed
against Render's own docs. So migrations have to be triggered by hand, once,
right after the first deploy (and again after any future migration is added).

**Do not** work around this with an `@app.on_event("startup")` hook in
`app/main.py`, even though `render.yaml` runs a single gunicorn worker today
(`-w 1` — see the comment there for why: Render's free instance is 512MB
RAM / 0.1 CPU, too little to load the embedding model once per worker at
`-w 4`). A startup hook ties migration success to every container
start/restart instead of one controlled, observable step, and would
reintroduce a real race — migrations running concurrently across worker
processes — the moment worker count goes back above one. Run migrations
from exactly one place, one time, by hand.

**Method A — from your local machine (recommended: no Render plan
restriction, and reuses `app/config.py`'s URL handling):**

```bash
# find the External Database URL on the case-law-db page in the Render
# dashboard -- looks like postgres://user:pass@host.render.com/db
export DATABASE_URL="<paste External Database URL>"
cd ~/Free-Case-Law-Search-for-Indian-Courts
uv run alembic upgrade head
```

This creates all tables and runs `CREATE EXTENSION IF NOT EXISTS vector`
(part of migration `0001`) against the real Render database.
`app/config.py` normalizes the plain `postgres://`/`postgresql://` URL
Render hands back to the `postgresql+psycopg://` form SQLAlchemy needs — no
manual edit required.

**Method B — via Render's dashboard Shell:** not available here — Shell/SSH
access is restricted to paid instance types (confirmed against Render's
docs), same restriction as `preDeployCommand`. It becomes an option only if
the web service is upgraded off the free tier; Method A works regardless of
plan, so it's the one to use.

**Verify pgvector is actually available** the first time you run this: if it
fails on `CREATE EXTENSION vector`, check Render's Postgres extension list
for your plan — the fallback is running Postgres as a second Docker-based
private service (`pgvector/pgvector:pg15`, same image CI already uses)
instead of Render's managed database.

### 3. Validate the deployment

```bash
curl https://<your-service>.onrender.com/health
# {"status":"ok"} -- confirms the app is up, not that migrations ran

curl -X POST https://<your-service>.onrender.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "oppression and mismanagement of a company", "search_mode": "hybrid"}'
# a 500 here means migrations haven't run yet (tables don't exist) --
# go back to step 2. A 200 with "results": [] is expected and fine at this
# point: migrations succeeded, there's just no data until "Seed data" runs.
```

### 4. Seed data

The free web service has no room to download a corpus, embed it, *and* serve
traffic within a build step — and `data/staging/` (the parquet this repo's
ingestion pipeline reads) isn't committed (550MB, gitignored). Seed from
your own machine instead, which already has the model cached and the corpus
staged locally:

```bash
export DATABASE_URL="<paste External Database URL>"
uv run python scripts/ingest_judgments.py --source data/staging --limit 100 --batch-size 32
```

**Keep `--limit 100`** — don't drop it to seed the full corpus. Render's
free Postgres has a **fixed 1GB storage cap**; the full 41,839-judgment
corpus produces 883,787 chunks, and the embeddings alone
(883,787 × 384 floats × 4 bytes ≈ 1.3GB) already exceed that on their own,
before raw text, indexes, or the HNSW index's own overhead. A full-corpus
run against this database would fail partway through on disk-full, after
burning real time getting there. 100 judgments (~2,000 chunks, well under
the cap) is enough to prove the deployed pipeline end-to-end; a bigger
sample only makes sense on a paid Postgres plan sized for it.

### 5. Environment variables

`DATABASE_URL` and `EMBEDDING_MODEL` are wired automatically by
`render.yaml`. Set `CORS_ORIGINS` by hand in the Render dashboard once the
frontend has a real URL (Environment tab, e.g.
`CORS_ORIGINS=https://your-app.vercel.app`) — left unset in the Blueprint
since no committed value should assume a specific deployment.

### 6. Post-seed validation

Once seeded, re-run the `/search` call from step 3 — it should now return
real ranked results instead of an empty/error response — and check
retrieval by id:

```bash
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
