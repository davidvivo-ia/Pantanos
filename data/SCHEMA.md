# Schema de datos

Todos los ficheros JSON con `ensure_ascii=False`, indentado 2 espacios.

## `reservoirs/{slug}.json` — Series temporales por embalse

```json
{
  "id": "albarellos",
  "name": "Albarellos",
  "basin": "mino-sil",
  "basin_name": "Miño - Sil",
  "is_hydroelectric": true,
  "capacity_hm3": 91.0,
  "levels": [
    { "date": "1988-05-01", "volume_hm3": 32.0, "pct": 35.16 },
    { "date": "1988-12-01", "volume_hm3": 44.0, "pct": 48.35 }
  ],
  "rainfall_local": [
    { "date": "2026-05-09", "mm": 4.2, "source": "AEMET", "station": "1495", "distance_km": 8.4 }
  ],
  "saih": [
    { "ts": "2026-05-10T18:00:00+02:00", "level_m": 312.4, "volume_hm3": 64.1, "outflow_m3s": 12.3 }
  ],
  "last_updated": "2026-05-10T18:30:00Z",
  "sources": ["MITECO", "AEMET"]
}
```

## `reservoirs/{slug}.meta.json` — Ficha estática (refresco mensual)

```json
{
  "id": "albarellos",
  "name": "Albarellos",
  "coords": [42.07, -8.06],
  "river": "Avia",
  "province": "Ourense",
  "ccaa": "Galicia",
  "dam": { "type": "gravedad", "height_m": 95, "length_m": 215, "year": 1969 },
  "capacity_hm3": 91.0,
  "surface_ha": 195,
  "uses": ["abastecimiento", "hidroeléctrico"],
  "history_html": "<p>...</p>",
  "history_source": "https://es.wikipedia.org/wiki/Embalse_de_Albarellos",
  "history_license": "CC-BY-SA 4.0",
  "photo": {
    "url": "/img/reservoirs/albarellos.jpg",
    "credit": "Foto: Autor en Wikimedia Commons (CC-BY-SA 4.0)",
    "source_url": "https://commons.wikimedia.org/wiki/File:..."
  },
  "wikidata_id": "Q5734020",
  "wikipedia_url": "https://es.wikipedia.org/wiki/Embalse_de_Albarellos"
}
```

## `reservoirs/{slug}.routes.json` — Rutas senderismo OSM (refresco mensual)

```json
{
  "id": "albarellos",
  "fetched": "2026-05-10",
  "search_radius_km": 10,
  "routes": [
    {
      "osm_id": "relation/12345678",
      "name": "GR-58 Sendero del Avia",
      "length_km": 14.2,
      "network": "rwn",
      "ref": "GR-58",
      "sac_scale": "hiking",
      "url": "https://www.openstreetmap.org/relation/12345678",
      "geometry": [[42.07, -8.06], [42.08, -8.05]]
    }
  ]
}
```

## `basins/{slug}.json` — Agregado por cuenca

```json
{
  "id": "ebro",
  "name": "Ebro",
  "capacity_hm3": 7563.0,
  "current_hm3": 5421.3,
  "pct": 71.7,
  "n_reservoirs": 88,
  "last_updated": "2026-05-10T18:30:00Z",
  "history": [
    { "date": "2026-05-04", "pct": 71.5 }
  ]
}
```

## `provinces/{slug}.json` — Agregado por provincia

Mismo formato que `basins/`.

## `summary.json` — Snapshot landing

```json
{
  "generated": "2026-05-10T18:30:00Z",
  "national": { "capacity_hm3": 56000, "current_hm3": 38400, "pct": 68.6 },
  "basins": [...],
  "top_filling": [...],
  "top_emptying": [...]
}
```

## `_lookup/aemet_station_per_reservoir.json`

Mapeo cacheado embalse → estación AEMET más cercana.

```json
{
  "albarellos": { "idema": "1495", "name": "OURENSE", "distance_km": 8.4, "lat": 42.31, "lon": -7.86 }
}
```

## `rainfall/national.json`, `rainfall/radar/{ts}.png`

Pluviómetros y mosaico radar nacional AEMET.
