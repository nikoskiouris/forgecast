"""GDELT 1.0 daily event ingest, filtered to AI-grid attention."""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import httpx

from forgecast.geo import cell_for
from forgecast.ingest.cameo import GOLDSTEIN, action_label, root_code, signal_for_theme
from forgecast.schema import Event
from forgecast.staticdata import resolve_geo

GDELT_DAILY = "http://data.gdeltproject.org/events/{stamp}.export.CSV.zip"

# Official GDELT 1.0 daily export (no header).
COL_ID = 0
COL_SQLDATE = 1
COL_ACTOR1 = 6
COL_ACTOR1_COUNTRY = 7
COL_ACTOR2 = 16
COL_ACTOR2_COUNTRY = 17
COL_EVENTCODE = 26
COL_GOLDSTEIN = 30
COL_TONE = 34
COL_ACTION_GEO_NAME = 50  # ActionGeo_FullName
COL_ACTION_GEO_CC = 51  # ActionGeo_CountryCode (FIPS)
COL_ACTION_LAT = 53
COL_ACTION_LON = 54
COL_SOURCEURL = 57

GRID_KEYWORDS = (
    "data center",
    "datacenter",
    "data-centre",
    "hyperscale",
    "ercot",
    "megawatt",
    "mega-watt",
    "gigawatt",
    "giga-site",
    "interconnection",
    "substation",
    "building permit",
    "ai campus",
    "loudoun",
    "ashburn",
    "abilene",
    "culpeper",
    "dominion energy",
    "pjm",
    "caiso",
    "miso",
    "permit",
)


def _has_grid_keyword(*parts: str | None) -> bool:
    blob = " ".join(p or "" for p in parts).lower()
    return any(kw in blob for kw in GRID_KEYWORDS)


def _parse_day(sql_date: str) -> datetime:
    return datetime.strptime(sql_date[:8], "%Y%m%d")


def _f(row: list[str], idx: int) -> float | None:
    if len(row) <= idx:
        return None
    raw = (row[idx] or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_gdelt_csv(raw: str) -> list[Event]:
    events: list[Event] = []
    reader = csv.reader(io.StringIO(raw), delimiter="\t")
    for row in reader:
        if len(row) <= COL_EVENTCODE:
            continue
        actor = (row[COL_ACTOR1] or "").strip() if len(row) > COL_ACTOR1 else ""
        target = (row[COL_ACTOR2] or "").strip() if len(row) > COL_ACTOR2 else ""
        url = row[COL_SOURCEURL].strip() if len(row) > COL_SOURCEURL else ""
        loc = row[COL_ACTION_GEO_NAME].strip() if len(row) > COL_ACTION_GEO_NAME else ""
        if not _has_grid_keyword(actor, target, loc, url):
            continue
        code = str(row[COL_EVENTCODE]).strip()
        lat = _f(row, COL_ACTION_LAT)
        lon = _f(row, COL_ACTION_LON)
        geo_id, geo_kind = resolve_geo(loc, lat, lon)
        try:
            goldstein = float(row[COL_GOLDSTEIN] or GOLDSTEIN.get(root_code(code), 0))
        except ValueError:
            goldstein = GOLDSTEIN.get(root_code(code), 0.0)
        try:
            tone = float(row[COL_TONE] or 0)
        except ValueError:
            tone = 0.0
        try:
            ts = _parse_day(row[COL_SQLDATE])
        except ValueError:
            continue
        eid = str(row[COL_ID]).strip() or hashlib.sha1(
            f"{ts}{actor}{code}{url}".encode()
        ).hexdigest()[:16]
        signal = signal_for_theme(None, " ".join([actor, target, loc, url]))
        events.append(
            Event(
                id=f"gdelt-{eid}",
                timestamp=ts,
                actor=actor or "UNK",
                actor_country="US",
                action=action_label(code),
                action_code=code,
                target=target or None,
                target_country="US",
                theme="grid",
                location=loc or None,
                lat=lat,
                lon=lon,
                h3=cell_for(lat, lon, 5) if lat is not None and lon is not None else None,
                geo_id=geo_id,
                geo_kind=geo_kind,  # type: ignore[arg-type]
                goldstein=goldstein,
                tone=tone,
                source_url=url or None,
                source="gdelt",
                signal_type=signal,
            )
        )
    return events


def fetch_gdelt_day(day: date, timeout: float = 60.0) -> list[Event]:
    stamp = day.strftime("%Y%m%d")
    url = GDELT_DAILY.format(stamp=stamp)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        name = zf.namelist()[0]
        raw = zf.read(name).decode("utf-8", errors="replace")
    return parse_gdelt_csv(raw)


def fetch_gdelt_range(start: date, end: date) -> list[Event]:
    out: list[Event] = []
    day = start
    while day <= end:
        try:
            out.extend(fetch_gdelt_day(day))
        except httpx.HTTPError:
            pass
        day += timedelta(days=1)
    return out


def source_host(url: str | None) -> str | None:
    if not url:
        return None
    return urlparse(url).netloc or None
