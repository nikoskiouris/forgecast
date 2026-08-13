"""MARTA service alerts via the public OTP GraphQL endpoint (no API key)."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from forgecast.city import LINE_PINS, MARTA_STATIONS, station_for_text
from forgecast.ingest.http import post_json
from forgecast.schema import CityEvent, EventKind

OTP_URL = "https://tracker.itsmarta.com/otp/routers/default/index/graphql"
MARTA_URL = "https://www.itsmarta.com/ride/alerts"

QUERY = """
{
  alerts {
    id
    alertHeaderText
    alertDescriptionText
    alertEffect
    alertCause
    alertUrl
    effectiveStartDate
    effectiveEndDate
    route { gtfsId shortName mode }
    entities {
      __typename
      ... on Route { gtfsId shortName mode }
      ... on Stop { gtfsId name }
    }
  }
}
"""


def _ts(value: object) -> datetime | None:
    try:
        n = int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    if n > 10_000_000_000:
        n = n // 1000
    return datetime.fromtimestamp(n, tz=timezone.utc)


def _pin(header: str, desc: str, route: dict | None, entities: list) -> tuple[float, float]:
    blob = f"{header} {desc}"
    hit = station_for_text(blob)
    if hit:
        return hit
    for ent in entities or []:
        name = (ent.get("name") or ent.get("shortName") or "") if isinstance(ent, dict) else ""
        hit = station_for_text(str(name))
        if hit:
            return hit
    mode = (route or {}).get("mode") or ""
    short = ((route or {}).get("shortName") or "").lower()
    if short in LINE_PINS:
        return LINE_PINS[short]
    if mode in {"SUBWAY", "RAIL"}:
        return MARTA_STATIONS["five points"]
    if mode == "TRAM":
        return LINE_PINS["streetcar"]
    return MARTA_STATIONS["five points"]


def _severity(header: str, effect: str | None, mode: str) -> str:
    h = (header or "").lower()
    e = (effect or "").upper()
    if "elevator" in h or "escalator" in h or e == "ACCESSIBILITY_ISSUE":
        return "low"
    if e in {"NO_SERVICE", "SIGNIFICANT_DELAYS", "DETOUR", "REDUCED_SERVICE"}:
        return "high" if mode in {"SUBWAY", "RAIL"} else "mid"
    if mode in {"SUBWAY", "RAIL"}:
        return "mid"
    return "low"


def fetch_marta(http: httpx.Client) -> list[CityEvent]:
    data = post_json(http, OTP_URL, {"query": QUERY}, headers={"Content-Type": "application/json"})
    if not isinstance(data, dict):
        return []
    alerts = (data.get("data") or {}).get("alerts") or []
    out: list[CityEvent] = []
    bus_cancel = 0
    for raw in alerts:
        header = (raw.get("alertHeaderText") or "").strip()
        desc = (raw.get("alertDescriptionText") or "").strip()
        if not header:
            continue
        route = raw.get("route") or {}
        mode = route.get("mode") or ""
        effect = raw.get("alertEffect")
        low = header.lower()
        if "cancellation" in low and mode == "BUS":
            bus_cancel += 1
            continue
        lat, lon = _pin(header, desc, route, raw.get("entities") or [])
        routes = []
        if route.get("shortName"):
            routes.append(str(route["shortName"]))
        metro = mode in {"SUBWAY", "RAIL"} and not station_for_text(header + " " + desc)
        eid = raw.get("id") or header
        out.append(
            CityEvent(
                id=f"marta:{str(eid)[-48:]}",
                kind=EventKind.TRANSIT,
                severity=_severity(header, effect, mode),
                title=header,
                summary=desc[:500] or header,
                lat=lat,
                lon=lon,
                start=_ts(raw.get("effectiveStartDate")),
                end=_ts(raw.get("effectiveEndDate")),
                source="MARTA",
                source_url=raw.get("alertUrl") or MARTA_URL,
                routes=routes,
                area=mode or None,
                raw_type=effect or mode,
                metro=metro,
            )
        )
    if bus_cancel:
        out.append(
            CityEvent(
                id="marta:bus-cancellations",
                kind=EventKind.TRANSIT,
                severity="mid" if bus_cancel >= 5 else "low",
                title=f"MARTA bus: {bus_cancel} routes have cancellations today",
                summary="Several bus routes are running reduced trips. Check your route before you leave.",
                lat=MARTA_STATIONS["five points"][0],
                lon=MARTA_STATIONS["five points"][1],
                source="MARTA",
                source_url=MARTA_URL,
                area="BUS",
                raw_type="REDUCED_SERVICE",
                metro=True,
            )
        )
    return out
