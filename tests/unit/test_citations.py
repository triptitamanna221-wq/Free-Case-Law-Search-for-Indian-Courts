"""Citation extraction, tested against strings taken from the real corpus."""

from app.ingestion.citations import extract_citations


def test_extracts_year_first_citation():
    [citation] = extract_citations("reported at 1961 AIR  268 in this matter")
    assert citation.citation_type == "AIR"
    assert citation.year == 1961
    assert citation.page == 268


def test_extracts_reporter_first_with_court_abbreviation():
    # "AIR (1977) SC 129," -- bracketed year, court, trailing comma
    [citation] = extract_citations("see AIR (1977) SC 129, where the Court held")
    assert (citation.citation_type, citation.year, citation.page) == ("AIR", 1977, 129)


def test_extracts_scr_with_bracketed_volume():
    # "1961 SCR  (1) 668" -- the volume in brackets sits between reporter and page
    [citation] = extract_citations("1961 SCR  (1) 668")
    assert (citation.citation_type, citation.year, citation.page) == ("SCR", 1961, 668)


def test_extracts_scc_supplementary_volume():
    # "1993 SCC  Supl.  (2) 59" appears verbatim in the corpus
    [citation] = extract_citations("1993 SCC  Supl.  (2) 59")
    assert (citation.citation_type, citation.year, citation.page) == ("SCC", 1993, 59)


def test_deduplicates_the_same_citation_written_two_ways():
    # A judgment that leans on one precedent shouldn't yield a row per mention.
    citations = extract_citations("1961 AIR 268 ... discussed further ... AIR 1961 268")
    assert len(citations) == 1


def test_returns_empty_for_text_without_citations():
    assert extract_citations("The appeal is allowed and the order is set aside.") == []
    assert extract_citations("") == []


def test_ignores_years_not_attached_to_a_reporter():
    # A bare date must not become a citation just by sitting near a number.
    assert extract_citations("On 13/09/1960 the Court delivered 268 pages") == []


def test_normalized_form_is_canonical():
    [citation] = extract_citations("AIR (1957) SC 628")
    assert citation.normalized == "AIR 1957 628"


def test_limit_caps_the_number_returned():
    text = "1961 AIR 268 and 1970 SCR 100 and 1985 SCC 400 and 1990 AIR 55"
    assert len(extract_citations(text, limit=2)) == 2


def test_preserves_original_spacing_collapsed_in_cited_text():
    # cited_text keeps what the document said, with runs of whitespace
    # collapsed, so it stays traceable back to the source.
    [citation] = extract_citations("1961 SCR  (1) 668")
    assert citation.cited_text == "1961 SCR (1) 668"
