from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from forgecast import __version__
from forgecast.config import DEMO_AS_OF, ROOT
from forgecast.explain import headline, render_markdown
from forgecast.forecast import WATCHLIST, load_training_world
from forgecast.forecast import forecast as run_forecast
from forgecast.geo import build_map
from forgecast.schema import DemoBundle, ForecastReport, MapPayload

WEB = Path(__file__).parent / "web"
DOCS = ROOT / "docs"

app = FastAPI(
    title="Forgecast",
    description="Calibrated forecasts of disruptions to the U.S. and allied defense industrial base.",
    version=__version__,
)


def _first_file(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_file():
            return path
    return None


@lru_cache(maxsize=1)
def _bundle() -> DemoBundle | None:
    path = _first_file(DOCS / "data" / "demo.json", WEB / "data" / "demo.json")
    if path is None:
        return None
    return DemoBundle.model_validate_json(path.read_text())


@lru_cache(maxsize=8)
def _report(as_of: str, horizon: int) -> ForecastReport:
    return run_forecast(
        as_of=date.fromisoformat(as_of),
        horizon_days=horizon,
        top_n=len(WATCHLIST),
    )


def _map_payload(as_of: str, horizon: int) -> MapPayload:
    bundle = _bundle()
    if bundle and as_of in bundle.snapshots:
        return bundle.snapshots[as_of]
    report = _report(as_of, horizon)
    events, _outcomes = load_training_world()
    return build_map(report, events=events)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": __version__, "demo": _bundle() is not None}


@app.get("/api/forecast", response_model=ForecastReport)
def api_forecast(
    as_of: str = Query(default=None, description="YYYY-MM-DD"),
    horizon: int = Query(default=180, ge=30, le=365),
) -> ForecastReport:
    day = as_of or DEMO_AS_OF.isoformat()
    return _report(day, horizon)


@app.get("/api/map", response_model=MapPayload)
def api_map(
    as_of: str = Query(default=None, description="YYYY-MM-DD"),
    horizon: int = Query(default=180, ge=30, le=365),
) -> MapPayload:
    day = as_of or DEMO_AS_OF.isoformat()
    return _map_payload(day, horizon)


@app.get("/api/report")
def api_report(
    as_of: str = Query(default=None),
    rank: int = Query(default=1, ge=1, le=20),
    pin: str | None = Query(default=None),
    horizon: int = 180,
) -> dict:
    day = as_of or DEMO_AS_OF.isoformat()
    payload = _map_payload(day, horizon)
    item = None
    if pin:
        item = next((p for p in payload.pins if p.id == pin), None)
        if item is None:
            raise HTTPException(status_code=404, detail="unknown pin")
    else:
        if not payload.pins:
            raise HTTPException(status_code=404, detail="no forecasts")
        item = payload.pins[min(rank, len(payload.pins)) - 1]
    report = _report(day, horizon)
    full = next((i for i in report.items if i.id == item.id), None)
    target = full or report.items[min(rank, len(report.items)) - 1]
    return {
        "headline": headline(target, report.horizon_days),
        "markdown": render_markdown(target, report.horizon_days),
        "item": target.model_dump(),
    }


@app.get("/")
def dashboard() -> FileResponse:
    path = _first_file(DOCS / "index.html", WEB / "index.html")
    if path is None:
        raise HTTPException(status_code=404, detail="UI missing")
    return FileResponse(path)


@app.get("/assets/{name}")
def assets(name: str) -> FileResponse:
    if "/" in name or name.startswith("."):
        raise HTTPException(status_code=400)
    path = _first_file(DOCS / "assets" / name, WEB / "assets" / name)
    if path is None:
        raise HTTPException(status_code=404)
    return FileResponse(path)


@app.get("/data/{name}")
def data_file(name: str) -> FileResponse:
    if "/" in name or name.startswith("."):
        raise HTTPException(status_code=400)
    path = _first_file(DOCS / "data" / name, WEB / "data" / name)
    if path is None:
        raise HTTPException(status_code=404)
    return FileResponse(path)
