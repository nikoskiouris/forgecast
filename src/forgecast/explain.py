"""Template explanations. LLM optional later; numbers come from the ensemble."""

from __future__ import annotations

from forgecast.features import FEATURE_NAMES, Entity
from forgecast.schema import Driver, Event, ForecastItem
from forgecast.staticdata import country_name

INCREASE = {
    "export_restriction": [
        "Formal export-license rule published for the material",
        "State media frames the material as a geopolitical lever",
        "Customs delays or quota rumors confirmed by multiple shippers",
    ],
    "shipping_threat": [
        "Successful attack on a commercial vessel in the chokepoint",
        "Major carriers announce a full route diversion",
        "War-risk premiums spike above a prior crisis peak",
    ],
    "sanctions": [
        "Coordinated G7/allied designation of the producer or bank",
        "Secondary-sanctions warning to freight and insurers",
    ],
    "civil_unrest": [
        "Security forces fire on protesters in a mining/port region",
        "Opposition calls a general strike covering export infrastructure",
    ],
    "conflict_escalation": [
        "Cross-border fires or blockade of a producing region",
        "Mobilization orders or no-fly/maritime exclusion zone",
    ],
    "factory_shutdown": [
        "Confirmed halt at a plant that is a single-source node",
        "Grid, siege, or safety shutdown lasting more than 14 days",
    ],
    "asset_seizure": [
        "Draft nationalization law or asset-freeze order",
        "Foreign operators ordered to transfer equity",
    ],
    "port_border_closure": [
        "Official closure of a commercial port or land crossing",
        "Force majeure notices from terminal operators",
    ],
}

DECREASE = {
    "export_restriction": [
        "Bilateral mineral-supply agreement or quota reinstatement",
        "Licenses issued at pre-crisis volumes for allied buyers",
        "New non-origin supply coming online (mine, recycler, stockpile release)",
    ],
    "shipping_threat": [
        "Sustained period without attacks and carriers returning to the route",
        "Credible multinational escort corridor with high compliance",
    ],
    "sanctions": [
        "Carve-outs for the material or wind-down licenses expanded",
        "De-escalatory diplomacy that historically preceded relief",
    ],
    "civil_unrest": [
        "Negotiated pause and reopening of mines/ports",
        "Protest activity falling below the 90-day median",
    ],
    "conflict_escalation": [
        "Ceasefire that restores commercial access",
        "Force posture returning to baseline",
    ],
    "factory_shutdown": [
        "Plant restart confirmed by shippers and power-grid load",
    ],
    "asset_seizure": [
        "Court or executive reversal; foreign operators remain in control",
    ],
    "port_border_closure": [
        "Port or crossing reopened to commercial traffic",
    ],
}


def drivers_from_features(x, events: list[Event], entity: Entity) -> list[Driver]:
    named = dict(zip(FEATURE_NAMES, x.tolist()))
    out: list[Driver] = []
    if named["threats_90"] >= 3:
        out.append(
            Driver(
                indicator="threat rhetoric (90d)",
                direction="up",
                detail=f"{int(named['threats_90'])} threat-class events involving {country_name(entity.country)}.",
            )
        )
    if named["sanctions_90"] >= 2:
        out.append(
            Driver(
                indicator="sanctions / embargo actions (90d)",
                direction="up",
                detail=f"{int(named['sanctions_90'])} reduce-relations or embargo-coded events.",
            )
        )
    if named["delta_tone"] < -0.8:
        out.append(
            Driver(
                indicator="tone deterioration",
                direction="up",
                detail="Average event tone is worse than the prior 90 days.",
            )
        )
    if named["exporter_share"] >= 0.4:
        out.append(
            Driver(
                indicator="supplier concentration",
                direction="up",
                detail=f"Exporter share for this node is about {named['exporter_share']:.0%}.",
            )
        )
    if named["interdependence"] >= 0.6:
        out.append(
            Driver(
                indicator="economic interdependence",
                direction="down",
                detail="High trade interdependence raises the cost of a cutoff (does not make it impossible).",
            )
        )
    if named["n_90"] < 2:
        out.append(
            Driver(
                indicator="quiet watch window",
                direction="down",
                detail="Few relevant events in the last 90 days; forecast sits near the base rate.",
            )
        )
    if not out:
        out.append(
            Driver(
                indicator="base rate",
                direction="up",
                detail="No single indicator dominates; probability is mostly the historical rate plus analog tilt.",
            )
        )
    return out[:5]


def recent_sources(events: list[Event], entity: Entity, n: int = 5) -> list[str]:
    urls = []
    for e in reversed(events):
        if e.actor_country != entity.country:
            continue
        if entity.material and e.material and e.material != entity.material:
            continue
        if e.source_url and e.source_url not in urls:
            urls.append(e.source_url)
        if len(urls) >= n:
            break
    return urls


def headline(item: ForecastItem, horizon_days: int) -> str:
    who = country_name(item.actor_country)
    what = item.disruption_type.value.replace("_", " ")
    target = item.material.replace("_", " ") if item.material else (item.chokepoint or "allied supply")
    pct = f"{item.probability:.0%}" if item.probability >= 0.01 else f"{item.probability:.1%}"
    delta = ""
    if item.delta is not None:
        pts = abs(int(round(item.delta * 100)))
        if item.delta > 0.005:
            prev = f"{item.previous_probability:.0%}" if item.previous_probability is not None else "last month"
            delta = f", up from {prev}" if item.previous_probability is not None else f", up {pts} points"
        elif item.delta < -0.005:
            prev = f"{item.previous_probability:.0%}" if item.previous_probability is not None else "last month"
            delta = f", down from {prev}"
    return (
        f"There is a {pct} probability of {what} affecting {target} "
        f"({who}) within {horizon_days} days{delta}."
    )


def render_markdown(item: ForecastItem, horizon_days: int) -> str:
    lines = [headline(item, horizon_days), ""]
    if item.exposed_programs:
        lines.append(
            f"Exposed programs: {', '.join(item.exposed_programs)}. "
            f"Suppliers: {len(item.exposed_suppliers)}."
        )
        lines.append("")
    lines.append("**What moved the forecast**")
    for d in item.drivers:
        arrow = "↑" if d.direction == "up" else "↓"
        lines.append(f"- {arrow} {d.indicator}: {d.detail}")
    lines.append("")
    lines.append("**Historical analogs**")
    if not item.analogs:
        lines.append("- No close analog above the similarity floor.")
    for a in item.analogs:
        lines.append(
            f"- {a.name} ({a.year}) — {a.similarity:.0%} similar. Outcome: {a.outcome}. {a.difference}"
        )
    lines.append("")
    lines.append("**What would raise the probability**")
    for s in item.would_increase:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("**What would lower the probability**")
    for s in item.would_decrease:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("**Sources**")
    for u in item.sources:
        lines.append(f"- {u}")
    return "\n".join(lines)


def fill_text_fields(item: ForecastItem) -> ForecastItem:
    key = item.disruption_type.value
    item.would_increase = INCREASE.get(key, INCREASE["export_restriction"])
    item.would_decrease = DECREASE.get(key, DECREASE["export_restriction"])
    return item
