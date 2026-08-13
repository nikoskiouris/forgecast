"""Gridpulse HTTP API. One process: map + forecast."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from forgecast import __version__
from forgecast.config import (
    DEFAULT_DB,
    DEFAULT_HORIZON_DAYS,
    DEMO_AS_OF,
    H3_RESOLUTIONS,
    ROOT,
    WEB_DIST,
)
from forgecast.explain import headline, render_markdown
from forgecast.forecast import forecast as run_forecast
from forgecast.geo import build_map
from forgecast.graph import Store
from forgecast.hexagg import hex_series, read_hex_parquet, week_index
from forgecast.sample import generate_world
from forgecast.schema import ForecastReport, MapPayload

DOCS = ROOT / "docs"

app = FastAPI(
    title="Gridpulse",
    description="Calibrated map of the AI power buildout. Publisher, not an adviser.",
    version=__version__,
)


def _first_dir(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_dir() and (path / "index.html").is_file():
            return path
    return None


def _static_root() -> Path | None:
    return _first_dir(WEB_DIST, DOCS)


def _store() -> Store | None:
    if DEFAULT_DB.exists():
        return Store(DEFAULT_DB)
    return None


@lru_cache(maxsize=4)
def _report(as_of: date, top_n: int) -> ForecastReport:
    return run_forecast(as_of=as_of, top_n=top_n, store=_store())


@lru_cache(maxsize=2)
def _map(as_of: date, top_n: int) -> MapPayload:
    report = _report(as_of, top_n)
    world = generate_world()
    return build_map(report, events=world.events)


def _parse_as_of(raw: str | None) -> date:
    if not raw:
        return DEMO_AS_OF
    return date.fromisoformat(raw)


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "product": "Gridpulse",
        "version": __version__,
        "as_of": str(DEMO_AS_OF),
    }


@app.get("/api/meta")
def meta() -> dict:
    baked = DOCS / "data" / "meta.json"
    if baked.is_file():
        import json

        return json.loads(baked.read_text())
    return {
        "product": "Gridpulse",
        "version": __version__,
        "as_of": str(DEMO_AS_OF),
        "horizon_days": DEFAULT_HORIZON_DAYS,
        "disclaimer": "Publisher, not an adviser. Mechanical ticker exposure is not a recommendation.",
    }


@app.get("/api/forecast")
def api_forecast(as_of: str | None = None, top_n: int = 16) -> dict:
    report = _report(_parse_as_of(as_of), top_n)
    return report.model_dump(mode="json")


@app.get("/api/map")
def api_map(as_of: str | None = None, top_n: int = 16) -> dict:
    payload = _map(_parse_as_of(as_of), top_n)
    return payload.model_dump(mode="json")


@app.get("/api/hex/{res}")
def api_hex(res: int, as_of: str | None = None) -> dict:
    if res not in H3_RESOLUTIONS:
        raise HTTPException(status_code=400, detail="res must be 3, 4, or 5")
    series = read_hex_parquet()
    if series is None or not series.h3:
        day = _parse_as_of(as_of)
        world = generate_world()
        known = [e for e in world.events if e.timestamp.date() <= day]
        series = hex_series(known, res=res)
    return series.model_dump(mode="json")


@app.get("/api/cell/{geo_id}")
def api_cell(geo_id: str, as_of: str | None = None) -> dict:
    report = _report(_parse_as_of(as_of), 32)
    items = [i.model_dump(mode="json") for i in report.items if i.geo_id == geo_id]
    if not items:
        raise HTTPException(status_code=404, detail="unknown geo_id")
    return {"geo_id": geo_id, "items": items}


@app.get("/api/flows")
def api_flows(as_of: str | None = None) -> dict:
    payload = _map(_parse_as_of(as_of), 16)
    return {"flows": [f.model_dump(mode="json") for f in payload.flows]}


@app.get("/api/events")
def api_events(as_of: str | None = None) -> dict:
    payload = _map(_parse_as_of(as_of), 16)
    return {"events": [p.model_dump(mode="json") for p in payload.pulses]}


@app.get("/api/report")
def api_report(as_of: str | None = None, rank: int = 1) -> dict:
    report = _report(_parse_as_of(as_of), 16)
    if not report.items:
        raise HTTPException(status_code=404, detail="no forecast")
    idx = max(0, min(rank, len(report.items)) - 1)
    item = report.items[idx]
    return {
        "headline": headline(item, report.horizon_days),
        "markdown": render_markdown(item, report.horizon_days),
        "item": item.model_dump(mode="json"),
    }


@app.get("/api/backtest")
def api_backtest() -> dict:
    baked = DOCS / "data" / "meta.json"
    if baked.is_file():
        import json

        meta = json.loads(baked.read_text())
        if "brier" in meta:
            return {
                "n": meta.get("n"),
                "brier": meta.get("brier"),
                "brier_skill": meta.get("brier_skill"),
                "base_rate": meta.get("base_rate"),
            }
    from forgecast.backtest import walk_forward
    from forgecast.staticdata import train_watchlist

    world = generate_world()
    scores, _ = walk_forward(
        world.events,
        world.outcomes,
        train_watchlist(),
        start=date(2016, 1, 1),
        end=date(2025, 7, 1),
    )
    return scores.model_dump(mode="json")


@app.get("/")
def dashboard() -> FileResponse:
    root = _static_root()
    if root is None:
        raise HTTPException(status_code=404, detail="UI missing — run npm run build or forgecast snapshot")
    return FileResponse(root / "index.html")


def _mount_static() -> None:
    root = _static_root()
    if root is None:
        return
    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    data = root / "data"
    if data.is_dir():
        app.mount("/data", StaticFiles(directory=data), name="data")


_mount_static()


@app.get("/{path:path}")
def spa(path: str) -> FileResponse:
    if path.startswith("api/"):
        raise HTTPException(status_code=404)
    root = _static_root()
    if root is None:
        raise HTTPException(status_code=404, detail="UI missing")
    candidate = (root / path).resolve()
    if str(candidate).startswith(str(root.resolve())) and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(root / "index.html")
