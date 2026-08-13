"""National Weather Service alerts + Open-Meteo hourly rain windows."""

from __future__ import annotations

from datetime import datetime

import httpx

from forgecast.city import CENTER_LAT, CENTER_LON, EASTERN, geom_latlon, metro_alert, now_eastern
from forgecast.ingest.http import get_json
from forgecast.schema import CityEvent, EventKind

NWS_URL = "https://api.weather.gov/alerts/active"
NWS_HEADERS = {"Accept": "application/geo+json"}
OM_URL = "https://api.open-meteo.com/v1/forecast"

# WMO: thunderstorms and heavy rain
STORM_CODES = {65, 75, 82, 95, 96, 99}
RAINY_CODES = {61, 63, 65, 80, 81, 82, 95, 96, 99}


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(EASTERN)
    except ValueError:
        return None


def _centroid(geom: dict | None) -> tuple[float, float] | None:
    pt = geom_latlon(geom)
    return pt


def fetch_nws(http: httpx.Client) -> list[CityEvent]:
    data = get_json(http, NWS_URL, {"area": "GA"}, headers=NWS_HEADERS)
    feats = data.get("features") or [] if isinstance(data, dict) else []
    out: list[CityEvent] = []
    for feat in feats:
        props = feat.get("properties") or {}
        same = (props.get("geocode") or {}).get("SAME") or []
        if not metro_alert(props.get("areaDesc"), same):
            continue
        event = props.get("event") or "Weather alert"
        sev_raw = (props.get("severity") or "").lower()
        severity = "high" if sev_raw in {"extreme", "severe"} else "mid" if sev_raw == "moderate" else "low"
        if "warning" in event.lower():
            severity = "high"
        pt = _centroid(feat.get("geometry")) or (CENTER_LAT, CENTER_LON)
        eid = props.get("id") or props.get("@id") or event
        out.append(
            CityEvent(
                id=f"nws:{eid[-40:]}",
                kind=EventKind.WEATHER,
                severity=severity,
                title=props.get("headline") or event,
                summary=(props.get("description") or event)[:500],
                lat=pt[0],
                lon=pt[1],
                start=_parse_iso(props.get("onset") or props.get("effective")),
                end=_parse_iso(props.get("ends") or props.get("expires")),
                source="National Weather Service",
                source_url=props.get("web") or "https://www.weather.gov/ffc/",
                area=props.get("areaDesc"),
                raw_type=event,
                metro=True,
            )
        )
    out.sort(key=lambda e: 0 if "peachtree" in (e.title + (e.source or "")).lower() else 1)
    return out


def _fmt_hour(dt: datetime) -> str:
    h = dt.strftime("%I").lstrip("0") or "12"
    return f"{h} {dt.strftime('%p').replace('AM', 'AM').replace('PM', 'PM')}"


def fetch_open_meteo(http: httpx.Client) -> list[CityEvent]:
    data = get_json(
        http,
        OM_URL,
        {
            "latitude": CENTER_LAT,
            "longitude": CENTER_LON,
            "hourly": "precipitation_probability,precipitation,weather_code,wind_gusts_10m",
            "forecast_days": 3,
            "timezone": "America/New_York",
        },
    )
    hourly = (data or {}).get("hourly") or {}
    times = hourly.get("time") or []
    probs = hourly.get("precipitation_probability") or []
    codes = hourly.get("weather_code") or []
    gusts = hourly.get("wind_gusts_10m") or []
    windows: list[tuple[int, int, int, bool]] = []
    i = 0
    n = min(len(times), len(probs) or len(times))
    while i < n:
        code = int(codes[i]) if i < len(codes) and codes[i] is not None else 0
        prob = int(probs[i]) if i < len(probs) and probs[i] is not None else 0
        stormy = code in STORM_CODES or prob >= 50
        if not stormy:
            i += 1
            continue
        j = i
        max_prob = prob
        any_storm = code in STORM_CODES
        while j < n:
            c = int(codes[j]) if j < len(codes) and codes[j] is not None else 0
            p = int(probs[j]) if j < len(probs) and probs[j] is not None else 0
            if not (c in RAINY_CODES or p >= 45):
                break
            max_prob = max(max_prob, p)
            any_storm = any_storm or c in STORM_CODES
            j += 1
        if j > i:
            windows.append((i, j, max_prob, any_storm))
        i = max(j, i + 1)
    now = now_eastern()
    out: list[CityEvent] = []
    for idx, (i, j, max_prob, any_storm) in enumerate(windows[:6]):
        start = datetime.fromisoformat(times[i]).replace(tzinfo=EASTERN)
        end_idx = min(j, len(times) - 1)
        end = datetime.fromisoformat(times[end_idx]).replace(tzinfo=EASTERN)
        if end < now:
            continue
        if (end - start).total_seconds() < 3600:
            continue
        span = f"{_fmt_hour(start)}–{_fmt_hour(end)}"
        if start.date() != now.date():
            span = f"{start.strftime('%A')} {span}"
        title = (
            f"Severe storms most likely {span}"
            if any_storm or max_prob >= 80
            else f"Rain likely {span}"
        )
        gust = None
        if gusts:
            chunk = [g for g in gusts[i:j] if isinstance(g, (int, float))]
            gust = max(chunk) if chunk else None
        bits = [f"Rain chances peak around {max_prob}%."]
        if any_storm:
            bits.append("Thunderstorms are in the forecast.")
        if gust and gust >= 45:
            bits.append(f"Gusts up to {int(gust)} km/h.")
        sev = "high" if any_storm or max_prob >= 80 else "mid"
        out.append(
            CityEvent(
                id=f"om:storm:{idx}:{times[i]}",
                kind=EventKind.WEATHER,
                severity=sev,
                title=title,
                summary=" ".join(bits),
                lat=CENTER_LAT,
                lon=CENTER_LON,
                start=start,
                end=end,
                source="Open-Meteo",
                source_url="https://open-meteo.com/",
                area="Metro Atlanta",
                raw_type="storm_window",
                metro=True,
            )
        )
    return out
