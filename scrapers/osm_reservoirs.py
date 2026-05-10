"""
OSM reservoirs — coordenadas y atributos básicos vía Overpass API.

Independiente de Wikidata; útil cuando WDQS no es accesible o como
fallback para embalses no presentes en Wikidata.

Ejecución:
    python -m scrapers.osm_reservoirs
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from scrapers.common import LOOKUP_DIR, RESERVOIRS_DIR, read_json, slugify_reservoir, write_json
from scrapers.common.http import make_client, fetch_json

log = logging.getLogger("osm_reservoirs")

OVERPASS = "https://overpass-api.de/api/interpreter"

# Spain ISO3166-1 = ES; reservoirs and dams.
QUERY = """
[out:json][timeout:120];
area["ISO3166-1"="ES"][admin_level=2];
(
  way["water"="reservoir"]["name"](area);
  relation["water"="reservoir"]["name"](area);
  way["landuse"="reservoir"]["name"](area);
  relation["landuse"="reservoir"]["name"](area);
);
out tags center;
"""


def _centroid(el: dict) -> tuple[float, float] | None:
    if "center" in el:
        return el["center"]["lat"], el["center"]["lon"]
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    return None


_PREFIXES = (
    "Embalse de ", "Embalse del ", "Embalse de la ", "Embalse de los ", "Embalse de las ",
    "Pantano de ", "Pantano del ", "Pantano de la ",
    "Presa de ", "Presa del ", "Presa de la ",
    "Encoro de ", "Encoro do ", "Encoro da ", "Encoro das ", "Encoro dos ",
    "Embassament de ", "Embassament del ", "Embassament d'", "Pantà de ", "Pantà del ",
    "Barragem de ", "Barragem do ",
)


def _slug_candidates(name: str) -> list[str]:
    """Generate slug variations to match MITECO names."""
    raw = name.strip()
    out = {raw}
    for prefix in _PREFIXES:
        if raw.lower().startswith(prefix.lower()):
            out.add(raw[len(prefix):])
            break
    # Also try removing trailing region/qualifier in parens.
    if "(" in raw:
        out.add(raw.split("(")[0].strip())
    return [slugify_reservoir(c) for c in out if c]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    with make_client() as client:
        log.info("Querying Overpass…")
        r = client.post(OVERPASS, data={"data": QUERY}, timeout=180)
        r.raise_for_status()
        data = r.json()

    elements = data.get("elements", [])
    log.info("Got %d OSM reservoir elements", len(elements))

    existing = {p.stem for p in RESERVOIRS_DIR.glob("*.json") if "." not in p.stem.replace("-", "")}
    miteco_slugs = {p.stem for p in RESERVOIRS_DIR.glob("*.json") if not p.name.endswith((".meta.json", ".routes.json"))}

    matched = 0
    duplicates = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("name:es") or tags.get("alt_name")
        if not name:
            continue
        coords = _centroid(el)
        if not coords:
            continue
        for slug in _slug_candidates(name):
            if slug not in miteco_slugs:
                continue
            meta_path = RESERVOIRS_DIR / f"{slug}.meta.json"
            existing_meta = read_json(meta_path) or {}
            if existing_meta.get("coords") and existing_meta.get("source") == "OSM":
                duplicates += 1
                break
            wikidata_qid = tags.get("wikidata")
            wikipedia = tags.get("wikipedia")
            if wikipedia and ":" in wikipedia:
                lang, title = wikipedia.split(":", 1)
                wikipedia_url = f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
            else:
                wikipedia_url = None
            new_meta = {
                "id": slug,
                "name": existing_meta.get("name") or name,
                "coords": list(coords),
                "river": tags.get("river") or existing_meta.get("river"),
                "wikidata_id": wikidata_qid or existing_meta.get("wikidata_id"),
                "wikipedia_url": wikipedia_url or existing_meta.get("wikipedia_url"),
                "osm": {
                    "type": el["type"],
                    "id": el["id"],
                    "url": f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
                },
                "source": "OSM",
                "fetched": now,
            }
            # Preserve any keys we already had (Wikidata-derived).
            for k, v in existing_meta.items():
                if k not in new_meta or new_meta[k] is None:
                    new_meta[k] = v
            write_json(meta_path, new_meta)
            matched += 1
            break

    log.info("Wrote/updated meta for %d reservoirs (skipped %d duplicates)", matched, duplicates)

    write_json(LOOKUP_DIR / "osm_reservoirs.json", {
        "fetched": now,
        "n_osm_elements": len(elements),
        "n_matched": matched,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
