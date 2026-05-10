"""Base abstractions for SAIH scrapers (one per Confederación Hidrográfica).

Each Confederación publica datos en formatos distintos: la BaseSAIH unifica
el output de modo que cada implementación concreta solo deba transformar al
schema común y la persistencia / merging quede gestionada aquí.

Schema esperado por implementaciones:
    [
        {
            "slug": "yesa",
            "ts": "2026-05-10T12:00:00Z",
            "level_m": 488.4,
            "volume_hm3": 312.1,
            "pct": 67.1,
            "outflow_m3s": 8.5,   # opcional
            "inflow_m3s": 12.3,   # opcional
        },
        ...
    ]
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

from scrapers.common import RESERVOIRS_DIR, read_json, write_json

log = logging.getLogger(__name__)


class BaseSAIH(ABC):
    name: str = "saih"
    confederacion: str = "?"

    @abstractmethod
    def fetch(self) -> list[dict]:
        """Return reservoir-level readings normalised to the common schema."""

    def run(self) -> int:
        records = self.fetch()
        log.info("[%s] fetched %d records", self.name, len(records))

        by_slug: dict[str, list[dict]] = defaultdict(list)
        for r in records:
            slug = r.pop("slug", None)
            if slug:
                by_slug[slug].append(r)

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        merged = 0
        for slug, points in by_slug.items():
            path = RESERVOIRS_DIR / f"{slug}.json"
            if not path.exists():
                log.warning("[%s] no MITECO record for slug=%s", self.name, slug)
                continue
            data = read_json(path) or {}
            saih_series: list[dict] = data.setdefault("saih", [])
            seen = {p.get("ts") for p in saih_series}
            for p in sorted(points, key=lambda x: x.get("ts", "")):
                if p.get("ts") in seen:
                    continue
                p["source"] = self.confederacion
                saih_series.append(p)
                seen.add(p.get("ts"))
            # Trim to last 90 days hourly (~2160 points) per reservoir.
            saih_series.sort(key=lambda x: x.get("ts", ""))
            data["saih"] = saih_series[-2200:]
            data["last_updated"] = now
            sources = set(data.get("sources", []))
            sources.add(self.confederacion)
            data["sources"] = sorted(sources)
            write_json(path, data)
            merged += 1
        log.info("[%s] merged into %d reservoirs", self.name, merged)
        return merged
