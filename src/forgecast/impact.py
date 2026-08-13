"""Score live city events against a person's places and commute."""

from __future__ import annotations

from datetime import datetime, timedelta

from forgecast.city import as_eastern, distance_to_route_km, haversine_km, now_eastern
from forgecast.schema import CityEvent, EventKind, ImpactItem, Place

NEAR_PLACE_KM = 1.6
NEAR_COMMUTE_KM = 0.9
AIRPORT_KM = 10.0
WEEK_KM = 4.0


def commute_pair(places: list[Place]) -> tuple[Place, Place] | None:
    by = {p.label.lower(): p for p in places}
    if "home" in by and "work" in by:
        return by["home"], by["work"]
    if len(places) >= 2:
        return places[0], places[1]
    return None


def _happening(ev: CityEvent, now: datetime) -> str:
    start, end = as_eastern(ev.start), as_eastern(ev.end)
    soon = now + timedelta(hours=18)
    week = now + timedelta(days=7)
    if end and end < now - timedelta(hours=2):
        return "past"
    if start and start > week:
        return "later"
    if start and now <= start <= soon:
        return "today"
    if start and start > soon:
        return "week"
    return "now"


def _place_hits(ev: CityEvent, places: list[Place]) -> tuple[list[str], float | None]:
    if ev.metro:
        return [p.label for p in places], 0.0
    if ev.kind is EventKind.AIRPORT:
        near = []
        best = None
        for p in places:
            d = haversine_km(p.lat, p.lon, ev.lat, ev.lon)
            best = d if best is None else min(best, d)
            if d <= AIRPORT_KM or "airport" in (p.address + p.label).lower():
                near.append(p.label)
        return near, best
    best = None
    near: list[str] = []
    for p in places:
        d = haversine_km(p.lat, p.lon, ev.lat, ev.lon)
        best = d if best is None else min(best, d)
        if d <= NEAR_PLACE_KM or (d <= WEEK_KM and ev.kind in {EventKind.EVENT, EventKind.WEATHER}):
            near.append(p.label)
    return near, best


def _on_commute(ev: CityEvent, coords: list[list[float]]) -> bool:
    if ev.metro or not coords:
        return False
    d = distance_to_route_km(ev.lat, ev.lon, coords)
    return d is not None and d <= NEAR_COMMUTE_KM


def _extra_minutes(ev: CityEvent, when: str) -> int:
    if ev.severity == "high":
        return 25 if ev.kind is EventKind.EVENT else 20
    if ev.severity == "mid":
        return 15
    return 10


def advice_for(
    ev: CityEvent,
    near: list[str],
    on_commute: bool,
    dest: str | None,
    when: str,
) -> str:
    who = near[0] if near else "your places"
    dest = dest or "work"
    if ev.kind is EventKind.WEATHER:
        low = ev.title.lower() + " " + ev.summary.lower()
        if "heat" in low:
            return "Heat advisory today. Ease off midday outdoor time; storms can still pop this afternoon."
        return ev.title
    if ev.kind is EventKind.TRANSIT:
        route = ev.routes[0] if ev.routes else "service"
        if ev.area in {"SUBWAY", "RAIL"} or any(x in ev.title.lower() for x in ("red", "gold", "blue", "green", "rail")):
            return f"MARTA {route} delays may affect trips near {who}."
        title = ev.title.rstrip(".")
        if not title.upper().startswith("MARTA"):
            title = "MARTA " + title
        return f"{title}. Check before you ride."
    if ev.kind is EventKind.AIRPORT:
        return "ATL delays. Build extra time if you fly or use Airport Station."
    if ev.kind is EventKind.EVENT:
        if on_commute or any(x in {n.lower() for n in near} for x in ("work", "home")):
            return f"Avoid {ev.area or 'the venue'} around event time: {ev.title}."
        return f"Major event nearby ({who}): {ev.title}."
    if ev.kind is EventKind.UTILITY:
        bit = ev.title.replace("Utility work: ", "").strip()
        return f"Utility work near {who}: {bit}"
    # roads
    mins = _extra_minutes(ev, when)
    if on_commute:
        return f"Leave {mins} minutes earlier: {ev.title} on your usual route to {dest}."
    if who:
        return f"{ev.title} near {who}."
    return ev.title


def score_event(
    ev: CityEvent,
    places: list[Place],
    commute: list[list[float]],
    dest: str | None,
    now: datetime | None = None,
) -> ImpactItem | None:
    now = now or now_eastern()
    when = _happening(ev, now)
    if when == "past":
        return None
    near, dist = _place_hits(ev, places)
    commute_hit = _on_commute(ev, commute)
    if ev.kind is EventKind.WEATHER and ev.metro:
        near = [p.label for p in places] or near
    if ev.kind is EventKind.TRANSIT and ev.metro and ev.severity != "low":
        near = near or [p.label for p in places]
    if not near and not commute_hit and not (ev.kind is EventKind.WEATHER and ev.metro):
        return None
    if when == "later" and not commute_hit and (dist or 99) > NEAR_PLACE_KM:
        return None

    score = 0.0
    if dist is not None:
        if dist <= 0.4:
            score += 80
        elif dist <= 1.6:
            score += 55
        elif dist <= 4:
            score += 22
    if commute_hit:
        score += 42
    if ev.metro and ev.kind is EventKind.WEATHER:
        score += 48 if ev.severity == "high" else 32
    if ev.kind is EventKind.TRANSIT and ev.severity != "low":
        score += 28
    if ev.kind is EventKind.EVENT:
        score += 30
    score += {"high": 20, "mid": 10, "low": 0}[ev.severity]
    if when == "today":
        score += 8
    if when == "week":
        score *= 0.65

    return ImpactItem(
        event_id=ev.id,
        kind=ev.kind,
        severity=ev.severity,
        title=ev.title,
        summary=ev.summary,
        advice=advice_for(ev, near, commute_hit, dest, when),
        lat=ev.lat,
        lon=ev.lon,
        distance_km=None if dist is None else round(dist, 2),
        near=near,
        on_commute=commute_hit,
        start=ev.start,
        end=ev.end,
        source=ev.source,
        source_url=ev.source_url,
        score=round(score, 1),
    )


def impacts(
    events: list[CityEvent],
    places: list[Place],
    commute: list[list[float]],
    dest: str | None = None,
    now: datetime | None = None,
    limit: int = 16,
) -> list[ImpactItem]:
    now = now or now_eastern()
    items = [score_event(ev, places, commute, dest, now) for ev in events]
    hit = [i for i in items if i and i.score > 0]
    hit.sort(key=lambda i: i.score, reverse=True)
    quotas = {
        EventKind.WEATHER: 2,
        EventKind.EVENT: 3,
        EventKind.TRANSIT: 3,
        EventKind.AIRPORT: 1,
        EventKind.ROAD: 5,
        EventKind.UTILITY: 2,
        EventKind.PLACE: 0,
    }
    used: dict[EventKind, int] = {k: 0 for k in quotas}
    picked: list[ImpactItem] = []
    for item in hit:
        if used[item.kind] >= quotas.get(item.kind, 2):
            continue
        near_dup = any(
            item.kind is p.kind and haversine_km(item.lat, item.lon, p.lat, p.lon) < 0.35
            for p in picked
        )
        if near_dup:
            continue
        picked.append(item)
        used[item.kind] += 1
        if len(picked) >= limit:
            break
    picked.sort(key=lambda i: i.score, reverse=True)
    return picked
