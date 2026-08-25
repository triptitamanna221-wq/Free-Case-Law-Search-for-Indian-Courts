# Data pipeline

Two scripts, run in sequence: pull real judgments from Hugging Face into
staging parquet, then chunk + embed + insert them into Postgres.

```bash
# 1. Download (or re-download) staged judgment data
uv run python scripts/download_datasets.py --max-rows 500   # fast local sample
uv run python scripts/download_datasets.py                  # full ~41.8K corpus

# 2. Ingest: chunk -> embed -> insert, with metrics
uv run python scripts/ingest_judgments.py --source data/staging --limit 200
uv run python scripts/ingest_judgments.py --source data/staging --dry-run --limit 20  # embedding-only smoke test, no DB
```

See [`docs/data_sources.md`](data_sources.md) for where the data comes from
and why.

## `scripts/download_datasets.py`

Downloads `sinhal/Indian_Supreme_Court_Judgments` from Hugging Face (JSONL,
no auth required) and normalizes it into `data/staging/supreme_court.parquet`
matching the common staging schema both ingestion scripts read
(`source_dataset`, `external_id`, `title`, `raw_text`, `source_url`, `court`,
`case_type`, `decision_date`, `judges`, `petitioner`, `respondent`). Streams
and writes incrementally (2000 rows/flush) rather than loading the whole
corpus into memory at once. `--max-rows N` caps the download for a fast local
sample instead of the full corpus.

## `scripts/ingest_judgments.py`

The production ingestion CLI. For each judgment batch (`--judgment-batch-size`,
default 100):

1. **Chunk**: `app.ingestion.chunking.chunk_text` splits each judgment's
   `raw_text` into overlapping, sentence-boundary-aware chunks
   (`--chunk-size`/`--chunk-overlap`, default 512/256 tokens), counted by the
   embedding model's real tokenizer (`model.tokenizer.encode`), not an
   approximation. A judgment that yields zero chunks (empty/whitespace text)
   is logged and skipped entirely — never written to the DB with zero chunks.
2. **Embed**: all chunks in the batch are embedded in one `model.encode()`
   call (`--batch-size`, default 64) — batched to bound memory and because
   one model call per chunk would be far slower than the model's own internal
   batching.
3. **Insert**: (skipped entirely under `--dry-run`) judgments are upserted
   first (idempotent on `(source_dataset, external_id)` — re-running never
   duplicates), then chunk rows are inserted carrying their already-computed
   embeddings, all in one transaction per judgment batch. A failed batch
   retries with backoff (`--max-retries`, transient `OperationalError` only)
   before being rolled back and skipped — one bad batch doesn't abort a
   500-judgment run.

### Metrics

Every run writes `data/ingestion_metrics.json`: judgment/chunk/token counts,
skipped/failed counts, total runtime, peak and post-cleanup memory (RSS), and
embedding/DB-insert latency (mean/p50/p95/max). Embedding latency is recorded
as *(batch wall-clock ÷ chunks in that batch)* — one sample per judgment
batch — since embedding always runs as a single batched model call, not one
call per chunk; a true per-chunk-isolated timing isn't observable without
defeating the batching the pipeline is built around. A human-readable summary
table prints at the end of every run.

`--dry-run` produces real embedding-latency numbers (it runs the actual model)
without touching the database, useful for isolating embedding throughput from
DB variance, or for environments without a running Postgres.

### `--source-type api`

A documented stub, not a silent mock: Indian Kanoon's own API is paid/metered
and no key is available in this project's environment. It raises
`NotImplementedError` pointing at `--source-type local` (the default) instead.

## Testing

```bash
uv run pytest tests/unit/test_chunking.py           # chunking, incl. token_counter injection
uv run pytest tests/integration/test_ingestion.py    # end-to-end against real Postgres
uv run pytest -m integration                         # every DB-marked test across the suite
```

`tests/integration/test_ingestion.py` uses a fake embedding model (whitespace
tokenizer, fixed-dimension vectors) so these tests stay fast and independent
of model weights — the real model's actual behavior is covered separately by
`tests/integration/test_search_endpoint.py` and by `--dry-run` runs against
real data. Covers: end-to-end ingest of 10 judgments (verifying DB counts and
that structured metadata — petitioner/respondent/judges/court — actually
lands), a malformed (empty-text) judgment being skipped entirely rather than
stored chunk-less, idempotent re-ingestion of a duplicate
`(source_dataset, external_id)`, and the retry helper recovering from /
exhausting on transient failures.
