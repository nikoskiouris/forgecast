"""Map forecasts onto a customer's programs and suppliers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from forgecast.schema import ForecastItem


def load_portfolio(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def apply_exposure(item: ForecastItem, portfolio: dict[str, Any]) -> ForecastItem:
    programs = []
    suppliers = []
    mat = item.material
    country = item.actor_country
    for prog in portfolio.get("programs", []):
        mats = prog.get("materials") or []
        if mat and mat in mats:
            programs.append(prog.get("name") or prog.get("id"))
        elif item.chokepoint or item.disruption_type.value in {
            "shipping_threat",
            "port_border_closure",
        }:
            programs.append(prog.get("name") or prog.get("id"))
    for sup in portfolio.get("suppliers", []):
        smats = sup.get("materials") or []
        scountry = sup.get("country")
        if mat and mat in smats and (scountry == country or not country):
            suppliers.append(sup.get("name") or sup.get("id"))
        elif scountry == country and item.disruption_type.value in {
            "civil_unrest",
            "conflict_escalation",
            "asset_seizure",
            "sanctions",
        }:
            suppliers.append(sup.get("name") or sup.get("id"))
    # Deduplicate, keep order.
    item.exposed_programs = list(dict.fromkeys(programs))
    item.exposed_suppliers = list(dict.fromkeys(suppliers))
    return item
