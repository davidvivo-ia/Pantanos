from scrapers.common.geo import haversine_km, nearest
from scrapers.common.ids import slugify_reservoir


def test_haversine_madrid_barcelona() -> None:
    d = haversine_km(40.4168, -3.7038, 41.3851, 2.1734)
    assert 500 < d < 510  # ~505 km


def test_haversine_zero() -> None:
    assert haversine_km(40.0, -3.0, 40.0, -3.0) == 0.0


def test_nearest_basic() -> None:
    pts = [
        {"name": "A", "lat": 40.0, "lon": -3.0},
        {"name": "B", "lat": 41.0, "lon": -3.0},
        {"name": "C", "lat": 39.0, "lon": -3.0},
    ]
    found = nearest(pts, 40.05, -3.0)
    assert found is not None
    p, d = found
    assert p["name"] == "A"
    assert d < 10


def test_nearest_handles_missing() -> None:
    pts = [
        {"name": "X"},
        {"name": "A", "lat": 40.0, "lon": -3.0},
    ]
    found = nearest(pts, 40.0, -3.0)
    assert found is not None
    p, _ = found
    assert p["name"] == "A"


def test_slugify() -> None:
    assert slugify_reservoir("Embalse de La Serena") == "embalse-de-la-serena"
    assert slugify_reservoir("Miño - Sil") == "mino-sil"
    assert slugify_reservoir("La Tajera") == "la-tajera"


def test_slugify_special_chars() -> None:
    assert slugify_reservoir("Cíjara/El Cíjara") == "cijara-el-cijara"
    assert slugify_reservoir("San Juan (Madrid)") == "san-juan-madrid"
