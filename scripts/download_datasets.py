"""Pull judgment datasets from Hugging Face and normalize them into one staging
schema under data/staging/*.parquet, ready for `app.ingestion.ingest_cli`.

Sourcing decision (see docs/data_sources.md for full provenance/licensing):
  - opennyaiorg/InJudgements_dataset (Apache-2.0, ~13K judgments, richer metadata)
  - Exploration-Lab/IL-TUR, CJPE config (CC-BY-NC-SA-4.0, ~34K SC judgments, text-only)

Both were themselves built by scraping Indian Kanoon under academic research use;
we don't scrape Indian Kanoon directly (no free bulk API, ToS-questionable at
50K-document scale).

Usage:
    uv run python scripts/download_datasets.py --dataset injudgements
    uv run python scripts/download_datasets.py --dataset il-tur
    uv run python scripts/download_datasets.py --dataset all
"""

import argparse
import logging
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download, list_repo_files

logger = logging.getLogger(__name__)

STAGING_DIR = Path("data/staging")

# Each dataset's real column names are inspected at pull time rather than assumed
# blind — HF dataset schemas drift and are inconsistently documented.
COLUMN_CANDIDATES = {
    "external_id": ["id", "case_id", "doc_id", "docid"],
    "title": ["title", "case_title", "name"],
    "raw_text": ["text", "judgment_text", "content", "full_text"],
    "source_url": ["url", "source_url", "indian_kanoon_url", "link"],
    "court": ["court", "court_name"],
    "case_type": ["case_type", "category", "label"],
    "decision_date": ["date", "decision_date", "judgment_date"],
}


def _resolve_column(available_columns: list[str], candidates: list[str]) -> str | None:
    lowered = {c.lower(): c for c in available_columns}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def _normalize_table(table: pa.Table, source_dataset: str) -> pa.Table:
    columns = table.column_names
    resolved = {
        field: _resolve_column(columns, candidates)
        for field, candidates in COLUMN_CANDIDATES.items()
    }
    if resolved["raw_text"] is None:
        raise ValueError(
            f"{source_dataset}: could not find a text column among {columns}. "
            "Update COLUMN_CANDIDATES['raw_text'] with the real column name."
        )

    def col(field: str) -> pa.Array:
        source_col = resolved[field]
        if source_col is None:
            return pa.nulls(table.num_rows, type=pa.string())
        return table.column(source_col).cast(pa.string())

    external_id = (
        col("external_id")
        if resolved["external_id"]
        else pa.array([str(i) for i in range(table.num_rows)])
    )
    title = col("title") if resolved["title"] else col("raw_text")

    return pa.table(
        {
            "source_dataset": pa.array([source_dataset] * table.num_rows),
            "external_id": external_id,
            "title": title,
            "raw_text": col("raw_text"),
            "source_url": col("source_url"),
            "court": col("court"),
            "case_type": col("case_type"),
            "decision_date": col("decision_date"),
        }
    )


def download_injudgements() -> Path:
    logger.info("Downloading opennyaiorg/InJudgements_dataset ...")
    files = list_repo_files("opennyaiorg/InJudgements_dataset", repo_type="dataset")
    parquet_files = [f for f in files if f.endswith(".parquet")]
    tables = []
    for f in parquet_files:
        local_path = hf_hub_download(
            "opennyaiorg/InJudgements_dataset", f, repo_type="dataset"
        )
        tables.append(pq.read_table(local_path))
    combined = pa.concat_tables(tables, promote_options="default")
    normalized = _normalize_table(combined, source_dataset="opennyaiorg/InJudgements_dataset")

    out_path = STAGING_DIR / "injudgements.parquet"
    pq.write_table(normalized, out_path)
    logger.info("Wrote %d rows to %s", normalized.num_rows, out_path)
    return out_path


def download_il_tur() -> Path:
    logger.info("Downloading Exploration-Lab/IL-TUR (CJPE config) ...")
    files = list_repo_files("Exploration-Lab/IL-TUR", repo_type="dataset")
    cjpe_files = [f for f in files if "cjpe" in f.lower() and f.endswith(".parquet")]
    if not cjpe_files:
        raise RuntimeError(f"No CJPE parquet files found among {files}")
    tables = [
        pq.read_table(hf_hub_download("Exploration-Lab/IL-TUR", f, repo_type="dataset"))
        for f in cjpe_files
    ]
    combined = pa.concat_tables(tables, promote_options="default")
    normalized = _normalize_table(combined, source_dataset="Exploration-Lab/IL-TUR:CJPE")

    out_path = STAGING_DIR / "il_tur_cjpe.parquet"
    pq.write_table(normalized, out_path)
    logger.info("Wrote %d rows to %s", normalized.num_rows, out_path)
    return out_path


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=["injudgements", "il-tur", "all"], default="injudgements")
    args = parser.parse_args()

    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    if args.dataset in ("injudgements", "all"):
        download_injudgements()
    if args.dataset in ("il-tur", "all"):
        download_il_tur()


if __name__ == "__main__":
    main()
