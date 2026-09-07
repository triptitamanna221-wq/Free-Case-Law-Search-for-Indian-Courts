"""Populate the `citations` table from judgments already in the database.

Runs as a separate pass rather than inside ingestion, for the same reason the
HNSW index build is separate: it needs the corpus to already be loaded. A
citation can only be resolved to a `cited_judgment_id` if the judgment it
points at is present, so resolution improves as the corpus grows and the pass
is meant to be re-run.

Idempotent: a judgment's existing rows are deleted before its new ones are
inserted, so re-running updates rather than duplicating.

    uv run python scripts/build_citations.py            # all judgments
    uv run python scripts/build_citations.py --limit 50
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.models.judgment import Citation, Judgment  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.ingestion.citations import extract_citations  # noqa: E402
from app.ingestion.loaders import iter_staged_judgments  # noqa: E402

logger = logging.getLogger("build_citations")

# The judgment's *own* reporter citations live under a CITATION: heading, which
# runs until the next all-caps heading (usually ACT: or HEADNOTE:).
_OWN_CITATION_BLOCK = re.compile(
    r"^\s*CITATION\s*:\s*$(?P<body>.*?)(?=^\s*[A-Z][A-Z ]{2,}\s*:\s*$|\Z)",
    re.MULTILINE | re.DOTALL,
)


def own_citations(raw_text: str) -> list[str]:
    """Normalized citations identifying this judgment itself."""
    match = _OWN_CITATION_BLOCK.search(raw_text or "")
    if not match:
        return []
    return [c.normalized for c in extract_citations(match.group("body"))]


def iter_judgments(session: Session, source: Path, limit: int | None = None) -> Iterator[tuple[int, str]]:
    """Yield (judgment_id, raw_text), reading text from the staged parquet.

    An earlier version read raw_text out of Postgres. That meant dragging the
    whole corpus (~24MB of text) across the wire only to compute something
    locally, and it reliably died mid-run -- first as "SSL connection has been
    closed unexpectedly", then, once paginated, as an outright TCP timeout.
    Paginating treated the symptom; the actual fix is not moving the data at
    all. The same parquet the ingest CLI read is still on disk, so the database
    is asked only for the id mapping, which is a few KB.

    Consequence worth knowing: a judgment in the database but absent from
    `source` is skipped, since there's no text to scan. That's the same
    staging file ingestion consumed, so in the normal post-ingest flow the two
    agree.
    """
    id_by_key = {
        (source_dataset, external_id): judgment_id
        for judgment_id, source_dataset, external_id in session.execute(
            select(Judgment.id, Judgment.source_dataset, Judgment.external_id)
        )
    }
    logger.info("fetched %d judgment ids from the database", len(id_by_key))

    yielded = 0
    for row in iter_staged_judgments(source, None):
        judgment_id = id_by_key.get((row.source_dataset, row.external_id))
        if judgment_id is None:
            continue  # staged but not ingested (e.g. this run used --limit)
        yield judgment_id, row.raw_text or ""
        yielded += 1
        if limit is not None and yielded >= limit:
            return


def build_index(judgments: list[tuple[int, str]]) -> dict[str, int]:
    """Map each judgment's own citation(s) to its id, for resolving references.

    A citation string claimed by two different judgments is dropped rather than
    resolved arbitrarily -- a wrong edge in a citation graph is worse than a
    missing one, since it reads as a real relationship.
    """
    index: dict[str, int] = {}
    ambiguous: set[str] = set()

    for judgment_id, raw_text in judgments:
        for normalized in own_citations(raw_text):
            if normalized in index and index[normalized] != judgment_id:
                ambiguous.add(normalized)
            index[normalized] = judgment_id

    for key in ambiguous:
        index.pop(key, None)
    if ambiguous:
        logger.info("dropped %d ambiguous citation keys", len(ambiguous))
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="only process N judgments")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/staging"),
        help="staged parquet the judgment text is read from (default: %(default)s)",
    )
    parser.add_argument(
        "--commit-every",
        type=int,
        default=50,
        help="judgments per transaction (default: %(default)s)",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    if not args.source.exists():
        logger.error(
            "--source %s does not exist. This pass reads judgment text from the same staged "
            "parquet the ingest CLI used; run scripts/download_datasets.py first.",
            args.source,
        )
        return 1

    with Session(engine) as session:
        judgments = list(iter_judgments(session, args.source, args.limit))
        logger.info("matched %d staged judgments to database rows", len(judgments))

        index = build_index(judgments)
        logger.info("indexed %d citation keys from the corpus", len(index))

        total_rows = 0
        resolved = 0
        judgments_with_citations = 0
        scanned = 0

        for judgment_id, raw_text in judgments:
            scanned += 1
            found = extract_citations(raw_text or "")
            # A judgment's own reporter citation appears in its header; that's
            # a self-reference, not a citation of another case.
            self_keys = set(own_citations(raw_text or ""))

            session.execute(delete(Citation).where(Citation.citing_judgment_id == judgment_id))

            new_rows = []
            for citation in found:
                if citation.normalized in self_keys:
                    continue
                cited_id = index.get(citation.normalized)
                # The CHECK constraint forbids citing == cited; a document that
                # references its own reporter number mid-text would trip it.
                if cited_id == judgment_id:
                    continue
                if cited_id is not None:
                    resolved += 1
                new_rows.append(
                    Citation(
                        citing_judgment_id=judgment_id,
                        cited_judgment_id=cited_id,
                        cited_text=citation.cited_text,
                        citation_type=citation.citation_type,
                    )
                )

            if new_rows:
                session.add_all(new_rows)
                judgments_with_citations += 1
                total_rows += len(new_rows)

            # Commit per page rather than once at the end: a single
            # transaction spanning the whole corpus is exactly what the
            # long-haul connection drops, and it would throw away every row
            # already computed. Committing as we go makes a re-run resume
            # cheaply, since each judgment's rows are deleted before reinsert.
            if scanned % args.commit_every == 0:
                session.commit()
                logger.info("committed through judgment id %d (%d scanned)", judgment_id, scanned)

        session.commit()

    print("=" * 56)
    print("CITATION EXTRACTION")
    print("=" * 56)
    print(f"  Judgments scanned          {scanned:>10}")
    print(f"  Judgments citing others    {judgments_with_citations:>10}")
    print(f"  Citation rows written      {total_rows:>10}")
    print(f"  Resolved within corpus     {resolved:>10}")
    print(f"  Unresolved (outside corpus){total_rows - resolved:>10}")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
