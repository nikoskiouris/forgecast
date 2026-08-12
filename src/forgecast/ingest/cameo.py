"""CAMEO / GDELT action codes mapped onto DIB disruption language."""

from __future__ import annotations

from forgecast.schema import DisruptionType

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

ROOT_TO_DISRUPTION: dict[str, DisruptionType | None] = {
    "14": DisruptionType.CIVIL_UNREST,
    "15": DisruptionType.CONFLICT_ESCALATION,
    "16": DisruptionType.SANCTIONS,
    "163": DisruptionType.SANCTIONS,
    "17": DisruptionType.ASSET_SEIZURE,
    "18": DisruptionType.CONFLICT_ESCALATION,
    "19": DisruptionType.CONFLICT_ESCALATION,
}

WATCH_CODES = {"10", "11", "12", "13", "14", "15", "16", "163", "17", "18", "19", "20"}


def root_code(code: str) -> str:
    if str(code).startswith("163"):
        return "163"
    return str(code)[:2] if len(str(code)) >= 2 else str(code)


def action_label(code: str) -> str:
    code = str(code)
    return ACTION_LABEL.get(code, ACTION_LABEL.get(root_code(code), "acts"))


def disruption_for_code(
    code: str,
    material: str | None = None,
    location: str | None = None,
) -> DisruptionType | None:
    root = root_code(code)
    loc = (location or "").lower()
    if "red sea" in loc or "suez" in loc or "hormuz" in loc or "bab" in loc:
        if root in {"15", "18", "19", "13"}:
            return DisruptionType.SHIPPING_THREAT
    if code.startswith("163") or root == "163":
        return DisruptionType.EXPORT_RESTRICTION if material else DisruptionType.SANCTIONS
    if root == "16" and material:
        return DisruptionType.EXPORT_RESTRICTION
    return ROOT_TO_DISRUPTION.get(root)
