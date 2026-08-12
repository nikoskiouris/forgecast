"""Deterministic historically-inspired event world for demos and backtests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np

from forgecast.ingest.cameo import GOLDSTEIN, action_label
from forgecast.schema import DisruptionType, Event, Outcome
from forgecast.staticdata import EPISODES, MATERIALS, outcomes_from_episodes

COUNTRIES = ["CN", "RU", "IR", "YE", "UA", "TW", "CD", "ID", "ZA", "AU", "MM", "TR", "EG", "JP", "DE"]
BG_CODES = ["01", "04", "05", "10", "11", "12"]
HOT_CODES = ["13", "14", "15", "16", "163", "19"]


def _eid(*parts: object) -> str:
    raw = "|".join(str(p) for p in parts)
    return "ev-" + hashlib.sha1(raw.encode()).hexdigest()[:16]


def _dt(d: date, rng: np.random.Generator) -> datetime:
    return datetime(d.year, d.month, d.day, int(rng.integers(0, 23)), int(rng.integers(0, 59)))


def _event(
    rng: np.random.Generator,
    day: date,
    country: str,
    code: str,
    material: str | None,
    target: str | None = "US",
    source: str = "sample",
    disruption: DisruptionType | None = None,
    location: str | None = None,
) -> Event:
    tone = float(GOLDSTEIN.get(code, 0.0)) + float(rng.normal(0, 1.2))
    return Event(
        id=_eid(day, country, code, material, rng.integers(0, 10_000_000)),
        timestamp=_dt(day, rng),
        actor=country,
        actor_country=country,
        action=action_label(code),
        action_code=code,
        target=target,
        target_country=target if target and len(target) == 2 else None,
        material=material,
        location=location,
        goldstein=float(GOLDSTEIN.get(code, 0.0)),
        tone=tone,
        source_url=f"https://example.invalid/events/{country}/{day.isoformat()}",
        source=source,
        disruption_type=disruption,
    )


@dataclass
class World:
    events: list[Event]
    outcomes: list[Outcome]


def generate_world(
    seed: int = 42,
    start: date = date(2009, 1, 1),
    end: date = date(2025, 12, 31),
) -> World:
    rng = np.random.default_rng(seed)
    events: list[Event] = []

    day = start
    while day <= end:
        # Sparse background diplomacy so the signal is not drowned.
        if int(rng.integers(0, 3)) == 0:
            c = str(rng.choice(COUNTRIES))
            code = str(rng.choice(BG_CODES))
            mat = str(rng.choice(MATERIALS)) if rng.random() < 0.15 else None
            events.append(_event(rng, day, c, code, mat))
        day += timedelta(days=1)

    for ep in EPISODES:
        peak: date = ep["peak"]
        country: str = ep["country"]
        material: str | None = ep["material"]
        disruption = ep["disruption"]
        is_miss = disruption is None
        # Ramp intensity over ~120 days.
        for delta in range(120, -1, -1):
            d = peak - timedelta(days=delta)
            if d < start or d > end:
                continue
            progress = 1.0 - delta / 120.0
            n = int(rng.poisson(0.4 + 2.2 * progress))
            for _ in range(n):
                if progress < 0.35:
                    code = str(rng.choice(["11", "12", "13", "10"]))
                elif progress < 0.75:
                    code = str(rng.choice(["13", "15", "16", "14"]))
                else:
                    code = str(rng.choice(["13", "16", "163", "15", "19"]))
                loc = None
                if ep["id"] in {"suez_2021"}:
                    loc = "Suez Canal"
                if ep["id"] in {"redsea_2023"}:
                    loc = "Red Sea"
                events.append(_event(rng, d, country, code, material, location=loc))
        # The actual disruption event (skip for near-misses).
        if not is_miss and start <= peak <= end:
            code = "163" if disruption in {
                DisruptionType.EXPORT_RESTRICTION,
                DisruptionType.SANCTIONS,
            } else "19"
            if disruption == DisruptionType.CIVIL_UNREST:
                code = "14"
            if disruption == DisruptionType.FACTORY_SHUTDOWN:
                code = "16"
            if disruption == DisruptionType.SHIPPING_THREAT:
                code = "19"
            loc = "Suez Canal" if ep["id"] == "suez_2021" else None
            loc = "Red Sea" if ep["id"] == "redsea_2023" else loc
            events.append(
                _event(
                    rng,
                    peak,
                    country,
                    code,
                    material,
                    disruption=disruption,
                    location=loc,
                    source="sample-label",
                )
            )
        # Mild aftershocks.
        if not is_miss:
            for delta in range(1, 45):
                d = peak + timedelta(days=delta)
                if d > end:
                    break
                if rng.random() < 0.25:
                    events.append(_event(rng, d, country, "11", material))

    events.sort(key=lambda e: e.timestamp)
    return World(events=events, outcomes=outcomes_from_episodes())
