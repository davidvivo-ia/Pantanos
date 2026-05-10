from scrapers.saih.ebro import SAIHEbro


def test_ebro_csv_parse_minimal() -> None:
    csv = "EMBALSE;FECHA;CAPACIDAD;VOLUMEN\nYesa;05/05/2026 12:00;446,00;312,10\n"
    out = SAIHEbro._parse_csv(csv)
    assert len(out) == 1
    rec = out[0]
    assert rec["slug"] == "yesa"
    assert rec["volume_hm3"] == 312.10
    assert rec["pct"] is not None
    assert 69.5 < rec["pct"] < 70.5


def test_ebro_csv_handles_missing_capacity() -> None:
    csv = "EMBALSE;FECHA;VOLUMEN\nYesa;05/05/2026 12:00;312,10\n"
    out = SAIHEbro._parse_csv(csv)
    assert out[0]["pct"] is None  # cannot compute without capacity
