# Pantanos

Datos abiertos de embalses, lluvia y rutas de senderismo en España.
Inspirado en [embalses.net](https://www.embalses.net), construido sobre fuentes oficiales (MITECO, AEMET, SAIH de las Confederaciones Hidrográficas) y comunitarias (Wikidata, OpenStreetMap).

## Arquitectura

- **Scrapers** (Python) ejecutados en GitHub Actions ingieren datos y commitean JSON al repo.
- **Frontend** (Astro estático) lee de `data/` y se despliega en GitHub Pages / Vercel.
- Sin servidor, sin base de datos, sin coste recurrente.

## Estructura

```
data/        JSON con datos (commit automático por Actions)
scrapers/    Scripts Python de ingestión
web/         Sitio Astro estático
```

## Desarrollo local

### Scrapers

```bash
cd scrapers
python -m venv .venv && source .venv/bin/activate
pip install -e ..
python -m scrapers.miteco_historical
python -m scrapers.miteco_weekly
```

### Frontend

```bash
cd web
npm install
npm run dev
```

## Fuentes de datos

- MITECO — Boletín hidrológico semanal y BD-Embalses
- AEMET OpenData — Pluviómetros y radar nacional
- SAIH de cada Confederación Hidrográfica — Niveles en tiempo real
- Wikidata + Wikipedia ES — Ficha técnica e historia (CC-BY-SA)
- OpenStreetMap (Overpass API) — Rutas de senderismo (ODbL)

## Licencia

Código bajo MIT. Datos y contenidos respetan la licencia de cada fuente original.
