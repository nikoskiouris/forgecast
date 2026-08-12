from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from forgecast import __version__
from forgecast.config import DEMO_AS_OF
from forgecast.explain import headline, render_markdown
from forgecast.forecast import forecast as run_forecast
from forgecast.schema import ForecastReport

WEB = Path(__file__).parent / "web"

app = FastAPI(
    title="Forgecast",
    description="Calibrated forecasts of disruptions to the U.S. and allied defense industrial base.",
    version=__version__,
)


@lru_cache(maxsize=8)
def _report(as_of: str, horizon: int) -> ForecastReport:
    return run_forecast(as_of=date.fromisoformat(as_of), horizon_days=horizon)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": __version__}


@app.get("/api/forecast", response_model=ForecastReport)
def api_forecast(
    as_of: str = Query(default=None, description="YYYY-MM-DD"),
    horizon: int = Query(default=180, ge=30, le=365),
) -> ForecastReport:
    day = as_of or DEMO_AS_OF.isoformat()
    return _report(day, horizon)


@app.get("/api/report")
def api_report(
    as_of: str = Query(default=None),
    rank: int = Query(default=1, ge=1, le=20),
    horizon: int = 180,
) -> dict:
    day = as_of or DEMO_AS_OF.isoformat()
    report = _report(day, horizon)
    item = report.items[min(rank, len(report.items)) - 1]
    return {
        "headline": headline(item, report.horizon_days),
        "markdown": render_markdown(item, report.horizon_days),
        "item": item.model_dump(),
    }


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return (WEB / "index.html").read_text()
