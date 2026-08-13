"""Build a personalized Atlanta day report from live events + user places."""

from __future__ import annotations

import httpx

from forgecast.briefing import kicker, quiet_copy, weekday_label
from forgecast.city import CENTER_LAT, CENTER_LON, in_metro
from forgecast.geocode import geocode_places
from forgecast.impact import commute_pair, corridor_verdict, impacts, stamp_routes
from forgecast.ingest.http import make_client
from forgecast.ingest.live import fetch_city_events
from forgecast.routing import commute_options
from forgecast.schema import CityBundle, CityEvent, CommuteRoute, DayReport, EventKind, Place

# Keep the JSON payload usable on GitHub Pages / first paint.
MAP_CAP = 180


def _priority(ev: CityEvent) -> tuple[int, int]:
    kind_rank = {
        EventKind.EVENT: 0,
        EventKind.WEATHER: 1,
        EventKind.AIRPORT: 2,
        EventKind.TRANSIT: 3,
        EventKind.ROAD: 4,
        EventKind.UTILITY: 5,
        EventKind.PLACE: 6,
    }
    sev = {"high": 0, "mid": 1, "low": 2}[ev.severity]
    return kind_rank.get(ev.kind, 9), sev


def map_events(events: list[CityEvent], keep_ids: set[str]) -> list[CityEvent]:
    ranked = sorted(events, key=_priority)
    picked: list[CityEvent] = []
    seen: set[str] = set()
    for ev in ranked:
        if ev.id in keep_ids and ev.id not in seen:
            picked.append(ev)
            seen.add(ev.id)
    for ev in ranked:
        if ev.id in seen:
            continue
        if ev.kind is EventKind.ROAD and ev.severity == "low" and len(picked) > 80:
            continue
        picked.append(ev)
        seen.add(ev.id)
        if len(picked) >= MAP_CAP:
            break
    return picked


def _notes(bundle: CityBundle, places: list[Place], n_items: int) -> list[str]:
    notes = list(bundle.notes)
    notes.insert(0, f"Watching {kicker(places)}.")
    if n_items == 0:
        notes.append(quiet_copy(len(bundle.events)))
    if bundle.sources_failed:
        notes.append("Live sources that missed: " + ", ".join(s.split(":")[0] for s in bundle.sources_failed))
    return notes


def build_day(
    raw_places: list[dict],
    bundle: CityBundle | None = None,
    http: httpx.Client | None = None,
) -> DayReport:
    own = http is None
    client = http or make_client()
    try:
        places = geocode_places(raw_places, client)
        for p in places:
            if not in_metro(p.lat, p.lon):
                raise ValueError(f"{p.label} is outside the Atlanta area.")
        bundle = bundle or fetch_city_events(client)
        pair = commute_pair(places)
        dest = pair[1].label if pair else None
        routes: list[CommuteRoute] = []
        commute: list[list[float]] = []
        if pair:
            try:
                routes = commute_options(client, pair[0].lon, pair[0].lat, pair[1].lon, pair[1].lat)
            except Exception:  # noqa: BLE001 — OSRM down still yields a straight-line commute
                routes = [
                    CommuteRoute(
                        id="yourroute",
                        name="your route",
                        coords=[[pair[0].lon, pair[0].lat], [pair[1].lon, pair[1].lat]],
                        kind="shortest",
                    )
                ]
            commute = routes[0].coords if routes else []
        items = impacts(bundle.events, places, commute, dest=dest, routes=routes)
        routes = stamp_routes(routes, items)
        keep = {i.event_id for i in items}
        events = map_events(bundle.events, keep)
        lat0 = sum(p.lat for p in places) / len(places)
        lon0 = sum(p.lon for p in places) / len(places)
        zoom = 11.0 if routes else (12.2 if len(places) == 1 else 11.2)
        return DayReport(
            as_of=bundle.as_of,
            weekday=weekday_label(bundle.as_of),
            center_lat=lat0,
            center_lon=lon0,
            zoom=zoom,
            places=places,
            commute=commute,
            routes=routes,
            corridor=corridor_verdict(routes, items),
            items=items,
            events=events,
            notes=_notes(bundle, places, len(items)),
            sources_ok=bundle.sources_ok,
            sources_failed=bundle.sources_failed,
        )
    finally:
        if own:
            client.close()


def city_overview(bundle: CityBundle | None = None, http: httpx.Client | None = None) -> DayReport:
    own = http is None and bundle is None
    client = http or (make_client() if bundle is None else None)
    try:
        bundle = bundle or fetch_city_events(client)
        events = map_events(bundle.events, set())
        return DayReport(
            as_of=bundle.as_of,
            weekday=weekday_label(bundle.as_of),
            center_lat=CENTER_LAT,
            center_lon=CENTER_LON,
            zoom=10.6,
            places=[],
            commute=[],
            items=[],
            events=events,
            notes=bundle.notes,
            sources_ok=bundle.sources_ok,
            sources_failed=bundle.sources_failed,
        )
    finally:
        if own and client is not None:
            client.close()
