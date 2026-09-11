"""Deterministic sample world of the AI power buildout."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache

import numpy as np

from forgecast.geo import cell_for
from forgecast.ingest.cameo import GOLDSTEIN, action_label
from forgecast.schema import Event, Outcome, SignalType
from forgecast.staticdata import (
    BAS,
    COUNTIES,
    EPISODES,
    coords,
    geo_kind_of,
    outcomes_from_episodes,
    place_name,
)

BG_CODES = ["01", "04", "05", "10", "11", "12"]
GEO_IDS = list(BAS) + list(COUNTIES)

THEME = {
    SignalType.LOAD_GROWTH: "load",
    SignalType.PERMIT_MW: "permit",
    SignalType.GIGA_SITE: "campus",
}


def _eid(*parts: object) -> str:
    raw = "|".join(str(p) for p in parts)
    return "ev-" + hashlib.sha1(raw.encode()).hexdigest()[:16]


def _dt(d: date, rng: np.random.Generator) -> datetime:
    return datetime(d.year, d.month, d.day, int(rng.integers(0, 23)), int(rng.integers(0, 59)))


def _event(
    rng: np.random.Generator,
    day: date,
    geo_id: str,
    code: str,
    signal: SignalType | None,
    source: str = "sample",
) -> Event:
    lat, lon = coords(geo_id)
    lat = lat + float(rng.normal(0, 0.08))
    lon = lon + float(rng.normal(0, 0.08))
    tone = float(GOLDSTEIN.get(code, 0.0)) + float(rng.normal(0, 1.2))
    kind = geo_kind_of(geo_id)
    return Event(
        id=_eid(day, geo_id, code, signal, rng.integers(0, 10_000_000)),
        timestamp=_dt(day, rng),
        actor=place_name(geo_id),
        actor_country="US",
        action=action_label(code),
        action_code=code,
        target="grid",
        target_country="US",
        theme=THEME.get(signal) if signal else None,
        location=place_name(geo_id),
        lat=lat,
        lon=lon,
        h3=cell_for(lat, lon, 5),
        geo_id=geo_id,
        geo_kind=kind,  # type: ignore[arg-type]
        goldstein=float(GOLDSTEIN.get(code, 0.0)),
        tone=tone,
        source_url=f"https://example.invalid/grid/{geo_id}/{day.isoformat()}",
        source=source,
        signal_type=signal,
    )


@dataclass
class World:
    events: list[Event]
    outcomes: list[Outcome]


@lru_cache(maxsize=2)
def generate_world(
    seed: int = 42,
    start: date = date(2009, 1, 1),
    end: date = date(2026, 12, 31),
) -> World:
    rng = np.random.default_rng(seed)
    events: list[Event] = []

    day = start
    while day <= end:
        if int(rng.integers(0, 3)) == 0:
            geo_id = str(rng.choice(GEO_IDS))
            code = str(rng.choice(BG_CODES))
            events.append(_event(rng, day, geo_id, code, None))
        day += timedelta(days=1)

    for ep in EPISODES:
        ramp = max((ep.peak - ep.start).days, 150)
        for delta in range(ramp, -1, -1):
            d = ep.peak - timedelta(days=delta)
            if d < start or d > end or d < ep.start:
                continue
            progress = 1.0 - delta / float(ramp)
            n = int(rng.poisson(0.6 + 2.8 * progress))
            for _ in range(n):
                if progress < 0.35:
                    code = str(rng.choice(["11", "12", "13", "10"]))
                elif progress < 0.75:
                    code = str(rng.choice(["13", "15", "16", "14"]))
                else:
                    code = str(rng.choice(["13", "16", "163", "15", "19"]))
                events.append(_event(rng, d, ep.geo_id, code, ep.signal))
        if start <= ep.peak <= end:
            code = "163" if ep.signal is SignalType.PERMIT_MW else "19"
            if ep.signal is SignalType.LOAD_GROWTH:
                code = "16"
            events.append(_event(rng, ep.peak, ep.geo_id, code, ep.signal, source="sample-label"))
        for delta in range(1, 45):
            d = ep.peak + timedelta(days=delta)
            if d > end:
                break
            if rng.random() < 0.25:
                events.append(_event(rng, d, ep.geo_id, "11", ep.signal))

    events.sort(key=lambda e: e.timestamp)
    return World(events=events, outcomes=outcomes_from_episodes())
