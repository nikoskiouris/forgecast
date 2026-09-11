"""County building permits. Census BPS / Socrata when a key exists; else empty."""

from __future__ import annotations

import os
from datetime import date, datetime

import httpx

from forgecast.geo import cell_for
from forgecast.schema import Event, SignalType
from forgecast.staticdata import COUNTIES, coords, place_name

CENSUS_BPS = "https://api.census.gov/data/timeseries/eits/bps"


def fetch_permits(
    start: date,
    end: date,
    fips: str = "51107",
) -> list[Event]:
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        return []
    if fips not in COUNTIES:
        return []
    params = {
        "get": "cell_value,data_type_code,time_slot_id,error_data,category_code,seasonally_adj",
        "for": f"county:{fips[2:]}",
        "in": f"state:{fips[:2]}",
        "time": start.year,
        "key": key,
    }
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            resp = client.get(CENSUS_BPS, params=params)
            resp.raise_for_status()
            rows = resp.json()
    except (httpx.HTTPError, ValueError):
        return []
    lat, lon = coords(fips)
    events: list[Event] = []
    for i, row in enumerate(rows[1:] if rows else []):
        events.append(
            Event(
                id=f"bps-{fips}-{start.year}-{i}",
                timestamp=datetime(start.year, 6, 1),
                actor=place_name(fips),
                action="files permit",
                action_code="01",
                theme="permit",
                location=place_name(fips),
                lat=lat,
                lon=lon,
                h3=cell_for(lat, lon, 5),
                geo_id=fips,
                geo_kind="county",
                source="census-bps",
                signal_type=SignalType.PERMIT_MW,
            )
        )
        if i > 20:
            break
    _ = end
    return events
