"""
OSM hiking routes — para cada embalse con coordenadas, busca rutas
`route=hiking` dentro de un radio configurable y persiste la lista.

Usa Overpass API. Sin clave; rate-limit suave (espaciar 2 s entre
requests). 401 embalses × 2 s ≈ 13 min por refresco.

Ejecución:
    python -m scrapers.osm_routes
    python -m scrapers.osm_routes --limit 5 --radius 5
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from scrapers.common import RESERVOIRS_DIR, LOOKUP_DIR, read_json, write_json  # noqa: F401
from scrapers.common.http import make_client

log = logging.getLogger("osm_routes")

OVERPASS = "https://overpass-api.de/api/interpreter"

QUERY_TEMPLATE = """
[out:json][timeout:60];
(
  relation["route"="hiking"](around:{radius},{lat},{lon});
);
out body;
>;
out skel qt;
"""


def _length_km_from_geom(coords: list[tuple[float, float]]) -> float:
    """Approx length of polyline in km using equirectangular projection."""
    from math import cos, radians, sqrt
    if len(coords) < 2:
        return 0.0
    total = 0.0
    for (la1, lo1), (la2, lo2) in zip(coords, coords[1:]):
        x = (radians(lo2) - radians(lo1)) * cos((radians(la1) + radians(la2)) / 2)
        y = radians(la2) - radians(la1)
        total += sqrt(x * x + y * y) * 6371.0088
    return total


def parse_routes(data: dict) -> list[dict]:
    nodes: dict[int, tuple[float, float]] = {}
    ways: dict[int, list[int]] = {}
    relations: list[dict] = []
    for el in data.get("elements", []):
        if el["type"] == "node":
            nodes[el["id"]] = (el["lat"], el["lon"])
        elif el["type"] == "way":
            ways[el["id"]] = el.get("nodes", [])
        elif el["type"] == "relation":
            relations.append(el)

    out = []
    for rel in relations:
        tags = rel.get("tags", {})
        coords: list[tuple[float, float]] = []
        for member in rel.get("members", []):
            if member["type"] == "way":
                for nid in ways.get(member["ref"], []):
                    if nid in nodes:
                        coords.append(nodes[nid])
        length = _length_km_from_geom(coords)
        if length < 2.0:
            continue
        out.append({
            "osm_id": f"relation/{rel['id']}",
            "name": tags.get("name") or tags.get("ref") or f"Ruta {rel['id']}",
            "ref": tags.get("ref"),
            "network": tags.get("network"),
            "sac_scale": tags.get("sac_scale"),
            "operator": tags.get("operator"),
            "length_km": round(length, 2),
            "url": f"https://www.openstreetmap.org/relation/{rel['id']}",
            # Keep a downsampled track for client-side rendering.
            "track": [[round(la, 5), round(lo, 5)] for la, lo in coords[:: max(1, len(coords) // 200)]],
        })
    out.sort(key=lambda r: r["length_km"], reverse=True)
    return out[:30]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--radius", type=int, default=10000, help="Radius in meters")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=2.0, help="Seconds between Overpass requests")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip reservoirs that already have non-empty routes file")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    targets: list[tuple[str, float, float]] = []
    for meta_path in sorted(RESERVOIRS_DIR.glob("*.meta.json")):
        meta = read_json(meta_path) or {}
        slug = meta_path.stem.replace(".meta", "")
        coords = meta.get("coords")
        if coords and len(coords) == 2:
            targets.append((slug, float(coords[0]), float(coords[1])))

    if args.limit:
        targets = targets[: args.limit]

    log.info("Querying routes for %d reservoirs (radius %dm)", len(targets), args.radius)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def fetch_with_retry(client, q: str, slug: str, attempts: int = 3):
        for attempt in range(attempts):
            try:
                r = client.post(OVERPASS, data={"data": q}, timeout=180)
                if r.status_code == 504:
                    raise TimeoutError(f"504 Overpass for {slug}")
                r.raise_for_status()
                return parse_routes(r.json())
            except Exception as e:
                if attempt < attempts - 1:
                    backoff = (attempt + 1) * 8
                    log.info("Retry %d for %s after %ds: %s", attempt + 1, slug, backoff, e)
                    time.sleep(backoff)
                else:
                    log.warning("Giving up on %s: %s", slug, e)
        return None

    with make_client() as client:
        total_routes = 0
        for i, (slug, lat, lon) in enumerate(targets, 1):
            existing = read_json(RESERVOIRS_DIR / f"{slug}.routes.json") or {}
            if args.skip_existing and existing.get("n", 0) > 0:
                continue
            q = QUERY_TEMPLATE.format(radius=args.radius, lat=lat, lon=lon)
            routes = fetch_with_retry(client, q, slug)
            if routes is None:
                # Don't overwrite existing data with an empty file on transient failure.
                if existing:
                    continue
                routes = []
            write_json(RESERVOIRS_DIR / f"{slug}.routes.json", {
                "id": slug,
                "fetched": now,
                "search_radius_km": args.radius / 1000,
                "n": len(routes),
                "routes": routes,
            })
            total_routes += len(routes)
            if i % 10 == 0:
                log.info("Progress %d/%d (cumulative routes: %d)", i, len(targets), total_routes)
            time.sleep(args.sleep)

    write_json(LOOKUP_DIR / "osm_routes_run.json", {
        "fetched": now,
        "n_reservoirs_queried": len(targets),
        "total_routes": total_routes,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
