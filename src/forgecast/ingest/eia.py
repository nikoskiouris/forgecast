"""EIA-930 balancing-authority load. Optional; demo uses the sample world."""

from __future__ import annotations

import os
from datetime import date, datetime

import httpx

from forgecast.geo import cell_for
from forgecast.schema import Event, SignalType
from forgecast.staticdata import coords, place_name

EIA_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"


def fetch_eia_load(
    start: date,
    end: date,
    ba: str = "ERCO",
    api_key: str | None = None,
) -> list[Event]:
    key = api_key or os.environ.get("EIA_API_KEY")
    if not key:
        return []
    params = {
        "api_key": key,
        "frequency": "daily",
        "data[0]": "value",
        "facets[respondent][]": ba,
        "facets[type][]": "D",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000,
    }
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        resp = client.get(EIA_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()
    rows = ((payload.get("response") or {}).get("data")) or []
    lat, lon = coords(ba if ba != "ERCOT" else "ERCO")
    geo_id = "ERCO" if ba in {"ERCO", "ERCOT"} else ba
    events: list[Event] = []
    for i, row in enumerate(rows):
        period = str(row.get("period") or "")
        try:
            ts = datetime.fromisoformat(period[:10])
        except ValueError:
            continue
        events.append(
            Event(
                id=f"eia-{geo_id}-{period}-{i}",
                timestamp=ts,
                actor=place_name(geo_id),
                action="reports load",
                action_code="01",
                theme="load",
                location=place_name(geo_id),
                lat=lat,
                lon=lon,
                h3=cell_for(lat, lon, 5),
                geo_id=geo_id,
                geo_kind="ba",
                source="eia-930",
                signal_type=SignalType.LOAD_GROWTH,
            )
        )
    return events
