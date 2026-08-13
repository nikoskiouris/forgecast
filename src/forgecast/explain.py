"""Template explanations. Numbers come from the ensemble."""

from __future__ import annotations

from forgecast.features import FEATURE_NAMES, Entity, horizon_for
from forgecast.schema import Driver, Event, ForecastItem, SignalType
from forgecast.staticdata import place_name

INCREASE = {
    "load_growth": [
        "Weekly peak load prints ≥8% YoY for two consecutive weeks",
        "New large-load interconnection queue additions in the BA",
        "Utility IRP or ERCOT CDR raises the official demand outlook",
    ],
    "permit_mw": [
        "County issues a data-center building permit above the giga-site MW bar",
        "Site plan or rezoning approved for a hyperscale campus",
        "Transmission upgrade filing that names the campus load",
    ],
    "giga_site": [
        "Named hyperscale or AI campus announcement with MW disclosed",
        "Power-purchase or behind-the-meter generation deal signed",
        "County economic-development memo confirming the tenant",
    ],
}

DECREASE = {
    "load_growth": [
        "Weekly peaks revert toward the five-year trend",
        "Queued large loads withdraw or slip beyond the horizon",
        "A mild weather year without a new industrial step-up",
    ],
    "permit_mw": [
        "Permit pipeline goes quiet for two quarters",
        "Moratorium, lawsuit, or water/power constraint stalls sites",
        "Filed MW is revised below the giga-site threshold",
    ],
    "giga_site": [
        "The rumored tenant walks or relocates the campus",
        "No named announcement by the 90-day mark",
        "Local opposition or interconnection denial becomes public",
    ],
}

THRESHOLDS = {
    SignalType.LOAD_GROWTH: "weekly peak load ≥8% YoY",
    SignalType.PERMIT_MW: "permit-MW giga-site threshold",
    SignalType.GIGA_SITE: "named campus announcement",
}


def drivers_from_features(x, events: list[Event], entity: Entity) -> list[Driver]:
    named = dict(zip(FEATURE_NAMES, x.tolist()))
    where = place_name(entity.geo_id)
    out: list[Driver] = []
    if named["attention_90"] >= 8:
        out.append(
            Driver(
                indicator="grid attention (90d)",
                direction="up",
                detail=f"{int(named['attention_90'])} relevant events at {where}.",
            )
        )
    if named["load_90"] >= 4:
        out.append(
            Driver(
                indicator="load-coded events (90d)",
                direction="up",
                detail=f"{int(named['load_90'])} load-growth-tagged events in the window.",
            )
        )
    if named["permit_90"] >= 4:
        out.append(
            Driver(
                indicator="permit-coded events (90d)",
                direction="up",
                detail=f"{int(named['permit_90'])} permit-MW-tagged events in the window.",
            )
        )
    if named["giga_90"] >= 3:
        out.append(
            Driver(
                indicator="campus-coded events (90d)",
                direction="up",
                detail=f"{int(named['giga_90'])} giga-site-tagged events in the window.",
            )
        )
    if named["analog_sim"] >= 0.35:
        out.append(
            Driver(
                indicator="historical analog",
                direction="up",
                detail=f"Closest analog similarity {named['analog_sim']:.0%}.",
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
        if e.geo_id != entity.geo_id:
            continue
        if e.source_url and e.source_url not in urls:
            urls.append(e.source_url)
        if len(urls) >= n:
            break
    return urls


def headline(item: ForecastItem, horizon_days: int) -> str:
    pct = f"{item.probability:.0%}"
    name = item.geo_name
    if item.signal_type is SignalType.LOAD_GROWTH:
        return (
            f"There is a {pct} probability that {name} weekly peak load grows "
            f"≥8% YoY within {horizon_days} days."
        )
    if item.signal_type is SignalType.PERMIT_MW:
        return (
            f"There is a {pct} probability that permit-MW in {name} crosses "
            f"the giga-site threshold within {horizon_days} days."
        )
    h = horizon_for(item.signal_type, horizon_days)
    return (
        f"There is a {pct} probability that a new giga-site is announced "
        f"in {name} within {h} days."
    )


def render_markdown(item: ForecastItem, horizon_days: int) -> str:
    lines = [headline(item, horizon_days), ""]
    if item.exposed_tickers:
        tickers = ", ".join(t.ticker for t in item.exposed_tickers)
        lines.append(f"Exposed: {tickers}. Mechanical mapping, not advice.")
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
    lines.append("")
    lines.append("_Publisher, not an adviser._")
    return "\n".join(lines)


def fill_text_fields(item: ForecastItem) -> ForecastItem:
    key = item.signal_type.value
    item.would_increase = INCREASE.get(key, INCREASE["load_growth"])
    item.would_decrease = DECREASE.get(key, DECREASE["load_growth"])
    item.threshold = THRESHOLDS.get(item.signal_type, item.threshold)
    return item
