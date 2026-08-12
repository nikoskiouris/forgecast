"""GDELT 1.0 daily event ingest, filtered to DIB-relevant CAMEO codes."""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import httpx

from forgecast.ingest.cameo import (
    GOLDSTEIN,
    WATCH_CODES,
    action_label,
    disruption_for_code,
    root_code,
)
from forgecast.schema import Event
from forgecast.staticdata import MATERIALS

ISO3_TO_ISO2 = {
    "CHN": "CN",
    "USA": "US",
    "RUS": "RU",
    "IRN": "IR",
    "YEM": "YE",
    "UKR": "UA",
    "TWN": "TW",
    "COD": "CD",
    "IDN": "ID",
    "ZAF": "ZA",
    "AUS": "AU",
    "MMR": "MM",
    "TUR": "TR",
    "EGY": "EG",
    "JPN": "JP",
    "DEU": "DE",
    "KOR": "KR",
    "GBR": "GB",
    "FRA": "FR",
    "IND": "IN",
}


def country_iso(code: str | None) -> str | None:
    if not code:
        return None
    code = code.strip().upper()
    if len(code) == 2:
        return code
    return ISO3_TO_ISO2.get(code, code[:2])


GDELT_DAILY = "http://data.gdeltproject.org/events/{stamp}.export.CSV.zip"

# GDELT 1.0 daily export has no header. Column indexes from the codebook.
COL_ID = 0
COL_SQLDATE = 1
COL_ACTOR1 = 6
COL_ACTOR1_COUNTRY = 7
COL_ACTOR2 = 16
COL_ACTOR2_COUNTRY = 17
COL_EVENTCODE = 26
COL_GOLDSTEIN = 30
COL_TONE = 34
COL_ACTION_GEO = 51
COL_SOURCEURL = 57

MATERIAL_KEYWORDS = {
    "titanium": "titanium",
    "rare earth": "rare_earths",
    "rare-earth": "rare_earths",
    "gallium": "gallium",
    "germanium": "germanium",
    "antimony": "antimony",
    "graphite": "graphite",
    "cobalt": "cobalt",
    "nickel": "nickel",
    "palladium": "palladium",
    "neon": "neon",
    "semiconductor": "semiconductors",
    "tungsten": "tungsten",
    "beryllium": "beryllium",
    "aluminum": "aluminum",
    "aluminium": "aluminum",
    "carbon fiber": "carbon_fiber",
}


def _material_from_text(*parts: str | None) -> str | None:
    blob = " ".join(p or "" for p in parts).lower()
    for kw, mat in MATERIAL_KEYWORDS.items():
        if kw in blob:
            return mat
    return None


def _parse_day(sql_date: str) -> datetime:
    return datetime.strptime(sql_date[:8], "%Y%m%d")


def parse_gdelt_csv(raw: str) -> list[Event]:
    events: list[Event] = []
    reader = csv.reader(io.StringIO(raw), delimiter="\t")
    for row in reader:
        if len(row) <= COL_EVENTCODE:
            continue
        code = str(row[COL_EVENTCODE]).strip()
        if root_code(code) not in WATCH_CODES and code not in WATCH_CODES:
            continue
        actor_country = country_iso(row[COL_ACTOR1_COUNTRY]) or "ZZ"
        target_country = country_iso(row[COL_ACTOR2_COUNTRY])
        actor = (row[COL_ACTOR1] or actor_country).strip()
        target = (row[COL_ACTOR2] or "").strip() or None
        url = row[COL_SOURCEURL].strip() if len(row) > COL_SOURCEURL else ""
        loc = row[COL_ACTION_GEO].strip() if len(row) > COL_ACTION_GEO else ""
        material = _material_from_text(actor, target, loc, url)
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
        events.append(
            Event(
                id=f"gdelt-{eid}",
                timestamp=ts,
                actor=actor,
                actor_country=actor_country,
                action=action_label(code),
                action_code=code,
                target=target,
                target_country=target_country,
                material=material if material in MATERIALS or material else material,
                location=loc or None,
                goldstein=goldstein,
                tone=tone,
                source_url=url or None,
                source="gdelt",
                disruption_type=disruption_for_code(code, material, loc),
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
