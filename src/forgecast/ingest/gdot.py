"""GDOT traffic interruptions for metro Atlanta (no API key)."""

from __future__ import annotations

import httpx

from forgecast.city import county_sql, from_epoch_ms, geom_latlon, in_metro, is_major_road
from forgecast.ingest.http import arcgis_query
from forgecast.schema import CityEvent, EventKind

LAYER = (
    "https://enterprisegis.dot.ga.gov/server/rest/services/"
    "EOC/EOC_TRAFFIC_LAYERS/MapServer/1/query"
)
SOURCE_URL = "https://511ga.org/"

KIND_BY_TYPE = {
    "roadwork": EventKind.ROAD,
    "accident": EventKind.ROAD,
    "incident": EventKind.ROAD,
    "congestion": EventKind.ROAD,
    "disabled vehicle": EventKind.ROAD,
    "weather": EventKind.WEATHER,
    "majorevent": EventKind.EVENT,
    "major event": EventKind.EVENT,
    "parade": EventKind.EVENT,
    "street event": EventKind.EVENT,
    "road race": EventKind.EVENT,
    "filming": EventKind.EVENT,
}


def _kind(raw: str | None) -> EventKind:
    return KIND_BY_TYPE.get((raw or "").strip().lower(), EventKind.ROAD)


def _severity(raw: str | None, road: str | None) -> str:
    t = (raw or "").lower()
    if t in {"majorevent", "major event", "parade", "road race", "street event"}:
        return "high"
    if t in {"accident", "incident"}:
        return "high"
    if t == "filming":
        return "mid"
    if is_major_road(road):
        return "mid"
    return "low"


def _title(attrs: dict) -> str:
    t = (attrs.get("TYPE") or "traffic").replace("_", " ")
    subtype = attrs.get("SUBTYPE") or ""
    road = attrs.get("PRIMARY_ROAD") or ""
    cross = attrs.get("CROSS_ROAD") or ""
    place = attrs.get("PLACE_NAME") or attrs.get("COUNTY_NAME") or ""
    label = subtype if subtype and subtype.lower() not in {t.lower(), "other"} else t
    if road and cross:
        head = f"{label} on {road} at {cross}"
    elif road:
        head = f"{label} on {road}"
    else:
        head = label
    if place:
        head = f"{head} ({place})"
    return head[0].upper() + head[1:]


def _keep(attrs: dict, lat: float, lon: float) -> bool:
    if not in_metro(lat, lon):
        return False
    raw = (attrs.get("TYPE") or "").lower()
    if raw != "roadwork":
        return True
    road = attrs.get("PRIMARY_ROAD")
    if is_major_road(road):
        return True
    place = (attrs.get("PLACE_NAME") or "").lower()
    # City streets still matter once we have a user pin; keep Atlanta-core work.
    return place in {
        "atlanta",
        "decatur",
        "brookhaven",
        "sandy springs",
        "east point",
        "college park",
        "smyrna",
        "marietta",
        "dunwoody",
        "chamblee",
        "doraville",
        "roswell",
    }


def fetch_gdot(http: httpx.Client) -> list[CityEvent]:
    where = county_sql()
    feats = arcgis_query(
        http,
        LAYER,
        {
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
        },
        max_records=2000,
    )
    out: list[CityEvent] = []
    for feat in feats:
        attrs = feat.get("attributes") or {}
        geom = feat.get("geometry")
        lat = attrs.get("LATITUDE")
        lon = attrs.get("LONGITUDE")
        if lat is None or lon is None:
            pt = geom_latlon(geom)
            if not pt:
                continue
            lat, lon = pt
        lat, lon = float(lat), float(lon)
        if not _keep(attrs, lat, lon):
            continue
        raw = attrs.get("TYPE")
        eid = attrs.get("EVENT_ID") or attrs.get("OBJECTID")
        desc = (attrs.get("DESCRIPTION") or attrs.get("PURPOSE") or "").strip()
        title = _title(attrs)
        roads = [r for r in [attrs.get("PRIMARY_ROAD"), attrs.get("CROSS_ROAD")] if r]
        out.append(
            CityEvent(
                id=f"gdot:{eid}",
                kind=_kind(raw),
                severity=_severity(raw, attrs.get("PRIMARY_ROAD")),
                title=title,
                summary=desc or title,
                lat=lat,
                lon=lon,
                start=from_epoch_ms(attrs.get("START_TIME")),
                end=from_epoch_ms(attrs.get("END_TIME")),
                source="GDOT 511",
                source_url=SOURCE_URL,
                roads=roads,
                area=attrs.get("PLACE_NAME") or attrs.get("COUNTY_NAME"),
                raw_type=raw,
            )
        )
    return out
