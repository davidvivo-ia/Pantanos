"""
Scraper MITECO semanal — refresca BD-Embalses.zip (que MITECO actualiza
los lunes con el bulletin de la semana) y regenera los JSON.

A diferencia de `miteco_historical`, este forzará la descarga fresca del
zip y reportará el diff respecto al último snapshot conocido.

Ejecución:
    python -m scrapers.miteco_weekly
"""

from __future__ import annotations

import logging
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from scrapers.common import DATA_DIR, read_json, write_json
from scrapers.miteco_historical import (
    download,
    export_csv,
    extract,
    parse,
    write_basin_aggregates,
    write_reservoirs,
    write_summary,
    _check_mdb_export,
)

log = logging.getLogger("miteco_weekly")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    _check_mdb_export()

    workdir = Path(tempfile.gettempdir()) / "pantanos-miteco-weekly"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    prev_summary = read_json(DATA_DIR / "summary.json") or {}
    prev_snapshot = prev_summary.get("snapshot_date")
    prev_pct = (prev_summary.get("national") or {}).get("pct")

    zip_path = download(workdir)
    mdb = extract(zip_path)
    csv_text = export_csv(mdb)
    rows, reservoirs = parse(csv_text)
    log.info("Parsed %d rows / %d reservoirs", len(rows), len(reservoirs))

    write_reservoirs(rows, reservoirs)
    write_basin_aggregates(rows, reservoirs)
    write_summary(reservoirs, rows)

    new_summary = read_json(DATA_DIR / "summary.json") or {}
    new_snapshot = new_summary.get("snapshot_date")
    new_pct = (new_summary.get("national") or {}).get("pct")

    if prev_snapshot == new_snapshot:
        log.warning("No new data: snapshot still %s. MITECO may not have published yet.", new_snapshot)
    else:
        log.info("New snapshot: %s (was %s) - national %s%% (was %s%%)",
                 new_snapshot, prev_snapshot, new_pct, prev_pct)

    write_json(DATA_DIR / "_lookup" / "miteco_last_run.json", {
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "previous_snapshot": prev_snapshot,
        "current_snapshot": new_snapshot,
        "previous_pct": prev_pct,
        "current_pct": new_pct,
        "delta_pct": (new_pct - prev_pct) if (prev_pct and new_pct) else None,
    })


if __name__ == "__main__":
    sys.exit(main())
