"""Feature vectors for (geo_id, signal) as of a date."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from forgecast.ingest.cameo import root_code
from forgecast.schema import Entity, Event, Outcome, SignalType

FEATURE_NAMES = [
    "n_30",
    "n_90",
    "n_180",
    "attention_90",
    "permit_90",
    "load_90",
    "giga_90",
    "mean_goldstein_90",
    "mean_tone_90",
    "delta_tone",
    "days_since_hot",
    "progress",
    "ba_flag",
    "analog_rate",
    "analog_sim",
]

HAZARD_FEATURES = [
    "n_30",
    "attention_90",
    "permit_90",
    "load_90",
    "giga_90",
    "days_since_hot",
    "progress",
]
SEQUENCE_FEATURES = [
    "attention_90",
    "permit_90",
    "load_90",
    "giga_90",
    "mean_goldstein_90",
    "mean_tone_90",
]

HOT_ROOTS = {"13", "15", "16", "163", "19"}


def horizon_for(signal: SignalType, default: int = 180) -> int:
    if signal is SignalType.GIGA_SITE:
        return 90
    return default


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
        if e.geo_id != entity.geo_id:
            continue
        if e.signal_type is not None and e.signal_type != entity.signal:
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

    def count_signal(window: list[Event], signal: SignalType) -> float:
        return float(sum(1 for e in window if e.signal_type is signal))

    last_hot = None
    for e in reversed(scoped):
        day = e.timestamp.date()
        if day > as_of:
            continue
        if e.signal_type is entity.signal or root_code(e.action_code) in HOT_ROOTS:
            last_hot = day
            break
    days_since = float((as_of - last_hot).days) if last_hot else 365.0
    progress = float(len(w30)) / float(max(len(w180), 1))

    vec = [
        float(len(w30)),
        float(len(w90)),
        float(len(w180)),
        float(len(w90)),
        count_signal(w90, SignalType.PERMIT_MW),
        count_signal(w90, SignalType.LOAD_GROWTH),
        count_signal(w90, SignalType.GIGA_SITE),
        _mean([e.goldstein for e in w90]),
        _mean([e.tone for e in w90]),
        _mean([e.tone for e in w90]) - _mean([e.tone for e in prev90]),
        days_since,
        progress,
        1.0 if entity.geo_kind == "ba" else 0.0,
        analog_rate,
        analog_sim,
    ]
    return np.asarray(vec, dtype=float)


def label_for(
    entity: Entity,
    as_of: date,
    outcomes: list[Outcome],
    horizon_days: int | None = None,
) -> int:
    horizon = horizon_for(entity.signal, horizon_days or 180)
    end = as_of + timedelta(days=horizon)
    for o in outcomes:
        if o.geo_id != entity.geo_id:
            continue
        if o.signal_type != entity.signal:
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
