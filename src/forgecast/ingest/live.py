"""Pull every live Atlanta feed. Never invent events if a source is down."""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx

from forgecast.city import haversine_km, now_eastern
from forgecast.ingest.faa import fetch_faa
from forgecast.ingest.gdot import fetch_gdot
from forgecast.ingest.http import make_client
from forgecast.ingest.marta import fetch_marta
from forgecast.ingest.permits import fetch_traffic_permits, fetch_utility_permits
from forgecast.ingest.weather import fetch_nws, fetch_open_meteo
from forgecast.schema import CityBundle, CityEvent, EventKind

Fetch = Callable[[httpx.Client], list[CityEvent]]

SOURCES: list[tuple[str, Fetch]] = [
    ("gdot", fetch_gdot),
    ("permits", fetch_traffic_permits),
    ("utility", fetch_utility_permits),
    ("nws", fetch_nws),
    ("open-meteo", fetch_open_meteo),
    ("marta", fetch_marta),
    ("faa", fetch_faa),
]


def _dedupe(events: list[CityEvent]) -> list[CityEvent]:
    seen: set[str] = set()
    unique: list[CityEvent] = []
    for ev in events:
        if ev.id in seen:
            continue
        seen.add(ev.id)
        unique.append(ev)
    return _fuzzy_dedupe(unique)


def _norm_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().lower()[:48]


def _fuzzy_dedupe(events: list[CityEvent]) -> list[CityEvent]:
    kept: list[CityEvent] = []
    for ev in events:
        skip = False
        title = _norm_title(ev.title)
        for other in kept:
            if other.kind != ev.kind:
                continue
            if ev.kind is EventKind.WEATHER and (other.raw_type or _norm_title(other.title)) == (
                ev.raw_type or title
            ):
                skip = True
                break
            close = haversine_km(other.lat, other.lon, ev.lat, ev.lon) < 0.45
            if close and _norm_title(other.title) == title:
                skip = True
                break
        if not skip:
            kept.append(ev)
    return kept


def _trim(events: list[CityEvent], cap: int = 800) -> list[CityEvent]:
    quotas = {
        EventKind.EVENT: 40,
        EventKind.WEATHER: 16,
        EventKind.AIRPORT: 4,
        EventKind.TRANSIT: 40,
        EventKind.ROAD: 420,
        EventKind.UTILITY: 160,
        EventKind.PLACE: 0,
    }
    buckets: dict[EventKind, list[CityEvent]] = {k: [] for k in quotas}
    sev = {"high": 0, "mid": 1, "low": 2}
    for ev in sorted(events, key=lambda e: sev.get(e.severity, 9)):
        buckets.setdefault(ev.kind, []).append(ev)
    out: list[CityEvent] = []
    for kind, n in quotas.items():
        out.extend(buckets.get(kind, [])[:n])
        if len(out) >= cap:
            return out[:cap]
    return out[:cap]


def fetch_city_events(http: httpx.Client | None = None) -> CityBundle:
    own = http is None
    client = http or make_client()
    events: list[CityEvent] = []
    ok: list[str] = []
    failed: list[str] = []
    try:
        for name, fn in SOURCES:
            try:
                chunk = fn(client)
                events.extend(chunk)
                ok.append(f"{name}:{len(chunk)}")
            except Exception as exc:  # noqa: BLE001 — one dead feed must not blank the city
                failed.append(f"{name}: {exc}")
    finally:
        if own:
            client.close()
    notes = [
        "Live Atlanta feeds: GDOT traffic, city lane/utility permits, NWS, Open-Meteo, MARTA, FAA.",
        "Map is evidence. The briefing is what sits on your places and commute.",
    ]
    if failed:
        notes.append("Some feeds missed this refresh: " + "; ".join(failed[:4]))
    return CityBundle(
        as_of=now_eastern(),
        events=_trim(_dedupe(events)),
        notes=notes,
        sources_ok=ok,
        sources_failed=failed,
    )
