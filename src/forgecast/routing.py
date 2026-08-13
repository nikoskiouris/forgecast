"""Named Atlanta corridors, not a single GPS polyline.

OSRM's fastest line is a hint. Locals choose I-85 vs I-285. Forgecast names
those habits and lets the briefing score the city against the one you drive.
"""

from __future__ import annotations

import re

import httpx

from forgecast.city import haversine_km
from forgecast.ingest.http import get_json
from forgecast.schema import CommuteRoute

OSRM = "https://router.project-osrm.org/route/v1/driving"

# I-285 clockwise from Spaghetti Junction (I-85 NE).
I285_RING: list[tuple[str, float, float]] = [
    ("i85-ne", -84.2590, 33.8915),
    ("us78", -84.2290, 33.8160),
    ("i20-e", -84.2060, 33.7460),
    ("i85-s", -84.4130, 33.6560),
    ("i75-s", -84.3950, 33.6550),
    ("i20-w", -84.4940, 33.7710),
    ("i75-n", -84.4590, 33.9090),
    ("ga400", -84.3570, 33.9170),
]

# Downtown Connector — the I-85/I-75 habit through the core.
DOWNTOWN = (-84.3908, 33.7550)

# 285 before 85 so "I 285" is not eaten as I-85.
HIGHWAY_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:i|interstate)\s*-?\s*285\b|atlanta bypass|the perimeter", re.IGNORECASE), "I-285"),
    (re.compile(r"\b(?:ga|georgia)\s*-?\s*400\b|\b400\b.*express|\bgeorgia 400", re.IGNORECASE), "GA-400"),
    (re.compile(r"\b(?:i|interstate)\s*-?\s*85\b|downtown connector|northeast expressway", re.IGNORECASE), "I-85"),
    (re.compile(r"\b(?:i|interstate)\s*-?\s*75\b", re.IGNORECASE), "I-75"),
    (re.compile(r"\b(?:i|interstate)\s*-?\s*20\b", re.IGNORECASE), "I-20"),
]

PERIMETER_MIN_KM = 14.0
DETACH_MAX = 1.85


def highways_from_text(blob: str) -> list[str]:
    found: list[str] = []
    for rx, name in HIGHWAY_RULES:
        if rx.search(blob or "") and name not in found:
            found.append(name)
    return found


def highways_from_osrm(route: dict) -> list[str]:
    bits: list[str] = []
    for leg in route.get("legs") or []:
        for step in leg.get("steps") or []:
            bits.append(str(step.get("ref") or ""))
            bits.append(str(step.get("name") or ""))
    return highways_from_text(" ".join(bits))


def name_corridor(highways: list[str]) -> str:
    """Atlanta habit names, not interstate numbers as the headline."""
    if "I-285" in highways:
        return "Perimeter"
    if "GA-400" in highways:
        return "GA-400"
    if "I-85" in highways and "I-75" in highways:
        return "Connector"
    if "I-85" in highways:
        return "I-85"
    if "I-75" in highways:
        return "I-75"
    if "I-20" in highways:
        return "I-20"
    return "local roads"


def spine_highways(name: str, highways: list[str] | None = None) -> set[str]:
    keys = set(highways or [])
    if name == "Perimeter":
        keys.add("I-285")
    elif name == "Connector":
        keys.update({"I-85", "I-75"})
    elif name in {"I-85", "I-75", "I-20", "GA-400"}:
        keys.add(name)
    return keys


def _slug(name: str, used: set[str]) -> str:
    base = name.lower().replace(" ", "")
    if base not in used:
        used.add(base)
        return base
    n = 2
    while f"{base}-{n}" in used:
        n += 1
    slug = f"{base}-{n}"
    used.add(slug)
    return slug


def _coords(route: dict, lon1: float, lat1: float, lon2: float, lat2: float) -> list[list[float]]:
    coords = ((route.get("geometry") or {}).get("coordinates")) or []
    if len(coords) >= 2:
        return coords
    return [[lon1, lat1], [lon2, lat2]]


def parse_osrm_route(
    raw: dict,
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
    kind: str,
    used_ids: set[str],
) -> CommuteRoute | None:
    coords = _coords(raw, lon1, lat1, lon2, lat2)
    if len(coords) < 2:
        return None
    highways = highways_from_osrm(raw)
    name = name_corridor(highways)
    duration = raw.get("duration")
    distance = raw.get("distance")
    return CommuteRoute(
        id=_slug(name, used_ids),
        name=name,
        detail="backup spine" if kind != "shortest" else "usual candidate",
        highways=highways,
        coords=coords,
        duration_s=None if duration is None else float(duration),
        distance_m=None if distance is None else float(distance),
        kind=kind,  # type: ignore[arg-type]
    )


def fetch_osrm(
    http: httpx.Client,
    points: list[tuple[float, float]],
    alternatives: bool = False,
) -> list[dict]:
    path = ";".join(f"{lon:.5f},{lat:.5f}" for lon, lat in points)
    params: dict[str, str] = {
        "overview": "simplified",
        "geometries": "geojson",
        "steps": "true",
    }
    if alternatives:
        params["alternatives"] = "true"
    data = get_json(http, f"{OSRM}/{path}", params)
    if not isinstance(data, dict):
        return []
    if data.get("code") not in (None, "Ok"):
        return []
    return [r for r in (data.get("routes") or []) if isinstance(r, dict)]


def _nearest_ring(lon: float, lat: float) -> int:
    best, idx = 1e9, 0
    for i, (_, rlon, rlat) in enumerate(I285_RING):
        d = haversine_km(lat, lon, rlat, rlon)
        if d < best:
            best, idx = d, i
    return idx


def shorter_arc_via(lon1: float, lat1: float, lon2: float, lat2: float) -> tuple[float, float] | None:
    """Midpoint of the shorter I-285 arc between the nearest ring nodes."""
    i0 = _nearest_ring(lon1, lat1)
    i1 = _nearest_ring(lon2, lat2)
    if i0 == i1:
        return None
    n = len(I285_RING)
    cw = (i1 - i0) % n
    ccw = (i0 - i1) % n
    clockwise = cw <= ccw
    idxs: list[int] = []
    i = i0
    for _ in range(n):
        i = (i + 1) % n if clockwise else (i - 1) % n
        if i == i1:
            break
        idxs.append(i)
    if not idxs:
        return None
    _name, lon, lat = I285_RING[idxs[len(idxs) // 2]]
    return lon, lat


def downtown_via(lon1: float, lat1: float, lon2: float, lat2: float) -> tuple[float, float] | None:
    """Force the Downtown Connector only when it is actually a corridor choice."""
    dlon, dlat = DOWNTOWN
    direct = haversine_km(lat1, lon1, lat2, lon2)
    via = haversine_km(lat1, lon1, dlat, dlon) + haversine_km(dlat, dlon, lat2, lon2)
    if direct < PERIMETER_MIN_KM:
        return None
    if via > direct * 1.65:
        return None
    return dlon, dlat


def _parse_many(
    raws: list[dict],
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
    kind: str,
    used_ids: set[str],
) -> list[CommuteRoute]:
    out: list[CommuteRoute] = []
    for i, raw in enumerate(raws):
        parsed = parse_osrm_route(raw, lon1, lat1, lon2, lat2, kind if i == 0 else "alternate", used_ids)
        if parsed:
            out.append(parsed)
    return out


def pick_corridors(routes: list[CommuteRoute]) -> list[CommuteRoute]:
    """Keep distinct named habits. Drop crazy detours."""
    if not routes:
        return []
    timed = [r for r in routes if r.duration_s]
    cap = None
    if timed:
        fastest = min(timed, key=lambda r: r.duration_s or 1e9)
        cap = (fastest.duration_s or 0) * DETACH_MAX
    viable = [r for r in routes if cap is None or not r.duration_s or r.duration_s <= cap]
    chosen: list[CommuteRoute] = []
    seen: set[str] = set()
    for route in viable:
        if route.name in seen:
            continue
        chosen.append(route)
        seen.add(route.name)
        if len(chosen) >= 3:
            break
    return chosen or routes[:1]


def commute_options(
    http: httpx.Client,
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> list[CommuteRoute]:
    used: set[str] = set()
    routes: list[CommuteRoute] = []
    try:
        raws = fetch_osrm(http, [(lon1, lat1), (lon2, lat2)], alternatives=True)
    except Exception:  # noqa: BLE001 — OSRM down still yields a straight line
        raws = []
    routes.extend(_parse_many(raws, lon1, lat1, lon2, lat2, "shortest", used))
    covered: set[str] = set()
    for route in routes:
        covered |= spine_highways(route.name, route.highways)
    direct = haversine_km(lat1, lon1, lat2, lon2)

    def _add_via(point: tuple[float, float] | None, want: str) -> None:
        if point is None or want in covered:
            return
        try:
            extra = fetch_osrm(http, [(lon1, lat1), point, (lon2, lat2)], alternatives=False)
        except Exception:  # noqa: BLE001
            extra = []
        for parsed in _parse_many(extra, lon1, lat1, lon2, lat2, "perimeter" if want == "I-285" else "alternate", used):
            if want in spine_highways(parsed.name, parsed.highways):
                routes.append(parsed)
                covered.update(spine_highways(parsed.name, parsed.highways))
                return

    if direct >= PERIMETER_MIN_KM:
        if "I-285" not in covered:
            _add_via(shorter_arc_via(lon1, lat1, lon2, lat2), "I-285")
        if "I-85" not in covered:
            _add_via(downtown_via(lon1, lat1, lon2, lat2), "I-85")

    picked = pick_corridors(routes)
    if picked:
        return picked
    return [
        CommuteRoute(
            id="yourroute",
            name="your route",
            detail="straight line — routing was down",
            coords=[[lon1, lat1], [lon2, lat2]],
            kind="shortest",
        )
    ]


def commute_route(
    http: httpx.Client,
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> list[list[float]]:
    opts = commute_options(http, lon1, lat1, lon2, lat2)
    return opts[0].coords if opts else [[lon1, lat1], [lon2, lat2]]
