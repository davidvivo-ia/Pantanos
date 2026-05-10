"""
AEMET per-reservoir — para cada embalse con coordenadas, encuentra la
estación AEMET más cercana y pega su lluvia diaria como serie
`rainfall_local` en `data/reservoirs/{slug}.json`.

Requiere haber ejecutado antes:
- `aemet_opendata` (genera `_lookup/aemet_stations.json`)
- algún scraper que provea coords (`osm_reservoirs` o `wikidata_meta`)

Ejecución:
    AEMET_API_KEY=… python -m scrapers.aemet_per_reservoir
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scrapers.aemet_opendata import AemetClient, BASE
from scrapers.common import LOOKUP_DIR, RESERVOIRS_DIR, read_json, write_json
from scrapers.common.geo import nearest

log = logging.getLogger("aemet_per_reservoir")


def build_lookup(reservoirs_with_coords: list[tuple[str, float, float]],
                 stations: list[dict]) -> dict[str, dict]:
    out = {}
    for slug, lat, lon in reservoirs_with_coords:
        result = nearest(stations, lat, lon)
        if result is None:
            continue
        st, dist = result
        out[slug] = {
            "idema": st["idema"],
            "name": st["name"],
            "distance_km": round(dist, 1),
            "lat": st["lat"],
            "lon": st["lon"],
            "altitude": st.get("altitude"),
        }
    return out


def fetch_station_history(client: AemetClient, idema: str,
                          start: datetime, end: datetime) -> list[dict]:
    """30 days max per call. Use /valores/climatologicos/diarios endpoint."""
    fmt = "%Y-%m-%dT%H:%M:%SUTC"
    url = (
        f"{BASE}/valores/climatologicos/diarios/datos/"
        f"fechaini/{start.strftime(fmt)}/fechafin/{end.strftime(fmt)}/"
        f"estacion/{idema}"
    )
    raw = client._resolve(url)
    return raw if isinstance(raw, list) else []


def to_rainfall_series(raw: list[dict]) -> list[dict]:
    out = []
    for d in raw:
        date = d.get("fecha")
        prec = d.get("prec")
        if date is None or prec in (None, "", "Ip"):
            mm = 0.0 if prec == "Ip" else None
        else:
            try:
                mm = float(str(prec).replace(",", "."))
            except ValueError:
                mm = None
        if date and mm is not None:
            out.append({"date": date, "mm": mm})
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="History window in days")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N reservoirs")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    api_key = os.environ.get("AEMET_API_KEY")
    if not api_key:
        log.error("AEMET_API_KEY missing. Skipping.")
        return 0

    stations = read_json(LOOKUP_DIR / "aemet_stations.json")
    if not stations:
        log.error("Run `python -m scrapers.aemet_opendata` first to populate stations.")
        return 1

    reservoirs_with_coords: list[tuple[str, float, float]] = []
    for meta_path in sorted(RESERVOIRS_DIR.glob("*.meta.json")):
        meta = read_json(meta_path) or {}
        slug = meta_path.stem.replace(".meta", "")
        coords = meta.get("coords")
        if coords and len(coords) == 2:
            reservoirs_with_coords.append((slug, float(coords[0]), float(coords[1])))

    log.info("Building station lookup for %d reservoirs with coords…", len(reservoirs_with_coords))
    lookup = build_lookup(reservoirs_with_coords, stations)
    write_json(LOOKUP_DIR / "aemet_station_per_reservoir.json", lookup)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)

    client = AemetClient(api_key)
    try:
        items = list(lookup.items())[: args.limit] if args.limit else list(lookup.items())
        for i, (slug, st) in enumerate(items, 1):
            try:
                raw = fetch_station_history(client, st["idema"], start, end)
                series = to_rainfall_series(raw)
            except Exception as e:
                log.warning("Failed station %s for %s: %s", st["idema"], slug, e)
                continue
            res_path = RESERVOIRS_DIR / f"{slug}.json"
            res = read_json(res_path) or {}
            res["rainfall_local"] = [
                {**pt, "source": "AEMET", "station": st["idema"], "distance_km": st["distance_km"]}
                for pt in series
            ]
            write_json(res_path, res)
            time.sleep(0.7)  # AEMET enforces ~1 req/s
            if i % 25 == 0:
                log.info("Progress %d/%d", i, len(items))
    finally:
        client.close()
    log.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
