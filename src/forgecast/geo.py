"""Coordinates for watchlist nodes, suppliers, and event pulses.

Production sites are approximate — enough to put a pin on the right mountain,
strait, or mill. Not a targeting product.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any

from forgecast.config import DEFAULT_PORTFOLIO
from forgecast.explain import headline
from forgecast.exposure import load_portfolio
from forgecast.schema import (
    DisruptionType,
    Event,
    ForecastItem,
    ForecastReport,
    MapPayload,
    MapPin,
    PulseEvent,
)
from forgecast.staticdata import country_name

# Capitals used to scatter background events so they don't stack.
CAPITALS: dict[str, tuple[float, float]] = {
    "CN": (39.90, 116.41),
    "RU": (55.75, 37.62),
    "IR": (35.69, 51.39),
    "YE": (15.37, 44.19),
    "UA": (50.45, 30.52),
    "TW": (25.03, 121.57),
    "CD": (-4.32, 15.31),
    "ID": (-6.21, 106.85),
    "ZA": (-25.75, 28.19),
    "AU": (-35.28, 149.13),
    "MM": (19.76, 96.08),
    "TR": (39.93, 32.86),
    "EG": (30.04, 31.24),
    "JP": (35.68, 139.65),
    "DE": (52.52, 13.40),
    "US": (38.91, -77.04),
    "KR": (37.57, 126.98),
    "GB": (51.51, -0.13),
    "CL": (-33.45, -70.67),
}

# (lat, lon, site label) — mines, mills, foundries, chokepoints.
NODES: dict[tuple[str, str | None], tuple[float, float, str]] = {
    ("CN", "rare_earths"): (40.66, 109.84, "Baotou"),
    ("CN", "gallium"): (24.69, 108.09, "Hechi"),
    ("CN", "germanium"): (23.36, 103.15, "Gejiu"),
    ("CN", "antimony"): (27.69, 111.44, "Xikuangshan"),
    ("CN", "graphite"): (47.58, 130.83, "Luobei"),
    ("RU", "titanium"): (58.05, 60.56, "Verkhnyaya Salda"),
    ("RU", "palladium"): (69.36, 88.19, "Norilsk"),
    ("UA", "neon"): (46.48, 30.73, "Odesa"),
    ("CD", "cobalt"): (-10.72, 25.47, "Kolwezi"),
    ("TW", "semiconductors"): (24.81, 120.97, "Hsinchu"),
    ("YE", None): (12.58, 43.33, "Bab el-Mandeb"),
    ("EG", None): (30.45, 32.35, "Suez Canal"),
    ("IR", None): (26.57, 56.25, "Strait of Hormuz"),
    ("MM", "rare_earths"): (25.87, 98.13, "Kachin"),
    ("ID", "nickel"): (-2.22, 121.59, "Morowali"),
}

CHOKEPOINTS: dict[str, tuple[float, float, str]] = {
    "Bab el-Mandeb / Red Sea": (12.58, 43.33, "Bab el-Mandeb"),
    "Suez Canal": (30.45, 32.35, "Suez Canal"),
    "Strait of Hormuz": (26.57, 56.25, "Strait of Hormuz"),
}

LOCATION_COORDS: dict[str, tuple[float, float]] = {
    "Suez Canal": (30.45, 32.35),
    "Red Sea": (14.50, 42.50),
    "Bab el-Mandeb": (12.58, 43.33),
    "Strait of Hormuz": (26.57, 56.25),
}

SUPPLIER_COORDS: dict[str, tuple[float, float, str]] = {
    "vsmpo": (58.05, 60.56, "Verkhnyaya Salda"),
    "mp_materials": (35.48, -115.53, "Mountain Pass"),
    "lynas": (-28.86, 122.42, "Mount Weld"),
    "tsmc": (24.81, 120.97, "Hsinchu"),
    "glencore_cd": (-10.72, 25.47, "Kolwezi"),
    "graphite_cn": (47.58, 130.83, "Luobei"),
    "ga_cn": (24.69, 108.09, "Hechi"),
    "ge_cn": (23.36, 103.15, "Gejiu"),
    "sb_cn": (27.69, 111.44, "Xikuangshan"),
    "neon_ua": (46.48, 30.73, "Odesa"),
}

WATCH_COUNTRIES = {k[0] for k in NODES}


def make_pin_id(country: str, material: str | None, disruption: DisruptionType) -> str:
    return f"{country}:{material or 'na'}:{disruption.value}"


def locate_node(
    country: str,
    material: str | None,
    chokepoint: str | None = None,
) -> tuple[float, float, str]:
    if chokepoint and chokepoint in CHOKEPOINTS:
        return CHOKEPOINTS[chokepoint]
    node = NODES.get((country, material))
    if node:
        return node
    if country in CAPITALS:
        lat, lon = CAPITALS[country]
        return lat, lon, country_name(country)
    return 20.0, 0.0, country_name(country)


def _jitter(lat: float, lon: float, key: str, scale: float = 0.85) -> tuple[float, float]:
    digest = hashlib.sha1(key.encode()).digest()
    dlat = (digest[0] / 255.0 - 0.5) * 2 * scale
    dlon = (digest[1] / 255.0 - 0.5) * 2 * scale
    return max(-85.0, min(85.0, lat + dlat)), max(-179.0, min(179.0, lon + dlon))


def locate_event(event: Event) -> tuple[float, float]:
    if event.location and event.location in LOCATION_COORDS:
        lat, lon = LOCATION_COORDS[event.location]
        return _jitter(lat, lon, event.id, scale=0.35)
    lat, lon = CAPITALS.get(event.actor_country, (20.0, 0.0))
    return _jitter(lat, lon, event.id)


def pin_from_item(item: ForecastItem, rank: int, horizon_days: int) -> MapPin:
    lat = item.lat if item.lat is not None else 20.0
    lon = item.lon if item.lon is not None else 0.0
    target = item.material.replace("_", " ") if item.material else (item.chokepoint or "supply")
    return MapPin(
        id=item.id,
        lat=lat,
        lon=lon,
        kind="forecast",
        label=item.actor_name,
        subtitle=f"{item.disruption_type.value.replace('_', ' ')} · {target}",
        site=item.site,
        country=item.actor_country,
        material=item.material,
        disruption_type=item.disruption_type,
        probability=item.probability,
        previous_probability=item.previous_probability,
        delta=item.delta,
        chokepoint=item.chokepoint,
        rank=rank,
        exposed_programs=item.exposed_programs,
        exposed_suppliers=item.exposed_suppliers,
        drivers=item.drivers,
        analogs=item.analogs,
        would_increase=item.would_increase,
        would_decrease=item.would_decrease,
        sources=item.sources,
        headline=headline(item, horizon_days),
    )


def supplier_pins(portfolio: dict[str, Any] | None = None) -> list[MapPin]:
    data = portfolio if portfolio is not None else (
        load_portfolio(DEFAULT_PORTFOLIO) if DEFAULT_PORTFOLIO.exists() else {}
    )
    pins: list[MapPin] = []
    for sup in data.get("suppliers", []):
        sid = str(sup.get("id") or "")
        coords = SUPPLIER_COORDS.get(sid)
        if not coords:
            continue
        country = str(sup.get("country") or "")
        material = (sup.get("materials") or [None])[0]
        # Risk pins already sit on the mill. Only plot allied / extra nodes.
        if (country, material) in NODES:
            continue
        lat, lon, site = coords
        mats = ", ".join((sup.get("materials") or [])[:3]).replace("_", " ")
        pins.append(
            MapPin(
                id=f"sup:{sid}",
                lat=lat,
                lon=lon,
                kind="supplier",
                label=str(sup.get("name") or sid),
                subtitle=mats,
                site=site,
                country=str(sup.get("country") or ""),
                material=(sup.get("materials") or [None])[0],
                exposed_programs=list(sup.get("programs") or []),
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
        if event.actor_country not in WATCH_COUNTRIES and event.actor_country not in CAPITALS:
            continue
        lat, lon = locate_event(event)
        picked.append(
            PulseEvent(
                id=event.id,
                lat=lat,
                lon=lon,
                timestamp=event.timestamp,
                actor_country=event.actor_country,
                actor_name=country_name(event.actor_country),
                action=event.action,
                material=event.material,
                tone=event.tone,
                location=event.location,
            )
        )
        if len(picked) >= limit:
            break
    picked.reverse()
    return picked


def build_map(
    report: ForecastReport,
    portfolio: dict[str, Any] | None = None,
    events: list[Event] | None = None,
) -> MapPayload:
    data = portfolio if portfolio is not None else (
        load_portfolio(DEFAULT_PORTFOLIO) if DEFAULT_PORTFOLIO.exists() else {}
    )
    programs = [str(p.get("name") or p.get("id")) for p in data.get("programs", [])]
    pins = [pin_from_item(item, i + 1, report.horizon_days) for i, item in enumerate(report.items)]
    pulse = pulse_events(events, report.as_of) if events else []
    return MapPayload(
        as_of=report.as_of,
        horizon_days=report.horizon_days,
        portfolio=report.portfolio,
        programs=programs,
        pins=pins,
        suppliers=supplier_pins(data),
        pulse=pulse,
        notes=report.notes,
    )
