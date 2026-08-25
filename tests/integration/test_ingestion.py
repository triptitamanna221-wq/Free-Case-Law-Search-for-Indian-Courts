import argparse

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.db.models import Chunk, Judgment
from app.ingestion.loaders import RawJudgment
from scripts.ingest_judgments import IngestionMetrics, process_batch, with_retries


class _FakeTokenizer:
    """Whitespace-split stand-in for the real subword tokenizer -- fast and
    deterministic, keeping these DB-focused tests independent of model weights."""

    def encode(self, text: str, add_special_tokens: bool = False) -> list[str]:
        return text.split()


class _FakeModel:
    tokenizer = _FakeTokenizer()

    def encode(self, texts: list[str], batch_size: int, show_progress_bar: bool) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    def get_sentence_embedding_dimension(self) -> int:
        return 384


def _args(**overrides) -> argparse.Namespace:
    defaults = dict(chunk_size=50, chunk_overlap=10, batch_size=32, max_retries=2, dry_run=False)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _metrics() -> IngestionMetrics:
    return IngestionMetrics(
        embedding_model="fake",
        embedding_dim=384,
        dry_run=False,
        chunk_size_tokens=50,
        chunk_overlap_tokens=10,
    )


def _judgment_row(source_dataset: str, external_id: str, **overrides) -> RawJudgment:
    defaults = dict(
        source_dataset=source_dataset,
        external_id=external_id,
        title=f"Case {external_id}",
        raw_text=f"This is judgment number {external_id}, a real dispute about property law. " * 15,
        court="Supreme Court of India",
        petitioner=f"Petitioner {external_id}",
        respondent=f"Respondent {external_id}",
        judges=["Judge A", "Judge B"],
        decision_date="2020-01-15",
    )
    defaults.update(overrides)
    return RawJudgment(**defaults)


@pytest.mark.integration
def test_process_batch_ingests_ten_judgments_end_to_end(db_session):
    source = "test-ingestion-e2e"
    rows = [_judgment_row(source, str(i)) for i in range(10)]
    metrics = _metrics()

    process_batch(db_session, rows, _FakeModel(), _args(), metrics)

    judgment_count = db_session.scalar(
        select(func.count()).select_from(Judgment).where(Judgment.source_dataset == source)
    )
    chunk_count = db_session.scalar(
        select(func.count())
        .select_from(Chunk)
        .join(Judgment, Chunk.judgment_id == Judgment.id)
        .where(Judgment.source_dataset == source)
    )

    assert judgment_count == 10
    assert chunk_count > 0
    assert metrics.judgments_processed == 10
    assert metrics.chunks_embedded == chunk_count
    assert metrics.failed_batches == 0

    seeded = db_session.scalar(
        select(Judgment).where(Judgment.source_dataset == source, Judgment.external_id == "0")
    )
    assert seeded.petitioner == "Petitioner 0"
    assert seeded.respondent == "Respondent 0"
    assert seeded.judges == ["Judge A", "Judge B"]
    assert seeded.court == "Supreme Court of India"

    first_chunk = db_session.scalar(
        select(Chunk).where(Chunk.judgment_id == seeded.id, Chunk.chunk_index == 0)
    )
    assert first_chunk.embedding is not None
    assert len(first_chunk.embedding) == 384


@pytest.mark.integration
def test_process_batch_skips_malformed_judgment_entirely(db_session):
    source = "test-ingestion-malformed"
    rows = [
        _judgment_row(source, "good"),
        _judgment_row(source, "bad-empty", raw_text=""),
        _judgment_row(source, "bad-whitespace", raw_text="   \n\t  "),
    ]
    metrics = _metrics()

    process_batch(db_session, rows, _FakeModel(), _args(), metrics)

    assert metrics.skipped_malformed == 2
    assert metrics.judgments_processed == 1

    remaining_ids = set(
        db_session.scalars(
            select(Judgment.external_id).where(Judgment.source_dataset == source)
        ).all()
    )
    # the malformed rows produced zero chunks and were never written at all --
    # not stored as chunk-less judgment rows.
    assert remaining_ids == {"good"}


@pytest.mark.integration
def test_process_batch_is_idempotent_on_constraint_conflict(db_session):
    source = "test-ingestion-duplicate"
    rows = [_judgment_row(source, "dup-1")]

    process_batch(db_session, rows, _FakeModel(), _args(), _metrics())
    # re-ingesting the exact same (source_dataset, external_id) must update in
    # place, not raise a unique-constraint violation or create a second row.
    process_batch(db_session, rows, _FakeModel(), _args(), _metrics())

    count = db_session.scalar(
        select(func.count()).select_from(Judgment).where(Judgment.source_dataset == source)
    )
    assert count == 1


@pytest.mark.integration
def test_with_retries_recovers_from_transient_failures():
    attempts = {"n": 0}

    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OperationalError("stmt", {}, Exception("connection reset"))
        return "ok"

    result = with_retries(flaky, max_attempts=5, retry_on=(OperationalError,), base_delay_s=0)

    assert result == "ok"
    assert attempts["n"] == 3


@pytest.mark.integration
def test_with_retries_raises_after_exhausting_attempts():
    def always_fails() -> None:
        raise OperationalError("stmt", {}, Exception("connection reset"))

    with pytest.raises(OperationalError):
        with_retries(always_fails, max_attempts=2, retry_on=(OperationalError,), base_delay_s=0)
