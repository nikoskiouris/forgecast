"""Coordinates, H3 cells, map pins, pulses, and BA↔county flows."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any

from forgecast.explain import headline
from forgecast.schema import (
    Event,
    FlowArc,
    ForecastItem,
    ForecastReport,
    MapPayload,
    MapPin,
    PulseEvent,
    SignalType,
)
from forgecast.staticdata import BAS, COUNTIES, PLANTS, coords, place_name

try:
    import h3 as _h3
except Exception:  # pragma: no cover
    _h3 = None  # type: ignore[assignment]

H3_DEFAULT_RES = 5


def cell_for(lat: float, lon: float, res: int = H3_DEFAULT_RES) -> str | None:
    if _h3 is None:
        return None
    try:
        return str(_h3.latlng_to_cell(lat, lon, res))
    except Exception:
        return None


def make_pin_id(geo_id: str, signal: SignalType) -> str:
    return f"{geo_id}:{signal.value}"


def locate(geo_id: str) -> tuple[float, float, str]:
    lat, lon = coords(geo_id)
    return lat, lon, place_name(geo_id)


def _jitter(lat: float, lon: float, key: str, scale: float = 0.35) -> tuple[float, float]:
    digest = hashlib.sha1(key.encode()).digest()
    dlat = (digest[0] / 255.0 - 0.5) * 2 * scale
    dlon = (digest[1] / 255.0 - 0.5) * 2 * scale
    return max(-85.0, min(85.0, lat + dlat)), max(-179.0, min(179.0, lon + dlon))


def pin_from_item(item: ForecastItem, rank: int, horizon_days: int) -> MapPin:
    lat = item.lat if item.lat is not None else 39.0
    lon = item.lon if item.lon is not None else -98.0
    return MapPin(
        id=item.id,
        lat=lat,
        lon=lon,
        kind="forecast",
        label=item.geo_name,
        subtitle=item.threshold,
        site=item.site,
        geo_id=item.geo_id,
        geo_kind=item.geo_kind,
        signal_type=item.signal_type,
        probability=item.probability,
        previous_probability=item.previous_probability,
        delta=item.delta,
        rank=rank,
        exposed_tickers=item.exposed_tickers,
        drivers=item.drivers,
        analogs=item.analogs,
        would_increase=item.would_increase,
        would_decrease=item.would_decrease,
        sources=item.sources,
        headline=headline(item, horizon_days),
        h3=item.h3,
    )


def plant_pins() -> list[MapPin]:
    pins: list[MapPin] = []
    for plant in PLANTS:
        pins.append(
            MapPin(
                id=str(plant["id"]),
                lat=float(plant["lat"]),
                lon=float(plant["lon"]),
                kind="plant",
                label=str(plant["name"]),
                subtitle=str(plant["operator"]),
                geo_id=str(plant["ba"]),
                geo_kind="ba",
            )
        )
    return pins


def pulse_events(
    events: list[Event],
    as_of: date,
    days: int = 90,
    limit: int = 80,
) -> list[PulseEvent]:
    start = as_of - timedelta(days=days)
    picked: list[PulseEvent] = []
    for event in reversed(events):
        day = event.timestamp.date()
        if day > as_of or day < start:
            continue
        if event.lat is None or event.lon is None:
            continue
        if event.signal_type is None:
            continue
        lat, lon = _jitter(event.lat, event.lon, event.id, scale=0.12)
        picked.append(
            PulseEvent(
                id=event.id,
                lat=lat,
                lon=lon,
                timestamp=event.timestamp,
                actor_country=event.actor_country,
                actor_name=event.actor,
                action=event.action,
                theme=event.theme,
                tone=event.tone,
                location=event.location,
                geo_id=event.geo_id,
            )
        )
        if len(picked) >= limit:
            break
    picked.reverse()
    return picked


def flow_arcs() -> list[FlowArc]:
    arcs: list[FlowArc] = []
    for fips, meta in COUNTIES.items():
        ba = str(meta["ba"])
        if ba not in BAS:
            continue
        clat, clon = coords(fips)
        blat, blon = coords(ba)
        arcs.append(
            FlowArc(
                src_lat=clat,
                src_lon=clon,
                dst_lat=blat,
                dst_lon=blon,
                src_id=fips,
                dst_id=ba,
                weight=1.0,
                label=f"{meta['name']} → {BAS[ba]['name']}",
            )
        )
    return arcs


def build_map(
    report: ForecastReport,
    events: list[Event] | None = None,
    portfolio: dict[str, Any] | None = None,
) -> MapPayload:
    _ = portfolio
    pins = [pin_from_item(item, i + 1, report.horizon_days) for i, item in enumerate(report.items)]
    pulse = pulse_events(events, report.as_of) if events else []
    return MapPayload(
        as_of=report.as_of,
        horizon_days=report.horizon_days,
        portfolio=report.portfolio,
        pins=pins,
        plants=plant_pins(),
        pulses=pulse,
        flows=flow_arcs(),
        notes=report.notes,
    )
