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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.models.judgment import Citation, Judgment  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.ingestion.citations import extract_citations  # noqa: E402

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


def build_index(session: Session) -> dict[str, int]:
    """Map each judgment's own citation(s) to its id, for resolving references.

    A citation string claimed by two different judgments is dropped rather than
    resolved arbitrarily -- a wrong edge in a citation graph is worse than a
    missing one, since it reads as a real relationship.
    """
    index: dict[str, int] = {}
    ambiguous: set[str] = set()

    for judgment_id, raw_text in session.execute(select(Judgment.id, Judgment.raw_text)):
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
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    with Session(engine) as session:
        index = build_index(session)
        logger.info("indexed %d citation keys from the corpus", len(index))

        query = select(Judgment.id, Judgment.raw_text).order_by(Judgment.id)
        if args.limit:
            query = query.limit(args.limit)
        rows = session.execute(query).all()

        total_rows = 0
        resolved = 0
        judgments_with_citations = 0

        for judgment_id, raw_text in rows:
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

        session.commit()

    print("=" * 56)
    print("CITATION EXTRACTION")
    print("=" * 56)
    print(f"  Judgments scanned          {len(rows):>10}")
    print(f"  Judgments citing others    {judgments_with_citations:>10}")
    print(f"  Citation rows written      {total_rows:>10}")
    print(f"  Resolved within corpus     {resolved:>10}")
    print(f"  Unresolved (outside corpus){total_rows - resolved:>10}")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
