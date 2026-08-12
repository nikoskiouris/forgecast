"""Feature vectors for (country, material, disruption) as of a date."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from forgecast.ingest.cameo import root_code
from forgecast.schema import DisruptionType, Event, Outcome
from forgecast.staticdata import EXPORTER_SHARE, interdependence

FEATURE_NAMES = [
    "n_30",
    "n_90",
    "n_180",
    "threats_90",
    "sanctions_90",
    "protests_90",
    "force_90",
    "fight_90",
    "material_90",
    "mean_goldstein_90",
    "mean_tone_90",
    "delta_tone",
    "days_since_hot",
    "exporter_share",
    "interdependence",
    "analog_rate",
    "analog_sim",
]

ROOT_BUCKETS = {
    "threats_90": {"13"},
    "sanctions_90": {"16", "163"},
    "protests_90": {"14"},
    "force_90": {"15"},
    "fight_90": {"18", "19"},
}


@dataclass
class Entity:
    country: str
    material: str | None
    disruption: DisruptionType


def _in_window(events: list[Event], start: date, end: date) -> list[Event]:
    out = []
    for e in events:
        d = e.timestamp.date()
        if start <= d <= end:
            out.append(e)
    return out


def _mean(xs: list[float], default: float = 0.0) -> float:
    return float(np.mean(xs)) if xs else default


def entity_events(events: list[Event], entity: Entity) -> list[Event]:
    out = []
    for e in events:
        if e.actor_country != entity.country:
            continue
        if entity.material and e.material and e.material != entity.material:
            continue
        out.append(e)
    return out


def feature_vector(
    events: list[Event],
    entity: Entity,
    as_of: date,
    analog_rate: float = 0.0,
    analog_sim: float = 0.0,
) -> np.ndarray:
    scoped = entity_events(events, entity)
    w30 = _in_window(scoped, as_of - timedelta(days=30), as_of)
    w90 = _in_window(scoped, as_of - timedelta(days=90), as_of)
    w180 = _in_window(scoped, as_of - timedelta(days=180), as_of)
    prev90 = _in_window(scoped, as_of - timedelta(days=180), as_of - timedelta(days=90))

    def count_roots(window: list[Event], roots: set[str]) -> float:
        return float(sum(1 for e in window if root_code(e.action_code) in roots))

    last_hot = None
    for e in reversed(scoped):
        if e.timestamp.date() > as_of:
            continue
        if root_code(e.action_code) in {"13", "15", "16", "163", "19"}:
            last_hot = e.timestamp.date()
            break
    days_since = float((as_of - last_hot).days) if last_hot else 365.0

    vec = [
        float(len(w30)),
        float(len(w90)),
        float(len(w180)),
        count_roots(w90, ROOT_BUCKETS["threats_90"]),
        count_roots(w90, ROOT_BUCKETS["sanctions_90"]),
        count_roots(w90, ROOT_BUCKETS["protests_90"]),
        count_roots(w90, ROOT_BUCKETS["force_90"]),
        count_roots(w90, ROOT_BUCKETS["fight_90"]),
        float(sum(1 for e in w90 if e.material == entity.material and entity.material)),
        _mean([e.goldstein for e in w90]),
        _mean([e.tone for e in w90]),
        _mean([e.tone for e in w90]) - _mean([e.tone for e in prev90]),
        days_since,
        float(EXPORTER_SHARE.get((entity.country, entity.material or ""), 0.05)),
        interdependence(entity.country, as_of.year),
        analog_rate,
        analog_sim,
    ]
    return np.asarray(vec, dtype=float)


def label_for(
    entity: Entity,
    as_of: date,
    outcomes: list[Outcome],
    horizon_days: int,
) -> int:
    end = as_of + timedelta(days=horizon_days)
    for o in outcomes:
        if o.country != entity.country:
            continue
        if o.disruption_type != entity.disruption:
            continue
        if entity.material and o.material and o.material != entity.material:
            continue
        if as_of < o.occurred_on <= end:
            return 1
    return 0


def month_starts(start: date, end: date) -> list[date]:
    dates = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        dates.append(date(y, m, 1))
        m += 1
        if m == 13:
            m = 1
            y += 1
    return dates
