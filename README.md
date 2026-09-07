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

**Live demo:** <https://free-case-law-search-for-indian-cou-tau.vercel.app>
(API: <https://case-law-search-api.onrender.com/docs>)

Try the query the keyword half can't answer — *"a company run into the ground
by its own directors"* — and note the result matches on the semantic path with
no shared vocabulary at all:

```bash
curl -X POST https://case-law-search-api.onrender.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "a company run into the ground by its own directors", "search_mode": "semantic"}'
```

Two caveats worth stating plainly, since they're visible to anyone who opens
the link: it's seeded with an **800-judgment sample**, not the full 41.8K corpus
(Neon's free tier caps at 0.5GB and 800 judgments already use 167MB), and the
**first request after ~15 minutes idle takes up to 2 minutes** while Render
wakes the free container. Everything after that is fast.

Frontend on Vercel, API on Render, Postgres on Neon — all free tiers, no card.

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
| Corpus processed | **41,839 judgments / 883,787 chunks** (427.4M tokens) — the full dataset, chunked + embedded end-to-end (`data/ingestion_metrics.json`). This run was `--dry-run`: embeddings computed and measured, not written to a database |
| Corpus **live** | **800 judgments / 16,287 chunks**, all embedded, in the deployed Neon database. Not the full corpus — Neon's free tier caps at 0.5GB and 800 judgments already occupy 167MB, so the whole thing needs a paid plan, not more code |
| Embedding latency (p50 / p95, ms/chunk) | **9.4 / 13.3** (n=20 batches, `data/seed_metrics_neon.json`) |
| DB insert latency (p50 / p95, per judgment) | **1118ms / 1389ms** (n=20) — a judgment row plus ~20 chunk rows each carrying a 384-dim vector. Measured writing from a laptop in India to `us-west-2`, so this is dominated by round-trip distance and says more about the link than the schema |
| Citations extracted | **490 rows across 190 judgments** (AIR 461 / SCR 26 / SCC 3), of which **8 resolve to another judgment in the corpus**. The low resolution rate is expected, not a defect: with 800 of 41,839 judgments loaded, a cited case is rarely also in the sample |
| Search latency, deployed | **~30ms hybrid, ~15ms semantic, ~4ms keyword** — measured against the live service |
| Test coverage | **64%** across the DB-free suites (`uv run pytest tests/unit tests/models --cov`, 46 tests). The uncovered remainder is the API/schema layer, exercised by `tests/integration` against real Postgres in CI |
| Cold start, deployed (Render free) | **~2 min** for the first request after an idle spin-down: Render sleeps free containers after 15 minutes, and the container doesn't accept traffic until `lifespan` has loaded the onnx session. Warm requests are unaffected |
| Serving memory peak | **~290MB** (onnxruntime path) vs **351MB** (torch), against a 512MB container — see the onnx bullet under [Why these choices](#why-these-choices) |

Every figure above is from an actual run against the real system. Nothing is
estimated or extrapolated; where something couldn't be measured it says so
rather than carrying a plausible-looking number.

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
- **Render for the app, Neon for Postgres — not Render for both.** The
  original setup used Render's own free Postgres and had to be migrated off
  it: that database is deleted **30 days after creation**, on a fixed clock
  rather than an activity one, so no keep-alive query prevents it. For a link
  an interviewer opens weeks after an application goes out, a database with an
  expiry date is the wrong foundation. Neon's free tier doesn't expire and
  resumes from scale-to-zero by itself. The cost is one more dashboard and a
  `DATABASE_URL` that is set by hand rather than wired by the Blueprint —
  deliberately `sync: false` in `render.yaml`, so a blueprint re-sync can't
  silently repoint production back at the expiring database.
- **Both regions pinned to US-West.** Render defaults to Oregon; the first
  Neon project was created in `us-east-2`, which put a cross-country hop in
  the path of every query — a hybrid search makes several round trips, and
  deployed latency rose from ~30ms to ~218ms. Re-creating the database in
  `us-west-2` was a five-minute fix for a 7x regression, and is the kind of
  thing that is invisible until measured.
- **Fly.io was evaluated twice and rejected both times.** Its widely-cited
  "3 VMs + 3GB Postgres free tier" was withdrawn for new accounts in 2024;
  what remains is a 2-hour/7-day trial, then a mandatory card and ~$2–5/mo.
  For a project whose premise is being free, that's a worse trade than the
  cold starts documented above.

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
   proposes one Web Service (`case-law-search-api`). It declares **no**
   database: Postgres lives on Neon (see [Why these choices](#why-these-choices)),
   so create a free project at [neon.com](https://neon.com) — pick a
   **US-West** region to sit beside Render's Oregon default — and paste its
   connection string into `DATABASE_URL` in the service's Environment tab.
3. Render builds the Docker image from
   `docker/Dockerfile`, then starts
   `gunicorn -w 1 --timeout 120 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000`
   (single worker, generous timeout — see the comment in `render.yaml` for
   why: Render's free instance is 512MB RAM / 0.1 CPU, and the embedding
   model is loaded once *per worker*, so worker count multiplies the biggest
   cost in the container). `app/main.py`'s `lifespan` hook warms the onnx
   session during boot, so the first visitor after an idle spin-down doesn't
   pay session init on top of Render's own ~1 minute wake-up. If you ever
   see the container restart with no traceback and gunicorn coming back at
   pid 1, suspect memory before timeouts — that signature is a kernel OOM
   kill, not an application error.
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
# the Neon connection string, from the project dashboard -- looks like
# postgresql://user:pass@ep-xxx.us-west-2.aws.neon.tech/neondb?sslmode=require
export DATABASE_URL="<paste Neon connection string>"
cd ~/Free-Case-Law-Search-for-Indian-Courts
uv run alembic upgrade head
```

This creates all tables and runs `CREATE EXTENSION IF NOT EXISTS vector`
(part of migration `0001`) against the real Neon database.
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
uv run python scripts/ingest_judgments.py --source data/staging --limit 100 --batch-size 32 \
  --metrics-path data/seed_metrics_neon.json
```

Pass `--metrics-path`. Without it the run writes to `data/ingestion_metrics.json`
and overwrites the full-corpus figures recorded there (41,839 judgments /
883,787 chunks) with this sample — they're separate results and both worth
keeping.

**Keep the `--limit`** — don't drop it to seed the full corpus. Neon's free
tier has a **hard 0.5GB cap**, and measured against the real database a
judgment costs ~209KB once its chunks, embeddings, tsvectors and the HNSW
index are counted. 800 judgments occupy 167MB; the ceiling is roughly 2,400.
The full 41,839-judgment corpus produces 883,787 chunks whose embeddings
alone (883,787 × 384 floats × 4 bytes ≈ 1.3GB) exceed the cap several times
over before any text is stored, so a full-corpus run fails partway through on
disk-full after burning hours getting there. That's a plan limit, not a code
limit — the same command loads the whole corpus against a database sized for
it.

Then build the citation graph, which needs the corpus already loaded:

```bash
uv run python scripts/build_citations.py
```

### 5. Environment variables

`EMBEDDING_MODEL` is set by `render.yaml`. `DATABASE_URL` is **not** — it's
marked `sync: false` and set by hand in the Render dashboard to the Neon
connection string, deliberately, so that a blueprint re-sync can't silently
repoint production at a different database.

`CORS_ORIGINS` can stay unset for the `web/` frontend. The browser never calls
this API directly — it calls the Next.js app's own same-origin `/api/*` routes,
which proxy server-side (see [`web/README.md`](web/README.md)). Set it only if
something else needs to reach the API from a browser.

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
- [x] Backend deployed to Render with a live URL, migrations applied, 800
      judgments seeded, `/search` and `/judgments/{id}` verified against it
- [x] Citation extraction populating the `citations` table (490 rows, 190
      judgments, 8 resolved within the corpus)
- [x] Full ~41.8K-judgment corpus chunked + embedded end-to-end (`--dry-run`:
      embed-only, measured, not written to a database)
- [ ] Full corpus *loaded into* Postgres — blocked on storage, not code: the
      embeddings alone are ~1.3GB against Neon free's 0.5GB cap, so this needs
      a paid database plan rather than further work here
- [x] `web/` deployed to Vercel and wired to the live API — verified in a real
      browser against the deployed URL (results render, detail panel opens, no
      mock fallback, zero console errors or failed requests)
- [ ] Later: auth (schema already has a `users` table for it)

## License

Code: MIT (or your preferred license — not yet chosen).
Data: see [`docs/data_sources.md`](docs/data_sources.md) — one source dataset
is CC-BY-NC-SA-4.0 (non-commercial).
