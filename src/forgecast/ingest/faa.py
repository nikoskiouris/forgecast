"""FAA NAS Status for Hartsfield-Jackson (ATL)."""

from __future__ import annotations

from datetime import datetime

import httpx

from forgecast.city import ATL_AIRPORT, EASTERN
from forgecast.ingest.http import get_json
from forgecast.schema import CityEvent, EventKind

FAA_URL = "https://nasstatus.faa.gov/api/airport-events"
FAA_PAGE = "https://nasstatus.faa.gov/"


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(EASTERN)
    except ValueError:
        return None


def _delay_text(block: dict | None, label: str) -> str | None:
    if not block:
        return None
    mins = block.get("avgDelay") or block.get("maxDelay") or block.get("delay") or block.get("reason")
    reason = block.get("reason") or block.get("trend") or ""
    if mins in (None, "", 0, "0"):
        if not reason:
            return None
        return f"{label}: {reason}"
    return f"{label}: {mins} ({reason})".strip(" ()")


def fetch_faa(http: httpx.Client) -> list[CityEvent]:
    rows = get_json(http, FAA_URL)
    if not isinstance(rows, list):
        return []
    out: list[CityEvent] = []
    for row in rows:
        if str(row.get("airportId") or "").upper() != "ATL":
            continue
        bits = []
        start = end = None
        high = False
        if row.get("airportClosure"):
            bits.append("Airport closure in effect")
            high = True
        for key, label in (
            ("groundStop", "Ground stop"),
            ("groundDelay", "Ground delay"),
            ("arrivalDelay", "Arrival delay"),
            ("departureDelay", "Departure delay"),
            ("deicing", "Deicing"),
        ):
            block = row.get(key)
            if not block:
                continue
            text = _delay_text(block if isinstance(block, dict) else {"reason": str(block)}, label)
            if text:
                bits.append(text)
                high = True
            if isinstance(block, dict):
                start = start or _parse(block.get("startTime") or block.get("createdAt"))
                end = end or _parse(block.get("endTime"))
        free = row.get("freeForm") or {}
        simple = (free.get("simpleText") or free.get("text") or "").strip()
        if simple and "CLSD TO NON SKED" not in simple.upper():
            bits.append(simple[:240])
        if not bits:
            continue
        lat, lon = ATL_AIRPORT
        try:
            lat = float(row.get("latitude") or lat)
            lon = float(row.get("longitude") or lon)
        except (TypeError, ValueError):
            pass
        out.append(
            CityEvent(
                id="faa:ATL",
                kind=EventKind.AIRPORT,
                severity="high" if high else "mid",
                title="Hartsfield-Jackson (ATL) delays",
                summary="; ".join(bits)[:500],
                lat=lat,
                lon=lon,
                start=start,
                end=end,
                source="FAA NAS Status",
                source_url=FAA_PAGE,
                area="ATL",
                raw_type="airport_delay",
            )
        )
    return out
