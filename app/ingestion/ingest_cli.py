"""Single ingestion entrypoint. The week-1 500-judgment smoke run and the eventual
~48K-judgment scale-up run are the same code path — only --limit differs.

Usage:
    uv run python -m app.ingestion.ingest_cli --limit 500
    uv run python -m app.ingestion.ingest_cli --stage embed-only
"""

import argparse
import logging
from pathlib import Path

import pyarrow.parquet as pq

from app.db.session import SessionLocal
from app.ingestion.loaders import (
    RawJudgment,
    chunk_pending_judgments,
    embed_pending_chunks,
    upsert_judgments,
)

logger = logging.getLogger(__name__)

DEFAULT_STAGING_DIR = Path("data/staging")


def _iter_staged_rows(staging_dir: Path, limit: int | None):
    yielded = 0
    for parquet_file in sorted(staging_dir.glob("*.parquet")):
        table = pq.read_table(parquet_file)
        for batch in table.to_batches(max_chunksize=500):
            for row in batch.to_pylist():
                if limit is not None and yielded >= limit:
                    return
                yield RawJudgment(
                    source_dataset=row["source_dataset"],
                    external_id=str(row["external_id"]),
                    title=row["title"],
                    raw_text=row["raw_text"],
                    source_url=row.get("source_url"),
                    court=row.get("court"),
                    case_type=row.get("case_type"),
                    decision_date=row.get("decision_date"),
                )
                yielded += 1


def run_load(staging_dir: Path, limit: int | None) -> None:
    db = SessionLocal()
    try:
        rows = list(_iter_staged_rows(staging_dir, limit))
        count = upsert_judgments(db, rows)
        logger.info("Upserted %d judgments from %s", count, staging_dir)
    finally:
        db.close()


def run_chunk() -> None:
    db = SessionLocal()
    try:
        total = 0
        while True:
            n = chunk_pending_judgments(db, batch_size=200)
            total += n
            if n == 0:
                break
        logger.info("Chunked %d judgments", total)
    finally:
        db.close()


def run_embed() -> None:
    db = SessionLocal()
    try:
        total = 0
        while True:
            n = embed_pending_chunks(db)
            total += n
            if n == 0:
                break
            logger.info("Embedded %d chunks so far", total)
        logger.info("Done. Embedded %d chunks total", total)
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=["load", "chunk", "embed", "all"],
        default="all",
        help="Which pipeline stage to run (default: all three in order).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of judgments loaded.")
    parser.add_argument("--staging-dir", type=Path, default=DEFAULT_STAGING_DIR)
    args = parser.parse_args()

    if args.stage in ("load", "all"):
        run_load(args.staging_dir, args.limit)
    if args.stage in ("chunk", "all"):
        run_chunk()
    if args.stage in ("embed", "all"):
        run_embed()


if __name__ == "__main__":
    main()
