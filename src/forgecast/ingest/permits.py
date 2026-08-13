"""City of Atlanta traffic-control and utility permits (ArcGIS, no key)."""

from __future__ import annotations

from datetime import timedelta

import httpx

from forgecast.city import from_epoch_ms, geom_latlon, in_metro, now_eastern
from forgecast.ingest.http import arcgis_query
from forgecast.schema import CityEvent, EventKind

BASE = "https://dpwgis.atlantaga.gov/hostingserver/rest/services"
TRAFFIC = f"{BASE}/Traffic_Control_Permit_Present_and_Future_new/FeatureServer/0/query"
UTILITY = f"{BASE}/Utility_Permit_Present_and_Future_new/FeatureServer/0/query"
PORTAL = "https://atldot.atlantaga.gov/"


def _active(start, end, now) -> bool:
    horizon = now + timedelta(days=14)
    if end and end < now - timedelta(days=1):
        return False
    return not (start and start > horizon)


def _lanes(val: object) -> bool:
    if val is None:
        return False
    s = str(val).strip().lower()
    return s not in {"", "none", "0", "null"}


def fetch_traffic_permits(http: httpx.Client) -> list[CityEvent]:
    feats = arcgis_query(
        http,
        TRAFFIC,
        {"where": "1=1", "outFields": "*", "returnGeometry": "true"},
        max_records=2000,
    )
    now = now_eastern()
    out: list[CityEvent] = []
    for feat in feats:
        a = feat.get("attributes") or {}
        status = (a.get("APPLICATION_STATUS") or "").lower()
        if status and status not in {"approved", "issued", "active"}:
            continue
        start = from_epoch_ms(a.get("START_DATE"))
        end = from_epoch_ms(a.get("END_DATE"))
        if not _active(start, end, now):
            continue
        pt = geom_latlon(feat.get("geometry"))
        lat = a.get("LATITUDE")
        lon = a.get("LONGITUDE")
        if lat and lon:
            try:
                pt = float(lat), float(lon)
            except (TypeError, ValueError):
                pass
        if not pt or not in_metro(*pt):
            continue
        ptype = a.get("PERMIT_TYPE") or "Lane closure"
        loc = (a.get("LOCATION") or a.get("LOCATION_NAME") or "").strip()
        title_src = (a.get("PROJECT_TITLE") or loc or ptype).strip()
        closed = a.get("LANES_CLOSED")
        full = "full street" in ptype.lower() or str(closed).lower() in {"all", "full"}
        if not full and not _lanes(closed) and "sidewalk" in ptype.lower() and "lane" not in ptype.lower():
            continue
        summary = (a.get("DESCRIPTION") or a.get("NATURE_OF_WORK") or loc or title_src).strip()
        sev = "high" if full else "mid" if _lanes(closed) else "low"
        pid = a.get("PERMIT_NUMBER") or a.get("OBJECTID")
        roads = [r for r in [a.get("LOCATION_NAME"), a.get("CROSS_STREET_1")] if r]
        out.append(
            CityEvent(
                id=f"permit:{pid}",
                kind=EventKind.ROAD,
                severity=sev,
                title=f"Street work: {title_src[:90]}",
                summary=summary[:400],
                lat=pt[0],
                lon=pt[1],
                start=start,
                end=end,
                source="Atlanta DOT permits",
                source_url=PORTAL,
                roads=roads,
                area=a.get("NPU"),
                raw_type=ptype,
            )
        )
    return out


def fetch_utility_permits(http: httpx.Client) -> list[CityEvent]:
    feats = arcgis_query(
        http,
        UTILITY,
        {"where": "1=1", "outFields": "*", "returnGeometry": "true"},
        max_records=1500,
    )
    now = now_eastern()
    out: list[CityEvent] = []
    for feat in feats:
        a = feat.get("attributes") or {}
        start = from_epoch_ms(a.get("START_DATE"))
        end = from_epoch_ms(a.get("END_DATE"))
        if not _active(start, end, now):
            continue
        closure = a.get("LANE_CLOSURE_TYPE")
        name = (a.get("PROJECT_NAME") or "").upper()
        if not _lanes(closure) and "CLOSURE" not in name and "ROAD CLOSURE" not in name:
            continue
        pt = geom_latlon(feat.get("geometry"))
        if not pt or not in_metro(*pt):
            continue
        loc = (a.get("LOCATION_NAME") or a.get("PROJECT_NAME") or "utility work").strip()
        summary = (a.get("DESCRIPTION_OF_WORK") or loc).strip()
        pid = a.get("PERMIT_NUMBER") or a.get("OBJECTID")
        full = "full" in str(closure).lower() or "ROAD CLOSURE" in name
        out.append(
            CityEvent(
                id=f"util:{pid}",
                kind=EventKind.UTILITY,
                severity="high" if full else "mid",
                title=f"Utility work: {loc[:90]}",
                summary=summary[:400],
                lat=pt[0],
                lon=pt[1],
                start=start,
                end=end,
                source="Atlanta Public Works",
                source_url=PORTAL,
                roads=[r for r in [a.get("LOCATION_NAME"), a.get("CROSS_STREET_1")] if r],
                area=a.get("NPU"),
                raw_type=str(closure) if closure else "utility",
            )
        )
    return out
