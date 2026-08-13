"""Geocode Atlanta addresses. Nominatim first, local gazetteer as backup."""

from __future__ import annotations

import time

import httpx

from forgecast.city import in_metro
from forgecast.ingest.http import USER_AGENT, get_json
from forgecast.schema import Place

NOMINATIM = "https://nominatim.openstreetmap.org/search"
PHOTON = "https://photon.komoot.io/api/"

# Real landmarks — not fake events. Speeds up known queries when OSM is vague.
GAZETTEER: dict[str, tuple[float, float, str]] = {
    "ponce city market": (33.7724, -84.3652, "Ponce City Market, Atlanta"),
    "georgia tech": (33.7756, -84.3963, "Georgia Institute of Technology"),
    "georgia institute of technology": (33.7756, -84.3963, "Georgia Institute of Technology"),
    "midtown": (33.7838, -84.3861, "Midtown Atlanta"),
    "downtown": (33.7550, -84.3900, "Downtown Atlanta"),
    "airport": (33.6407, -84.4277, "Hartsfield-Jackson Atlanta International Airport"),
    "atl": (33.6407, -84.4277, "Hartsfield-Jackson Atlanta International Airport"),
    "hartsfield": (33.6407, -84.4277, "Hartsfield-Jackson Atlanta International Airport"),
    "five points": (33.7539, -84.3916, "Five Points, Atlanta"),
    "buckhead": (33.8484, -84.3733, "Buckhead, Atlanta"),
    "decatur": (33.7748, -84.2963, "Decatur, Georgia"),
    "mercedes-benz stadium": (33.7553, -84.4008, "Mercedes-Benz Stadium"),
    "mercedes benz stadium": (33.7553, -84.4008, "Mercedes-Benz Stadium"),
    "state farm arena": (33.7573, -84.3963, "State Farm Arena"),
    "truist park": (33.8908, -84.4677, "Truist Park"),
    "lenox square": (33.8463, -84.3620, "Lenox Square"),
    "atlantic station": (33.7925, -84.3959, "Atlantic Station"),
    "inman park": (33.7575, -84.3528, "Inman Park, Atlanta"),
    "east atlanta": (33.7400, -84.3460, "East Atlanta Village"),
    "virginia highland": (33.7820, -84.3540, "Virginia-Highland"),
    "old fourth ward": (33.7660, -84.3660, "Old Fourth Ward"),
    "west midtown": (33.7980, -84.4130, "West Midtown, Atlanta"),
    "grant park": (33.7340, -84.3730, "Grant Park, Atlanta"),
    "briarlake": (33.8439, -84.2722, "Briarlake Road, Atlanta"),
    "briarlake road": (33.8439, -84.2722, "Briarlake Road, Atlanta"),
    "briarlake forest": (33.8439, -84.2722, "Briarlake Road, Atlanta"),
    "buffington": (33.6137, -84.4894, "5200 Buffington Road, College Park"),
    "buffington road": (33.6137, -84.4894, "5200 Buffington Road, College Park"),
    "chick-fil-a headquarters": (33.6137, -84.4894, "5200 Buffington Road, College Park"),
    "chick fila headquarters": (33.6137, -84.4894, "5200 Buffington Road, College Park"),
}

_TYPOS = (("brairlake", "briarlake"), ("buffinton", "buffington"))


def _norm(q: str) -> str:
    text = " ".join(q.lower().replace(",", " ").split())
    for bad, good in _TYPOS:
        text = text.replace(bad, good)
    return text


def gazetteer_lookup(query: str) -> Place | None:
    q = _norm(query)
    if q in GAZETTEER:
        lat, lon, name = GAZETTEER[q]
        return Place(label="place", address=name, lat=lat, lon=lon)
    contained = [(k, v) for k, v in GAZETTEER.items() if k in q]
    if contained:
        _key, val = max(contained, key=lambda kv: len(kv[0]))
        lat, lon, name = val
        return Place(label="place", address=name, lat=lat, lon=lon)
    for key, val in GAZETTEER.items():
        if q in key:
            lat, lon, name = val
            return Place(label="place", address=name, lat=lat, lon=lon)
    return None


def _qualify(query: str) -> str:
    q = query.strip()
    low = q.lower()
    if "atlanta" in low or " ga" in low or low.endswith("ga") or "georgia" in low:
        return q
    return q + ", Atlanta, GA"


def _nominatim(http: httpx.Client, query: str) -> Place | None:
    params = {
        "q": _qualify(query),
        "format": "jsonv2",
        "limit": 5,
        "addressdetails": 1,
        "countrycodes": "us",
        "viewbox": "-84.90,34.26,-83.90,33.47",
        "bounded": 1,
    }
    rows = get_json(http, NOMINATIM, params, headers={"User-Agent": USER_AGENT})
    if not isinstance(rows, list):
        return None
    for row in rows:
        try:
            lat, lon = float(row["lat"]), float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if in_metro(lat, lon):
            return Place(label="place", address=str(row.get("display_name") or query), lat=lat, lon=lon)
    return None


_STOP = {"atlanta", "ga", "georgia", "road", "rd", "street", "st", "ave", "dr", "ne", "nw", "se", "sw"}


def _tokens(query: str) -> list[str]:
    return [t for t in _norm(query).split() if t not in _STOP and not t.isdigit()]


def _photon_score(query: str, hay: str, housenumber: str | None) -> int:
    q = _norm(query)
    score = sum(3 for t in _tokens(query) if t in hay)
    if housenumber and housenumber in q.split():
        score += 2
    return score


def _photon(http: httpx.Client, query: str) -> Place | None:
    data = get_json(
        http,
        PHOTON,
        {"q": _qualify(query), "lat": 33.75, "lon": -84.39, "limit": 5},
    )
    feats = data.get("features") or [] if isinstance(data, dict) else []
    ranked: list[tuple[int, Place]] = []
    for feat in feats:
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        if not in_metro(lat, lon):
            continue
        props = feat.get("properties") or {}
        name = props.get("name") or query
        street = " ".join(str(x) for x in [props.get("housenumber"), props.get("street")] if x)
        city = props.get("city") or "Atlanta"
        addr = ", ".join(x for x in [street or name, city, "GA"] if x)
        hay = _norm(f"{name} {street} {city}")
        place = Place(label="place", address=addr, lat=lat, lon=lon)
        ranked.append((_photon_score(query, hay, props.get("housenumber") and str(props.get("housenumber"))), place))
    if not ranked:
        return None
    ranked.sort(key=lambda row: row[0], reverse=True)
    return ranked[0][1]


def geocode(query: str, http: httpx.Client, label: str = "place") -> Place:
    q = (query or "").strip()
    if not q:
        raise ValueError("empty address")
    hit = gazetteer_lookup(q)
    # Gazetteer only if the query is clearly that landmark, not a street number.
    if hit and not any(ch.isdigit() for ch in q):
        return Place(label=label, address=hit.address, lat=hit.lat, lon=hit.lon)
    place = None
    try:
        place = _nominatim(http, q)
    except Exception:  # noqa: BLE001 — fall through to Photon
        place = None
    if place is None:
        try:
            place = _photon(http, q)
        except Exception:  # noqa: BLE001 — then gazetteer / error
            place = None
    if hit and place:
        hit_score = _photon_score(q, _norm(hit.address), None)
        place_score = _photon_score(q, _norm(place.address), None)
        if hit_score > place_score:
            return Place(label=label, address=hit.address, lat=hit.lat, lon=hit.lon)
    if place is None and hit:
        return Place(label=label, address=hit.address, lat=hit.lat, lon=hit.lon)
    if place is None:
        raise ValueError(f"Could not find an Atlanta-area match for: {query}")
    return Place(label=label, address=place.address, lat=place.lat, lon=place.lon)


def geocode_places(
    items: list[dict],
    http: httpx.Client,
) -> list[Place]:
    out: list[Place] = []
    for i, raw in enumerate(items):
        label = str(raw.get("label") or f"place{i+1}").strip() or f"place{i+1}"
        lat, lon = raw.get("lat"), raw.get("lon")
        address = str(raw.get("address") or "").strip()
        if lat is not None and lon is not None:
            out.append(Place(label=label, address=address or label, lat=float(lat), lon=float(lon)))
            continue
        if not address:
            continue
        if i:
            time.sleep(1.0)  # Nominatim 1 req/sec
        out.append(geocode(address, http, label=label))
    if not out:
        raise ValueError("Enter at least one Atlanta address.")
    return out
