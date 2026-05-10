from scrapers.miteco_historical import _parse_es_float, _parse_iso_date


def test_parse_es_float_decimal_comma() -> None:
    assert _parse_es_float("91,00") == 91.0
    assert _parse_es_float("3,5") == 3.5


def test_parse_es_float_invalid() -> None:
    assert _parse_es_float("") is None
    assert _parse_es_float("abc") is None
    assert _parse_es_float(None) is None  # type: ignore[arg-type]


def test_parse_iso_date_ok() -> None:
    assert _parse_iso_date("2026-05-05") == "2026-05-05"
    assert _parse_iso_date("1988-01-01") == "1988-01-01"


def test_parse_iso_date_bad() -> None:
    assert _parse_iso_date("") is None
    assert _parse_iso_date("not-a-date") is None
    assert _parse_iso_date("05/05/2026") is None  # only ISO accepted
