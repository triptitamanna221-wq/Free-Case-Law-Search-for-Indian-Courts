"""Production ingestion CLI: staged judgments -> chunks -> embeddings -> Postgres,
with per-run metrics written for CV/benchmarking purposes.

Data source: real Indian court judgments via `scripts/download_datasets.py`
(the `opennyaiorg/InJudgements_dataset` HuggingFace dataset -- itself built by
academically scraping Indian Kanoon; see docs/data_sources.md). Indian Kanoon's
own API is paid/metered with no key available here, so --source-type api is a
documented stub, not a silent mock -- run download_datasets.py first instead.

Usage:
    uv run python scripts/download_datasets.py --dataset injudgements
    uv run python scripts/ingest_judgments.py --source data/staging --limit 200
    uv run python scripts/ingest_judgments.py --source data/staging --dry-run --limit 20

Every metric in data/ingestion_metrics.json comes from an actual run of this
script -- there is no synthetic/estimated fallback path.
"""

from __future__ import annotations

import argparse
import gc
import itertools
import json
import logging
import os
import platform
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

import psutil
from sentence_transformers import SentenceTransformer
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from tqdm import tqdm

from app.db.models import Chunk
from app.db.session import SessionLocal
from app.ingestion.chunking import chunk_text
from app.ingestion.embedder import BATCH_SIZE, EMBEDDING_MODEL_NAME, embed_texts
from app.ingestion.loaders import RawJudgment, iter_staged_judgments, upsert_judgments

logger = logging.getLogger("ingest_judgments")

T = TypeVar("T")

DEFAULT_JUDGMENT_BATCH_SIZE = int(os.environ.get("JUDGMENT_BATCH_SIZE", "100"))
DEFAULT_CHUNK_SIZE_TOKENS = 512
DEFAULT_CHUNK_OVERLAP_TOKENS = 256
DEFAULT_MAX_RETRIES = 3


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments, with env-var fallbacks for values that also make
    sense as deployment config (DATABASE_URL is read separately by app.config)."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(os.environ.get("INGEST_SOURCE", "data/staging")),
        help="Staged parquet file or directory (see scripts/download_datasets.py).",
    )
    parser.add_argument(
        "--source-type",
        choices=["local", "api"],
        default="local",
        help="'api' is a documented stub (no Indian Kanoon API key available); use 'local'.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of judgments processed.")
    parser.add_argument(
        "--judgment-batch-size",
        type=int,
        default=DEFAULT_JUDGMENT_BATCH_SIZE,
        help="Judgments per DB transaction (default: %(default)s).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.environ.get("BATCH_SIZE", str(BATCH_SIZE))),
        help="Chunk texts per model.encode() call (default: %(default)s).",
    )
    parser.add_argument(
        "--embedding-model",
        default=os.environ.get("EMBEDDING_MODEL", EMBEDDING_MODEL_NAME),
        help="sentence-transformers model name (default: %(default)s).",
    )
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE_TOKENS)
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP_TOKENS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chunk and embed but never touch the database -- isolates embedding "
        "throughput/latency from DB variance.",
    )
    parser.add_argument("--metrics-path", type=Path, default=Path("data/ingestion_metrics.json"))
    return parser.parse_args(argv)


def with_retries(
    func: Callable[[], T],
    *,
    max_attempts: int,
    retry_on: tuple[type[Exception], ...],
    on_retry: Callable[[], None] | None = None,
    base_delay_s: float = 1.0,
    description: str = "operation",
) -> T:
    """Retry `func` with exponential backoff on transient failures. Used for DB
    batch writes here; the same shape applies to a future live API source
    (transient HTTP errors), which is why retry_on/description are parameters
    rather than hardcoded to SQLAlchemy's OperationalError.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except retry_on as exc:
            last_exc = exc
            logger.warning("%s failed (attempt %d/%d): %s", description, attempt, max_attempts, exc)
            if on_retry is not None:
                on_retry()
            if attempt < max_attempts:
                time.sleep(base_delay_s * (2 ** (attempt - 1)))
    assert last_exc is not None
    raise last_exc


def _batched(iterable: Iterable[T], size: int) -> Iterator[list[T]]:
    it = iter(iterable)
    while batch := list(itertools.islice(it, size)):
        yield batch


def _peak_rss_mb() -> float:
    """Historical peak resident set size since process start (a high-water
    mark that doesn't decrease -- distinct from _current_rss_mb below)."""
    try:
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak / (1024 * 1024) if platform.system() == "Darwin" else peak / 1024
    except ImportError:  # pragma: no cover - resource is POSIX-only
        return _current_rss_mb()


def _current_rss_mb() -> float:
    return psutil.Process().memory_info().rss / (1024 * 1024)


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * (pct / 100)
    lo, hi = int(k), min(int(k) + 1, len(sorted_values) - 1)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


@dataclass
class LatencyStats:
    """Per-sample latency tracker. Percentiles are computed across whatever
    unit the caller records (see IngestionMetrics for what a "sample" means
    for embedding vs. DB latency)."""

    samples_ms: list[float] = field(default_factory=list)

    def record(self, ms: float) -> None:
        self.samples_ms.append(ms)

    def summary(self) -> dict[str, float | int | None]:
        if not self.samples_ms:
            return {"count": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None, "max_ms": None}
        ordered = sorted(self.samples_ms)
        return {
            "count": len(ordered),
            "mean_ms": round(sum(ordered) / len(ordered), 3),
            "p50_ms": round(_percentile(ordered, 50), 3),
            "p95_ms": round(_percentile(ordered, 95), 3),
            "max_ms": round(ordered[-1], 3),
        }


@dataclass
class IngestionMetrics:
    embedding_model: str
    embedding_dim: int
    dry_run: bool
    chunk_size_tokens: int
    chunk_overlap_tokens: int
    judgments_processed: int = 0
    chunks_embedded: int = 0
    total_tokens: int = 0
    skipped_malformed: int = 0
    failed_batches: int = 0
    total_runtime_s: float = 0.0
    peak_memory_mb: float = 0.0
    memory_after_cleanup_mb: float = 0.0
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    # embedding latency is recorded as (batch wall-clock / chunks in that batch):
    # embedding always runs as one batched model.encode() call per judgment
    # batch, so a true per-chunk-isolated timing isn't observable without
    # defeating the batching this pipeline is built around. Each sample below
    # is therefore one judgment-batch's average per-chunk cost.
    embedding_latency_ms_per_chunk: LatencyStats = field(default_factory=LatencyStats)
    db_batch_latency_ms: LatencyStats = field(default_factory=LatencyStats)
    db_latency_ms_per_record: LatencyStats = field(default_factory=LatencyStats)

    def record_embedding_batch(self, n_chunks: int, elapsed_ms: float) -> None:
        self.chunks_embedded += n_chunks
        if n_chunks:
            self.embedding_latency_ms_per_chunk.record(elapsed_ms / n_chunks)

    def record_db_batch(self, n_judgments: int, elapsed_ms: float) -> None:
        self.db_batch_latency_ms.record(elapsed_ms)
        if n_judgments:
            self.db_latency_ms_per_record.record(elapsed_ms / n_judgments)

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim,
            "dry_run": self.dry_run,
            "chunk_size_tokens": self.chunk_size_tokens,
            "chunk_overlap_tokens": self.chunk_overlap_tokens,
            "judgments_processed": self.judgments_processed,
            "chunks_embedded": self.chunks_embedded,
            "total_tokens": self.total_tokens,
            "skipped_malformed": self.skipped_malformed,
            "failed_batches": self.failed_batches,
            "total_runtime_s": round(self.total_runtime_s, 2),
            "peak_memory_mb": round(self.peak_memory_mb, 1),
            "memory_after_cleanup_mb": round(self.memory_after_cleanup_mb, 1),
            "embedding_latency_ms_per_chunk": self.embedding_latency_ms_per_chunk.summary(),
            "db_insert_latency_ms_per_batch": self.db_batch_latency_ms.summary(),
            "db_insert_latency_ms_per_record": self.db_latency_ms_per_record.summary(),
        }


def process_batch(
    db: Session | None,
    batch: list[RawJudgment],
    model: SentenceTransformer,
    args: argparse.Namespace,
    metrics: IngestionMetrics,
) -> None:
    """Chunk + embed one judgment batch, then (unless --dry-run) write it in a
    single DB transaction: judgments upserted first, then chunk rows carrying
    their already-computed embeddings. On failure the whole batch is rolled
    back and skipped -- one bad batch doesn't abort a 500-judgment run.
    """

    def token_counter(s: str) -> int:
        return len(model.tokenizer.encode(s, add_special_tokens=False))

    valid_rows: list[RawJudgment] = []
    chunk_texts: list[str] = []
    chunk_owners: list[tuple[str, str, int]] = []  # (source_dataset, external_id, chunk_index)
    for row in batch:
        pieces = chunk_text(
            row.raw_text,
            chunk_size=args.chunk_size,
            overlap=args.chunk_overlap,
            token_counter=token_counter,
        )
        if not pieces:
            logger.warning(
                "Judgment %s produced no chunks (empty/whitespace text); skipping entirely", row.external_id
            )
            metrics.skipped_malformed += 1
            continue
        valid_rows.append(row)
        for index, piece in enumerate(pieces):
            chunk_texts.append(piece)
            chunk_owners.append((row.source_dataset, row.external_id, index))
            metrics.total_tokens += token_counter(piece)

    if not chunk_texts:
        logger.warning("Batch produced zero usable chunks; skipping")
        return

    embed_start = time.perf_counter()
    vectors = embed_texts(chunk_texts, model=model, batch_size=args.batch_size, show_progress_bar=True)
    embed_elapsed_ms = (time.perf_counter() - embed_start) * 1000
    metrics.record_embedding_batch(len(chunk_texts), embed_elapsed_ms)
    metrics.judgments_processed += len(valid_rows)

    if args.dry_run:
        logger.info(
            "[dry-run] %d judgments -> %d chunks embedded in %.1fms (%.2fms/chunk)",
            len(valid_rows),
            len(chunk_texts),
            embed_elapsed_ms,
            embed_elapsed_ms / len(chunk_texts),
        )
        return

    def _write_batch() -> None:
        ids = upsert_judgments(db, valid_rows)
        chunk_rows = [
            Chunk(
                judgment_id=ids[(source_dataset, external_id)],
                chunk_index=chunk_index,
                text=chunk_texts[i],
                embedding=vectors[i],
            )
            for i, (source_dataset, external_id, chunk_index) in enumerate(chunk_owners)
            if (source_dataset, external_id) in ids
        ]
        db.add_all(chunk_rows)
        db.commit()

    db_start = time.perf_counter()
    try:
        with_retries(
            _write_batch,
            max_attempts=args.max_retries,
            retry_on=(OperationalError,),
            on_retry=db.rollback,
            description="db batch write",
        )
    except Exception:
        db.rollback()
        logger.error(
            "Batch of %d judgments failed after %d retries; skipping",
            len(valid_rows),
            args.max_retries,
            exc_info=True,
        )
        metrics.failed_batches += 1
        return
    db_elapsed_ms = (time.perf_counter() - db_start) * 1000
    metrics.record_db_batch(len(valid_rows), db_elapsed_ms)


def write_metrics(metrics: IngestionMetrics, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics.to_dict(), indent=2) + "\n")
    logger.info("Wrote metrics to %s", path)


def print_summary(metrics: IngestionMetrics) -> None:
    d = metrics.to_dict()
    line = "=" * 60
    print(f"\n{line}\nINGESTION SUMMARY{'  [DRY RUN]' if d['dry_run'] else ''}\n{line}")
    for label, value in [
        ("Judgments processed", d["judgments_processed"]),
        ("Chunks embedded", d["chunks_embedded"]),
        ("Total tokens", d["total_tokens"]),
        ("Skipped (malformed)", d["skipped_malformed"]),
        ("Failed batches", d["failed_batches"]),
        ("Total runtime (s)", f"{d['total_runtime_s']:.2f}"),
        ("Peak memory (MB)", f"{d['peak_memory_mb']:.1f}"),
        ("Memory after cleanup (MB)", f"{d['memory_after_cleanup_mb']:.1f}"),
    ]:
        print(f"  {label:<28}{value:>15}")
    print(f"{'-' * 60}\nEmbedding latency (ms/chunk, per-batch average):")
    for k, v in d["embedding_latency_ms_per_chunk"].items():
        print(f"  {k:<12}{v}")
    if not d["dry_run"]:
        print(f"{'-' * 60}\nDB insert latency (ms/record):")
        for k, v in d["db_insert_latency_ms_per_record"].items():
            print(f"  {k:<12}{v}")
    print(line)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    args = parse_args(argv)

    if args.source_type == "api":
        raise NotImplementedError(
            "Live API ingestion isn't wired up: Indian Kanoon's own API is paid/metered "
            "and no key is available in this environment. Run "
            "`uv run python scripts/download_datasets.py` to pull real Indian "
            "Kanoon-sourced judgments via an open academic dataset, then use "
            "--source-type local (the default) against its output."
        )

    if not args.source.exists():
        raise FileNotFoundError(
            f"--source {args.source} does not exist. This CLI reads staged parquet written by "
            "`uv run python scripts/download_datasets.py` -- run that first, then point --source "
            "at its output (default: data/staging). '--source hf' or similar shorthand isn't "
            "supported: there's no single step that both downloads and ingests."
        )

    logger.info("Loading embedding model: %s", args.embedding_model)
    model = SentenceTransformer(args.embedding_model)
    embedding_dim = model.get_embedding_dimension()
    logger.info("Model loaded. Embedding dimension: %d", embedding_dim)

    metrics = IngestionMetrics(
        embedding_model=args.embedding_model,
        embedding_dim=embedding_dim,
        dry_run=args.dry_run,
        chunk_size_tokens=args.chunk_size,
        chunk_overlap_tokens=args.chunk_overlap,
    )

    rows = list(iter_staged_judgments(args.source, args.limit))
    if not rows:
        raise RuntimeError(
            f"--source {args.source} exists but yielded 0 usable judgments. Check it actually "
            "contains .parquet file(s) with a non-empty raw_text column -- refusing to write a "
            "misleadingly 'successful' all-zero metrics file."
        )
    logger.info("Loaded %d staged judgments from %s", len(rows), args.source)

    db = None if args.dry_run else SessionLocal()
    run_start = time.perf_counter()
    try:
        for batch in tqdm(
            list(_batched(rows, args.judgment_batch_size)), desc="Ingesting judgment batches", unit="batch"
        ):
            process_batch(db, batch, model, args, metrics)
    finally:
        if db is not None:
            db.close()

    metrics.total_runtime_s = time.perf_counter() - run_start
    metrics.peak_memory_mb = _peak_rss_mb()

    del model
    gc.collect()
    metrics.memory_after_cleanup_mb = _current_rss_mb()

    write_metrics(metrics, args.metrics_path)
    print_summary(metrics)


if __name__ == "__main__":
    main()
