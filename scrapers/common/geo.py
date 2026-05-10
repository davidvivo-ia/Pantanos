from math import radians, sin, cos, asin, sqrt


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in km."""
    r = 6371.0088
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def nearest(points: list[dict], lat: float, lon: float, *, lat_key="lat", lon_key="lon") -> tuple[dict, float] | None:
    best, best_d = None, float("inf")
    for p in points:
        plat, plon = p.get(lat_key), p.get(lon_key)
        if plat is None or plon is None:
            continue
        d = haversine_km(lat, lon, float(plat), float(plon))
        if d < best_d:
            best, best_d = p, d
    return (best, best_d) if best is not None else None
