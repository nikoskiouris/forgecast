from __future__ import annotations

from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DEFAULT_DB = DATA_DIR / "forgecast.db"
DEFAULT_PORTFOLIO = DATA_DIR / "portfolios" / "demo_defense.yaml"
DEFAULT_HORIZON_DAYS = 180
DEFAULT_LOOKBACK_DAYS = 365
# Sample world ends 2025. This date sits before the 2024 antimony controls.
DEMO_AS_OF = date(2024, 6, 1)
