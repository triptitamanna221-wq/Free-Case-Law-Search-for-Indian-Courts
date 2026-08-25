import logging
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Chunk, Judgment
from app.ingestion.chunking import chunk_text
from app.ingestion.embedder import BATCH_SIZE, embed_texts

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RawJudgment:
    source_dataset: str
    external_id: str
    title: str
    raw_text: str
    source_url: str | None = None
    court: str | None = None
    case_type: str | None = None
    decision_date: str | None = None
    judges: list[str] | None = None
    petitioner: str | None = None
    respondent: str | None = None


def iter_staged_judgments(
    source: Path, limit: int | None = None
) -> Generator[RawJudgment, None, None]:
    """Stream RawJudgment rows from staged parquet, in batches, so a 50K-row
    corpus is never fully materialized in memory. `source` is either a single
    parquet file or a directory of them (read in sorted filename order for
    deterministic --limit behavior across runs).

    A row missing raw_text is skipped with a warning rather than raised --
    one malformed row from an upstream dataset shouldn't abort the whole load.
    """
    parquet_files = [source] if source.is_file() else sorted(source.glob("*.parquet"))
    yielded = 0
    for parquet_file in parquet_files:
        table = pq.read_table(parquet_file)
        for batch in table.to_batches(max_chunksize=500):
            for row in batch.to_pylist():
                if limit is not None and yielded >= limit:
                    return
                if not row.get("raw_text") or not row.get("raw_text").strip():
                    logger.warning(
                        "Skipping malformed row (empty raw_text): source=%s external_id=%s",
                        parquet_file.name,
                        row.get("external_id"),
                    )
                    continue
                yield RawJudgment(
                    source_dataset=row["source_dataset"],
                    external_id=str(row["external_id"]),
                    title=row["title"],
                    raw_text=row["raw_text"],
                    source_url=row.get("source_url"),
                    court=row.get("court"),
                    case_type=row.get("case_type"),
                    decision_date=row.get("decision_date"),
                    judges=row.get("judges") or None,
                    petitioner=row.get("petitioner"),
                    respondent=row.get("respondent"),
                )
                yielded += 1


def _parse_decision_date(raw: str | None) -> date | None:
    """HF dataset date fields arrive as free-form strings with inconsistent
    formats; only ISO 'YYYY-MM-DD' is parsed, anything else is left NULL rather
    than guessed at.
    """
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def upsert_judgments(db: Session, rows: Iterable[RawJudgment]) -> dict[tuple[str, str], int]:
    """Idempotent batch upsert keyed on (source_dataset, external_id). Safe to
    re-run after a crash: rows already present are updated in place, not duplicated.

    Returns {(source_dataset, external_id): judgment_id} for every row in this
    batch, so callers can immediately chunk/embed the just-written judgments
    without a re-query. Keyed on the pair, not external_id alone, since that's
    the actual DB unique constraint -- a batch could in principle span two
    source datasets whose external_ids collide.
    Does not commit -- caller controls the transaction boundary.
    """
    ids: dict[tuple[str, str], int] = {}
    for row in rows:
        stmt = (
            insert(Judgment)
            .values(
                source_dataset=row.source_dataset,
                external_id=row.external_id,
                title=row.title,
                raw_text=row.raw_text,
                source_url=row.source_url,
                court=row.court,
                case_type=row.case_type,
                decision_date=_parse_decision_date(row.decision_date),
                judges=row.judges,
                petitioner=row.petitioner,
                respondent=row.respondent,
            )
            .on_conflict_do_update(
                index_elements=["source_dataset", "external_id"],
                set_={"title": row.title, "raw_text": row.raw_text},
            )
            .returning(Judgment.id)
        )
        judgment_id = db.execute(stmt).scalar_one()
        ids[(row.source_dataset, row.external_id)] = judgment_id
    return ids


def chunk_pending_judgments(db: Session, batch_size: int = 200) -> int:
    """Chunk raw_text for judgments not yet chunked. Resumable: only touches
    judgments with ingestion_status='pending', and advances their status once
    chunks are written, so a restarted run never re-chunks the same judgment.
    """
    judgments = db.scalars(
        select(Judgment).where(Judgment.ingestion_status == "pending").limit(batch_size)
    ).all()

    for judgment in judgments:
        pieces = chunk_text(judgment.raw_text)
        for index, piece in enumerate(pieces):
            db.execute(
                insert(Chunk)
                .values(judgment_id=judgment.id, chunk_index=index, text=piece)
                .on_conflict_do_nothing(index_elements=["judgment_id", "chunk_index"])
            )
        judgment.ingestion_status = "chunked"

    db.commit()
    return len(judgments)


def embed_pending_chunks(db: Session, batch_size: int = BATCH_SIZE) -> int:
    """Embed chunks with embedding IS NULL, one batched model call per page.
    Resumable at chunk granularity: a crash mid-run loses no already-committed work.
    """
    chunks = db.scalars(
        select(Chunk).where(Chunk.embedding.is_(None)).limit(batch_size)
    ).all()
    if not chunks:
        return 0

    vectors = embed_texts([chunk.text for chunk in chunks])
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk.embedding = vector
    db.commit()

    _mark_fully_embedded_judgments(db, {chunk.judgment_id for chunk in chunks})
    return len(chunks)


def _mark_fully_embedded_judgments(db: Session, judgment_ids: set[int]) -> None:
    if not judgment_ids:
        return
    fully_embedded = text(
        """
        SELECT judgment_id FROM chunks
        WHERE judgment_id = ANY(:judgment_ids)
        GROUP BY judgment_id
        HAVING bool_and(embedding IS NOT NULL)
        """
    )
    rows = db.execute(fully_embedded, {"judgment_ids": list(judgment_ids)}).all()
    ready_ids = [row.judgment_id for row in rows]
    if ready_ids:
        db.execute(
            update(Judgment)
            .where(Judgment.id.in_(ready_ids))
            .values(ingestion_status="embedded")
        )
        db.commit()
