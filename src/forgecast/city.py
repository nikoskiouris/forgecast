"""Atlanta metro geography: bbox, stations, distance, road helpers."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")

# Tight enough to be "Atlanta area", wide enough for the perimeter and airport.
SOUTH, WEST, NORTH, EAST = 33.47, -84.90, 34.26, -83.90
CENTER_LAT = 33.749
CENTER_LON = -84.388

METRO_COUNTIES = (
    "Fulton",
    "DeKalb",
    "Cobb",
    "Gwinnett",
    "Clayton",
    "Fayette",
    "Henry",
    "Douglas",
    "Rockdale",
    "Cherokee",
    "Forsyth",
    "Coweta",
    "Paulding",
    "Walton",
)

CORE_COUNTIES = (
    "Fulton",
    "DeKalb",
    "Cobb",
    "Gwinnett",
    "Clayton",
    "Fayette",
    "Henry",
    "Douglas",
)

CORE_SAME = {
    "013121",
    "013089",
    "013067",
    "013135",
    "013063",
    "013113",
    "013151",
    "013097",
}

METRO_COUNTY_SQL = ",".join(f"'{c}'" for c in METRO_COUNTIES)

MAJOR_PREFIXES = ("I-", "I ", "US-", "US ", "GA-400", "SR 400", "SR400", "GA 400")
MAJOR_NEEDLES = (
    "DOWNTOWN CONNECTOR",
    "CONNECTOR",
    "LANGFORD",
    "STONE MOUNTAIN FREEWAY",
    "PERIMETER",
)

# Hartsfield-Jackson
ATL_AIRPORT = (33.6407, -84.4277)

# Real rail stations — used to pin MARTA alerts that name a stop or line.
MARTA_STATIONS: dict[str, tuple[float, float]] = {
    "airport": (33.6407, -84.4463),
    "college park": (33.6517, -84.4488),
    "east point": (33.6766, -84.4406),
    "lakewood": (33.7006, -84.4289),
    "oakland city": (33.7170, -84.4253),
    "west end": (33.7358, -84.4136),
    "garnett": (33.7480, -84.3963),
    "five points": (33.7539, -84.3916),
    "georgia state": (33.7505, -84.3863),
    "peachtree center": (33.7591, -84.3876),
    "civic center": (33.7663, -84.3872),
    "north avenue": (33.7717, -84.3867),
    "north ave": (33.7717, -84.3867),
    "midtown": (33.7811, -84.3863),
    "arts center": (33.7893, -84.3872),
    "lindbergh": (33.8220, -84.3694),
    "buckhead": (33.8478, -84.3676),
    "medical center": (33.9107, -84.3516),
    "dunwoody": (33.9210, -84.3444),
    "sandy springs": (33.9322, -84.3515),
    "north springs": (33.9445, -84.3573),
    "lenox": (33.8472, -84.3566),
    "brookhaven": (33.8600, -84.3394),
    "chamblee": (33.8876, -84.3069),
    "doraville": (33.9022, -84.2803),
    "king memorial": (33.7499, -84.3756),
    "inman park": (33.7575, -84.3528),
    "edgewood": (33.7619, -84.3396),
    "east lake": (33.7652, -84.3126),
    "decatur": (33.7747, -84.2971),
    "avondale": (33.7752, -84.2818),
    "kensington": (33.7747, -84.2515),
    "indian creek": (33.7699, -84.2293),
    "west lake": (33.7532, -84.4453),
    "ashby": (33.7563, -84.4176),
    "vine city": (33.7566, -84.4040),
    "gwcc": (33.7590, -84.3977),
    "cnn center": (33.7590, -84.3977),
    "mercedes-benz": (33.7553, -84.4008),
    "bankhead": (33.7719, -84.4287),
    "hamilton e. holmes": (33.7544, -84.4696),
    "holmes": (33.7544, -84.4696),
}

LINE_PINS: dict[str, tuple[float, float]] = {
    "red": MARTA_STATIONS["lindbergh"],
    "gold": MARTA_STATIONS["five points"],
    "blue": MARTA_STATIONS["georgia state"],
    "green": MARTA_STATIONS["ashby"],
    "streetcar": MARTA_STATIONS["peachtree center"],
}

VENUES: dict[str, tuple[float, float]] = {
    "mercedes-benz stadium": (33.7553, -84.4008),
    "state farm arena": (33.7573, -84.3963),
    "truist park": (33.8908, -84.4677),
    "gas south arena": (33.9913, -84.0942),
    "ponce city market": (33.7724, -84.3652),
}


def now_eastern() -> datetime:
    return datetime.now(EASTERN)


def as_eastern(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).astimezone(EASTERN)
    return dt.astimezone(EASTERN)


def from_epoch_ms(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        ms = int(float(value))
    except (TypeError, ValueError):
        return None
    # Time-of-day stored against year 1900 shows up as a large negative.
    if ms < 0:
        return None
    if ms < 10_000_000_000:
        ms *= 1000
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    # Drop nonsense far-past timestamps.
    if dt.year < 2018:
        return None
    return dt.astimezone(EASTERN)


def in_metro(lat: float, lon: float) -> bool:
    return SOUTH <= lat <= NORTH and WEST <= lon <= EAST


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _xy(lat: float, lon: float, lat0: float) -> tuple[float, float]:
    r = 6371.0
    x = math.radians(lon) * math.cos(math.radians(lat0)) * r
    y = math.radians(lat) * r
    return x, y


def point_to_segment_km(
    lat: float,
    lon: float,
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    lat0 = (lat1 + lat2) / 2 or lat
    px, py = _xy(lat, lon, lat0)
    ax, ay = _xy(lat1, lon1, lat0)
    bx, by = _xy(lat2, lon2, lat0)
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return haversine_km(lat, lon, lat1, lon1)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    qx, qy = ax + t * dx, ay + t * dy
    # Convert back approximately via distances to A.
    return math.hypot(px - qx, py - qy)


def distance_to_route_km(lat: float, lon: float, coords: list[list[float]]) -> float | None:
    """`coords` are [lon, lat] like GeoJSON / OSRM."""
    if len(coords) < 2:
        return None
    best = 1e9
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i][0], coords[i][1]
        lon2, lat2 = coords[i + 1][0], coords[i + 1][1]
        best = min(best, point_to_segment_km(lat, lon, lat1, lon1, lat2, lon2))
    return best


def midpoint(coords: list[list[float]]) -> tuple[float, float] | None:
    if not coords:
        return None
    pt = coords[len(coords) // 2]
    if len(pt) < 2:
        return None
    return float(pt[1]), float(pt[0])


def geom_latlon(geom: dict | None) -> tuple[float, float] | None:
    if not geom:
        return None
    if "y" in geom and "x" in geom:
        return float(geom["y"]), float(geom["x"])
    if geom.get("paths"):
        path = geom["paths"][0]
        if path:
            pt = path[len(path) // 2]
            return float(pt[1]), float(pt[0])
    if geom.get("rings"):
        ring = geom["rings"][0]
        if ring:
            pt = ring[len(ring) // 2]
            return float(pt[1]), float(pt[0])
    coords = geom.get("coordinates")
    if not coords:
        return None
    gtype = geom.get("type") or ""
    if gtype == "Point" or (isinstance(coords[0], (int, float)) and len(coords) >= 2):
        return float(coords[1]), float(coords[0])
    # LineString or flatten first point
    cur = coords
    while isinstance(cur, list) and cur and isinstance(cur[0], list):
        cur = cur[len(cur) // 2]
    if isinstance(cur, list) and len(cur) >= 2 and isinstance(cur[0], (int, float)):
        return float(cur[1]), float(cur[0])
    return None


def is_major_road(name: str | None) -> bool:
    n = (name or "").upper().strip()
    if not n:
        return False
    if any(n.startswith(p) for p in MAJOR_PREFIXES):
        return True
    return any(needle in n for needle in MAJOR_NEEDLES)


def county_sql() -> str:
    return f"COUNTY_NAME in ({METRO_COUNTY_SQL})"


def metro_alert(area_desc: str | None, same_codes: list[str] | None) -> bool:
    codes = {str(c) for c in (same_codes or [])}
    if codes & CORE_SAME:
        return True
    text = (area_desc or "").lower()
    if "atlanta" in text:
        return True
    return any(c.lower() in text for c in CORE_COUNTIES)


def station_for_text(text: str) -> tuple[float, float] | None:
    blob = (text or "").lower()
    # Longer names first so "peachtree center" beats "center".
    for name, xy in sorted(MARTA_STATIONS.items(), key=lambda kv: -len(kv[0])):
        if name in blob:
            return xy
    for name, xy in LINE_PINS.items():
        if f"{name} line" in blob or f"{name}-line" in blob:
            return xy
    return None
