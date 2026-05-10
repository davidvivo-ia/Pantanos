from scrapers.common.paths import DATA_DIR, RESERVOIRS_DIR, BASINS_DIR, PROVINCES_DIR, LOOKUP_DIR
from scrapers.common.ids import slugify_reservoir
from scrapers.common.io import read_json, write_json

__all__ = [
    "DATA_DIR",
    "RESERVOIRS_DIR",
    "BASINS_DIR",
    "PROVINCES_DIR",
    "LOOKUP_DIR",
    "slugify_reservoir",
    "read_json",
    "write_json",
]
