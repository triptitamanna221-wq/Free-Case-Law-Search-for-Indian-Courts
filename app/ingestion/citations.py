"""Extracts Indian law-report citations from judgment text.

The patterns here were written against the strings that actually occur in this
corpus rather than against an idealised citation grammar -- the source is OCR'd
and inconsistently spaced, so `1961 AIR  268`, `AIR (1977) SC 129` and
`1993 SCC  Supl.  (2) 59` all appear and all have to parse.

Scope is deliberately narrow: reporter citations (AIR/SCR/SCC), not party-name
references like "Kesavananda Bharati v. State of Kerala". Matching parties
reliably needs entity resolution against a case index this project doesn't
have, and a regex that half-does it would populate the table with noise that
looks authoritative.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Reporters this corpus actually uses. Kept as an alternation rather than a
# generic \w+ so that arbitrary capitalised words near a year don't match.
REPORTERS = ("AIR", "SCR", "SCC")

# Two orderings occur, both common in Indian reporting:
#   year-first : "1961 AIR 268", "1961 SCR  (1) 668", "1993 SCC Supl. (2) 59"
#   reporter-first: "AIR 1957 SC 628", "AIR (1977) SC 129", "AIR (1963) All. 47"
# The optional bracketed volume and court abbreviation are what make a single
# tidy pattern impossible.
_YEAR_FIRST = re.compile(
    r"\b(?P<year>1[89]\d{2}|20\d{2})\s+"
    rf"(?P<reporter>{'|'.join(REPORTERS)})\b"
    r"(?:\s+Supl\.?)?"
    r"(?:\s*\(\s*\d+\s*\))?"
    r"\s*(?P<page>\d{1,5})\b"
)

_REPORTER_FIRST = re.compile(
    rf"\b(?P<reporter>{'|'.join(REPORTERS)})\s+"
    r"\(?(?P<year>1[89]\d{2}|20\d{2})\)?\s+"
    r"(?P<court>SC|All\.?|Cal\.?|Bom\.?|Mad\.?|Ker\.?|Del\.?)?\s*,?\s*"
    r"(?P<page>\d{1,5})\b"
)


@dataclass(frozen=True)
class ExtractedCitation:
    """One reporter citation found in a judgment's text."""

    cited_text: str
    citation_type: str
    year: int
    page: int

    @property
    def normalized(self) -> str:
        """Canonical `AIR 1961 268` form, used to de-duplicate the same
        citation written two different ways in one judgment."""
        return f"{self.citation_type} {self.year} {self.page}"


def extract_citations(text: str, *, limit: int | None = None) -> list[ExtractedCitation]:
    """Find reporter citations in `text`, de-duplicated, in order of appearance.

    De-duplication is on the normalized form, so `1961 AIR 268` and
    `AIR (1961) 268` in the same judgment count once -- a judgment that
    discusses one precedent repeatedly shouldn't produce twenty rows.
    """
    if not text:
        return []

    found: list[ExtractedCitation] = []
    seen: set[str] = set()

    for pattern in (_YEAR_FIRST, _REPORTER_FIRST):
        for match in pattern.finditer(text):
            citation = ExtractedCitation(
                cited_text=" ".join(match.group(0).split()),
                citation_type=match.group("reporter").upper(),
                year=int(match.group("year")),
                page=int(match.group("page")),
            )
            if citation.normalized in seen:
                continue
            seen.add(citation.normalized)
            found.append(citation)
            if limit is not None and len(found) >= limit:
                return found

    return found
