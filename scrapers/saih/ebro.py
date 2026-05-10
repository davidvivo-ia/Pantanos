"""SAIH Ebro scraper.

La Confederación Hidrográfica del Ebro publica datos abiertos del SAIH
con licencia libre. El endpoint canónico es un CSV con la última lectura
de todos los embalses de la cuenca.

NOTA sobre URLs: CHEbro mueve sus URLs ocasionalmente. Mantén la URL
en `EBRO_LATEST_URL` actualizada — el patrón histórico ha sido:
    - https://www.saihebro.com/saihebro/datos/embalses_csv.php
    - https://www.chebro.es/.../embalses-actuales.csv

Si el formato cambia, ajustar `_parse_csv` en consecuencia.

Ejecución:
    python -m scrapers.saih.ebro
"""

from __future__ import annotations

import csv
import io
import logging
import os
import sys
from datetime import datetime, timezone

from scrapers.common.http import make_client, fetch_bytes
from scrapers.common.ids import slugify_reservoir
from scrapers.saih.base import BaseSAIH

log = logging.getLogger("saih.ebro")

EBRO_LATEST_URL = os.environ.get(
    "SAIH_EBRO_URL",
    "https://www.saihebro.com/saihebro/datos/embalses_csv.php",
)


def _parse_float(s: str | None) -> float | None:
    if s is None or s == "":
        return None
    try:
        return float(str(s).replace(",", "."))
    except ValueError:
        return None


class SAIHEbro(BaseSAIH):
    name = "saih.ebro"
    confederacion = "SAIH-Ebro"

    def fetch(self) -> list[dict]:
        with make_client() as client:
            data = fetch_bytes(client, EBRO_LATEST_URL)
        text = data.decode("latin-1") if b"\xf1" in data else data.decode("utf-8", errors="replace")
        return self._parse_csv(text)

    @staticmethod
    def _parse_csv(text: str) -> list[dict]:
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        out: list[dict] = []
        # CHEbro field names vary. We try a list of common keys.
        name_keys = ("EMBALSE", "Embalse", "embalse", "NOMBRE")
        date_keys = ("FECHA", "Fecha", "fecha")
        vol_keys = ("VOLUMEN", "Volumen", "volumen", "VOL", "AGUA_ACTUAL")
        cap_keys = ("CAPACIDAD", "Capacidad", "VOL_TOTAL", "AGUA_TOTAL")
        level_keys = ("COTA", "Cota", "cota", "NIVEL")

        def first(d: dict, keys) -> str | None:
            for k in keys:
                if d.get(k) not in (None, ""):
                    return d[k]
            return None

        ts_now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for row in reader:
            name = first(row, name_keys)
            if not name:
                continue
            ts = first(row, date_keys) or ts_now
            try:
                if "/" in ts:
                    ts = datetime.strptime(ts.strip(), "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
            except ValueError:
                pass
            volume = _parse_float(first(row, vol_keys))
            capacity = _parse_float(first(row, cap_keys))
            level = _parse_float(first(row, level_keys))
            pct = round(100 * volume / capacity, 2) if (volume and capacity) else None
            out.append({
                "slug": slugify_reservoir(name.strip()),
                "ts": ts,
                "level_m": level,
                "volume_hm3": volume,
                "pct": pct,
            })
        return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    return 0 if SAIHEbro().run() >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
