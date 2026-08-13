from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from forgecast import __version__
from forgecast.config import ROOT
from forgecast.day import build_day, city_overview
from forgecast.geocode import geocode
from forgecast.ingest.http import make_client
from forgecast.ingest.live import fetch_city_events
from forgecast.schema import CityBundle, DayReport, Place

WEB = Path(__file__).parent / "web"
DOCS = ROOT / "docs"

app = FastAPI(
    title="Forgecast",
    description="Know what will affect your day in Atlanta—before it does.",
    version=__version__,
)

_CACHE: tuple[float, CityBundle] | None = None
_TTL = 180.0


class PlaceIn(BaseModel):
    label: str = "home"
    address: str = ""
    lat: float | None = None
    lon: float | None = None


class DayRequest(BaseModel):
    places: list[PlaceIn] = Field(default_factory=list)


def _first_file(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_file():
            return path
    return None


@lru_cache(maxsize=1)
def _baked() -> CityBundle | None:
    path = _first_file(DOCS / "data" / "demo.json", WEB / "data" / "demo.json")
    if path is None:
        return None
    try:
        return CityBundle.model_validate_json(path.read_text())
    except (ValueError, TypeError, OSError):
        return None


def live_bundle(force: bool = False) -> CityBundle:
    global _CACHE
    now = time.time()
    if not force and _CACHE and now - _CACHE[0] < _TTL:
        return _CACHE[1]
    try:
        bundle = fetch_city_events()
        _CACHE = (now, bundle)
        return bundle
    except Exception:  # noqa: BLE001 — fall back to last baked snapshot
        baked = _baked()
        if baked:
            return baked
        raise


@app.get("/api/health")
def health() -> dict:
    baked = _baked()
    return {
        "ok": True,
        "version": __version__,
        "city": "Atlanta",
        "demo": baked is not None,
        "live": True,
    }


@app.get("/api/events", response_model=CityBundle)
def api_events(refresh: bool = False) -> CityBundle:
    try:
        return live_bundle(force=refresh)
    except Exception as exc:
        baked = _baked()
        if baked:
            return baked
        raise HTTPException(status_code=502, detail=f"city feeds unavailable: {exc}") from exc


@app.get("/api/geocode", response_model=Place)
def api_geocode(q: str = Query(..., min_length=2)) -> Place:
    try:
        with make_client() as http:
            return geocode(q, http, label="place")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _from_query(home: str | None, work: str | None, gym: str | None) -> list[dict]:
    raw = []
    if home:
        raw.append({"label": "home", "address": home})
    if work:
        raw.append({"label": "work", "address": work})
    if gym:
        raw.append({"label": "gym", "address": gym})
    return raw


@app.get("/api/day", response_model=DayReport)
def api_day_get(
    home: str | None = None,
    work: str | None = None,
    gym: str | None = None,
) -> DayReport:
    bundle = live_bundle()
    raw = _from_query(home, work, gym)
    if not raw:
        return city_overview(bundle)
    try:
        return build_day(raw, bundle=bundle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/day", response_model=DayReport)
def api_day_post(body: DayRequest) -> DayReport:
    bundle = live_bundle()
    raw = [p.model_dump() for p in body.places if p.address or (p.lat is not None and p.lon is not None)]
    if not raw:
        return city_overview(bundle)
    try:
        return build_day(raw, bundle=bundle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/")
def dashboard() -> FileResponse:
    path = _first_file(WEB / "index.html", DOCS / "index.html")
    if path is None:
        raise HTTPException(status_code=404, detail="UI missing")
    return FileResponse(path)


@app.get("/assets/{name}")
def assets(name: str) -> FileResponse:
    if "/" in name or name.startswith("."):
        raise HTTPException(status_code=400)
    path = _first_file(WEB / "assets" / name, DOCS / "assets" / name)
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
