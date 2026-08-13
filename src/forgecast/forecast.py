"""Forecast engine: as-of cutoff, ensemble probabilities, analogs, exposure."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from forgecast.analogs import analog_summary
from forgecast.backtest import build_xy
from forgecast.config import DEFAULT_HORIZON_DAYS, DEFAULT_PORTFOLIO, DEMO_AS_OF
from forgecast.explain import drivers_from_features, fill_text_fields, recent_sources
from forgecast.exposure import apply_exposure, load_portfolio
from forgecast.features import Entity, feature_vector, month_starts
from forgecast.geo import locate_node, make_pin_id
from forgecast.graph import Store
from forgecast.models import Ensemble
from forgecast.sample import generate_world
from forgecast.schema import DisruptionType, Event, ForecastItem, ForecastReport, Outcome
from forgecast.staticdata import country_name

WATCHLIST: list[Entity] = [
    Entity("CN", "rare_earths", DisruptionType.EXPORT_RESTRICTION),
    Entity("CN", "gallium", DisruptionType.EXPORT_RESTRICTION),
    Entity("CN", "germanium", DisruptionType.EXPORT_RESTRICTION),
    Entity("CN", "antimony", DisruptionType.EXPORT_RESTRICTION),
    Entity("CN", "graphite", DisruptionType.EXPORT_RESTRICTION),
    Entity("RU", "titanium", DisruptionType.EXPORT_RESTRICTION),
    Entity("RU", "palladium", DisruptionType.SANCTIONS),
    Entity("UA", "neon", DisruptionType.FACTORY_SHUTDOWN),
    Entity("CD", "cobalt", DisruptionType.CIVIL_UNREST),
    Entity("TW", "semiconductors", DisruptionType.CONFLICT_ESCALATION),
    Entity("YE", None, DisruptionType.SHIPPING_THREAT),
    Entity("EG", None, DisruptionType.SHIPPING_THREAT),
    Entity("IR", None, DisruptionType.SHIPPING_THREAT),
    Entity("MM", "rare_earths", DisruptionType.CIVIL_UNREST),
    Entity("ID", "nickel", DisruptionType.EXPORT_RESTRICTION),
]


def load_training_world(store: Store | None = None) -> tuple[list[Event], list[Outcome]]:
    world = generate_world()
    if store is None or store.count() == 0:
        return world.events, world.outcomes
    live = store.events_as_of(date.today(), lookback_days=365 * 20)
    # Prefer live rows when present; keep sample outcomes for backtest labels.
    if live:
        return live, world.outcomes
    return world.events, world.outcomes


def fit_model(events: list[Event], outcomes: list[Outcome], as_of: date) -> Ensemble:
    train_end = as_of - timedelta(days=DEFAULT_HORIZON_DAYS + 1)
    start = date(2012, 1, 1)
    if train_end <= start:
        train_end = date(2018, 1, 1)
    dates = month_starts(start, train_end)
    # Quarterly snapshots keep training fast without dropping the signal.
    dates = [d for d in dates if d.month in {1, 4, 7, 10}]
    X, y, _ = build_xy(events, outcomes, WATCHLIST, dates, DEFAULT_HORIZON_DAYS)
    return Ensemble().fit(X, y)


def _item_for(
    model: Ensemble,
    events: list[Event],
    outcomes: list[Outcome],
    entity: Entity,
    as_of: date,
    prev_as_of: date,
    portfolio: dict,
) -> ForecastItem:
    known = [e for e in events if e.timestamp.date() <= as_of]
    analog = analog_summary(known, entity, as_of, outcomes)
    x = feature_vector(known, entity, as_of, analog.rate, analog.max_similarity)
    p = float(model.predict_proba(x.reshape(1, -1))[0])

    known_prev = [e for e in events if e.timestamp.date() <= prev_as_of]
    analog_p = analog_summary(known_prev, entity, prev_as_of, outcomes)
    xp = feature_vector(known_prev, entity, prev_as_of, analog_p.rate, analog_p.max_similarity)
    p_prev = float(model.predict_proba(xp.reshape(1, -1))[0])

    chokepoint = None
    if entity.disruption == DisruptionType.SHIPPING_THREAT:
        chokepoint = {
            "YE": "Bab el-Mandeb / Red Sea",
            "EG": "Suez Canal",
            "IR": "Strait of Hormuz",
        }.get(entity.country)

    lat, lon, site = locate_node(entity.country, entity.material, chokepoint)
    item = ForecastItem(
        id=make_pin_id(entity.country, entity.material, entity.disruption),
        disruption_type=entity.disruption,
        actor_country=entity.country,
        actor_name=country_name(entity.country),
        material=entity.material,
        chokepoint=chokepoint,
        site=site,
        lat=lat,
        lon=lon,
        probability=round(p, 4),
        previous_probability=round(p_prev, 4),
        delta=round(p - p_prev, 4),
        drivers=drivers_from_features(x, known, entity),
        analogs=analog.matches,
        sources=recent_sources(known, entity),
    )
    item = fill_text_fields(item)
    return apply_exposure(item, portfolio)


def forecast(
    as_of: date | None = None,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    portfolio_path: Path | None = None,
    store: Store | None = None,
    model: Ensemble | None = None,
    top_n: int = 16,
) -> ForecastReport:
    as_of = as_of or DEMO_AS_OF
    portfolio_path = portfolio_path or DEFAULT_PORTFOLIO
    portfolio = load_portfolio(portfolio_path) if portfolio_path.exists() else {"name": "none", "programs": [], "suppliers": []}
    events, outcomes = load_training_world(store)
    if model is None:
        model = fit_model(events, outcomes, as_of)
    prev = as_of - timedelta(days=30)
    items = [
        _item_for(model, events, outcomes, ent, as_of, prev, portfolio) for ent in WATCHLIST
    ]
    items.sort(key=lambda i: i.probability, reverse=True)
    notes = [
        "Probabilities are calibrated ensemble outputs, not declarations that an event will happen.",
        "Historical similarity is one input. Structural differences are called out explicitly.",
        "Sample-world backtests prove the pipeline. Live GDELT ingest improves coverage, not automatic accuracy.",
    ]
    return ForecastReport(
        as_of=as_of,
        horizon_days=horizon_days,
        portfolio=portfolio.get("name", "demo"),
        items=items[:top_n],
        notes=notes,
    )
