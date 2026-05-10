from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RESERVOIRS_DIR = DATA_DIR / "reservoirs"
BASINS_DIR = DATA_DIR / "basins"
PROVINCES_DIR = DATA_DIR / "provinces"
LOOKUP_DIR = DATA_DIR / "_lookup"
RAINFALL_DIR = DATA_DIR / "rainfall"

for d in (RESERVOIRS_DIR, BASINS_DIR, PROVINCES_DIR, LOOKUP_DIR, RAINFALL_DIR):
    d.mkdir(parents=True, exist_ok=True)
