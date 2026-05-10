"""
Wikidata + Wikipedia ES — ficha técnica, coordenadas, foto e historia.

Una sola consulta SPARQL al endpoint de Wikidata trae todos los embalses
en España con sus propiedades. Luego, para los que tienen sitelink a
Wikipedia ES, descargamos un extracto narrativo via REST API.

Ejecución:
    python -m scrapers.wikidata_meta
    python -m scrapers.wikidata_meta --limit 5  # debug
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from scrapers.common import RESERVOIRS_DIR, LOOKUP_DIR, write_json, slugify_reservoir
from scrapers.common.http import make_client, fetch_json, fetch_bytes

log = logging.getLogger("wikidata_meta")

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIPEDIA_REST = "https://es.wikipedia.org/api/rest_v1/page/summary/{}"
COMMONS_FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/{}"

# Q131681 = embalse / reservoir; Q29 = España; Q12323 = presa (dam)
SPARQL_QUERY = """
SELECT DISTINCT ?item ?itemLabel ?coord ?image ?river ?riverLabel
                ?inception ?capacity ?surface ?height ?length ?damType ?damTypeLabel
                ?article ?provinceLabel
WHERE {
  VALUES ?type { wd:Q131681 wd:Q1321568 wd:Q12323 }
  ?item wdt:P31/wdt:P279* ?type ;
        wdt:P17 wd:Q29 .
  OPTIONAL { ?item wdt:P625 ?coord . }
  OPTIONAL { ?item wdt:P18 ?image . }
  OPTIONAL { ?item wdt:P403 ?river . }
  OPTIONAL { ?item wdt:P571 ?inception . }
  OPTIONAL { ?item wdt:P2234 ?capacity . }
  OPTIONAL { ?item wdt:P2046 ?surface . }
  OPTIONAL { ?item wdt:P2044 ?height . }
  OPTIONAL { ?item wdt:P2043 ?length . }
  OPTIONAL { ?item wdt:P186 ?damType . }
  OPTIONAL { ?item wdt:P131 ?province . }
  OPTIONAL {
    ?article schema:about ?item ;
             schema:isPartOf <https://es.wikipedia.org/> .
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "es". }
}
"""


def _parse_point(coord: str | None) -> tuple[float, float] | None:
    """`Point(-3.123 40.456)` → (40.456, -3.123)."""
    if not coord or not coord.startswith("Point("):
        return None
    inner = coord[len("Point("):-1]
    try:
        lon, lat = inner.split(" ")
        return float(lat), float(lon)
    except (ValueError, IndexError):
        return None


def query_wikidata(client) -> list[dict]:
    log.info("Querying Wikidata SPARQL endpoint…")
    headers = {
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    r = client.post(SPARQL_ENDPOINT, data={"query": SPARQL_QUERY},
                    headers=headers, timeout=120)
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def collapse(rows: list[dict]) -> dict[str, dict]:
    """Multiple rows per item due to OPTIONAL joins → fold into one record."""
    by_qid: dict[str, dict] = {}
    for r in rows:
        qid = r["item"]["value"].rsplit("/", 1)[-1]
        rec = by_qid.setdefault(qid, {
            "qid": qid,
            "label": r.get("itemLabel", {}).get("value"),
            "coords": None,
            "image": None,
            "river": None,
            "year": None,
            "capacity_hm3": None,
            "surface_ha": None,
            "dam_height_m": None,
            "dam_length_m": None,
            "dam_type": None,
            "wikipedia_es": None,
            "province": None,
        })
        if not rec["coords"]:
            rec["coords"] = _parse_point(r.get("coord", {}).get("value"))
        if not rec["image"] and r.get("image"):
            rec["image"] = r["image"]["value"]
        if not rec["river"] and r.get("riverLabel"):
            rec["river"] = r["riverLabel"]["value"]
        if not rec["year"] and r.get("inception"):
            rec["year"] = r["inception"]["value"][:4]
        if not rec["capacity_hm3"] and r.get("capacity"):
            try:
                rec["capacity_hm3"] = float(r["capacity"]["value"])
            except ValueError:
                pass
        if not rec["surface_ha"] and r.get("surface"):
            try:
                # P2046 unit varies; mostly km² → ha
                rec["surface_ha"] = float(r["surface"]["value"])
            except ValueError:
                pass
        if not rec["dam_height_m"] and r.get("height"):
            try:
                rec["dam_height_m"] = float(r["height"]["value"])
            except ValueError:
                pass
        if not rec["dam_length_m"] and r.get("length"):
            try:
                rec["dam_length_m"] = float(r["length"]["value"])
            except ValueError:
                pass
        if not rec["dam_type"] and r.get("damTypeLabel"):
            rec["dam_type"] = r["damTypeLabel"]["value"]
        if not rec["wikipedia_es"] and r.get("article"):
            rec["wikipedia_es"] = r["article"]["value"]
        if not rec["province"] and r.get("provinceLabel"):
            rec["province"] = r["provinceLabel"]["value"]
    return by_qid


def match_to_reservoirs(items: dict[str, dict]) -> dict[str, dict]:
    """Match Wikidata items to MITECO reservoirs by slug of label."""
    matched: dict[str, dict] = {}
    for qid, rec in items.items():
        label = rec.get("label") or ""
        # Wikidata labels often "Embalse de X"; MITECO uses just "X".
        candidates = {label, label.replace("Embalse de ", "").replace("Embalse del ", "").replace("Pantano de ", "")}
        for c in candidates:
            slug = slugify_reservoir(c)
            if (RESERVOIRS_DIR / f"{slug}.json").exists() and slug not in matched:
                matched[slug] = rec
                rec["matched_slug"] = slug
                break
    return matched


def fetch_wikipedia_summary(client, article_url: str) -> dict | None:
    title = article_url.rsplit("/", 1)[-1]
    try:
        data = fetch_json(client, WIKIPEDIA_REST.format(quote(title, safe="")))
    except Exception as e:
        log.warning("Summary fetch failed for %s: %s", title, e)
        return None
    return {
        "extract_html": data.get("extract_html") or f"<p>{data.get('extract', '')}</p>",
        "extract": data.get("extract"),
        "url": data.get("content_urls", {}).get("desktop", {}).get("page", article_url),
        "license": "CC-BY-SA 4.0",
    }


def download_photo(client, image_url: str, slug: str, dst_dir: Path) -> str | None:
    """Download Commons file via Special:FilePath. Returns site-relative path."""
    filename = image_url.rsplit("/", 1)[-1]
    src = COMMONS_FILEPATH.format(quote(filename, safe=""))
    dst_dir.mkdir(parents=True, exist_ok=True)
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        ext = "jpg"
    dst = dst_dir / f"{slug}.{ext}"
    try:
        png = fetch_bytes(client, src + "?width=1200")
    except Exception as e:
        log.warning("Photo download failed for %s: %s", slug, e)
        return None
    if len(png) < 1024:
        log.warning("Photo too small (%d bytes) for %s, skipping", len(png), slug)
        return None
    dst.write_bytes(png)
    return f"/img/reservoirs/{dst.name}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="Only enrich first N reservoirs (debug)")
    parser.add_argument("--no-photos", action="store_true",
                        help="Skip photo downloads")
    parser.add_argument("--no-wikipedia", action="store_true",
                        help="Skip Wikipedia summary fetch")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    photo_dir = Path(__file__).resolve().parents[1] / "web" / "public" / "img" / "reservoirs"

    with make_client() as client:
        rows = query_wikidata(client)
        log.info("SPARQL returned %d rows", len(rows))
        items = collapse(rows)
        log.info("Collapsed to %d items", len(items))
        matched = match_to_reservoirs(items)
        log.info("Matched %d/%d MITECO reservoirs", len(matched),
                 sum(1 for _ in RESERVOIRS_DIR.glob("*.json") if not _.name.endswith(".meta.json") and not _.name.endswith(".routes.json")))

        write_json(LOOKUP_DIR / "wikidata_index.json", {
            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_total": len(items),
            "n_matched": len(matched),
        })

        slugs = list(matched.keys())[: args.limit] if args.limit else list(matched.keys())

        for i, slug in enumerate(slugs, 1):
            rec = matched[slug]
            meta = {
                "id": slug,
                "name": rec.get("label"),
                "wikidata_id": rec["qid"],
                "coords": list(rec["coords"]) if rec["coords"] else None,
                "river": rec.get("river"),
                "province": rec.get("province"),
                "dam": {
                    "type": rec.get("dam_type"),
                    "height_m": rec.get("dam_height_m"),
                    "length_m": rec.get("dam_length_m"),
                    "year": rec.get("year"),
                },
                "capacity_hm3": rec.get("capacity_hm3"),
                "surface_ha": rec.get("surface_ha"),
                "wikipedia_url": rec.get("wikipedia_es"),
                "photo": None,
                "history": None,
                "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }

            if rec.get("wikipedia_es") and not args.no_wikipedia:
                summary = fetch_wikipedia_summary(client, rec["wikipedia_es"])
                if summary:
                    meta["history"] = summary
                time.sleep(0.2)

            if rec.get("image") and not args.no_photos:
                rel = download_photo(client, rec["image"], slug, photo_dir)
                if rel:
                    meta["photo"] = {
                        "url": rel,
                        "credit": "Wikimedia Commons (CC-BY-SA / dominio público)",
                        "source_url": rec["image"],
                    }
                time.sleep(0.2)

            write_json(RESERVOIRS_DIR / f"{slug}.meta.json", meta)
            if i % 25 == 0:
                log.info("Processed %d/%d", i, len(slugs))

        log.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
