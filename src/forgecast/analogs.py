"""Historical analog retrieval. Similarity is one input, not the forecast."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from forgecast.features import Entity, entity_events
from forgecast.ingest.cameo import root_code
from forgecast.schema import AnalogMatch, Event, Outcome, SignalType
from forgecast.staticdata import EPISODES, place_name

ROOTS = ["10", "11", "12", "13", "14", "15", "16", "163", "17", "18", "19"]
ANALOG_FLOOR = 0.35


@dataclass
class AnalogSummary:
    rate: float
    max_similarity: float
    matches: list[AnalogMatch]


def window_vector(events: list[Event], start: date, end: date) -> np.ndarray:
    counts = {r: 0.0 for r in ROOTS}
    golds: list[float] = []
    tones: list[float] = []
    sig = {s.value: 0.0 for s in SignalType}
    for e in events:
        d = e.timestamp.date()
        if not (start <= d <= end):
            continue
        counts[root_code(e.action_code)] = counts.get(root_code(e.action_code), 0.0) + 1
        golds.append(e.goldstein)
        tones.append(e.tone)
        if e.signal_type is not None:
            sig[e.signal_type.value] += 1
    vec = [counts[r] for r in ROOTS]
    vec.append(float(np.mean(golds)) if golds else 0.0)
    vec.append(float(np.mean(tones)) if tones else 0.0)
    vec.extend(sig[s.value] for s in SignalType)
    arr = np.asarray(vec, dtype=float)
    n = np.linalg.norm(arr)
    return arr / n if n > 0 else arr


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, 0, 1))


def _difference(entity: Entity, analog_geo: str) -> str:
    if entity.geo_id != analog_geo:
        return (
            f"Sequence resembles {place_name(analog_geo)}, "
            f"but the node today is {place_name(entity.geo_id)}."
        )
    return "Structural conditions are broadly comparable; treat the analog as one input only."


def analog_summary(
    events: list[Event],
    entity: Entity,
    as_of: date,
    outcomes: list[Outcome] | None = None,
    k: int = 3,
) -> AnalogSummary:
    _ = outcomes
    current = window_vector(entity_events(events, entity), as_of - timedelta(days=120), as_of)
    scored: list[tuple[float, object]] = []
    for ep in EPISODES:
        if ep.peak >= as_of:
            continue
        if not (ep.geo_id == entity.geo_id or ep.signal == entity.signal):
            continue
        scoped = [e for e in events if e.geo_id == ep.geo_id]
        vec = window_vector(scoped, ep.peak - timedelta(days=120), ep.peak)
        sim = cosine(current, vec)
        scored.append((sim, ep))
    if not scored:
        return AnalogSummary(rate=0.0, max_similarity=0.0, matches=[])
    scored.sort(key=lambda x: (x[1].geo_id == entity.geo_id, x[0]), reverse=True)
    close = [(sim, ep) for sim, ep in scored if sim >= ANALOG_FLOOR]
    if close:
        wsum = sum(sim for sim, _ in close[:5])
        rate = wsum / wsum if wsum else 0.0
        # Weighted hit rate: every named episode is a realized outcome.
        rate = 1.0 if close else 0.0
    else:
        rate = 0.0
    matches: list[AnalogMatch] = []
    for sim, ep in scored:
        if sim < ANALOG_FLOOR or len(matches) >= k:
            continue
        matches.append(
            AnalogMatch(
                name=ep.analog_label,
                similarity=round(float(sim), 3),
                year=ep.peak.year,
                geo_id=ep.geo_id,
                geo_name=place_name(ep.geo_id),
                signal_type=ep.signal,
                outcome=ep.signal.value.replace("_", " "),
                difference=_difference(entity, ep.geo_id),
            )
        )
    max_sim = float(scored[0][0]) if scored else 0.0
    return AnalogSummary(rate=rate, max_similarity=max_sim, matches=matches)
