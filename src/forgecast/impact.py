"""Score live city events against a person's places and corridors."""

from __future__ import annotations

from datetime import datetime, timedelta

from forgecast.city import as_eastern, distance_to_route_km, haversine_km, now_eastern
from forgecast.schema import CityEvent, CommuteRoute, EventKind, ImpactItem, Place

NEAR_PLACE_KM = 1.6
NEAR_COMMUTE_KM = 0.9
AIRPORT_KM = 10.0
WEEK_KM = 4.0

TIERS = (
    ("hits", "Hits your day"),
    ("could", "Could hit you"),
    ("later", "Later this week"),
)


def commute_pair(places: list[Place]) -> tuple[Place, Place] | None:
    by = {p.label.lower(): p for p in places}
    if "home" in by and "work" in by:
        return by["home"], by["work"]
    if len(places) >= 2:
        return places[0], places[1]
    return None


def as_routes(commute: list[list[float]], routes: list[CommuteRoute] | None) -> list[CommuteRoute]:
    if routes:
        return routes
    if commute and len(commute) >= 2:
        return [CommuteRoute(id="commute", name="your route", coords=commute, kind="shortest")]
    return []


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


def route_hits(ev: CityEvent, routes: list[CommuteRoute]) -> list[CommuteRoute]:
    if ev.metro or not routes:
        return []
    hit: list[CommuteRoute] = []
    for route in routes:
        if _on_commute(ev, route.coords):
            hit.append(route)
    return hit


def _extra_minutes(ev: CityEvent, when: str) -> int:
    if ev.severity == "high":
        return 25 if ev.kind is EventKind.EVENT else 20
    if ev.severity == "mid":
        return 15
    return 10


def extra_minutes(ev: CityEvent | ImpactItem) -> int:
    return _extra_minutes(ev, "now")


def advice_for(
    ev: CityEvent,
    near: list[str],
    on_commute: bool,
    dest: str | None,
    when: str,
    route_names: list[str] | None = None,
    usual_name: str | None = None,
) -> str:
    who = near[0] if near else "your places"
    dest = dest or "work"
    names = [n for n in (route_names or []) if n]
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
    mins = _extra_minutes(ev, when)
    if on_commute and len(names) > 1:
        return f"Leave {mins} minutes earlier: {ev.title} sits on both {' and '.join(names)}."
    if on_commute and names:
        label = names[0]
        if usual_name and label == usual_name:
            return f"Leave {mins} minutes earlier: {ev.title} on your usual {label}."
        return f"Leave {mins} minutes earlier: {ev.title} on {label}."
    if names:
        return f"On {' / '.join(names)} (not your usual): {ev.title}."
    if on_commute:
        return f"Leave {mins} minutes earlier: {ev.title} on your usual route to {dest}."
    if who:
        return f"{ev.title} near {who}."
    return ev.title


def tier_for(
    when: str,
    on_usual: bool,
    on_alt: bool,
    dist: float | None,
    ev: CityEvent,
    usual_id: str | None,
) -> str:
    if when == "week":
        return "later"
    close = dist is not None and dist <= 0.4
    severe_wx = ev.kind is EventKind.WEATHER and ev.severity == "high"
    if usual_id is None:
        if on_usual or on_alt or close or severe_wx:
            return "hits"
        return "could"
    if on_usual or close or severe_wx:
        return "hits"
    return "could"


def score_event(
    ev: CityEvent,
    places: list[Place],
    commute: list[list[float]],
    dest: str | None,
    now: datetime | None = None,
    routes: list[CommuteRoute] | None = None,
    usual_id: str | None = None,
) -> ImpactItem | None:
    now = now or now_eastern()
    when = _happening(ev, now)
    if when == "past":
        return None
    near, dist = _place_hits(ev, places)
    corridor = as_routes(commute, routes)
    hit = route_hits(ev, corridor)
    usual = usual_id or (corridor[0].id if len(corridor) == 1 else None)
    on_usual = any(r.id == usual for r in hit) if usual else bool(hit)
    on_alt = any(r.id != usual for r in hit) if usual else False
    commute_hit = bool(hit)
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
    if on_usual:
        score += 50
    elif commute_hit:
        score += 28
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

    names = []
    for r in hit:
        if r.name not in names:
            names.append(r.name)
    usual_name = next((r.name for r in corridor if r.id == usual), None)
    return ImpactItem(
        event_id=ev.id,
        kind=ev.kind,
        severity=ev.severity,
        title=ev.title,
        summary=ev.summary,
        advice=advice_for(ev, near, on_usual or (usual is None and commute_hit), dest, when, names, usual_name),
        lat=ev.lat,
        lon=ev.lon,
        distance_km=None if dist is None else round(dist, 2),
        near=near,
        on_commute=on_usual or (usual is None and commute_hit),
        on_routes=[r.id for r in hit],
        route_names=names,
        tier=tier_for(when, on_usual, on_alt, dist, ev, usual),
        start=ev.start,
        end=ev.end,
        source=ev.source,
        source_url=ev.source_url,
        score=round(score, 1),
    )


def stamp_routes(routes: list[CommuteRoute], items: list[ImpactItem]) -> list[CommuteRoute]:
    out: list[CommuteRoute] = []
    roadish = {EventKind.ROAD, EventKind.EVENT, EventKind.UTILITY}
    for route in routes:
        on = [i for i in items if route.id in i.on_routes]
        extra = sum(extra_minutes(i) for i in on if i.kind in roadish)
        out.append(route.model_copy(update={"hits": len(on), "extra_min": extra}))
    return out


def retier(items: list[ImpactItem], routes: list[CommuteRoute], usual_id: str | None) -> list[ImpactItem]:
    """Re-stack after the person names the corridor they actually drive."""
    out: list[ImpactItem] = []
    usual_name = next((r.name for r in routes if r.id == usual_id), None)
    for item in items:
        on_usual = usual_id in item.on_routes if usual_id else bool(item.on_routes)
        on_alt = bool(item.on_routes) and (usual_id not in item.on_routes if usual_id else False)
        when = "week" if item.tier == "later" else "now"
        dummy = CityEvent(
            id=item.event_id,
            kind=item.kind,
            severity=item.severity,
            title=item.title,
            lat=item.lat,
            lon=item.lon,
            source=item.source,
        )
        tier = "later" if item.tier == "later" else tier_for(
            when, on_usual, on_alt, item.distance_km, dummy, usual_id
        )
        advice = item.advice
        if item.kind is EventKind.ROAD:
            advice = advice_for(
                dummy, item.near, on_usual or (usual_id is None and bool(item.on_routes)),
                "work", when, item.route_names, usual_name,
            )
        out.append(item.model_copy(update={
            "on_commute": on_usual or (usual_id is None and bool(item.on_routes)),
            "tier": tier,
            "advice": advice,
        }))
    out.sort(key=lambda i: ({"hits": 0, "could": 1, "later": 2}[i.tier], -i.score))
    return out


def corridor_verdict(routes: list[CommuteRoute], items: list[ImpactItem], usual_id: str | None = None) -> str:
    if not routes:
        return ""
    stamped = stamp_routes(routes, items)
    messy = [r for r in stamped if r.hits]
    clean = [r for r in stamped if not r.hits]
    names = " vs ".join(r.name for r in stamped)
    if len(stamped) == 1:
        r = stamped[0]
        if not r.hits:
            return f"{r.name} looks clear. Nothing loud is sitting on your corridor."
        return f"{r.name} is in trouble today — {r.hits} hit{'s' if r.hits != 1 else ''} on your corridor."
    if usual_id is None:
        if not messy:
            return f"{names}. Both look clear. Tap the corridor you actually drive."
        if clean:
            return (
                f"{messy[0].name} is the messy habit today. {clean[0].name} is the clean corridor. "
                "Tap the one you actually drive."
            )
        worst = max(stamped, key=lambda r: (r.hits, r.extra_min))
        return f"Every corridor has weather. {worst.name} is the loudest. Tap the one you actually drive."
    usual = next((r for r in stamped if r.id == usual_id), stamped[0])
    others = [r for r in stamped if r.id != usual_id]
    if not usual.hits and others and others[0].hits:
        return f"Your {usual.name} is clean. {others[0].name} is the messy one — stay on your habit."
    if usual.hits and others and not others[0].hits:
        return f"Your usual {usual.name} is in trouble. {others[0].name} is the clean corridor today."
    if usual.hits:
        return f"Your {usual.name} has {usual.hits} hit{'s' if usual.hits != 1 else ''} today."
    return f"Your {usual.name} looks clear."


def impacts(
    events: list[CityEvent],
    places: list[Place],
    commute: list[list[float]],
    dest: str | None = None,
    now: datetime | None = None,
    limit: int = 16,
    routes: list[CommuteRoute] | None = None,
    usual_id: str | None = None,
) -> list[ImpactItem]:
    now = now or now_eastern()
    corridor = as_routes(commute, routes)
    items = [score_event(ev, places, commute, dest, now, corridor, usual_id) for ev in events]
    hit = [i for i in items if i and i.score > 0]
    hit.sort(key=lambda i: i.score, reverse=True)
    quotas = {
        EventKind.WEATHER: 2,
        EventKind.EVENT: 3,
        EventKind.TRANSIT: 3,
        EventKind.AIRPORT: 1,
        EventKind.ROAD: 6,
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
    picked.sort(key=lambda i: ({"hits": 0, "could": 1, "later": 2}[i.tier], -i.score))
    return picked
