"""
AEMET OpenData — pluviómetros nacionales y mosaico radar.

Requiere variable de entorno AEMET_API_KEY (gratuita en
https://opendata.aemet.es).

Ejecución:
    AEMET_API_KEY=… python -m scrapers.aemet_opendata
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from scrapers.common import DATA_DIR, LOOKUP_DIR, write_json
from scrapers.common.http import make_client, fetch_json, fetch_bytes

log = logging.getLogger("aemet_opendata")

BASE = "https://opendata.aemet.es/opendata/api"
EP_STATIONS = f"{BASE}/valores/climatologicos/inventarioestaciones/todasestaciones"
EP_OBS_ALL = f"{BASE}/observacion/convencional/todas"
EP_RADAR_NAC = f"{BASE}/red/radar/nacional"
RAINFALL_DIR = DATA_DIR / "rainfall"
RADAR_DIR = RAINFALL_DIR / "radar"


class AemetClient:
    """Two-stage AEMET fetch: endpoint returns {datos, metadatos} URLs."""

    def __init__(self, api_key: str):
        self._client = make_client(headers={"api_key": api_key, "cache-control": "no-cache"})

    def close(self) -> None:
        self._client.close()

    def _resolve(self, endpoint: str) -> dict | list:
        meta = fetch_json(self._client, endpoint)
        if not isinstance(meta, dict) or "datos" not in meta:
            raise RuntimeError(f"AEMET unexpected response: {meta}")
        # AEMET serves data behind a CDN URL; small backoff helps avoid 429.
        time.sleep(0.6)
        return fetch_json(self._client, meta["datos"])

    def stations(self) -> list[dict]:
        raw = self._resolve(EP_STATIONS)
        return raw if isinstance(raw, list) else []

    def observations(self) -> list[dict]:
        raw = self._resolve(EP_OBS_ALL)
        return raw if isinstance(raw, list) else []

    def radar_nacional(self) -> bytes:
        meta = fetch_json(self._client, EP_RADAR_NAC)
        time.sleep(0.6)
        return fetch_bytes(self._client, meta["datos"])


def _parse_aemet_lat(s: str | None) -> float | None:
    """AEMET uses '402423N' format for lat/lon."""
    if not s:
        return None
    try:
        d, m, sec = int(s[0:2]), int(s[2:4]), int(s[4:6])
        sign = -1 if s[-1] in ("S", "W") else 1
        return sign * (d + m / 60 + sec / 3600)
    except (ValueError, IndexError):
        return None


def normalize_stations(raw: list[dict]) -> list[dict]:
    out = []
    for s in raw:
        lat = _parse_aemet_lat(s.get("latitud"))
        lon = _parse_aemet_lat(s.get("longitud"))
        if lat is None or lon is None:
            continue
        out.append({
            "idema": s.get("indicativo"),
            "name": s.get("nombre"),
            "province": s.get("provincia"),
            "altitude": float(s["altitud"]) if s.get("altitud") else None,
            "lat": lat, "lon": lon,
        })
    return out


def normalize_observations(raw: list[dict]) -> list[dict]:
    out = []
    for o in raw:
        ts = o.get("fint")
        out.append({
            "idema": o.get("idema"),
            "ts": ts,
            "name": o.get("ubi"),
            "lat": o.get("lat"),
            "lon": o.get("lon"),
            "temp_c": o.get("ta"),
            "rain_mm_1h": o.get("prec"),
            "wind_dir": o.get("dv"),
            "wind_speed": o.get("vv"),
            "humidity": o.get("hr"),
            "pressure": o.get("pres"),
        })
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    api_key = os.environ.get("AEMET_API_KEY")
    if not api_key:
        log.error("AEMET_API_KEY env var missing. Skipping. Get a free key at https://opendata.aemet.es")
        return 0  # not fatal — keep CI green when secret is unset

    RADAR_DIR.mkdir(parents=True, exist_ok=True)

    client = AemetClient(api_key)
    try:
        log.info("Fetching AEMET station inventory…")
        stations_raw = client.stations()
        stations = normalize_stations(stations_raw)
        write_json(LOOKUP_DIR / "aemet_stations.json", stations)
        log.info("Got %d stations", len(stations))

        log.info("Fetching last-hour observations (all stations)…")
        obs = normalize_observations(client.observations())
        write_json(RAINFALL_DIR / "national.json", {
            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n": len(obs),
            "observations": obs,
        })
        log.info("Got %d observations", len(obs))

        log.info("Fetching national radar mosaic…")
        try:
            png = client.radar_nacional()
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
            radar_path = RADAR_DIR / f"{ts}.png"
            radar_path.write_bytes(png)
            (RADAR_DIR / "latest.png").write_bytes(png)
            log.info("Radar saved: %s (%.1f KB)", radar_path.name, len(png) / 1024)
        except (httpx.HTTPError, RuntimeError) as e:
            log.warning("Radar fetch failed (often rate-limited): %s", e)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
