import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

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


def upsert_judgments(db: Session, rows: Iterable[RawJudgment]) -> int:
    """Idempotent batch upsert keyed on (source_dataset, external_id). Safe to
    re-run after a crash: rows already present are updated in place, not duplicated.
    """
    count = 0
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
            )
            .on_conflict_do_update(
                index_elements=["source_dataset", "external_id"],
                set_={"title": row.title, "raw_text": row.raw_text},
            )
        )
        db.execute(stmt)
        count += 1
    db.commit()
    return count


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
