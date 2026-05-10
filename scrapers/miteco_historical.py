"""
Scraper MITECO histórico — bootstrap de la BD-Embalses.zip.

Descarga el archivo Microsoft Access de MITECO con datos semanales de
todos los embalses peninsulares >5 hm3 desde 1988, lo extrae con mdbtools
y genera un JSON por embalse en data/reservoirs/{slug}.json.

Requiere `mdbtools` instalado (mdb-export).

Ejecución:
    python -m scrapers.miteco_historical
"""

from __future__ import annotations

import csv
import io
import logging
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from scrapers.common import (
    BASINS_DIR,
    LOOKUP_DIR,
    RESERVOIRS_DIR,
    DATA_DIR,
    read_json,
    slugify_reservoir,
    write_json,
)
from scrapers.common.http import make_client, download_to

log = logging.getLogger("miteco_historical")

ZIP_URL = (
    "https://www.miteco.gob.es/content/dam/miteco/es/agua/temas/"
    "evaluacion-de-los-recursos-hidricos/boletin-hidrologico/"
    "Historico-de-embalses/BD-Embalses.zip"
)
TABLE_NAME = "T_Datos Embalses 1988-2026"


def _check_mdb_export() -> None:
    if not shutil.which("mdb-export"):
        raise SystemExit(
            "mdb-export not found. Install with: apt-get install -y mdbtools  "
            "(or `brew install mdbtools` on macOS)"
        )


def _parse_es_float(s: str) -> float | None:
    if s == "" or s is None:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _parse_iso_date(s: str) -> str | None:
    """Date emitted by mdb-export with `-T %Y-%m-%d`."""
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def download(workdir: Path) -> Path:
    zip_path = workdir / "BD-Embalses.zip"
    if zip_path.exists() and zip_path.stat().st_size > 1_000_000:
        log.info("Reusing %s", zip_path)
        return zip_path
    log.info("Downloading %s …", ZIP_URL)
    with make_client() as client:
        download_to(client, ZIP_URL, zip_path)
    log.info("Downloaded %.1f MB", zip_path.stat().st_size / 1e6)
    return zip_path


def extract(zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".mdb")]
        if not names:
            raise RuntimeError("No .mdb file inside zip")
        target = zip_path.parent / names[0]
        if not target.exists() or target.stat().st_size < 1_000_000:
            zf.extract(names[0], path=zip_path.parent)
    log.info("Extracted MDB: %s (%.1f MB)", target.name, target.stat().st_size / 1e6)
    return target


def export_csv(mdb: Path, table: str = TABLE_NAME) -> str:
    """Export with ISO datetime format to avoid US/EU ambiguity."""
    out = subprocess.run(
        ["mdb-export", "-T", "%Y-%m-%d", "-D", "%Y-%m-%d", str(mdb), table],
        check=True, capture_output=True, text=True
    )
    return out.stdout


def parse(csv_text: str) -> tuple[list[dict], dict[str, dict]]:
    """Return (rows, reservoirs) where reservoirs maps slug → metadata."""
    reader = csv.DictReader(io.StringIO(csv_text))
    rows: list[dict] = []
    reservoirs: dict[str, dict] = {}
    skipped = 0
    for r in reader:
        basin = (r.get("AMBITO_NOMBRE") or "").strip()
        name = (r.get("EMBALSE_NOMBRE") or "").strip()
        date = _parse_iso_date((r.get("FECHA") or "").strip())
        capacity = _parse_es_float((r.get("AGUA_TOTAL") or "").strip())
        current = _parse_es_float((r.get("AGUA_ACTUAL") or "").strip())
        if not name or not date or capacity is None or current is None:
            skipped += 1
            continue
        slug = slugify_reservoir(name)
        rows.append({
            "slug": slug,
            "name": name,
            "basin": basin,
            "date": date,
            "capacity": capacity,
            "current": current,
            "is_hydro": (r.get("ELECTRICO_FLAG") or "").strip() == "1",
        })
        meta = reservoirs.setdefault(slug, {
            "id": slug, "name": name, "basin": basin,
            "is_hydroelectric": False,
            "capacities": set(), "first_date": date, "last_date": date,
        })
        meta["is_hydroelectric"] = meta["is_hydroelectric"] or (
            (r.get("ELECTRICO_FLAG") or "").strip() == "1"
        )
        meta["capacities"].add(capacity)
        meta["first_date"] = min(meta["first_date"], date)
        meta["last_date"] = max(meta["last_date"], date)
    if skipped:
        log.warning("Skipped %d malformed rows", skipped)
    return rows, reservoirs


def write_reservoirs(rows: list[dict], reservoirs: dict[str, dict]) -> None:
    by_slug: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_slug[r["slug"]].append(r)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for slug, items in by_slug.items():
        items.sort(key=lambda x: x["date"])
        meta = reservoirs[slug]
        capacity = max(meta["capacities"])
        levels = [
            {
                "date": it["date"],
                "volume_hm3": round(it["current"], 2),
                "pct": round(100.0 * it["current"] / it["capacity"], 2) if it["capacity"] else None,
            }
            for it in items
        ]
        path = RESERVOIRS_DIR / f"{slug}.json"
        existing = read_json(path) or {}
        out = {
            "id": slug,
            "name": meta["name"],
            "basin": slugify_reservoir(meta["basin"]),
            "basin_name": meta["basin"],
            "is_hydroelectric": meta["is_hydroelectric"],
            "capacity_hm3": round(capacity, 2),
            "first_record": meta["first_date"],
            "last_record": meta["last_date"],
            "levels": levels,
            "rainfall_local": existing.get("rainfall_local", []),
            "saih": existing.get("saih", []),
            "last_updated": now,
            "sources": sorted(set(existing.get("sources", []) + ["MITECO"])),
        }
        write_json(path, out)


def write_basin_aggregates(rows: list[dict], reservoirs: dict[str, dict]) -> None:
    by_basin: dict[str, dict] = defaultdict(lambda: {
        "n": 0, "capacity": 0.0, "history": defaultdict(lambda: [0.0, 0.0])
    })

    latest_per_reservoir: dict[str, dict] = {}
    for r in rows:
        prev = latest_per_reservoir.get(r["slug"])
        if not prev or r["date"] > prev["date"]:
            latest_per_reservoir[r["slug"]] = r

    capacities: dict[str, float] = {
        slug: max(reservoirs[slug]["capacities"]) for slug in reservoirs
    }

    for slug, r in latest_per_reservoir.items():
        b = by_basin[r["basin"]]
        b["n"] += 1
        b["capacity"] += capacities[slug]

    for r in rows:
        cap = capacities[r["slug"]]
        h = by_basin[r["basin"]]["history"][r["date"]]
        h[0] += r["current"]
        h[1] += cap

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for basin_name, agg in by_basin.items():
        slug = slugify_reservoir(basin_name)
        history = sorted(agg["history"].items())
        latest_date, latest_vals = history[-1]
        cur, cap = latest_vals
        out = {
            "id": slug,
            "name": basin_name,
            "n_reservoirs": agg["n"],
            "capacity_hm3": round(agg["capacity"], 2),
            "current_hm3": round(cur, 2),
            "pct": round(100.0 * cur / cap, 2) if cap else None,
            "last_updated": now,
            "history": [
                {"date": d, "current_hm3": round(v[0], 2), "pct": round(100.0 * v[0] / v[1], 2) if v[1] else None}
                for d, v in history
            ],
        }
        write_json(BASINS_DIR / f"{slug}.json", out)


def write_summary(reservoirs: dict[str, dict], rows: list[dict]) -> None:
    latest_per_reservoir: dict[str, dict] = {}
    for r in rows:
        prev = latest_per_reservoir.get(r["slug"])
        if not prev or r["date"] > prev["date"]:
            latest_per_reservoir[r["slug"]] = r

    capacities = {slug: max(reservoirs[slug]["capacities"]) for slug in reservoirs}

    total_cap = sum(capacities.values())
    total_cur = sum(r["current"] for r in latest_per_reservoir.values())
    snapshot_date = max(r["date"] for r in latest_per_reservoir.values())

    enriched = []
    for slug, r in latest_per_reservoir.items():
        cap = capacities[slug]
        meta = reservoirs[slug]
        enriched.append({
            "id": slug,
            "name": meta["name"],
            "basin": slugify_reservoir(meta["basin"]),
            "basin_name": meta["basin"],
            "capacity_hm3": round(cap, 2),
            "volume_hm3": round(r["current"], 2),
            "pct": round(100.0 * r["current"] / cap, 2) if cap else None,
            "date": r["date"],
        })
    enriched.sort(key=lambda x: (x["pct"] or 0), reverse=True)

    summary = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "snapshot_date": snapshot_date,
        "national": {
            "capacity_hm3": round(total_cap, 2),
            "current_hm3": round(total_cur, 2),
            "pct": round(100.0 * total_cur / total_cap, 2) if total_cap else None,
            "n_reservoirs": len(latest_per_reservoir),
        },
        "reservoirs": enriched,
    }
    write_json(DATA_DIR / "summary.json", summary)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    _check_mdb_export()
    workdir = Path(tempfile.gettempdir()) / "pantanos-miteco"
    workdir.mkdir(parents=True, exist_ok=True)

    zip_path = download(workdir)
    mdb = extract(zip_path)
    log.info("Exporting table from MDB …")
    csv_text = export_csv(mdb)
    log.info("Parsing CSV …")
    rows, reservoirs = parse(csv_text)
    log.info("Parsed %d rows across %d reservoirs", len(rows), len(reservoirs))

    log.info("Writing per-reservoir JSON …")
    write_reservoirs(rows, reservoirs)
    log.info("Writing basin aggregates …")
    write_basin_aggregates(rows, reservoirs)
    log.info("Writing summary.json …")
    write_summary(reservoirs, rows)

    LOOKUP_DIR.mkdir(parents=True, exist_ok=True)
    write_json(LOOKUP_DIR / "miteco_index.json", {
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "url": ZIP_URL,
        "table": TABLE_NAME,
        "n_rows": len(rows),
        "n_reservoirs": len(reservoirs),
    })

    log.info("Done. Wrote %d reservoirs", len(reservoirs))


if __name__ == "__main__":
    sys.exit(main())
