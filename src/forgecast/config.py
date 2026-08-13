from __future__ import annotations

from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DEFAULT_DB = DATA_DIR / "forgecast.db"
DEFAULT_PORTFOLIO = DATA_DIR / "portfolios" / "gridpulse.yaml"
HEX_PARQUET = DATA_DIR / "hex_week.parquet"
MAP_DIR = DATA_DIR / "map"
WEB_DIR = ROOT / "web"
WEB_DIST = WEB_DIR / "dist"
PKG_WEB = Path(__file__).resolve().parent / "web"
DEFAULT_HORIZON_DAYS = 180
DEFAULT_LOOKBACK_DAYS = 365
DEMO_AS_OF = date(2026, 6, 1)
H3_RESOLUTIONS = (3, 4, 5)
