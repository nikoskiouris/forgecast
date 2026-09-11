"""CAMEO / GDELT action codes. GDELT is attention only — never a label."""

from __future__ import annotations

from forgecast.schema import SignalType

GOLDSTEIN = {
    "01": 0.0,
    "04": 1.0,
    "05": 3.5,
    "10": -5.0,
    "11": -2.0,
    "12": -4.0,
    "13": -6.0,
    "14": -6.5,
    "15": -7.0,
    "16": -7.0,
    "163": -8.0,
    "17": -7.0,
    "18": -9.0,
    "19": -10.0,
}

ACTION_LABEL = {
    "01": "states",
    "04": "consults",
    "05": "cooperates with",
    "10": "demands",
    "11": "disapproves",
    "12": "rejects",
    "13": "threatens",
    "14": "protests",
    "15": "exhibits force",
    "16": "reduces relations",
    "163": "imposes embargo or sanctions",
    "17": "coerces",
    "18": "assaults",
    "19": "fights",
}

WATCH_CODES = {"10", "11", "12", "13", "14", "15", "16", "163", "17", "18", "19", "20"}


def root_code(code: str) -> str:
    if str(code).startswith("163"):
        return "163"
    return str(code)[:2] if len(str(code)) >= 2 else str(code)


def action_label(code: str) -> str:
    code = str(code)
    return ACTION_LABEL.get(code, ACTION_LABEL.get(root_code(code), "acts"))


def signal_for_theme(theme: str | None = None, text: str = "") -> SignalType | None:
    blob = f"{theme or ''} {text}".lower()
    if any(k in blob for k in ("giga", "campus", "hyperscale", "data center", "datacenter")):
        if "permit" in blob or "megawatt" in blob or "mw" in blob:
            return SignalType.PERMIT_MW
        return SignalType.GIGA_SITE
    if any(k in blob for k in ("permit", "megawatt", "mega-watt")):
        return SignalType.PERMIT_MW
    if any(k in blob for k in ("load", "ercot", "peak demand", "weekly peak")):
        return SignalType.LOAD_GROWTH
    return None
