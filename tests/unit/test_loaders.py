from datetime import date

from app.ingestion.loaders import _parse_decision_date


def test_parses_iso_date():
    assert _parse_decision_date("1998-05-12") == date(1998, 5, 12)


def test_parses_iso_datetime_by_truncating_to_date():
    assert _parse_decision_date("1998-05-12T00:00:00Z") == date(1998, 5, 12)


def test_none_input_returns_none():
    assert _parse_decision_date(None) is None


def test_empty_string_returns_none():
    assert _parse_decision_date("") is None


def test_unparseable_free_text_returns_none_rather_than_guessing():
    assert _parse_decision_date("12th May 1998") is None
