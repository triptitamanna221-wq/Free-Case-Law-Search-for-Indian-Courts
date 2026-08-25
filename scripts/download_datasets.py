"""Pull judgment datasets from Hugging Face and normalize them into one staging
schema under data/staging/*.parquet, ready for `app.ingestion.ingest_cli` and
`scripts/ingest_judgments.py`.

Sourcing decision (see docs/data_sources.md for the full history):
  - Default: sinhal/Indian_Supreme_Court_Judgments (OpenRAIL, ~41.8K judgments,
    sourced from JUDIS.NIC.IN, the Supreme Court's own official judgment
    repository), no HuggingFace auth required.
  - opennyaiorg/InJudgements_dataset and Exploration-Lab/IL-TUR were the two
    datasets originally identified during planning (multi-court diversity),
    but both turned out to require HuggingFace authentication (gated repos)
    that isn't available in this environment. Their download functions are
    kept below for anyone with `huggingface-cli login` access who wants that
    diversity, but they are NOT the default.

We don't scrape Indian Kanoon directly: no free bulk API, ToS-questionable at
50K-document scale.

Usage:
    uv run python scripts/download_datasets.py                    # default: supreme-court
    uv run python scripts/download_datasets.py --max-rows 500      # fast local sample
    uv run python scripts/download_datasets.py --dataset injudgements  # requires HF_TOKEN
"""

import argparse
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download, list_repo_files

logger = logging.getLogger(__name__)

STAGING_DIR = Path("data/staging")

STAGING_SCHEMA = pa.schema(
    [
        ("source_dataset", pa.string()),
        ("external_id", pa.string()),
        ("title", pa.string()),
        ("raw_text", pa.string()),
        ("source_url", pa.string()),
        ("court", pa.string()),
        ("case_type", pa.string()),
        ("decision_date", pa.string()),
        ("judges", pa.list_(pa.string())),
        ("petitioner", pa.string()),
        ("respondent", pa.string()),
    ]
)

_CASE_TYPE_PREFIX = re.compile(r"^[^\d]+")


def _clean_str(value: object) -> str | None:
    """Collapse pandas/JSON NaN-as-string and blank values to a real None."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s and s.lower() != "nan" and s != "-" else None


def _normalize_judgment_date(raw: str | None) -> str | None:
    """Source dates are 'DD-MM-YYYY'; normalized to ISO 'YYYY-MM-DD' here so
    app.ingestion.loaders._parse_decision_date can stay a strict ISO-only
    parser instead of special-casing every source dataset's date format.
    """
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%d-%m-%Y").date().isoformat()
    except ValueError:
        return None


def _derive_title(pet: str | None, res: str | None, case_no: str | None, external_id: str) -> str:
    if pet and res:
        return f"{pet} vs {res}"
    return case_no or f"Judgment {external_id}"


def _derive_case_type(case_no: str | None) -> str | None:
    if not case_no:
        return None
    match = _CASE_TYPE_PREFIX.match(case_no)
    return match.group(0).strip() or None if match else None


def download_supreme_court_judgments(max_rows: int | None = None) -> Path:
    """sinhal/Indian_Supreme_Court_Judgments: real Supreme Court of India
    judgments sourced from JUDIS.NIC.IN (the Court's own official judgment
    repository). OpenRAIL license, no auth required -- the default source.
    `full_text` retains the original OCR/scrape artifacts (e.g. "company" for
    "com", "number" for "no", a known corruption pattern in some Indian court
    OCR pipelines); left as-is rather than "corrected", since silently
    rewriting judgment text is worse than a visible artifact.

    Streams the source JSONL and writes staging parquet incrementally (2000
    rows/flush) rather than materializing the whole ~41.8K-row corpus in
    memory at once.
    """
    logger.info("Downloading sinhal/Indian_Supreme_Court_Judgments ...")
    local_path = Path(
        hf_hub_download("sinhal/Indian_Supreme_Court_Judgments", "laww_dataset.jsonl", repo_type="dataset")
    )

    out_path = STAGING_DIR / "supreme_court.parquet"
    flush_every = 2000
    rows_buffer: list[dict] = []
    total_written = 0
    total_skipped = 0
    writer: pq.ParquetWriter | None = None

    def flush() -> None:
        nonlocal writer, total_written
        if not rows_buffer:
            return
        if writer is None:
            writer = pq.ParquetWriter(out_path, STAGING_SCHEMA)
        writer.write_table(pa.Table.from_pylist(rows_buffer, schema=STAGING_SCHEMA))
        total_written += len(rows_buffer)
        rows_buffer.clear()

    with local_path.open(encoding="utf-8") as f:
        for line in f:
            if max_rows is not None and total_written + len(rows_buffer) >= max_rows:
                break
            record = json.loads(line)
            raw_text = _clean_str(record.get("full_text"))
            if not raw_text:
                total_skipped += 1
                continue

            external_id = str(record.get("csv_id") or record.get("diary_no") or total_written)
            pet = _clean_str(record.get("pet"))
            res = _clean_str(record.get("res"))
            case_no = _clean_str(record.get("case_no"))
            bench = _clean_str(record.get("bench"))
            judges = [j.strip() for j in bench.split(",") if j.strip()] if bench else None

            rows_buffer.append(
                {
                    "source_dataset": "sinhal/Indian_Supreme_Court_Judgments",
                    "external_id": external_id,
                    "title": _derive_title(pet, res, case_no, external_id),
                    "raw_text": raw_text,
                    "source_url": _clean_str(record.get("temp_link")),
                    "court": "Supreme Court of India",
                    "case_type": _derive_case_type(case_no),
                    "decision_date": _normalize_judgment_date(_clean_str(record.get("judgment_dates"))),
                    "judges": judges,
                    "petitioner": pet,
                    "respondent": res,
                }
            )
            if len(rows_buffer) >= flush_every:
                flush()

    flush()
    if writer is not None:
        writer.close()

    logger.info("Wrote %d rows to %s (skipped %d with no text)", total_written, out_path, total_skipped)
    return out_path


# --- Datasets requiring HF auth (kept for anyone with access; not the default) ---

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
        field: _resolve_column(columns, candidates) for field, candidates in COLUMN_CANDIDATES.items()
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
        col("external_id") if resolved["external_id"] else pa.array([str(i) for i in range(table.num_rows)])
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
    """Requires HuggingFace auth (gated repo) -- see module docstring."""
    logger.info("Downloading opennyaiorg/InJudgements_dataset ...")
    files = list_repo_files("opennyaiorg/InJudgements_dataset", repo_type="dataset")
    parquet_files = [f for f in files if f.endswith(".parquet")]
    tables = [
        pq.read_table(hf_hub_download("opennyaiorg/InJudgements_dataset", f, repo_type="dataset"))
        for f in parquet_files
    ]
    combined = pa.concat_tables(tables, promote_options="default")
    normalized = _normalize_table(combined, source_dataset="opennyaiorg/InJudgements_dataset")

    out_path = STAGING_DIR / "injudgements.parquet"
    pq.write_table(normalized, out_path)
    logger.info("Wrote %d rows to %s", normalized.num_rows, out_path)
    return out_path


def download_il_tur() -> Path:
    """Requires HuggingFace auth (gated repo) -- see module docstring."""
    logger.info("Downloading Exploration-Lab/IL-TUR (CJPE config) ...")
    files = list_repo_files("Exploration-Lab/IL-TUR", repo_type="dataset")
    cjpe_files = [f for f in files if "cjpe" in f.lower() and f.endswith(".parquet")]
    if not cjpe_files:
        raise RuntimeError(f"No CJPE parquet files found among {files}")
    tables = [
        pq.read_table(hf_hub_download("Exploration-Lab/IL-TUR", f, repo_type="dataset")) for f in cjpe_files
    ]
    combined = pa.concat_tables(tables, promote_options="default")
    normalized = _normalize_table(combined, source_dataset="Exploration-Lab/IL-TUR:CJPE")

    out_path = STAGING_DIR / "il_tur_cjpe.parquet"
    pq.write_table(normalized, out_path)
    logger.info("Wrote %d rows to %s", normalized.num_rows, out_path)
    return out_path


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dataset",
        choices=["supreme-court", "injudgements", "il-tur", "all"],
        default="supreme-court",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Cap rows written (supreme-court only) -- for a fast local sample "
        "instead of the full ~41.8K-row corpus.",
    )
    args = parser.parse_args()

    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    if args.dataset in ("supreme-court", "all"):
        download_supreme_court_judgments(max_rows=args.max_rows)
    if args.dataset in ("injudgements", "all"):
        download_injudgements()
    if args.dataset in ("il-tur", "all"):
        download_il_tur()


if __name__ == "__main__":
    main()
