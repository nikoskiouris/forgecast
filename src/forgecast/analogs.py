"""Historical analog retrieval. Similarity is an input, not the whole forecast."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from forgecast.ingest.cameo import root_code
from forgecast.schema import AnalogMatch, Event, Outcome
from forgecast.staticdata import EPISODES, country_name, interdependence
from forgecast.features import Entity, entity_events

ROOTS = ["10", "11", "12", "13", "14", "15", "16", "163", "17", "18", "19"]


@dataclass
class AnalogSummary:
    rate: float
    max_similarity: float
    matches: list[AnalogMatch]


def window_vector(events: list[Event], start: date, end: date) -> np.ndarray:
    counts = {r: 0.0 for r in ROOTS}
    golds: list[float] = []
    tones: list[float] = []
    mats = 0.0
    for e in events:
        d = e.timestamp.date()
        if not (start <= d <= end):
            continue
        counts[root_code(e.action_code)] = counts.get(root_code(e.action_code), 0.0) + 1
        golds.append(e.goldstein)
        tones.append(e.tone)
        if e.material:
            mats += 1
    vec = [counts[r] for r in ROOTS]
    vec.append(float(np.mean(golds)) if golds else 0.0)
    vec.append(float(np.mean(tones)) if tones else 0.0)
    vec.append(mats)
    arr = np.asarray(vec, dtype=float)
    n = np.linalg.norm(arr)
    return arr / n if n > 0 else arr


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, 0, 1))


def _difference(entity: Entity, analog_country: str, analog_year: int, as_of: date) -> str:
    now = interdependence(entity.country, as_of.year)
    then = interdependence(analog_country, analog_year)
    if now > then + 0.15:
        return (
            f"Economic interdependence with the US/allies is substantially higher today "
            f"({now:.2f} vs {then:.2f} in {analog_year})."
        )
    if now + 0.15 < then:
        return (
            f"Economic interdependence is lower today ({now:.2f} vs {then:.2f} in {analog_year}), "
            "so a break may be politically cheaper."
        )
    if entity.country != analog_country:
        return (
            f"Event sequence resembles {country_name(analog_country)}, "
            f"but the actor today is {country_name(entity.country)}."
        )
    return "Structural conditions are broadly comparable; treat the analog as one input only."


def analog_summary(
    events: list[Event],
    entity: Entity,
    as_of: date,
    outcomes: list[Outcome] | None = None,
    k: int = 3,
) -> AnalogSummary:
    current = window_vector(entity_events(events, entity), as_of - timedelta(days=120), as_of)
    scored: list[tuple[float, dict]] = []
    for ep in EPISODES:
        peak: date = ep["peak"]
        if peak >= as_of:
            continue
        if not (
            ep["country"] == entity.country
            or (ep["material"] and entity.material and ep["material"] == entity.material)
            or ep["disruption"] == entity.disruption
        ):
            continue
        scoped = [e for e in events if e.actor_country == ep["country"]]
        vec = window_vector(scoped, peak - timedelta(days=120), peak)
        sim = cosine(current, vec)
        scored.append((sim, ep))
    if not scored:
        return AnalogSummary(rate=0.0, max_similarity=0.0, matches=[])
    scored.sort(key=lambda x: x[0], reverse=True)
    matches: list[AnalogMatch] = []
    close = [(sim, ep) for sim, ep in scored if sim >= 0.45]
    if close:
        wsum = sum(sim for sim, _ in close[:5])
        osum = sum(sim * (1.0 if ep["disruption"] else 0.0) for sim, ep in close[:5])
        rate = osum / wsum if wsum else 0.0
    else:
        rate = 0.0
    for sim, ep in scored:
        if sim < 0.4 or len(matches) >= k:
            continue
        outcome = ep["disruption"].value if ep["disruption"] else "no disruption (near miss)"
        matches.append(
            AnalogMatch(
                name=ep["name"],
                similarity=round(sim, 3),
                year=ep["peak"].year,
                country=ep["country"],
                material=ep["material"],
                outcome=outcome,
                difference=_difference(entity, ep["country"], ep["peak"].year, as_of),
            )
        )
    max_sim = scored[0][0] if scored else 0.0
    return AnalogSummary(rate=rate, max_similarity=max_sim, matches=matches)
